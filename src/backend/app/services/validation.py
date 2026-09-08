"""Deterministic topology validation rules (PRD §5.6, VR-01 through VR-08).

Each rule is a pure function returning (passed: bool, detail: str).
The topology runner calls these and persists Conflict records for failures.

Rules:
  VR-01  Building footprint must be inside parcel within tolerance.
  VR-02  Detect unit overlap on the same floor.
  VR-03  Detect unexpected gaps between units on a floor.
  VR-04  Detect vertical overlap between floors.
  VR-05  Detect building boundary violation (building extends beyond parcel).
  VR-06  Detect near-duplicate geometry.
  VR-07  Detect orphan building/floor/unit records.
  VR-08  Failed validation creates a conflict record (handled by runner).
  VR-09  Conflicts block VERIFIED status but do not block ingestion (enforced at verify endpoint).
"""

from typing import Optional

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# VR-01 / VR-05: Containment — building footprint inside parcel
# ---------------------------------------------------------------------------

def containment_ok(building: BaseGeometry, parcel: BaseGeometry, tolerance: float = 0.0) -> bool:
    """VR-01 / VR-05: Check that a building footprint lies within its parcel boundary.

    Tolerance is intentionally explicit; production can use buffer(tolerance)
    after confirming the jurisdiction's measurement policy.
    """
    if tolerance:
        return building.within(parcel.buffer(tolerance))
    return building.within(parcel)


def check_containment(
    child_geom: BaseGeometry,
    parent_geom: BaseGeometry,
    child_id: str,
    parent_id: str,
    tolerance: float = 0.0,
) -> tuple[bool, str]:
    """VR-01 / VR-05: Return (passed, detail) for containment check."""
    if containment_ok(child_geom, parent_geom, tolerance):
        return True, ""
    # Compute how much protrudes
    difference = child_geom.difference(parent_geom)
    protrusion_area = difference.area if not difference.is_empty else 0.0
    detail = (
        f"VR-01/VR-05: {child_id} protrudes beyond {parent_id} "
        f"by {protrusion_area:.6f} sq-units"
    )
    return False, detail


def check_boundary_violation(
    child_geom: BaseGeometry,
    parent_geom: BaseGeometry,
    child_id: str,
    parent_id: str,
    tolerance: float = 0.0,
) -> tuple[bool, str]:
    """VR-05: Detect building boundary violation (extending beyond parcel)."""
    passed, detail = check_containment(child_geom, parent_geom, child_id, parent_id, tolerance)
    if not passed:
        detail = detail.replace("VR-01/VR-05", "VR-05")
    return passed, detail


# ---------------------------------------------------------------------------
# VR-02: Unit overlap on the same floor
# ---------------------------------------------------------------------------

def overlap_ratio(a: BaseGeometry, b: BaseGeometry) -> float:
    """Compute Intersection-over-Union (IoU) for two geometries."""
    union_area = a.union(b).area
    if union_area == 0:
        return 0.0
    return a.intersection(b).area / union_area


def check_unit_overlap(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    id_a: str,
    id_b: str,
    overlap_threshold: float = 0.01,
) -> tuple[bool, str]:
    """VR-02: Detect if two units on the same floor overlap beyond threshold."""
    iou = overlap_ratio(geom_a, geom_b)
    if iou <= overlap_threshold:
        return True, ""
    detail = (
        f"VR-02: Units {id_a} and {id_b} overlap with IoU={iou:.4f} "
        f"(threshold: {overlap_threshold})"
    )
    return False, detail


# ---------------------------------------------------------------------------
# VR-03: Gap detection between units on a floor
# ---------------------------------------------------------------------------

