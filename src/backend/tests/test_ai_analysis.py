"""Tests for AI/GIS analysis adapters, status gating, and service orchestration (PRD §5.4)."""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.analysis.base import validate_ai_status, AnalysisResult, ALLOWED_AI_STATUSES
from app.analysis.elevation_adapter import DsmDemHeightAdapter
from app.analysis.floor_estimator_adapter import FloorEstimatorAdapter
from app.analysis.footprint_adapter import PretrainedFootprintAdapter
from app.analysis.service import AnalysisService
from app.models.property_object import PropertyObject
from app.models.source_observation import SourceObservation
from app.models.evidence import Evidence
from app.models.change_event import ChangeEvent


def test_status_gating_enforcement():
    """Test that AI analysis outputs strictly CANNOT have VERIFIED status."""
    # Allowed statuses
    for status in ("INFERRED", "inferred", "DERIVED", "derived", "PROVISIONAL"):
        assert validate_ai_status(status) in ALLOWED_AI_STATUSES

    # VERIFIED status MUST raise ValueError
    with pytest.raises(ValueError, match="Status Gating Violation"):
        validate_ai_status("VERIFIED")

    with pytest.raises(ValueError, match="Status Gating Violation"):
        validate_ai_status("verified")

    # Invalid status
    with pytest.raises(ValueError, match="Invalid AI analysis status"):
        validate_ai_status("UNAPPROVED")


def test_analysis_result_contract():
    """Test AnalysisResult validation and automated metadata attachment."""
    res = AnalysisResult(
        adapter_name="test_adapter",
        adapter_version="1.0.0",
        status="DERIVED",
        confidence=0.85,
        data={"height": 12.5},
    )
    assert res.status == "DERIVED"
    assert res.evidence["adapter"] == "test_adapter"
    assert "executed_at" in res.evidence

    # Reject VERIFIED directly on AnalysisResult creation
    with pytest.raises(ValueError, match="Status Gating Violation"):
        AnalysisResult(
            adapter_name="test_adapter",
            adapter_version="1.0.0",
            status="VERIFIED",
            confidence=0.99,
            data={"verified": True},
        )

    # Reject out of bounds confidence
    with pytest.raises(ValueError, match="Confidence score"):
        AnalysisResult(
            adapter_name="test_adapter",
            adapter_version="1.0.0",
            status="INFERRED",
            confidence=1.5,
            data={},
        )


def test_dsm_dem_height_adapter_scalars():
    """Test building height extraction from single DSM and DEM scalar pair."""
    adapter = DsmDemHeightAdapter()
    assert adapter.name == "dsm_dem_height"

    # DSM = 45.0m, DEM = 30.0m -> height = 15.0m
    result = adapter.analyze({"dsm": 45.0, "dem": 30.0, "sensor_type": "LiDAR"})

    assert result.status == "DERIVED"  # Not VERIFIED
    assert result.data["building_height"] == 15.0
    assert result.data["base_elevation"] == 30.0
    assert result.data["z_min"] == 30.0
    assert result.data["z_max"] == 45.0
    assert result.confidence >= 0.85
    assert result.evidence["sensor_type"] == "LiDAR"
    assert len(result.warnings) == 0


def test_dsm_dem_height_adapter_sample_array():
    """Test height extraction with sample array, p90 calculation, and negative delta clipping."""
    adapter = DsmDemHeightAdapter()

    # Surface samples with one negative noise anomaly (e.g. excavation / sensor noise)
    dsm_samples = [45.0, 45.2, 44.8, 45.1, 46.0, 28.0]  # last one is lower than DEM
    dem_samples = [30.0, 30.0, 30.0, 30.0, 30.0, 30.0]

    result = adapter.analyze({
        "dsm_samples": dsm_samples,
        "dem_samples": dem_samples,
        "sensor_type": "Drone_Photogrammetry",
    })

    assert result.status == "DERIVED"
    assert result.data["building_height"] > 0
    assert result.data["base_elevation"] == 30.0
    assert result.evidence["sample_count"] == 6
    # Warning generated for the negative sample
    assert len(result.warnings) == 1
    assert "Negative elevation delta" in result.warnings[0]
    assert result.evidence["negative_samples_count"] == 1


def test_floor_estimator_adapter():
    """Test floor estimation and vertical interval slicing from height."""
    adapter = FloorEstimatorAdapter()
    assert adapter.name == "floor_estimator"

    # 18.0m residential building with default 3.0m/floor -> 6 floors
    result = adapter.analyze({
        "height": 18.0,
        "use_type": "residential",
        "base_elevation": 20.0,
    })

    assert result.status == "INFERRED"  # Never VERIFIED
    assert result.data["floor_count"] == 6
    assert result.data["floor_height"] == 3.0
    assert result.data["z_min"] == 20.0
    assert result.data["z_max"] == 38.0

    levels = result.data["levels"]
    assert len(levels) == 6
    assert levels[0]["floor_seq"] == 1
    assert levels[0]["z_min"] == 20.0
    assert levels[0]["z_max"] == 23.0
    assert levels[5]["floor_seq"] == 6
    assert levels[5]["z_max"] == 38.0

    # Commercial heuristic
    comm_result = adapter.analyze({
        "height": 19.0,
        "use_type": "commercial",  # typical 3.8m
        "base_elevation": 0.0,
    })
    assert comm_result.data["floor_count"] == 5
    assert comm_result.data["floor_height"] == 3.8


def test_pretrained_footprint_adapter_bbox():
    """Test footprint polygon derivation from bounding box."""
    adapter = PretrainedFootprintAdapter()
    assert adapter.name == "pretrained_footprint_extractor"

    result = adapter.analyze({
        "bbox": [77.590, 12.970, 77.592, 12.972],
        "coverage_ratio": 0.60,
    })

    assert result.status == "INFERRED"  # Never VERIFIED
    geom = result.data["geometry"]
    assert geom["type"] == "Polygon"
    assert result.data["vertex_count"] >= 4
    assert result.data["rectangularity"] >= 0.90
    assert result.confidence >= 0.75


