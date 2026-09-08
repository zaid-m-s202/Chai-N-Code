"""Integration tests for REST API endpoints (PRD §8, §9 Acceptance Criteria 7, 8)."""

import json
from datetime import datetime, timezone
from uuid import uuid4
from app.models.property_object import PropertyObject
from app.models.conflict import Conflict
from app.models.source_observation import SourceObservation


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_ready_endpoint(client):
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "database" in data


def test_ingestion_and_property_retrieval(client):
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [75.85, 26.91]},
                "properties": {
                    "ulpin": "RJ14JAIPUR01",
                    "type": "building",
                    "building_seq": 1,
                    "height": 14.5,
                    "confidence": 0.82,
                }
            }
        ]
    }
    file_bytes = json.dumps(sample_geojson).encode("utf-8")
    files = {"file": ("jaipur_pilot.geojson", file_bytes, "application/json")}

    # Upload file synchronously
    upload_res = client.post(
        "/api/v1/ingestion/jobs?async_exec=false",
        files=files,
        data={"source_system": "pilot_upload"}
    )
    assert upload_res.status_code == 201
    job_data = upload_res.json()
    assert job_data["status"] == "COMPLETED"
    assert job_data["record_count"] == 1

    # List properties
    list_res = client.get("/api/v1/properties")
    assert list_res.status_code == 200
    props = list_res.json()
    assert len(props) >= 1
    three_d_id = props[0]["three_d_property_id"]
    assert "RJ14JAIPUR01" in three_d_id

    # Get detail
    detail_res = client.get(f"/api/v1/properties/{three_d_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["three_d_property_id"] == three_d_id

    # Get history
    history_res = client.get(f"/api/v1/properties/{three_d_id}/history")
    assert history_res.status_code == 200
    assert len(history_res.json()["events"]) >= 1

    # Phase 1 Acceptance: Source metadata is queryable via evidence endpoint
    evidence_res = client.get(f"/api/v1/properties/{three_d_id}/evidence")
    assert evidence_res.status_code == 200
    evidence_list = evidence_res.json()
    assert len(evidence_list) >= 1
    assert evidence_list[0]["source_system"] == "pilot_upload"
    assert evidence_list[0]["file_reference"] == "jaipur_pilot.geojson"


def test_ingestion_idempotency(client):
    """PRD: Idempotent ingestion jobs."""
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [75.80, 26.90]},
                "properties": {"ulpin": "IDEMP001", "type": "building", "building_seq": 1}
            }
        ]
    }
    file_bytes = json.dumps(sample_geojson).encode("utf-8")
    files = {"file": ("idemp.geojson", file_bytes, "application/json")}

    # First upload
    res1 = client.post("/api/v1/ingestion/jobs?async_exec=false", files=files)
    assert res1.status_code == 201
    job1 = res1.json()
    assert job1["status"] == "COMPLETED"

    # Second identical upload returns idempotent completed job without creating duplicate
    files2 = {"file": ("idemp.geojson", file_bytes, "application/json")}
    res2 = client.post("/api/v1/ingestion/jobs?async_exec=false", files=files2)
    assert res2.status_code == 201
    job2 = res2.json()
    assert job2["id"] == job1["id"]
    assert job2["status"] == "COMPLETED"


def test_officer_can_verify_provisional_property(client, db_session, officer_token):
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0001-B001-F01-U001",
        type="unit",
        status="PROVISIONAL",
        confidence=0.85,
    )
    db_session.add(prop)
    db_session.commit()

    # Unauthorized attempt fails (PRD Acceptance Criterion 8)
    unauth_res = client.post(f"/api/v1/properties/{prop.three_d_property_id}/verify")
    assert unauth_res.status_code in (401, 403)

    # Authorized verifying officer succeeds (PRD Acceptance Criterion 7)
    auth_res = client.post(
        f"/api/v1/properties/{prop.three_d_property_id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"notes": "Ground survey matches floor plan"},
    )
    assert auth_res.status_code == 200
    data = auth_res.json()
    assert data["status"] == "VERIFIED"
    assert data["confidence"] == 1.0


def test_field_surveyor_cannot_verify(client, db_session, surveyor_token):
    """PRD §2: Field surveyor submits evidence; cannot verify."""
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0002-B001-F01-U001",
        type="unit",
        status="PROVISIONAL",
        confidence=0.85,
    )
    db_session.add(prop)
    db_session.commit()

    res = client.post(
        f"/api/v1/properties/{prop.three_d_property_id}/verify",
        headers={"Authorization": f"Bearer {surveyor_token}"},
        json={"notes": "I surveyed this"},
    )
    assert res.status_code == 403
    assert "VERIFYING_OFFICER" in res.json()["detail"]


def test_verification_blocked_by_open_conflicts(client, db_session, officer_token):
    """PRD VR-09: Conflicts block VERIFIED status."""
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0003-B001-F01-U001",
        type="unit",
        status="PROVISIONAL",
        confidence=0.75,
    )
    db_session.add(prop)
    db_session.flush()

    conflict = Conflict(
        property_object_id=prop.id,
        rule_code="VR-01",
        description="Footprint extends outside parcel boundary by 1.2m",
        status="OPEN",
    )
    db_session.add(conflict)
    db_session.commit()

    # Attempt to verify must be blocked with HTTP 409
    res = client.post(
        f"/api/v1/properties/{prop.three_d_property_id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"notes": "Trying to verify despite conflict"},
    )
    assert res.status_code == 409
    assert "open conflict" in res.json()["detail"]


