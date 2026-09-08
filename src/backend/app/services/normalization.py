"""GIS and attribute normalization service.

Handles:
1. Coordinate Reference System (CRS) normalization to canonical EPSG:4326.
2. Physical dimension unit normalization to SI meters (m).
3. Geometric validation and topological repair.
"""

import re
from typing import Any, Optional, Union
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import make_valid


CANONICAL_CRS = "EPSG:4326"

# Conversion factors to standard SI meters (m)
UNIT_TO_METERS = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "metre": 1.0,
    "metres": 1.0,
    "ft": 0.3048,
    "feet": 0.3048,
    "foot": 0.3048,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    "yd": 0.9144,
    "yard": 0.9144,
    "yards": 0.9144,
}

_NUMERIC_WITH_UNIT_PATTERN = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z]+)?$")


def normalize_unit(value: Union[float, int, str, None], unit_hint: Optional[str] = None) -> Optional[float]:
    """Convert any height/dimension value to standard SI meters.
    
    Examples:
        normalize_unit(10.0, "ft") -> 3.048
        normalize_unit("30 feet") -> 9.144
        normalize_unit(15.5) -> 15.5
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        numeric_val = float(value)
        unit_str = (unit_hint or "m").lower().strip()
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        match = _NUMERIC_WITH_UNIT_PATTERN.match(cleaned)
        if match:
            numeric_val = float(match.group(1))
            unit_str = (match.group(2) or unit_hint or "m").lower().strip()
        else:
            try:
                numeric_val = float(cleaned)
                unit_str = (unit_hint or "m").lower().strip()
            except ValueError:
                return None
    else:
        return None

    factor = UNIT_TO_METERS.get(unit_str, 1.0)
    return round(numeric_val * factor, 4)


def is_geographic_crs(crs_str: str) -> bool:
    """Check if the CRS is standard WGS84 EPSG:4326."""
    norm = crs_str.upper().strip()
    return norm in ("EPSG:4326", "4326", "WGS84", "CRS84", "OGC:CRS84")


def normalize_crs(
    geometry: Optional[BaseGeometry],
    source_crs: str = CANONICAL_CRS,
    target_crs: str = CANONICAL_CRS,
) -> Optional[BaseGeometry]:
    """Reproject a Shapely geometry from source_crs to target_crs (default EPSG:4326)."""
    if geometry is None:
        return None

    if is_geographic_crs(source_crs) and is_geographic_crs(target_crs):
        return geometry

    try:
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        transformed_geom = transform(transformer.transform, geometry)
        return transformed_geom
    except Exception as exc:
        raise ValueError(f"Failed to transform geometry from {source_crs} to {target_crs}: {exc}") from exc


def validate_and_repair_geometry(geometry: Optional[BaseGeometry]) -> Optional[BaseGeometry]:
    """Validate geometry and repair self-intersections or degenerate rings."""
    if geometry is None or geometry.is_empty:
        return None

    geom = geometry
    if not geom.is_valid:
        geom = make_valid(geom)
        if not geom.is_valid:
            geom = geom.buffer(0)

    # Validate coordinate bounds if in EPSG:4326
    minx, miny, maxx, maxy = geom.bounds
    if minx < -180.0 or maxx > 180.0 or miny < -90.0 or maxy > 90.0:
        # If coordinates are outside valid geographic latitude/longitude range,
        # note: might be projected coordinates mislabeled as EPSG:4326
        pass

    return geom
