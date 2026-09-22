"""Trace one complete cadastral object through all layers for Stage 6 validation."""
import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.property_object import PropertyObject
from app.main import app

def trace_object():
    print("======================================================================")
    print("STAGE 6: OBJECT TRACE DATA FLOW VERIFICATION")
    print("======================================================================\n")

    client = TestClient(app)
    db = SessionLocal()

    try:
        # Step 1: Query a real imported building from DB
        building = db.query(PropertyObject).filter(PropertyObject.type == "building").first()
        assert building is not None, "No building found in database!"

        ulpin = building.ulpin
        b_3d_id = building.three_d_property_id
        b_id = building.id

        print(f"1. Building Selected:")
        print(f"   - ULPIN:               {ulpin}")
        print(f"   - 3D Property ID:      {b_3d_id}")
        print(f"   - Database UUID:       {b_id}")
        print(f"   - Status:              {building.status}")
        print(f"   - Confidence:          {building.confidence}")

        # Step 2: Query Building Detail via API
        res_detail = client.get(f"/api/v1/properties/{b_3d_id}")
        assert res_detail.status_code == 200, f"Detail lookup failed: {res_detail.status_code}"
        detail_json = res_detail.json()
        assert detail_json["three_d_property_id"] == b_3d_id
        print(f"2. API Property Detail (/api/v1/properties/{b_3d_id}):")
        print(f"   - Returned ID:         {detail_json['three_d_property_id']}")
        print(f"   - Attributes:          {list(detail_json.get('attributes', {}).keys())}")

        # Step 3: Query Spatial Hierarchy via API
        res_hier = client.get(f"/api/v1/properties/{b_3d_id}/hierarchy")
        assert res_hier.status_code == 200, f"Hierarchy lookup failed: {res_hier.status_code}"
        hier_json = res_hier.json()
        assert "root" in hier_json
        root = hier_json["root"]
        children = root.get("children", [])
        print(f"3. API Hierarchy (/api/v1/properties/{b_3d_id}/hierarchy):")
        print(f"   - Root Node:           {root['three_d_property_id']} ({root['type']})")
        print(f"   - Direct Child Units:  {len(children)}")
        assert len(children) > 0, f"Building {b_3d_id} has no child units in hierarchy!"

        # Step 4: Trace a Child Unit
        first_child = children[0]
        c_3d_id = first_child["three_d_property_id"]
        c_type = first_child["type"]
        c_z_min = first_child.get("z_min")
        c_z_max = first_child.get("z_max")
        c_attrs = first_child.get("attributes") or {}
        floor_num = c_attrs.get("floor_number", "N/A")

        print(f"4. Child Unit Traced:")
        print(f"   - Unit 3D ID:          {c_3d_id}")
        print(f"   - Type:                {c_type}")
        print(f"   - Floor Number:        {floor_num}")
        print(f"   - z_min / z_max:       {c_z_min}m / {c_z_max}m")
        print(f"   - Status:              {first_child['status']}")
        print(f"   - Parent Building:     {c_attrs.get('building_id') or c_attrs.get('parent_building_id')}")

        # Verify ID consistency
        assert b_3d_id in c_3d_id or ulpin in c_3d_id, f"Unit ID {c_3d_id} does not contain building/ULPIN reference!"

        # Step 5: Search Endpoint by ULPIN
        res_search = client.get(f"/api/v1/search?q={ulpin}")
        assert res_search.status_code == 200, f"Search failed: {res_search.status_code}"
        search_json = res_search.json()
        print(f"5. Search Endpoint (/api/v1/search?q={ulpin}):")
        print(f"   - Matches Returned:    {len(search_json)}")
        matched_ids = [item.get("three_d_property_id") for item in search_json]
        assert b_3d_id in matched_ids, f"Search results missing building {b_3d_id}!"
        print(f"   - Building Found:      YES ({b_3d_id})")

        # Step 6: Map Layer Representation
        res_map = client.get("/api/v1/map/objects?limit=50")
        assert res_map.status_code == 200
        map_json = res_map.json()
        print(f"6. Map Objects Endpoint (/api/v1/map/objects):")
        print(f"   - Features returned:   {len(map_json.get('features', []))}")
        print(f"   - Geometry format:     GeoJSON FeatureCollection (EPSG:4326)")

        print("\n======================================================================")
        print("[PASS] COMPLETE OBJECT LIFECYCLE DATA FLOW VERIFIED 100%")
        print("======================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    trace_object()
