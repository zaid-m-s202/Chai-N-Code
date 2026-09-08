"""Tests for ingestion adapters and pipeline execution (PRD §5.1 / Acceptance Criterion 1, 2 / Phase 2)."""

import json
from uuid import uuid4
from app.ingestion.adapters.geojson_adapter import GeoJSONAdapter
from app.ingestion.adapters.csv_adapter import CSVAdapter
from app.ingestion.pipeline import process_ingestion
from app.models.ingestion_job import IngestionJob
from app.models.property_object import PropertyObject
from app.models.evidence import Evidence
from app.models.change_event import ChangeEvent
from app.models.conflict import Conflict
from app.models.source_observation import SourceObservation


def test_geojson_adapter_parsing():
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[77.59, 12.97], [77.60, 12.97], [77.60, 12.98], [77.59, 12.98], [77.59, 12.97]]]
                },
                "properties": {
                    "ulpin": "KA03BLR001",
                    "type": "building",
                    "building_seq": 1,
                    "height": 18.5,
                    "floor_count": 6,
                    "confidence": 0.88,
                }
            }
        ]
    }
    adapter = GeoJSONAdapter()
    records = adapter.parse(json.dumps(sample_geojson).encode("utf-8"), "test.geojson")

    assert len(records) == 1
    assert records[0].ulpin == "KA03BLR001"
    assert records[0].object_type == "building"
    assert records[0].height == 18.5
    assert records[0].floor_count == 6
    assert records[0].source_confidence == 0.88
    assert records[0].geometry is not None


def test_csv_adapter_parsing():
    csv_content = (
        "ulpin,type,building_seq,floor_seq,unit_seq,latitude,longitude,height\n"
        "DL01NDLS01,building,1,0,0,28.6139,77.2090,12.0\n"
        "DL01NDLS01,unit,1,1,101,28.6139,77.2090,3.0\n"
    )
    adapter = CSVAdapter()
    records = adapter.parse(csv_content.encode("utf-8"), "survey.csv")

    assert len(records) == 2
    assert records[0].ulpin == "DL01NDLS01"
    assert records[0].object_type == "building"
    assert records[0].height == 12.0
    assert records[1].unit_seq == 101


def test_pipeline_end_to_end(db_session):
    job = IngestionJob(
        id=uuid4(),
        filename="ward_pilot.geojson",
        format="geojson",
        status="PENDING",
    )
    db_session.add(job)
    db_session.commit()

    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[72.82, 18.92], [72.83, 18.92], [72.83, 18.93], [72.82, 18.93], [72.82, 18.92]]]
                },
                "properties": {
                    "ulpin": "MH01MUM009",
                    "type": "building",
                    "building_seq": 1,
                    "height": 24.0,
                    "confidence": 0.85,
                }
            }
        ]
    }

    processed_job = process_ingestion(
        db=db_session,
        job_id=job.id,
        filename="ward_pilot.geojson",
        file_content=json.dumps(sample_geojson).encode("utf-8"),
        file_format="geojson",
        source_system="drone_survey_2026",
    )

    assert processed_job.status == "COMPLETED"
    assert processed_job.record_count == 1

    # Verify PropertyObject was created
    expected_id = "MH01MUM009-B001-F00-U000"
    prop = db_session.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == expected_id
    ).first()
    assert prop is not None
    assert prop.type == "building"
    # AI/ingested record starts non-verified
    assert prop.status in ("INFERRED", "DERIVED")

    # Verify Evidence provenance is stored (Acceptance Criterion 2)
    evidence = db_session.query(Evidence).filter(
        Evidence.property_object_id == prop.id
    ).first()
    assert evidence is not None
    assert evidence.file_reference == "ward_pilot.geojson"
    assert evidence.source_system == "drone_survey_2026"

    # Verify ChangeEvent history event is created (PRD §5.9)
    event = db_session.query(ChangeEvent).filter(
        ChangeEvent.property_object_id == prop.id,
        ChangeEvent.event_type == "created",
    ).first()
    assert event is not None