def test_search_and_map_endpoints(client, db_session):
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0004-B001-F01-U001",
        type="building",
        status="DERIVED",
        confidence=0.8,
    )
    db_session.add(prop)
    db_session.commit()

    # Search
    search_res = client.get("/api/v1/search?q=INTEST0004")
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) >= 1

    # Map objects
    map_res = client.get("/api/v1/map/objects")
    assert map_res.status_code == 200
    fc = map_res.json()
    assert fc["type"] == "FeatureCollection"
    assert isinstance(fc["features"], list)


def test_get_property_observations_and_refuse(client, db_session):
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0005-B001-F00-U000",
        type="building",
        status="DERIVED",
        confidence=0.8,
        attributes={"height": 20.0},
    )
    db_session.add(prop)
    db_session.flush()

    obs1 = SourceObservation(
        property_object_id=prop.id,
        attribute_name="height",
        observed_value={"value": 20.0},
        source_confidence=0.9,
        observed_at=datetime.now(timezone.utc),
    )
    obs2 = SourceObservation(
        property_object_id=prop.id,
        attribute_name="height",
        observed_value={"value": 22.0},
        source_confidence=0.85,
        observed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([obs1, obs2])
    db_session.commit()

    # Query observations
    obs_res = client.get(f"/api/v1/properties/{prop.three_d_property_id}/observations")
    assert obs_res.status_code == 200
    records = obs_res.json()
    assert len(records) == 2
    assert records[0]["attribute_name"] == "height"

    # Trigger re-fusion
    refuse_res = client.post(f"/api/v1/properties/{prop.three_d_property_id}/refuse")
    assert refuse_res.status_code == 200
    refuse_data = refuse_res.json()
    assert refuse_data["three_d_property_id"] == prop.three_d_property_id
    assert refuse_data["observations_count"] == 2
    assert 20.0 <= refuse_data["fused_height"] <= 22.0
    assert refuse_data["has_conflict"] is False


def test_hierarchy_endpoint(client, db_session):
    parcel = PropertyObject(
        id=uuid4(),
        three_d_property_id="INAPITEST-B000-F00-U000",
        type="parcel",
        status="VERIFIED",
        confidence=1.0,
    )
    db_session.add(parcel)
    db_session.flush()

    bldg = PropertyObject(
        id=uuid4(),
        three_d_property_id="INAPITEST-B001-F00-U000",
        type="building",
        parent_id=parcel.id,
        status="PROVISIONAL",
        confidence=0.9,
    )
    db_session.add(bldg)
    db_session.commit()

    res = client.get(f"/api/v1/properties/{parcel.three_d_property_id}/hierarchy")
    assert res.status_code == 200
    data = res.json()
    assert data["root"]["three_d_property_id"] == parcel.three_d_property_id
    assert len(data["root"]["children"]) == 1
    assert data["root"]["children"][0]["three_d_property_id"] == bldg.three_d_property_id


def test_split_and_merge_api_endpoints(client, db_session, officer_token):
    # Setup parent unit
    unit = PropertyObject(
        id=uuid4(),
        three_d_property_id="INAPISPLIT-B001-F01-U001",
        type="unit",
        status="PROVISIONAL",
        confidence=0.9,
        z_min=0.0,
        z_max=3.0,
    )
    db_session.add(unit)
    db_session.commit()

    # Split API call
    split_payload = {
        "split_units": [
            {"unit_name": "Suite A", "z_min": 0.0, "z_max": 3.0},
            {"unit_name": "Suite B", "z_min": 0.0, "z_max": 3.0},
        ],
        "reason": "Subdivision for leasing",
    }
    split_res = client.post(
        f"/api/v1/properties/{unit.three_d_property_id}/split",
        headers={"Authorization": f"Bearer {officer_token}"},
        json=split_payload,
    )
    assert split_res.status_code == 200
    split_data = split_res.json()
    assert split_data["superseded_unit_id"] == unit.three_d_property_id
    assert len(split_data["new_units"]) == 2
    u2_id = split_data["new_units"][0]["three_d_property_id"]
    u3_id = split_data["new_units"][1]["three_d_property_id"]
    assert u2_id == "INAPISPLIT-B001-F01-U002"
    assert u3_id == "INAPISPLIT-B001-F01-U003"

    # Merge API call on the new units U002 and U003
    merge_payload = {
        "unit_ids": [u2_id, u3_id],
        "merged_attributes": {"notes": "Recombined suite"},
        "reason": "Single tenant re-acquisition",
    }
    merge_res = client.post(
        "/api/v1/properties/merge",
        headers={"Authorization": f"Bearer {officer_token}"},
        json=merge_payload,
    )
    assert merge_res.status_code == 200
    merge_data = merge_res.json()
    assert merge_data["superseded_unit_ids"] == [u2_id, u3_id]
    # New merged unit ID must be U004 (never U001, U002, or U003)
    assert merge_data["merged_unit"]["three_d_property_id"] == "INAPISPLIT-B001-F01-U004"


def test_quick_token_endpoint(client):
    """Test quick-token endpoint for UI role switching."""
    # Officer role
    res = client.post("/api/v1/auth/quick-token?role=VERIFYING_OFFICER")
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert len(token) > 20

    # Surveyor role
    res_surv = client.post("/api/v1/auth/quick-token?role=FIELD_SURVEYOR")
    assert res_surv.status_code == 200

    # Invalid role
    res_bad = client.post("/api/v1/auth/quick-token?role=SUPERHERO")
    assert res_bad.status_code == 400



