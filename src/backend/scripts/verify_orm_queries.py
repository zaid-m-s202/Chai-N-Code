import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


from app.database import Base, setup_sqlite_mocks
from app.models.user import User
from app.models.ingestion_job import IngestionJob
from app.models.property_object import PropertyObject
from app.models.property_record import PropertyRecord
from app.models.evidence import Evidence
from app.models.source_observation import SourceObservation
from app.models.conflict import Conflict
from app.models.change_event import ChangeEvent
from app.schemas.properties import PropertyDetail
from app.api.properties import _property_to_detail


def run_orm_verification():
    engine = sa.create_engine("sqlite:///:memory:")
    sa.event.listen(engine, "connect", setup_sqlite_mocks)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Step 1: Create User...")
    user = User(
        id=uuid.uuid4(),
        username="officer_deshmukh",
        password_hash="argon2id$mockhash",
        role="VERIFYING_OFFICER",
    )
    session.add(user)
    session.commit()

    print("Step 2: Create IngestionJob...")
    job = IngestionJob(
        id=uuid.uuid4(),
        filename="pune_zone4_cadastre.geojson",
        format="geojson",
        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status="COMPLETED",
        record_count=100,
        operator_id=user.id,
    )
    session.add(job)
    session.commit()

    print("Step 3: Create Parent Parcel PropertyObject...")
    parcel = PropertyObject(
        id=uuid.uuid4(),
        type="parcel",
        three_d_property_id="MH2701440001",
        ulpin="MH2701440001",
        z_min=0.0,
        z_max=0.0,
        stratum="SURFACE",
        volume_m3=0.0,
        confidence=1.0,
        status="VERIFIED",
        attributes={"khasra_no": "144/1", "village": "Shivajinagar"},
    )
    session.add(parcel)
    session.commit()

    print("Step 4: Create Child Building & 3D Unit PropertyObject...")
    building = PropertyObject(
        id=uuid.uuid4(),
        type="building",
        parent_id=parcel.id,
        three_d_property_id="MH2701440001-B001",
        ulpin="MH2701440001",
        z_min=0.0,
        z_max=36.0,
        stratum="ABOVE_GROUND",
        volume_m3=14400.0,
        confidence=0.95,
        status="VERIFIED",
        attributes={"building_name": "Tower A", "floors": 12},
    )
    session.add(building)
    session.commit()

    unit = PropertyObject(
        id=uuid.uuid4(),
        type="unit",
        parent_id=building.id,
        three_d_property_id="MH2701440001-B001-F04-U402",
        ulpin="MH2701440001",
        z_min=12.0,
        z_max=15.0,
        stratum="ABOVE_GROUND",
        volume_m3=240.0,
        confidence=0.92,
        status="PROVISIONAL",
        attributes={"unit_number": "402", "carpet_area_sqm": 80.0},
    )
    session.add(unit)
    session.commit()

    print("Step 5: Create PropertyRecord linking unit to registry...")
    legal_record = PropertyRecord(
        id=uuid.uuid4(),
        property_object_id=unit.id,
        three_d_property_id=unit.three_d_property_id,
        ulpin=unit.ulpin,
        owner_party_id="PARTY-PR-2026-9921",
        registration_number="HAVELI-PUN-2026-1044",
        rights_type="strata_title",
        encumbrances=[],
        linkage_status="LINKED",
        source_system="MAHA_IGR",
        created_by=user.id,
    )
    session.add(legal_record)
    session.commit()

    print("Step 6: Create Evidence, SourceObservation, Conflict, ChangeEvent...")
    evidence = Evidence(
        id=uuid.uuid4(),
        property_object_id=unit.id,
        evidence_type="survey_bim",
        file_reference="s3://cadastre/bim/tower_a_fl4.ifc",
        file_hash="abc123hash",
        operator_id=user.id,
        ingestion_job_id=job.id,
    )
    session.add(evidence)

    obs = SourceObservation(
        id=uuid.uuid4(),
        property_object_id=unit.id,
        attribute_name="carpet_area_sqm",
        observed_value=80.0,
        source_confidence=0.95,
        ingestion_job_id=job.id,
    )
    session.add(obs)

    conflict = Conflict(
        id=uuid.uuid4(),
        property_object_id=unit.id,
        rule_code="VR-01",
        description="Minor overhang checked against parent bounding volume",
        severity="WARNING",
        status="RESOLVED",
        resolved_by=user.id,
    )
    session.add(conflict)

    change = ChangeEvent(
        id=uuid.uuid4(),
        property_object_id=unit.id,
        event_type="created",
        new_state={"status": "PROVISIONAL", "ulpin": unit.ulpin},
        actor_id=user.id,
        evidence_id=evidence.id,
    )
    session.add(change)
    session.commit()

    print("Step 7: Execute ORM Queries & Filter Checks...")
    # Query 1: Filter by ULPIN
    results_ulpin = session.query(PropertyObject).filter(PropertyObject.ulpin == "MH2701440001").all()
    assert len(results_ulpin) == 3, f"Expected 3 objects for ULPIN, got {len(results_ulpin)}"
    print(f"  [PASS] ULPIN query returned {len(results_ulpin)} hierarchy entities")

    # Query 2: Stratum query
    subterranean_or_above = session.query(PropertyObject).filter(PropertyObject.stratum == "ABOVE_GROUND").all()
    assert len(subterranean_or_above) == 2
    print(f"  [PASS] Stratum query returned {len(subterranean_or_above)} ABOVE_GROUND entities")

    # Query 3: Volume & 3D Property ID query
    unit_obj = session.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == "MH2701440001-B001-F04-U402"
    ).one()
    assert unit_obj.volume_m3 == 240.0
    assert unit_obj.parent_id == building.id
    print(f"  [PASS] Unit volume_m3={unit_obj.volume_m3}, parent_id verified")

    # Query 4: Legal linkage join
    joined_record = session.query(PropertyRecord).filter(
        PropertyRecord.property_object_id == unit_obj.id
    ).one()
    assert joined_record.ulpin == unit_obj.ulpin
    assert joined_record.rights_type == "strata_title"
    print(f"  [PASS] Legal record joined successfully: ULPIN={joined_record.ulpin}")

    # Query 5: Schema detail serialization
    detail = _property_to_detail(unit_obj)
    assert detail.ulpin == "MH2701440001"
    assert detail.stratum == "ABOVE_GROUND"
    assert detail.volume_m3 == 240.0
    print("  [PASS] Schema serialization includes ulpin, stratum, volume_m3")

    session.close()
    print("\n--- ALL ORM QUERIES AND RELATIONSHIPS VERIFIED SUCCESSFULLY ---")


if __name__ == "__main__":
    run_orm_verification()
