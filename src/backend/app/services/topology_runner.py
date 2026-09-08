"""Batch topology validation runner (PRD §5.6, VR-08).

Executes all deterministic validation rules against the spatial database
and persists Conflict records for any failures.

VR-08: Failed validation creates a conflict record.
VR-09: Conflicts block VERIFIED status but do not block ingestion.
"""

from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Optional

from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.models.property_object import PropertyObject
from app.models.conflict import Conflict
from app.services.validation import (
    check_containment,
    check_unit_overlap,
    check_floor_gap,
    check_vertical_overlap,
    check_near_duplicate,
    check_orphan,
)


def _get_shapely_geom(prop: PropertyObject):
    """Attempt to extract a Shapely geometry from a PropertyObject."""
    if prop.attributes and "geojson_geometry" in prop.attributes:
        from shapely.geometry import shape
        try:
            return shape(prop.attributes["geojson_geometry"])
        except Exception:
            pass
    if prop.geometry is not None:
        try:
            return to_shape(prop.geometry)
        except Exception:
            pass
    return None


def _create_conflict(
    db: Session,
    prop: PropertyObject,
    rule_code: str,
    description: str,
    severity: str = "ERROR",
) -> Conflict:
    """Create a conflict record if one doesn't already exist for this rule+property."""
    existing = db.query(Conflict).filter(
        Conflict.property_object_id == prop.id,
        Conflict.rule_code == rule_code,
        Conflict.status == "OPEN",
    ).first()
    if existing:
        return existing

    conflict = Conflict(
        property_object_id=prop.id,
        rule_code=rule_code,
        description=description,
        severity=severity,
        status="OPEN",
    )
    db.add(conflict)
    return conflict


def run_containment_checks(db: Session) -> list[dict[str, Any]]:
    """VR-01 / VR-05: Building footprint must be inside its parcel."""
    results = []
    buildings = db.query(PropertyObject).filter(
        PropertyObject.type == "building",
        PropertyObject.superseded_by.is_(None),
        PropertyObject.parent_id.isnot(None),
    ).all()

    for bldg in buildings:
        parent = db.query(PropertyObject).filter(
            PropertyObject.id == bldg.parent_id,
        ).first()
        if not parent:
            continue

        bldg_geom = _get_shapely_geom(bldg)
        parent_geom = _get_shapely_geom(parent)
        if bldg_geom is None or parent_geom is None:
            continue

        passed, detail = check_containment(
            bldg_geom, parent_geom,
            bldg.three_d_property_id, parent.three_d_property_id,
        )
        if not passed:
            conflict = _create_conflict(db, bldg, "VR-01", detail)
            results.append({
                "rule": "VR-01",
                "property_id": bldg.three_d_property_id,
                "detail": detail,
                "conflict_id": str(conflict.id) if conflict.id else None,
            })

    return results


def run_unit_overlap_checks(db: Session) -> list[dict[str, Any]]:
    """VR-02: Detect unit overlap on the same floor."""
    results = []

    # Group units by parent (floor)
    floors = db.query(PropertyObject).filter(
        PropertyObject.type == "floor",
        PropertyObject.superseded_by.is_(None),
    ).all()

    for floor in floors:
        units = db.query(PropertyObject).filter(
            PropertyObject.type == "unit",
            PropertyObject.parent_id == floor.id,
            PropertyObject.superseded_by.is_(None),
        ).all()

        if len(units) < 2:
            continue

        for unit_a, unit_b in combinations(units, 2):
            geom_a = _get_shapely_geom(unit_a)
            geom_b = _get_shapely_geom(unit_b)
            if geom_a is None or geom_b is None:
                continue

            passed, detail = check_unit_overlap(
                geom_a, geom_b,
                unit_a.three_d_property_id, unit_b.three_d_property_id,
            )
            if not passed:
                conflict = _create_conflict(db, unit_a, "VR-02", detail)
                results.append({
                    "rule": "VR-02",
                    "property_id": unit_a.three_d_property_id,
                    "detail": detail,
                })

    return results


def run_floor_gap_checks(db: Session) -> list[dict[str, Any]]:
    """VR-03: Detect unexpected gaps between units on a floor."""
    results = []

    floors = db.query(PropertyObject).filter(
        PropertyObject.type == "floor",
        PropertyObject.superseded_by.is_(None),
    ).all()

    for floor in floors:
        units = db.query(PropertyObject).filter(
            PropertyObject.type == "unit",
            PropertyObject.parent_id == floor.id,
            PropertyObject.superseded_by.is_(None),
        ).all()

        if len(units) < 2:
            continue

        unit_geoms = [g for u in units if (g := _get_shapely_geom(u)) is not None]
        floor_geom = _get_shapely_geom(floor)

        passed, detail = check_floor_gap(
            unit_geoms, floor_geom, floor.three_d_property_id,
        )
        if not passed:
            conflict = _create_conflict(db, floor, "VR-03", detail, severity="WARNING")
            results.append({
                "rule": "VR-03",
                "property_id": floor.three_d_property_id,
                "detail": detail,
            })

    return results