def test_conflicting_observations_generate_conflict_and_preserve_raw(db_session):
    """Phase 2 Acceptance: multiple observations create fused values, conflicts generate records, raw preserved."""
    # Ingestion 1: Initial survey with height 20.0m
    job1 = IngestionJob(id=uuid4(), filename="survey1.csv", format="csv", status="PENDING")
    db_session.add(job1)
    db_session.commit()

    csv1 = (
        "ulpin,type,building_seq,floor_seq,unit_seq,height,confidence,source_id\n"
        "KA03CONF01,building,1,0,0,20.0,0.90,DRONE_INITIAL\n"
    )
    process_ingestion(
        db=db_session,
        job_id=job1.id,
        filename="survey1.csv",
        file_content=csv1.encode("utf-8"),
        file_format="csv",
        source_system="drone_initial",
    )

    prop = db_session.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == "KA03CONF01-B001-F00-U000"
    ).first()
    assert prop is not None
    assert prop.attributes["height"] == 20.0

    # Ingestion 2: Conflicting re-survey with height 40.0m (diff = 20.0m > 3.0m threshold)
    job2 = IngestionJob(id=uuid4(), filename="survey2.csv", format="csv", status="PENDING")
    db_session.add(job2)
    db_session.commit()

    csv2 = (
        "ulpin,type,building_seq,floor_seq,unit_seq,height,confidence,source_id\n"
        "KA03CONF01,building,1,0,0,40.0,0.85,FIELD_CONTRADICT\n"
    )
    process_ingestion(
        db=db_session,
        job_id=job2.id,
        filename="survey2.csv",
        file_content=csv2.encode("utf-8"),
        file_format="csv",
        source_system="field_contradict",
    )

    db_session.refresh(prop)
    # Fused value is updated
    assert prop.attributes["height"] != 20.0
    assert prop.attributes["height"] > 20.0

    # Conflict record MUST be created for the property (PRD FR-FUS-03 / VR-08)
    conflict = db_session.query(Conflict).filter(
        Conflict.property_object_id == prop.id,
        Conflict.rule_code == "VR-FUS-01",
        Conflict.status == "OPEN",
    ).first()
    assert conflict is not None
    assert "Contradictory observations detected" in conflict.description

    # Both raw observations MUST be preserved in source_observations (FR-FUS-01, FR-STD-04)
    raw_obs = db_session.query(SourceObservation).filter(
        SourceObservation.property_object_id == prop.id,
        SourceObservation.attribute_name == "height",
    ).all()
    assert len(raw_obs) == 2
    raw_vals = [o.observed_value["value"] for o in raw_obs]
    assert 20.0 in raw_vals
    assert 40.0 in raw_vals


def test_ingest_conflicting_geojson_fixture(db_session):
    """Test ingesting sample_data/conflicting_observations.geojson directly."""
    import pathlib
    fixture_path = pathlib.Path(__file__).parents[3] / "sample_data" / "conflicting_observations.geojson"
    if not fixture_path.exists():
        fixture_path = pathlib.Path("sample_data/conflicting_observations.geojson")
    with open(fixture_path, "rb") as f:
        content = f.read()

    job = IngestionJob(id=uuid4(), filename="conflicting.geojson", format="geojson", status="PENDING")
    db_session.add(job)
    db_session.commit()

    process_ingestion(
        db=db_session,
        job_id=job.id,
        filename="conflicting.geojson",
        file_content=content,
        file_format="geojson",
        source_system="fixture_test",
    )

    prop = db_session.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == "INMH0234999-B001-F00-U000"
    ).first()
    assert prop is not None
    # 18.0m vs 38.0m -> difference 20m > 3m tolerance -> Conflict record created
    conflict = db_session.query(Conflict).filter(
        Conflict.property_object_id == prop.id,
        Conflict.rule_code == "VR-FUS-01",
        Conflict.status == "OPEN",
    ).first()
    assert conflict is not None

    # Raw observations preserved
    observations = db_session.query(SourceObservation).filter(
        SourceObservation.property_object_id == prop.id,
        SourceObservation.attribute_name == "height",
    ).all()
    assert len(observations) == 2

