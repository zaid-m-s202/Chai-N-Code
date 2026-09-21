#!/usr/bin/env python3
"""
3D Cadastral Unit & Floor Synthesizer
Generates 3D Floor-by-Floor and Unit-by-Unit cadastral geometries with:
- Standard UIPIN: {ULPIN}-B{bldg:03d}-F{floor:02d}-U{unit:03d}
- Vertical extents (z_min, z_max)
- Exploded vertical separation heights
- Floor colors matching the Cadastral System Architecture (Basement, Floor 1 Amber, Floor 2 Green, Floor 3 Cyan)
- Partitioned unit polygons (Unit A, Unit B, etc.)
"""

import json
import os
import sys
from shapely.geometry import shape, mapping, box, MultiPolygon, Polygon
from shapely.ops import unary_union

INPUT_GEOJSON = os.path.join(os.path.dirname(__file__), "..", "cadastral_3d_buildings.geojson")
OUTPUT_PUBLIC = os.path.join(os.path.dirname(__file__), "..", "src", "frontend", "public", "cadastral_3d_units.geojson")
OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "..", "cadastral_3d_units.geojson")

FLOOR_COLORS = {
    -1: "#64748b",  # Basement / Parking - Slate Gray
    1: "#f59e0b",   # Floor 1 - Amber / Gold
    2: "#10b981",   # Floor 2 - Emerald Green
    3: "#0ea5e9",   # Floor 3 - Cyan / Sky Blue
    4: "#8b5cf6",   # Floor 4 - Purple
    5: "#ec4899",   # Floor 5 - Pink
    6: "#6366f1",   # Floor 6 - Indigo
}

DEFAULT_UPPER_COLORS = ["#8b5cf6", "#ec4899", "#3b82f6", "#14b8a6", "#f97316"]


import re

def parse_levels(val) -> int:
    if val is None:
        return 1
    if isinstance(val, (int, float)):
        return max(1, int(val))
    val_str = str(val).strip().lower()
    m = re.search(r'(?:ground|g)\s*\+\s*(\d+)', val_str)
    if m:
        return int(m.group(1)) + 1
    m = re.search(r'\d+', val_str)
    if m:
        return max(1, int(m.group(0)))
    return 1


def partition_polygon_into_units(poly: Polygon, num_units: int = 2) -> list[Polygon]:
    """Partitions a floor polygon into realistic unit subdivisions."""
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.area <= 0:
        return []

    minx, miny, maxx, maxy = poly.bounds
    width = maxx - minx
    height = maxy - miny

    units = []
    if num_units == 2:
        if width >= height:
            mid_x = (minx + maxx) / 2
            box_a = box(minx - 1, miny - 1, mid_x, maxy + 1)
            box_b = box(mid_x, miny - 1, maxx + 1, maxy + 1)
        else:
            mid_y = (miny + maxy) / 2
            box_a = box(minx - 1, miny - 1, maxx + 1, mid_y)
            box_b = box(minx - 1, mid_y, maxx + 1, maxy + 1)

        u_a = poly.intersection(box_a)
        u_b = poly.intersection(box_b)

        for u in [u_a, u_b]:
            if isinstance(u, Polygon) and u.area > 0:
                units.append(u)
            elif isinstance(u, MultiPolygon):
                for p in u.geoms:
                    if p.area > 0:
                        units.append(p)
    else:
        units.append(poly)

    if not units:
        units.append(poly)
    return units