def test_pretrained_footprint_adapter_parcel():
    """Test footprint inference inside a parcel polygon with morphological setback."""
    adapter = PretrainedFootprintAdapter()

    parcel_poly = {
        "type": "Polygon",
        "coordinates": [[
            [77.0, 12.0],
            [77.001, 12.0],
            [77.001, 12.001],
            [77.0, 12.001],
            [77.0, 12.0],
        ]]
    }

    result = adapter.analyze({
        "parcel_geometry": parcel_poly,
        "scale_factor": 0.70,
    })

    assert result.status == "INFERRED"
    geom = result.data["geometry"]
    assert geom["type"] == "Polygon"
    assert result.data["approx_area"] > 0


def test_analysis_service_property_pipeline(db_session: Session):
    """Test running the full analysis pipeline on a PropertyObject.
    
    Verifies:
    - Observations created (height, floor_count)
    - Evidence created
    - z_min/z_max updated
    - Status promoted to DERIVED (NOT VERIFIED)
    - ChangeEvent audit log persisted
    """
    service = AnalysisService()

    # Create synthetic test building
    prop = PropertyObject(
        id=uuid.uuid4(),
        three_d_property_id="IN-DL-DEL-0001-001",
        type="building",
        confidence=0.4,
        status="SYNTHETIC",
        attributes={"use_type": "residential"},
    )
    db_session.add(prop)
    db_session.commit()

    # Execute analysis with elevation profile
    elev_data = {"dsm": 45.0, "dem": 30.0, "sensor_type": "LiDAR"}
    output = service.analyze_property(
        db=db_session,
        property_id=prop.id,
        elevation_data=elev_data,
        use_type="residential",
    )

    assert output["property_id"] == str(prop.id)
    assert output["z_min"] == 30.0
    assert output["z_max"] == 45.0
    assert output["status"] == "DERIVED"  # Promoted from SYNTHETIC, but NEVER VERIFIED
    assert output["confidence"] > 0.7

    # Refresh DB entity
    db_session.refresh(prop)
    assert prop.z_min == 30.0
    assert prop.z_max == 45.0
    assert prop.status == "DERIVED"
    assert "analysis" in prop.attributes
    assert prop.attributes["analysis"]["estimated_floors"] == 5  # 15m / 3m = 5 floors

    # Check SourceObservations
    obs = db_session.query(SourceObservation).filter(
        SourceObservation.property_object_id == prop.id
    ).all()
    attr_names = {o.attribute_name for o in obs}
    assert "height" in attr_names
    assert "floor_count" in attr_names

    # Check Evidence
    ev = db_session.query(Evidence).filter(
        Evidence.property_object_id == prop.id
    ).first()
    assert ev is not None
    assert ev.evidence_type == "ai_analysis_run"

    # Check ChangeEvent
    events = db_session.query(ChangeEvent).filter(
        ChangeEvent.property_object_id == prop.id
    ).all()
    assert len(events) >= 1
    assert events[-1].event_type == "height_updated"


def test_verified_property_not_overwritten(db_session: Session):
    """Test that a VERIFIED property retains its VERIFIED status during AI analysis."""
    service = AnalysisService()

    prop = PropertyObject(
        id=uuid.uuid4(),
        three_d_property_id="IN-DL-DEL-0001-002",
        type="building",
        confidence=0.99,
        status="VERIFIED",
        z_min=10.0,
        z_max=25.0,
    )
    db_session.add(prop)
    db_session.commit()

    # Re-run analysis on already-verified property
    output = service.analyze_property(
        db=db_session,
        property_id=prop.id,
        elevation_data={"dsm": 46.0, "dem": 30.0},
    )

    db_session.refresh(prop)
    # Verification authority decision must NOT be demoted or changed by AI
    assert prop.status == "VERIFIED"
    assert output["status"] == "VERIFIED"


def test_api_analysis_endpoints(client):
    """Test HTTP endpoints for AI adapters and on-demand analysis."""
    # 1. GET adapters list
    res_list = client.get("/api/v1/analysis/adapters")
    assert res_list.status_code == 200
    adapters = res_list.json()
    names = [a["name"] for a in adapters]
    assert "dsm_dem_height" in names
    assert "floor_estimator" in names
    assert "pretrained_footprint_extractor" in names

    # 2. POST /api/v1/analysis/dsm-dem-height
    h_res = client.post("/api/v1/analysis/dsm-dem-height", json={
        "dsm": 52.0,
        "dem": 32.0,
        "sensor_type": "Stereo_Satellite",
    })
    assert h_res.status_code == 200
    data = h_res.json()
    assert data["status"] == "DERIVED"
    assert data["data"]["building_height"] == 20.0

    # 3. POST /api/v1/analysis/estimate-floors
    f_res = client.post("/api/v1/analysis/estimate-floors", json={
        "height": 20.0,
        "use_type": "residential",
        "base_elevation": 32.0,
    })
    assert f_res.status_code == 200
    f_data = f_res.json()
    assert f_data["status"] == "INFERRED"
    assert f_data["data"]["floor_count"] == 7  # 20 / 3.0 = 6.67 -> 7 floors

    # 4. POST /api/v1/analysis/extract-footprints
    p_res = client.post("/api/v1/analysis/extract-footprints", json={
        "bbox": [77.10, 12.10, 77.12, 12.12],
        "coverage_ratio": 0.5,
    })
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["status"] == "INFERRED"
    assert p_data["data"]["geometry"]["type"] == "Polygon"
