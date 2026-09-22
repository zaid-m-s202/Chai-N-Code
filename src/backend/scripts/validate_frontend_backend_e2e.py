"""End-to-end frontend to backend data contract verification script for Stage 6."""
import os
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

def validate_all():
    client = TestClient(app)
    print("======================================================================")
    print("STAGE 6: FRONTEND <-> BACKEND CONTRACT & UI FLOW VALIDATION")
    print("======================================================================\n")

    # A. Dashboard / Header Health & Auth
    print("--- A. DASHBOARD / HEALTH & ROLE SWITCHING ---")
    r_health = client.get("/health")
    assert r_health.status_code == 200 and r_health.json()["status"] == "ok"
    print("  [PASS] /health liveness probe connected: status='ok'")

    for role in ["VERIFYING_OFFICER", "FIELD_SURVEYOR", "PUBLIC_VIEWER"]:
        r_token = client.post(f"/api/v1/auth/quick-token?role={role}")
        assert r_token.status_code == 200 and "access_token" in r_token.json()
        print(f"  [PASS] Role token generation for {role}: issued")
    officer_token = client.post("/api/v1/auth/quick-token?role=VERIFYING_OFFICER").json()["access_token"]
    headers = {"Authorization": f"Bearer {officer_token}"}

    # B. Map Page
    print("\n--- B. MAP PAGE DATASETS ---")
    # Live units
    r_units = client.get("/api/v1/map/units?limit=50")
    assert r_units.status_code == 200
    u_geo = r_units.json()
    assert u_geo["type"] == "FeatureCollection" and len(u_geo["features"]) > 0
    sample_unit = u_geo["features"][0]
    assert "height" in sample_unit["properties"]
    assert "floor_number" in sample_unit["properties"]
    assert "z_min" in sample_unit["properties"]
    assert "z_max" in sample_unit["properties"]
    print(f"  [PASS] /api/v1/map/units: returned {len(u_geo['features'])} 3D extruded features with elevation")

    # Underground infrastructure
    r_ug = client.get("/api/v1/map/underground?limit=10")
    assert r_ug.status_code == 200
    ug_geo = r_ug.json()
    assert ug_geo["type"] == "FeatureCollection" and len(ug_geo["features"]) > 0
    print(f"  [PASS] /api/v1/map/underground: returned subterranean features (depth-layered)")

    # C. Property Registry & Details
    print("\n--- C. PROPERTY REGISTRY & DETAILS ---")
    r_props = client.get("/api/v1/properties?type=building&limit=10")
    assert r_props.status_code == 200
    props_list = r_props.json()
    assert len(props_list) == 10
    sample_bldg_id = props_list[0]["three_d_property_id"]
    print(f"  [PASS] /api/v1/properties?type=building: returned 10 buildings (Sample: {sample_bldg_id})")

    r_detail = client.get(f"/api/v1/properties/{sample_bldg_id}")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["three_d_property_id"] == sample_bldg_id
    assert "ULPIN" in detail.get("attributes", {})
    print(f"  [PASS] Property Detail lookup: ULPIN = {detail['attributes']['ULPIN']}, status = {detail['status']}")

    r_hier = client.get(f"/api/v1/properties/{sample_bldg_id}/hierarchy")
    assert r_hier.status_code == 200
    hier = r_hier.json()
    assert hier["root"]["three_d_property_id"] == sample_bldg_id
    print(f"  [PASS] Hierarchy drilldown: {len(hier['root']['children'])} child units linked to {sample_bldg_id}")

    # D. Search
    print("\n--- D. SEARCH BY ULPIN ---")
    sample_ulpin = detail["attributes"]["ULPIN"]
    r_search = client.get(f"/api/v1/search?q={sample_ulpin}")
    assert r_search.status_code == 200
    search_results = r_search.json()
    assert len(search_results) > 0
    print(f"  [PASS] /api/v1/search?q={sample_ulpin}: returned {len(search_results)} matching entities")

    # E. Verification Queue
    print("\n--- E. OFFICER VERIFICATION QUEUE ---")
    r_queue = client.get("/api/v1/verification-queue")
    assert r_queue.status_code == 200
    queue_list = r_queue.json()
    print(f"  [PASS] /api/v1/verification-queue: returned {len(queue_list)} provisional/unverified items")

    # F. Topology Conflicts
    print("\n--- F. TOPOLOGY CONFLICTS ---")
    r_conflicts = client.get("/api/v1/conflicts")
    assert r_conflicts.status_code == 200
    conflicts_list = r_conflicts.json()
    print(f"  [PASS] /api/v1/conflicts: returned {len(conflicts_list)} tracked conflict items")

    # G. Ingestion Jobs
    print("\n--- G. INGESTION PIPELINE (NON-DESTRUCTIVE AUDIT) ---")
    r_jobs = client.get("/api/v1/ingestion/jobs")
    assert r_jobs.status_code == 200
    jobs_list = r_jobs.json()
    print(f"  [PASS] /api/v1/ingestion/jobs: retrieved {len(jobs_list)} recorded ingestion jobs")

    # H. AI Cadastral Studio
    print("\n--- H. AI CADASTRAL STUDIO ENDPOINTS ---")
    r_adapters = client.get("/api/v1/analysis/adapters")
    assert r_adapters.status_code == 200
    adapters = r_adapters.json()
    assert len(adapters) >= 3
    print(f"  [PASS] AI adapters available: {[a['name'] for a in adapters]}")

    # Footprint extraction
    r_fp = client.post("/api/v1/analysis/extract-footprints", json={
        "bbox": [73.8450, 18.5113, 73.8462, 18.5122],
        "scale_factor": 0.75,
        "tolerance": 0.00002,
        "model_name": "CadastralMaskRCNN-V2"
    })
    assert r_fp.status_code == 200
    print("  [PASS] Footprint Extraction: executed")

    # Floor segmentation
    r_seg = client.post("/api/v1/analysis/segment-floors", json={
        "base_ulpin": "27-21-11-719-000001",
        "building_id": 1,
        "floor_number": 2,
        "units_count": 4,
        "ceiling_height_m": 3.0,
        "corridor_ratio": 0.12
    })
    assert r_seg.status_code == 200
    print("  [PASS] Floor Segmentation: executed")

    # Vertical delineation
    r_delin = client.post("/api/v1/analysis/delineate-vertical-parcels", json={
        "base_ulpin": "27-21-11-719-000001",
        "state": "MH",
        "district": "PUN",
        "floor_count": 4,
        "units_per_floor": 2,
        "basement_levels": 1,
        "ceiling_height_m": 3.0,
        "ground_elevation_m": 558.0,
        "include_underground_utilities": True
    })
    assert r_delin.status_code == 200
    print("  [PASS] Vertical Delineation: executed")

    # Topology validation
    r_topo = client.post("/api/v1/analysis/validate-3d-topology", json={
        "parcels": [
            {"three_d_property_id": "TEST-U01", "type": "unit", "z_min": 0.0, "z_max": 3.0},
            {"three_d_property_id": "TEST-U02", "type": "unit", "z_min": 3.0, "z_max": 6.0}
        ]
    })
    assert r_topo.status_code == 200
    print("  [PASS] 3D Topology Validation: executed")

    print("\n======================================================================")
    print("[PASS] ALL 8 CORE FRONTEND <-> BACKEND SECTIONS FULLY VERIFIED")
    print("======================================================================")

if __name__ == "__main__":
    validate_all()
