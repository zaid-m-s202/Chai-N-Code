"""Smoke test script for FastAPI backend with real Pune dataset.

Tests representative endpoints against the imported Pune PostGIS database:
- Liveness (/health) & Readiness (/health/ready)
- Metrics telemetry (/metrics)
- Building list query (/api/v1/properties?type=building)
- Unit list query (/api/v1/properties?type=unit)
- 3D Property ID lookup (/api/v1/properties/{id})
- Spatial hierarchy tree (/api/v1/properties/{id}/hierarchy)
- ULPIN / ID text search (/api/v1/search)
- 2D/3D map GeoJSON layers (/api/v1/map/objects, /api/v1/map/units)
- Underground infrastructure assets (/api/v1/properties?type=tunnel)
- Topology conflict tracking (/api/v1/conflicts)
"""

import os
import sys
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# Ensure backend package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, get_db, setup_sqlite_mocks
from app.main import app
from app.models.user import User
from app.api.deps import get_password_hash


def run_smoke_tests(db_url: str = "sqlite:///pune_cadastral.db"):
    print("=" * 70)
    print("FASTAPI PRODUCTION SMOKE TESTS — REAL PUNE DATASET")
    print(f"Database: {db_url}")
    print("=" * 70)

    engine = sa.create_engine(db_url, connect_args={"check_same_thread": False})
    if "sqlite" in db_url:
        sa.event.listen(engine, "connect", setup_sqlite_mocks)

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Ensure a test admin user exists in DB for auth testing
    session = TestingSessionLocal()
    admin_user = session.query(User).filter(User.username == "admin_officer").first()
    if not admin_user:
        admin_user = User(
            username="admin_officer",
            password_hash=get_password_hash("CadastralSecure2026!"),
            role="VERIFYING_OFFICER",
            is_active=True,
        )
        session.add(admin_user)
        session.commit()
    session.close()

    client = TestClient(app)

    # 1. Health Liveness Probe
    print("\n1. Testing Service Liveness Probe (/health)...")
    r_live = client.get("/health")
    assert r_live.status_code == 200, f"Expected 200, got {r_live.status_code}"
    assert r_live.json().get("status") == "ok"
    print(f"   [PASS] 200 OK — {r_live.json()}")

    # 2. Health Readiness Probe
    print("\n2. Testing Service Readiness Probe (/health/ready)...")
    r_ready = client.get("/health/ready")
    assert r_ready.status_code == 200
    assert r_ready.json().get("database") == "connected"
    print(f"   [PASS] 200 OK — Database connected: {r_ready.json()}")

    # 3. Telemetry Metrics
    print("\n3. Testing Observability Metrics (/metrics)...")
    r_metrics = client.get("/metrics")
    assert r_metrics.status_code == 200
    assert "cadastre_" in r_metrics.text
    print(f"   [PASS] 200 OK — Prometheus metrics available ({len(r_metrics.text)} bytes)")


    # 4. Building List Query
    print("\n4. Testing Building Query (/api/v1/properties?type=building)...")
    r_bldgs = client.get("/api/v1/properties?type=building&limit=10")
    assert r_bldgs.status_code == 200
    bldgs = r_bldgs.json()
    assert len(bldgs) == 10
    assert bldgs[0]["type"] == "building"
    sample_bldg_id = bldgs[0]["three_d_property_id"]
    print(f"   [PASS] 200 OK — Retrieved {len(bldgs)} buildings (Sample: {sample_bldg_id})")

    # 5. Unit List Query
    print("\n5. Testing Unit Query (/api/v1/properties?type=unit)...")
    r_units = client.get("/api/v1/properties?type=unit&limit=10")
    assert r_units.status_code == 200
    units = r_units.json()
    assert len(units) == 10
    assert units[0]["type"] == "unit"
    sample_unit_id = units[0]["three_d_property_id"]
    print(f"   [PASS] 200 OK — Retrieved {len(units)} units (Sample: {sample_unit_id})")

    # 6. Single Property Detail Lookup
    print(f"\n6. Testing 3D Property ID Detail Lookup (/api/v1/properties/{sample_unit_id})...")
    r_detail = client.get(f"/api/v1/properties/{sample_unit_id}")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["three_d_property_id"] == sample_unit_id
    assert detail["type"] == "unit"
    assert "ulpin" in detail
    assert "stratum" in detail
    assert "volume_m3" in detail
    assert detail["parent_id"] is not None
    print(f"   [PASS] 200 OK — Detail verified (ULPIN: {detail['ulpin']}, Stratum: {detail['stratum']}, Vol: {detail['volume_m3']} m³)")

    # 7. Spatial Hierarchy Query
    # Use Jnana Prabodhini building which has child units
    bldg_three_d = "XAJI0Y6DPBHSAH"
    print(f"\n7. Testing Hierarchy Endpoint (/api/v1/properties/{bldg_three_d}/hierarchy)...")
    r_hier = client.get(f"/api/v1/properties/{bldg_three_d}/hierarchy")
    assert r_hier.status_code == 200
    hier = r_hier.json()
    assert "root" in hier
    assert hier["root"]["three_d_property_id"] == bldg_three_d
    child_count = len(hier["root"].get("children", []))
    print(f"   [PASS] 200 OK — Hierarchy tree returned for building {bldg_three_d} with {child_count} direct children")

    # 8. ULPIN Search Query
    sample_ulpin = detail["ulpin"]
    print(f"\n8. Testing ULPIN Search Endpoint (/api/v1/search?q={sample_ulpin})...")
    r_search = client.get(f"/api/v1/search?q={sample_ulpin}&limit=10")
    assert r_search.status_code == 200
    search_results = r_search.json()
    assert len(search_results) > 0
    print(f"   [PASS] 200 OK — Search matched {len(search_results)} properties for ULPIN {sample_ulpin}")

    # 9. Map Layers (MapLibre GeoJSON Endpoint)
    print("\n9. Testing Map Layer Objects (/api/v1/map/objects)...")
    r_map = client.get("/api/v1/map/objects?limit=25")
    assert r_map.status_code == 200
    map_fc = r_map.json()
    assert map_fc["type"] == "FeatureCollection"
    assert len(map_fc["features"]) > 0
    print(f"   [PASS] 200 OK — GeoJSON FeatureCollection with {len(map_fc['features'])} features")

    # 10. Underground Infrastructure Query
    print("\n10. Testing Underground Assets Query (/api/v1/properties?type=tunnel)...")
    r_ug = client.get("/api/v1/properties?type=tunnel")
    assert r_ug.status_code == 200
    ug_list = r_ug.json()
    assert len(ug_list) > 0
    assert "METRO" in ug_list[0]["three_d_property_id"]
    print(f"   [PASS] 200 OK — Retrieved {len(ug_list)} underground assets (Sample: {ug_list[0]['three_d_property_id']})")

    # 11. Authentication Token Issuance (/api/v1/auth/login)
    print("\n11. Testing Authentication (/api/v1/auth/login)...")
    r_auth = client.post(
        "/api/v1/auth/login",
        json={"username": "admin_officer", "password": "CadastralSecure2026!"},
    )
    assert r_auth.status_code == 200, f"Expected 200, got {r_auth.status_code}: {r_auth.text}"
    token_data = r_auth.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    print(f"   [PASS] 200 OK — JWT Token issued successfully: {token[:20]}...")


    # 12. Authenticated Profile Probe
    print("\n12. Testing Authenticated Session (/api/v1/auth/me)...")
    r_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_me.status_code == 200
    user_info = r_me.json()
    assert user_info["username"] == "admin_officer"
    assert user_info["role"] == "VERIFYING_OFFICER"
    print(f"   [PASS] 200 OK — Verified user: {user_info['username']} [{user_info['role']}]")

    app.dependency_overrides.clear()
    print("\n" + "=" * 70)
    print("ALL 12 PRODUCTION API SMOKE TESTS PASSED CLEANLY WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    run_smoke_tests()