def check_floor_gap(
    unit_geometries: list[BaseGeometry],
    floor_geom: Optional[BaseGeometry],
    floor_id: str,
    gap_threshold: float = 0.05,
) -> tuple[bool, str]:
    """VR-03: Detect unexpected gaps between units on a floor.

    If a floor geometry is provided, compute the uncovered area.
    If not, check for disjoint gaps between adjacent units.
    """
    if not unit_geometries or len(unit_geometries) < 2:
        return True, ""

    units_union = unary_union(unit_geometries)

    if floor_geom is not None and not floor_geom.is_empty:
        uncovered = floor_geom.difference(units_union)
        if uncovered.is_empty:
            return True, ""
        gap_ratio = uncovered.area / floor_geom.area if floor_geom.area > 0 else 0.0
        if gap_ratio <= gap_threshold:
            return True, ""
        detail = (
            f"VR-03: Floor {floor_id} has {gap_ratio:.2%} uncovered area "
            f"between units (threshold: {gap_threshold:.2%})"
        )
        return False, detail

    # Without floor geometry, check if units form a connected set
    if units_union.geom_type == "MultiPolygon":
        num_components = len(list(units_union.geoms))
        if num_components > 1:
            detail = (
                f"VR-03: Floor {floor_id} has {num_components} disjoint unit clusters "
                f"(potential gap/anomaly)"
            )
            return False, detail

    return True, ""


# ---------------------------------------------------------------------------
# VR-04: Vertical overlap between floors
# ---------------------------------------------------------------------------

def check_vertical_overlap(
    z_min_a: float,
    z_max_a: float,
    z_min_b: float,
    z_max_b: float,
    id_a: str,
    id_b: str,
    tolerance: float = 0.01,
) -> tuple[bool, str]:
    """VR-04: Detect vertical overlap between two floor extents.

    Two floors overlap vertically if their [z_min, z_max] intervals intersect
    beyond a tolerance.
    """
    overlap_start = max(z_min_a, z_min_b)
    overlap_end = min(z_max_a, z_max_b)
    overlap_amount = overlap_end - overlap_start

    if overlap_amount <= tolerance:
        return True, ""

    detail = (
        f"VR-04: Vertical overlap between {id_a} [{z_min_a}m–{z_max_a}m] "
        f"and {id_b} [{z_min_b}m–{z_max_b}m]: {overlap_amount:.2f}m overlap"
    )
    return False, detail


# ---------------------------------------------------------------------------
# VR-06: Near-duplicate geometry detection
# ---------------------------------------------------------------------------

def check_near_duplicate(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    id_a: str,
    id_b: str,
    hausdorff_threshold: float = 0.5,
    area_ratio_threshold: float = 0.95,
) -> tuple[bool, str]:
    """VR-06: Detect near-duplicate geometries using Hausdorff distance and area similarity.

    Two geometries are near-duplicates if:
    - Hausdorff distance is below threshold, AND
    - Area ratio (smaller/larger) exceeds threshold.
    """
    if geom_a.is_empty or geom_b.is_empty:
        return True, ""

    hausdorff = geom_a.hausdorff_distance(geom_b)

    area_a = geom_a.area
    area_b = geom_b.area
    if max(area_a, area_b) == 0:
        return True, ""

    area_ratio = min(area_a, area_b) / max(area_a, area_b)

    if hausdorff >= hausdorff_threshold or area_ratio < area_ratio_threshold:
        return True, ""  # Sufficiently different

    detail = (
        f"VR-06: Near-duplicate geometry detected between {id_a} and {id_b}. "
        f"Hausdorff={hausdorff:.6f} (threshold: {hausdorff_threshold}), "
        f"Area ratio={area_ratio:.4f} (threshold: {area_ratio_threshold})"
    )
    return False, detail


# ---------------------------------------------------------------------------
# VR-07: Orphan detection
# ---------------------------------------------------------------------------

def check_orphan(
    obj_type: str,
    parent_id: Optional[str],
    obj_id: str,
) -> tuple[bool, str]:
    """VR-07: Detect orphan records — objects that should have parents but don't.

    - parcel: no parent required (top-level)
    - building: must have a parcel parent
    - floor: must have a building parent
    - unit: must have a floor parent
    """
    if obj_type == "parcel":
        return True, ""  # Parcels are top-level

    if parent_id is None:
        expected_parent = {
            "building": "parcel",
            "floor": "building",
            "unit": "floor",
        }.get(obj_type, "parent")
        detail = (
            f"VR-07: Orphan {obj_type} detected: {obj_id} "
            f"has no {expected_parent} parent"
        )
        return False, detail

    return True, ""
