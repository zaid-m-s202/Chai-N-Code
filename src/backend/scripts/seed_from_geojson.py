#!/usr/bin/env python3
"""Seed the SQLite database from cadastral_3d_units.geojson.

Directly inserts PropertyObject records so the /api/v1/map/units endpoint
returns data immediately. Uses batch inserts for speed on the ~30MB file.

Usage:
    cd src/backend
    python scripts/seed_from_geojson.py
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, engine, SessionLocal
from app.models.property_object import PropertyObject

# Also import all models so Base.metadata knows all tables
import app.models  # noqa: F401


_cand1 = os.path.join(os.path.dirname(__file__), "..", "..", "..", "cadastral_3d_units.geojson")
_cand2 = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "cadastral_3d_units.geojson")
GEOJSON_PATH = _cand1 if os.path.exists(_cand1) else _cand2


BATCH_SIZE = 500


def seed():
    # 1. Create tables if they don't exist
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 2. Check if real data already seeded
    existing_count = db.query(PropertyObject).filter(
        PropertyObject.type == "unit"
    ).count()

    if existing_count > 50:
        print(f"Database already contains {existing_count} units. Skipping seed.")
        print("To re-seed, delete cadastral_dev.db and re-run.")
        db.close()
        return


    # 3. Load GeoJSON
    if not os.path.exists(GEOJSON_PATH):
        print(f"ERROR: {GEOJSON_PATH} not found.")
        print("Run `python scripts/generate_3d_units.py` first.")
        sys.exit(1)

    print(f"Loading {GEOJSON_PATH}...")
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"Found {len(features)} features to seed.")

    # 4. Batch-insert features as PropertyObject records
    inserted = 0
    batch = []

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry")

        three_d_id = props.get("three_d_property_id") or props.get("UIPIN") or f"UNIT-{uuid.uuid4().hex[:12]}"

        # Determine object type from floor_number or three_d_id
        obj_type = "unit"

        prop = PropertyObject(
            id=uuid.uuid4(),
            type=obj_type,
            three_d_property_id=three_d_id,
            z_min=props.get("z_min"),
            z_max=props.get("z_max"),
            confidence=props.get("confidence", 0.85),
            status=props.get("status", "DERIVED"),
            attributes={
                "geojson_geometry": geom,
                "height": props.get("height"),
                "floor_count": props.get("floor_count"),
                "floor_number": props.get("floor_number"),
                "building_id": props.get("parent_building_id"),
                "parent_building_id": props.get("parent_building_id"),
                "ULPIN": props.get("ULPIN"),
                "ulpin": props.get("ULPIN"),
                "UIPIN": props.get("UIPIN"),
                "building_name": props.get("building_name"),
                "floor_name": props.get("floor_name"),
                "unit_number": props.get("unit_number"),
                "unit_id": props.get("unit_id"),
                "unit_label": props.get("unit_number"),
                "use": props.get("use_type"),
                "use_type": props.get("use_type"),
                "area_sqm": props.get("area_sqm"),
                "color": props.get("color"),
            },
            source_list=[],
        )
        batch.append(prop)

        if len(batch) >= BATCH_SIZE:
            db.add_all(batch)
            db.flush()
            inserted += len(batch)
            print(f"  Inserted {inserted}/{len(features)}...")
            batch = []

    # Flush remaining
    if batch:
        db.add_all(batch)
        inserted += len(batch)

    db.commit()
    print(f"\nDone! Seeded {inserted} PropertyObject records into the database.")
    db.close()


if __name__ == "__main__":
    seed()