def main():
    print(f"Reading {INPUT_GEOJSON}...")
    with open(INPUT_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    buildings = data.get("features", [])
    print(f"Loaded {len(buildings)} buildings.")

    unit_features = []
    processed_buildings = 0

    for bldg in buildings:
        props = bldg.get("properties", {})
        geom_dict = bldg.get("geometry")
        if not geom_dict:
            continue

        try:
            bldg_geom = shape(geom_dict)
            if not bldg_geom.is_valid:
                bldg_geom = bldg_geom.buffer(0)
        except Exception:
            continue

        ulpin = props.get("ULPIN", "27-21-00-000-000000")
        bldg_3d_id = props.get("three_d_property_id", "BLDG0000000000")
        bldg_name = props.get("name") or props.get("addr:housenumber") or f"Building {bldg_3d_id[:6]}"
        levels = parse_levels(props.get("building:levels"))
        levels = max(1, min(levels, 12))  # Cap levels between 1 and 12 for high performance
        building_use = props.get("building", "residential")

        # Create floor polygons to partition
        base_polys = []
        if isinstance(bldg_geom, Polygon):
            base_polys = [bldg_geom]
        elif isinstance(bldg_geom, MultiPolygon):
            base_polys = list(bldg_geom.geoms)

        if not base_polys:
            continue

        primary_poly = max(base_polys, key=lambda p: p.area)
        poly_units = partition_polygon_into_units(primary_poly, num_units=2)
        if len(poly_units) < 2:
            poly_units = [primary_poly, primary_poly]

        # ── 1. Basement / Parking (Z: -3.0m to 0.0m) ──────────────────────────
        # For multi-floor buildings (levels >= 2), include Basement / Parking
        if levels >= 2:
            for u_idx, u_geom in enumerate(poly_units[:2]):
                unit_label = f"Parking Bay P-{u_idx+1:02d}"
                unit_id = f"P{u_idx+1:02d}"
                uipin = f"{ulpin}-B001-F00-U{u_idx+1:03d}"

                feature = {
                    "type": "Feature",
                    "geometry": mapping(u_geom),
                    "properties": {
                        "three_d_property_id": uipin,
                        "UIPIN": uipin,
                        "ULPIN": ulpin,
                        "parent_building_id": bldg_3d_id,
                        "building_name": bldg_name,
                        "floor_number": -1,
                        "floor_name": "Basement / Parking",
                        "unit_number": unit_label,
                        "unit_id": unit_id,
                        "z_min": -3.0,
                        "z_max": 0.0,
                        "height": 3.0,
                        "color": FLOOR_COLORS[-1],
                        "use_type": "Parking / Storage",
                        "status": "VERIFIED",
                        "area_sqm": round(u_geom.area * 111319.5 * 111319.5 * 0.9, 1),
                        "confidence": 0.95,
                    },
                }
                unit_features.append(feature)

        # ── 2. Above-Ground Floors (Floor 1, Floor 2, Floor 3, ...) ────────────
        for floor_idx in range(1, levels + 1):
            z_min = (floor_idx - 1) * 3.0
            z_max = floor_idx * 3.0
            floor_color = FLOOR_COLORS.get(floor_idx, DEFAULT_UPPER_COLORS[(floor_idx - 1) % len(DEFAULT_UPPER_COLORS)])

            for u_idx, u_geom in enumerate(poly_units[:2]):
                letter = "A" if u_idx == 0 else "B"
                unit_number = f"Unit {floor_idx}{letter}"
                unit_id = f"U-{floor_idx}{letter}"
                unit_seq = floor_idx * 10 + (u_idx + 1)
                uipin = f"{ulpin}-B001-F{floor_idx:02d}-U{unit_seq:03d}"

                feature = {
                    "type": "Feature",
                    "geometry": mapping(u_geom),
                    "properties": {
                        "three_d_property_id": uipin,
                        "UIPIN": uipin,
                        "ULPIN": ulpin,
                        "parent_building_id": bldg_3d_id,
                        "building_name": bldg_name,
                        "floor_number": floor_idx,
                        "floor_name": f"Floor {floor_idx}",
                        "unit_number": unit_number,
                        "unit_id": unit_id,
                        "z_min": z_min,
                        "z_max": z_max,
                        "height": 3.0,
                        "color": floor_color,
                        "use_type": "Residential" if "apart" in building_use or "res" in building_use else "Commercial",
                        "status": "PROVISIONAL" if floor_idx > 2 else "VERIFIED",
                        "area_sqm": round(u_geom.area * 111319.5 * 111319.5 * 0.9, 1),
                        "confidence": 0.90 if floor_idx > 2 else 0.96,
                    },
                }
                unit_features.append(feature)

        processed_buildings += 1

    fc = {
        "type": "FeatureCollection",
        "name": "cadastral_3d_units",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": unit_features,
    }

    print(f"Generated {len(unit_features)} 3D unit records across {processed_buildings} buildings.")

    os.makedirs(os.path.dirname(OUTPUT_PUBLIC), exist_ok=True)
    with open(OUTPUT_PUBLIC, "w", encoding="utf-8") as f:
        json.dump(fc, f, separators=(",", ":"))
    print(f"Saved to {OUTPUT_PUBLIC}")

    with open(OUTPUT_ROOT, "w", encoding="utf-8") as f:
        json.dump(fc, f, separators=(",", ":"))
    print(f"Saved to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