def run_vertical_overlap_checks(db: Session) -> list[dict[str, Any]]:
    """VR-04: Detect vertical overlap between floors in the same building."""
    results = []

    buildings = db.query(PropertyObject).filter(
        PropertyObject.type == "building",
        PropertyObject.superseded_by.is_(None),
    ).all()

    for bldg in buildings:
        floors = db.query(PropertyObject).filter(
            PropertyObject.type == "floor",
            PropertyObject.parent_id == bldg.id,
            PropertyObject.superseded_by.is_(None),
        ).order_by(PropertyObject.z_min.asc()).all()

        if len(floors) < 2:
            continue

        for floor_a, floor_b in combinations(floors, 2):
            if floor_a.z_min is None or floor_a.z_max is None:
                continue
            if floor_b.z_min is None or floor_b.z_max is None:
                continue

            passed, detail = check_vertical_overlap(
                floor_a.z_min, floor_a.z_max,
                floor_b.z_min, floor_b.z_max,
                floor_a.three_d_property_id, floor_b.three_d_property_id,
            )
            if not passed:
                conflict = _create_conflict(db, floor_a, "VR-04", detail)
                results.append({
                    "rule": "VR-04",
                    "property_id": floor_a.three_d_property_id,
                    "detail": detail,
                })

    return results


def run_duplicate_checks(db: Session) -> list[dict[str, Any]]:
    """VR-06: Detect near-duplicate geometry among same-type siblings."""
    results = []

    for obj_type in ("building", "unit"):
        objects = db.query(PropertyObject).filter(
            PropertyObject.type == obj_type,
            PropertyObject.superseded_by.is_(None),
        ).all()

        if len(objects) < 2:
            continue

        for obj_a, obj_b in combinations(objects, 2):
            # Only compare siblings (same parent)
            if obj_a.parent_id != obj_b.parent_id:
                continue

            geom_a = _get_shapely_geom(obj_a)
            geom_b = _get_shapely_geom(obj_b)
            if geom_a is None or geom_b is None:
                continue

            passed, detail = check_near_duplicate(
                geom_a, geom_b,
                obj_a.three_d_property_id, obj_b.three_d_property_id,
            )
            if not passed:
                conflict = _create_conflict(db, obj_a, "VR-06", detail, severity="WARNING")
                results.append({
                    "rule": "VR-06",
                    "property_id": obj_a.three_d_property_id,
                    "detail": detail,
                })

    return results


def run_orphan_checks(db: Session) -> list[dict[str, Any]]:
    """VR-07: Detect orphan building/floor/unit records without parents."""
    results = []

    for obj_type in ("building", "floor", "unit"):
        objects = db.query(PropertyObject).filter(
            PropertyObject.type == obj_type,
            PropertyObject.superseded_by.is_(None),
        ).all()

        for obj in objects:
            passed, detail = check_orphan(
                obj.type,
                str(obj.parent_id) if obj.parent_id else None,
                obj.three_d_property_id,
            )
            if not passed:
                conflict = _create_conflict(db, obj, "VR-07", detail, severity="ERROR")
                results.append({
                    "rule": "VR-07",
                    "property_id": obj.three_d_property_id,
                    "detail": detail,
                })

    return results


def run_all_topology_checks(db: Session) -> dict[str, Any]:
    """Execute the complete suite of deterministic topology rules.

    VR-08: Each failed rule creates a Conflict record in the database.
    VR-09: Conflicts block VERIFIED status but do not block ingestion.

    Returns a summary of all findings.
    """
    all_results = []

    all_results.extend(run_containment_checks(db))
    all_results.extend(run_unit_overlap_checks(db))
    all_results.extend(run_floor_gap_checks(db))
    all_results.extend(run_vertical_overlap_checks(db))
    all_results.extend(run_duplicate_checks(db))
    all_results.extend(run_orphan_checks(db))

    db.commit()

    # Group by rule code
    by_rule: dict[str, int] = {}
    for r in all_results:
        by_rule[r["rule"]] = by_rule.get(r["rule"], 0) + 1

    return {
        "total_violations": len(all_results),
        "violations_by_rule": by_rule,
        "details": all_results,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
