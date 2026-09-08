"""Property lifecycle operations: split, merge, and spatial hierarchy tree.

Maps to PRD §5.5 (FR-3D-06, FR-3D-07) and §5.9:
- Never reuses an old 3D Property ID.
- Split/merge creates new IDs and soft-retires old records via `superseded_by`.
- All operations log immutable `change_events`.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.property_object import PropertyObject
from app.models.change_event import ChangeEvent
from app.services.id_generator import make_3d_property_id, parse_3d_property_id
from app.schemas.lifecycle import SplitUnitSpec, HierarchyNode


def get_highest_unit_sequence(db: Session, ulpin: str, building_seq: int, floor_seq: int) -> int:
    """Find the highest unit sequence ever used for this building and floor (active + superseded)."""
    prefix = f"{ulpin}-B{building_seq:03d}-F{floor_seq:02d}-U"
    records = db.query(PropertyObject.three_d_property_id).filter(
        PropertyObject.three_d_property_id.like(f"{prefix}%")
    ).all()

    max_seq = 0
    for (prop_id,) in records:
        try:
            parsed = parse_3d_property_id(prop_id)
            if parsed["unit_seq"] > max_seq:
                max_seq = parsed["unit_seq"]
        except Exception:
            continue
    return max_seq


def split_unit(
    db: Session,
    target_property_id: str,
    split_specs: list[SplitUnitSpec],
    actor_id: Optional[UUID] = None,
    evidence_id: Optional[UUID] = None,
    reason: Optional[str] = None,
) -> tuple[PropertyObject, list[PropertyObject]]:
    """Split an active unit into multiple new units, superseding the original unit.
    
    Rule FR-3D-06: Never reuses old IDs.
    Rule FR-3D-07: Split/merge creates new IDs and supersedes old IDs.
    """
    if len(split_specs) < 2:
        raise ValueError("At least 2 new units are required for a split operation.")

    parent_unit = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == target_property_id
    ).first()

    if not parent_unit:
        raise ValueError(f"Target property '{target_property_id}' not found.")
    if parent_unit.superseded_by is not None:
        raise ValueError(f"Unit '{target_property_id}' is already superseded and cannot be split.")
    if parent_unit.type != "unit":
        raise ValueError(f"Only 'unit' objects can be split. Target is a '{parent_unit.type}'.")

    parsed = parse_3d_property_id(target_property_id)
    ulpin = parsed["ulpin"]
    bldg_seq = parsed["building_seq"]
    flr_seq = parsed["floor_seq"]

    # Ensure new unit sequences strictly increment beyond any previously assigned sequence
    current_highest = get_highest_unit_sequence(db, ulpin, bldg_seq, flr_seq)

    new_units: list[PropertyObject] = []
    now = datetime.now(timezone.utc)

    for spec in split_specs:
        current_highest += 1
        new_id = make_3d_property_id(ulpin, bldg_seq, flr_seq, current_highest)

        unit_attrs = dict(parent_unit.attributes or {})
        if spec.attributes:
            unit_attrs.update(spec.attributes)
        unit_attrs["split_from"] = target_property_id
        if spec.unit_name:
            unit_attrs["unit_name"] = spec.unit_name

        new_unit = PropertyObject(
            three_d_property_id=new_id,
            type="unit",
            parent_id=parent_unit.parent_id,
            geometry=parent_unit.geometry,
            z_min=spec.z_min if spec.z_min is not None else parent_unit.z_min,
            z_max=spec.z_max if spec.z_max is not None else parent_unit.z_max,
            attributes=unit_attrs,
            confidence=parent_unit.confidence,
            status="PROVISIONAL",
            source_list=list(parent_unit.source_list or []),
            created_at=now,
        )
        db.add(new_unit)
        db.flush()

        # Log creation event for new child unit
        create_event = ChangeEvent(
            property_object_id=new_unit.id,
            event_type="created",
            old_state=None,
            new_state={
                "three_d_property_id": new_id,
                "type": "unit",
                "status": "PROVISIONAL",
                "event": "unit_split_child",
                "split_from": target_property_id,
            },
            actor_id=actor_id,
            evidence_id=evidence_id,
        )
        db.add(create_event)
        new_units.append(new_unit)

    # Soft-retire parent unit by pointing superseded_by to the first new unit
    parent_unit.superseded_by = new_units[0].id
    old_status = parent_unit.status

    split_event = ChangeEvent(
        property_object_id=parent_unit.id,
        event_type="unit_split",
        old_state={"status": old_status, "active": True},
        new_state={
            "status": "SUPERSEDED",
            "active": False,
            "superseded_by": [u.three_d_property_id for u in new_units],
            "reason": reason,
        },
        actor_id=actor_id,
        evidence_id=evidence_id,
    )
    db.add(split_event)

    db.commit()
    for u in new_units:
        db.refresh(u)
    db.refresh(parent_unit)

    return parent_unit, new_units


def merge_units(
    db: Session,
    unit_ids: list[str],
    merged_attributes: Optional[dict[str, Any]] = None,
    actor_id: Optional[UUID] = None,
    evidence_id: Optional[UUID] = None,
    reason: Optional[str] = None,
) -> tuple[list[PropertyObject], PropertyObject]:
    """Merge two or more existing active units into one new combined unit.
    
    Rule FR-3D-06: Never reuses old IDs.
    Rule FR-3D-07: Split/merge creates new IDs and supersedes old IDs.
    """
    if len(unit_ids) < 2:
        raise ValueError("At least 2 units are required for a merge operation.")

    units = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id.in_(unit_ids)
    ).all()

    if len(units) != len(unit_ids):
        found_ids = {u.three_d_property_id for u in units}
        missing = set(unit_ids) - found_ids
        raise ValueError(f"One or more units not found: {missing}")

    for u in units:
        if u.superseded_by is not None:
            raise ValueError(f"Unit '{u.three_d_property_id}' is already superseded and cannot be merged.")
        if u.type != "unit":
            raise ValueError(f"Only 'unit' objects can be merged. Found '{u.type}' for '{u.three_d_property_id}'.")

    # Verify all units belong to the same building and floor
    parsed_first = parse_3d_property_id(units[0].three_d_property_id)
    ulpin = parsed_first["ulpin"]
    bldg_seq = parsed_first["building_seq"]
    flr_seq = parsed_first["floor_seq"]

    for u in units[1:]:
        p = parse_3d_property_id(u.three_d_property_id)
        if p["ulpin"] != ulpin or p["building_seq"] != bldg_seq or p["floor_seq"] != flr_seq:
            raise ValueError("All units in a merge operation must belong to the same building and floor level.")

    # Generate a brand-new unit sequence that has NEVER been used
    current_highest = get_highest_unit_sequence(db, ulpin, bldg_seq, flr_seq)
    new_unit_seq = current_highest + 1
    new_merged_id = make_3d_property_id(ulpin, bldg_seq, flr_seq, new_unit_seq)

    # Vertical extent encompasses all contributing units
    z_mins = [u.z_min for u in units if u.z_min is not None]
    z_maxs = [u.z_max for u in units if u.z_max is not None]
    fused_z_min = min(z_mins) if z_mins else 0.0
    fused_z_max = max(z_maxs) if z_maxs else None

    # Merge attributes and track lineage
    combined_attrs = {}
    for u in units:
        if u.attributes:
            combined_attrs.update(u.attributes)
    if merged_attributes:
        combined_attrs.update(merged_attributes)
    combined_attrs["merged_from"] = unit_ids

    # Consolidated source list
    combined_sources: list[str] = []
    for u in units:
        for s in (u.source_list or []):
            if s not in combined_sources:
                combined_sources.append(s)

    avg_conf = sum(u.confidence for u in units) / len(units)
    now = datetime.now(timezone.utc)

    merged_unit = PropertyObject(
        three_d_property_id=new_merged_id,
        type="unit",
        parent_id=units[0].parent_id,
        geometry=units[0].geometry,
        z_min=fused_z_min,
        z_max=fused_z_max,
        attributes=combined_attrs,
        confidence=round(avg_conf, 2),
        status="PROVISIONAL",
        source_list=combined_sources,
        created_at=now,
    )
    db.add(merged_unit)
    db.flush()

    # Log creation event for merged unit
    create_event = ChangeEvent(
        property_object_id=merged_unit.id,
        event_type="created",
        old_state=None,
        new_state={
            "three_d_property_id": new_merged_id,
            "type": "unit",
            "status": "PROVISIONAL",
            "event": "unit_merged",
            "merged_from": unit_ids,
        },
        actor_id=actor_id,
        evidence_id=evidence_id,
    )
    db.add(create_event)

    # Soft-retire each contributing unit
    for u in units:
        u.superseded_by = merged_unit.id
        old_st = u.status
        merge_event = ChangeEvent(
            property_object_id=u.id,
            event_type="unit_merged",
            old_state={"status": old_st, "active": True},
            new_state={
                "status": "SUPERSEDED",
                "active": False,
                "superseded_by": new_merged_id,
                "reason": reason,
            },
            actor_id=actor_id,
            evidence_id=evidence_id,
        )
        db.add(merge_event)

    db.commit()
    db.refresh(merged_unit)
    for u in units:
        db.refresh(u)

    return units, merged_unit


def build_hierarchy_tree(db: Session, root_property: PropertyObject) -> HierarchyNode:
    """Recursively construct the spatial hierarchy tree (parcel -> building -> floor -> unit)."""
    children = db.query(PropertyObject).filter(
        PropertyObject.parent_id == root_property.id,
        PropertyObject.superseded_by.is_(None),
    ).order_by(PropertyObject.three_d_property_id.asc()).all()

    child_nodes = [build_hierarchy_tree(db, child) for child in children]

    return HierarchyNode(
        id=root_property.id,
        three_d_property_id=root_property.three_d_property_id,
        type=root_property.type,
        status=root_property.status,
        confidence=root_property.confidence,
        z_min=root_property.z_min,
        z_max=root_property.z_max,
        attributes=root_property.attributes,
        children=child_nodes,
    )
