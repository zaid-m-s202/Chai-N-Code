"""Configurable floor-height heuristic and 3D vertical extent estimation service.

Maps to PRD §5.5 (FR-3D-04) and §5.4 (FR-AI-04):
- Generates vertical bounds (z_min, z_max) for floors and units.
- Uses configurable heuristics by property use type (residential, commercial, industrial).
"""

from typing import Any, Optional


# Configurable default floor heights in meters (m) by building use classification
DEFAULT_FLOOR_HEIGHTS_BY_USE = {
    "residential": 3.0,
    "commercial": 3.8,
    "office": 3.6,
    "retail": 4.2,
    "industrial": 5.0,
    "mixed_zone": 3.5,
    "educational": 3.6,
    "healthcare": 4.0,
}
DEFAULT_FALLBACK_FLOOR_HEIGHT = 3.0  # meters


def get_typical_floor_height(use_type: Optional[str] = None) -> float:
    """Retrieve calibrated floor height heuristic based on occupancy/use type."""
    if not use_type:
        return DEFAULT_FALLBACK_FLOOR_HEIGHT
    clean_use = use_type.lower().strip()
    return DEFAULT_FLOOR_HEIGHTS_BY_USE.get(clean_use, DEFAULT_FALLBACK_FLOOR_HEIGHT)


def estimate_building_levels(
    total_height: Optional[float],
    floor_count: Optional[int],
    use_type: Optional[str] = "residential",
    base_elevation: float = 0.0,
) -> tuple[float, int, float]:
    """Derive consistent (height, floor_count, floor_height) using calibrated heuristics.
    
    Returns:
        (effective_height, effective_floor_count, floor_height)
    """
    heuristic_floor_h = get_typical_floor_height(use_type)

    if total_height is not None and total_height > 0:
        if floor_count is not None and floor_count > 0:
            effective_floor_h = round(total_height / floor_count, 2)
            return float(total_height), int(floor_count), effective_floor_h
        else:
            computed_floors = max(1, round(total_height / heuristic_floor_h))
            effective_floor_h = round(total_height / computed_floors, 2)
            return float(total_height), int(computed_floors), effective_floor_h
    elif floor_count is not None and floor_count > 0:
        computed_height = round(floor_count * heuristic_floor_h, 2)
        return float(computed_height), int(floor_count), heuristic_floor_h
    else:
        # Default 1 floor building
        return heuristic_floor_h, 1, heuristic_floor_h


def compute_floor_vertical_extents(
    floor_count: int,
    floor_height: float,
    base_z: float = 0.0,
) -> list[dict[str, Any]]:
    """Compute vertical bounds (z_min, z_max) for all levels in a building."""
    levels = []
    current_z = base_z
    for f in range(1, floor_count + 1):
        z_start = round(current_z, 2)
        z_end = round(current_z + floor_height, 2)
        levels.append({
            "floor_seq": f,
            "z_min": z_start,
            "z_max": z_end,
            "height": round(floor_height, 2),
        })
        current_z = z_end
    return levels


def compute_unit_vertical_extent(
    floor_seq: int,
    floor_height: float,
    base_z: float = 0.0,
) -> tuple[float, float]:
    """Compute (z_min, z_max) for a unit residing on a specific floor sequence."""
    if floor_seq <= 0:
        # Ground level unit
        return round(base_z, 2), round(base_z + floor_height, 2)
    z_min = round(base_z + (floor_seq - 1) * floor_height, 2)
    z_max = round(z_min + floor_height, 2)
    return z_min, z_max
