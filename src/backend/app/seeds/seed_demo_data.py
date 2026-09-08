"""Seed script for populating the database with realistic demo cadastral data.

Includes:
- Multi-tier 3D spatial hierarchy (Parcel -> Building -> Floor -> Unit)
- Realistic Indian urban pilot ward properties (Shivaji Nagar, Pune & Koramangala, Bengaluru)
- Mixed property statuses (VERIFIED, PROVISIONAL, DERIVED, INFERRED, SYNTHETIC)
- Preserved raw multi-source observations (Drone LiDAR, DGPS, Architectural CAD)
- Provenance evidence records with cryptographic SHA-256 hashes
- Deliberate topology conflicts (VR-02 unit overlap, VR-04 floor gap) for verification queue triage
- Authoritative land registry records (ULPIN, freehold, strata title, bank mortgages)
- Immutable event-sourced change event logs
- Pre-configured government users for all 4 RBAC roles

Usage:
    python -m app.seeds.seed_demo_data [--db-url sqlite:///cadastral_demo.db]
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_password_hash
from app.models.user import User
from app.models.property_object import PropertyObject
from app.models.source_observation import SourceObservation
from app.models.evidence import Evidence
from app.models.conflict import Conflict
from app.models.change_event import ChangeEvent
from app.models.property_record import PropertyRecord
from app.models.ingestion_job import IngestionJob
from app.database import Base


def setup_sqlite_mocks(dbapi_connection, connection_record):
    """Register mock SpatiaLite functions so GeoAlchemy2 DDL runs cleanly on SQLite."""
    dbapi_connection.create_function("RecoverGeometryColumn", 5, lambda *args: 1)
    dbapi_connection.create_function("DiscardGeometryColumn", 2, lambda *args: 1)
    dbapi_connection.create_function("CreateSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("DisableSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("CheckSpatialIndex", 2, lambda *args: 1)
    dbapi_connection.create_function("InitSpatialMetaData", 0, lambda: 1)
    dbapi_connection.create_function("InitSpatialMetaData", 1, lambda *args: 1)
    def mock_geom_from_ewkt(val):
        if not val:
            return None
        try:
            from shapely import wkt, wkb
            wkt_str = str(val).split(";", 1)[-1]
            geom = wkt.loads(wkt_str)
            return wkb.dumps(geom, hex=True, srid=4326)
        except Exception:
            return val

    dbapi_connection.create_function("GeomFromEWKT", 1, mock_geom_from_ewkt)
    dbapi_connection.create_function("GeomFromWKB", 1, lambda val: val)
    dbapi_connection.create_function("AsEWKB", 1, lambda val: val)


def run_seed(db: Session | None = None, db_url: str | None = None) -> dict:
    """Execute the full demo dataset seeding transaction."""
    close_after = False
    if db is None:
        from app.config import settings
        target_url = db_url or os.environ.get("DATABASE_URL") or settings.DATABASE_URL or "sqlite:///./cadastral_dev.db"
        print(f"[SEED] Target Database: {target_url}")
        engine_kwargs = {}
        if "sqlite" in target_url:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        eng = create_engine(target_url, **engine_kwargs)
        if "sqlite" in target_url:
            event.listen(eng, "connect", setup_sqlite_mocks)
        Base.metadata.create_all(bind=eng)
        sm = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
        db = sm()
        close_after = True

    try:
        print("[SEED] Starting 3D Cadastral Intelligence demo seeding...")

        # -------------------------------------------------------------
        # 1. System Users (RBAC)
        # -------------------------------------------------------------
        user_specs = [
            ("officer_sharma", "VERIFYING_OFFICER", "DemoPass123!"),
            ("surveyor_verma", "FIELD_SURVEYOR", "DemoPass123!"),
            ("citizen_patel", "PUBLIC_VIEWER", "DemoPass123!"),
            ("admin_cadastre", "ADMIN", "DemoPass123!"),
        ]
        created_users = {}
        for username, role, password in user_specs:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(
                    username=username,
                    password_hash=get_password_hash(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.flush()
            created_users[username] = user
        print(f"[SEED] Seeded {len(created_users)} demo users.")

        officer = created_users["officer_sharma"]
        surveyor = created_users["surveyor_verma"]

        # -------------------------------------------------------------
        # 2. Ingestion Jobs (Provenance Baseline)
        # -------------------------------------------------------------
        job1 = db.query(IngestionJob).filter(IngestionJob.filename == "ward_120_pune_drone_survey.geojson").first()
        if not job1:
            job1 = IngestionJob(
                filename="ward_120_pune_drone_survey.geojson",
                format="geojson",
                file_hash="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                status="COMPLETED",
                record_count=18,
                operator_id=surveyor.id,
            )
            db.add(job1)
            db.flush()

        job2 = db.query(IngestionJob).filter(IngestionJob.filename == "ward_120_building_plans.csv").first()
        if not job2:
            job2 = IngestionJob(
                filename="ward_120_building_plans.csv",
                format="csv",
                file_hash="5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
                status="COMPLETED",
                record_count=24,
                operator_id=surveyor.id,
            )
            db.add(job2)
            db.flush()

        # -------------------------------------------------------------
        # 3. Spatial Hierarchy: Ward 120 (Pune) - Parcel 1
        # -------------------------------------------------------------
        p1_id = "INMH0234567-B000-F00-U000"
        p1 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == p1_id).first()
        if not p1:
            p1 = PropertyObject(
                three_d_property_id=p1_id,
                type="parcel",
                parent_id=None,
                confidence=0.98,
                status="VERIFIED",
                attributes={
                    "ulpin": "INMH0234567",
                    "ward": "Ward 120 - Shivaji Nagar",
                    "city": "Pune",
                    "state": "Maharashtra",
                    "area_sqm": 2450.0,
                    "zoning": "Commercial-Mixed",
                    "land_use": "Urban High-Density",
                },
            )
            db.add(p1)
            db.flush()

        b1_id = "INMH0234567-B001-F00-U000"
        b1 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == b1_id).first()
        if not b1:
            b1 = PropertyObject(
                three_d_property_id=b1_id,
                type="building",
                parent_id=p1.id,
                confidence=0.95,
                status="VERIFIED",
                z_min=560.0,
                z_max=588.0,
                attributes={
                    "name": "Kalyani Commercial Apex",
                    "height": 28.0,
                    "floor_count": 8,
                    "structure_type": "RCC Framed",
                    "construction_year": 2021,
                    "ground_elevation": 560.0,
                },
            )
            db.add(b1)
            db.flush()

        f1_id = "INMH0234567-B001-F01-U000"
        f1 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == f1_id).first()
        if not f1:
            f1 = PropertyObject(
                three_d_property_id=f1_id,
                type="floor",
                parent_id=b1.id,
                confidence=0.92,
                status="VERIFIED",
                z_min=560.0,
                z_max=563.5,
                attributes={"floor_index": 1, "floor_label": "Ground Floor", "height": 3.5, "use": "Commercial/Banking"},
            )
            db.add(f1)
            db.flush()

        f2_id = "INMH0234567-B001-F02-U000"
        f2 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == f2_id).first()
        if not f2:
            f2 = PropertyObject(
                three_d_property_id=f2_id,
                type="floor",
                parent_id=b1.id,
                confidence=0.90,
                status="PROVISIONAL",
                z_min=563.5,
                z_max=567.0,
                attributes={"floor_index": 2, "floor_label": "First Floor", "height": 3.5, "use": "IT Offices"},
            )
            db.add(f2)
            db.flush()

        u101_id = "INMH0234567-B001-F01-U001"
        u101 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == u101_id).first()
        if not u101:
            u101 = PropertyObject(
                three_d_property_id=u101_id,
                type="unit",
                parent_id=f1.id,
                confidence=1.0,
                status="VERIFIED",
                z_min=560.0,
                z_max=563.5,
                attributes={"unit_number": "101", "carpet_area_sqm": 240.0, "use": "Bank Branch", "door_no": "101-A"},
            )
            db.add(u101)
            db.flush()

        u102_id = "INMH0234567-B001-F01-U002"
        u102 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == u102_id).first()
        if not u102:
            u102 = PropertyObject(
                three_d_property_id=u102_id,
                type="unit",
                parent_id=f1.id,
                confidence=0.88,
                status="PROVISIONAL",
                z_min=560.0,
                z_max=563.5,
                attributes={"unit_number": "102", "carpet_area_sqm": 195.0, "use": "Retail Pharmacy", "door_no": "101-B"},
            )
            db.add(u102)
            db.flush()

        u201_id = "INMH0234567-B001-F02-U001"
        u201 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == u201_id).first()
        if not u201:
            u201 = PropertyObject(
                three_d_property_id=u201_id,
                type="unit",
                parent_id=f2.id,
                confidence=0.85,
                status="PROVISIONAL",
                z_min=563.5,
                z_max=567.0,
                attributes={"unit_number": "201", "carpet_area_sqm": 310.0, "use": "Tech Workspace"},
            )
            db.add(u201)
            db.flush()

        # Building 2 (with deliberate topology conflicts)
        b2_id = "INMH0234567-B002-F00-U000"
        b2 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == b2_id).first()
        if not b2:
            b2 = PropertyObject(
                three_d_property_id=b2_id,
                type="building",
                parent_id=p1.id,
                confidence=0.78,
                status="PROVISIONAL",
                z_min=560.0,
                z_max=574.0,
                attributes={"name": "Apex Residential Annexe", "height": 14.0, "floor_count": 4, "use": "Residential"},
            )
            db.add(b2)
            db.flush()

        f21_id = "INMH0234567-B002-F01-U000"
        f21 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == f21_id).first()
        if not f21:
            f21 = PropertyObject(
                three_d_property_id=f21_id,
                type="floor",
                parent_id=b2.id,
                confidence=0.80,
                status="PROVISIONAL",
                z_min=560.0,
                z_max=563.0,
                attributes={"floor_index": 1, "floor_label": "Ground Floor"},
            )
            db.add(f21)
            db.flush()

        u2101_id = "INMH0234567-B002-F01-U001"
        u2101 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == u2101_id).first()
        if not u2101:
            u2101 = PropertyObject(
                three_d_property_id=u2101_id,
                type="unit",
                parent_id=f21.id,
                confidence=0.75,
                status="PROVISIONAL",
                z_min=560.0,
                z_max=563.0,
                attributes={"unit_number": "G-01", "carpet_area_sqm": 120.0, "use": "2BHK Residence"},
            )
            db.add(u2101)
            db.flush()

        u2102_id = "INMH0234567-B002-F01-U002"
        u2102 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == u2102_id).first()
        if not u2102:
            u2102 = PropertyObject(
                three_d_property_id=u2102_id,
                type="unit",
                parent_id=f21.id,
                confidence=0.72,
                status="PROVISIONAL",
                z_min=560.0,
                z_max=563.0,
                attributes={"unit_number": "G-02", "carpet_area_sqm": 115.0, "use": "2BHK Residence"},
            )
            db.add(u2102)
            db.flush()

        # -------------------------------------------------------------
        # 4. Bengaluru Pilot - Parcel 2 (AI-derived)
        # -------------------------------------------------------------
        p2_id = "INKA0987654-B000-F00-U000"
        p2 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == p2_id).first()
        if not p2:
            p2 = PropertyObject(
                three_d_property_id=p2_id,
                type="parcel",
                parent_id=None,
                confidence=0.96,
                status="VERIFIED",
                attributes={
                    "ulpin": "INKA0987654",
                    "ward": "Ward 151 - Koramangala",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "area_sqm": 1850.0,
                    "zoning": "Residential-Commercial Mixed",
                },
            )
            db.add(p2)
            db.flush()

        b3_id = "INKA0987654-B001-F00-U000"
        b3 = db.query(PropertyObject).filter(PropertyObject.three_d_property_id == b3_id).first()
        if not b3:
            b3 = PropertyObject(
                three_d_property_id=b3_id,
                type="building",
                parent_id=p2.id,
                confidence=0.71,
                status="DERIVED",
                z_min=920.0,
                z_max=938.5,
                attributes={
                    "name": "Greenview Heights",
                    "height": 18.5,
                    "floor_count": 6,
                    "derivation_algorithm": "dsm_dem_height_adapter_v1",
                    "estimated_by_ai": True,
                },
            )
            db.add(b3)
            db.flush()

        # -------------------------------------------------------------
        # 5. Provenance Evidence Records
        # -------------------------------------------------------------
        ev1 = db.query(Evidence).filter(Evidence.file_hash == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08").first()
        if not ev1:
            ev1 = Evidence(
                property_object_id=b1.id,
                evidence_type="geojson_drone_survey",
                file_reference="s3://cadastre-raw-surveys/pune/ward_120_drone.geojson",
                file_hash="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                original_crs="EPSG:4326",
                original_format="geojson",
                source_system="PUNE_SMART_CITY_DRONE_CELL",
                operator_id=surveyor.id,
                ingestion_job_id=job1.id,
                captured_at=datetime.now(timezone.utc) - timedelta(days=14),
            )
            db.add(ev1)
            db.flush()

        ev2 = db.query(Evidence).filter(Evidence.file_hash == "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8").first()
        if not ev2:
            ev2 = Evidence(
                property_object_id=u101.id,
                evidence_type="architectural_sanctioned_plan",
                file_reference="s3://cadastre-municipal-drawings/pune/sanctioned_apex_tower.pdf",
                file_hash="5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
                original_crs="LOCAL_SURVEY_COORDS",
                original_format="csv",
                source_system="PMC_BUILDING_PERMISSION_DEPT",
                operator_id=surveyor.id,
                ingestion_job_id=job2.id,
                captured_at=datetime.now(timezone.utc) - timedelta(days=45),
            )
            db.add(ev2)
            db.flush()

        # -------------------------------------------------------------
        # 6. Preserved Raw Source Observations (Append-Only)
        # -------------------------------------------------------------
        obs_specs = [
            (b1.id, "height", 28.0, 0.95, "PUNE_DRONE_LIDAR_2026", job1.id),
            (b1.id, "height", 27.8, 0.90, "PMC_SANCTIONED_PLAN_ARCH_2021", job2.id),
            (b1.id, "floor_count", 8, 0.98, "FIELD_SURVEYOR_DGPS_RECORD", job1.id),
            (u101.id, "carpet_area_sqm", 240.0, 0.99, "ARCHITECT_MEASURED_AS_BUILT", job2.id),
            (b2.id, "height", 14.0, 0.85, "PUNE_DRONE_SURVEY_2026", job1.id),
            (b3.id, "height", 18.5, 0.72, "AI_DSM_DEM_ANALYSIS_RUN", None),
        ]
        for pobj_id, attr_name, val, conf, src_id, jid in obs_specs:
            obs = db.query(SourceObservation).filter(
                SourceObservation.property_object_id == pobj_id,
                SourceObservation.attribute_name == attr_name,
                SourceObservation.source_id == src_id,
            ).first()
            if not obs:
                obs = SourceObservation(
                    property_object_id=pobj_id,
                    attribute_name=attr_name,
                    observed_value=val,
                    source_confidence=conf,
                    source_id=src_id,
                    ingestion_job_id=jid,
                    observed_at=datetime.now(timezone.utc) - timedelta(days=10),
                )
                db.add(obs)
        db.flush()

        # -------------------------------------------------------------
        # 7. Topology Conflicts (Deliberate for Officer Triage & VR-09 Demo)
        # -------------------------------------------------------------
        c1 = db.query(Conflict).filter(
            Conflict.property_object_id == u2101.id,
            Conflict.rule_code == "VR-02",
        ).first()
        if not c1:
            c1 = Conflict(
                property_object_id=u2101.id,
                rule_code="VR-02",
                severity="ERROR",
                status="OPEN",
                description=(
                    "VR-02 Unit Overlap: Unit G-01 overlaps by 14.2% with Unit G-02 "
                    "on Floor G of Apex Residential Annexe (INMH0234567-B002-F01-U001 vs U002)."
                ),
            )
            db.add(c1)

        c2 = db.query(Conflict).filter(
            Conflict.property_object_id == b2.id,
            Conflict.rule_code == "VR-04",
        ).first()
        if not c2:
            c2 = Conflict(
                property_object_id=b2.id,
                rule_code="VR-04",
                severity="WARNING",
                status="OPEN",
                description=(
                    "VR-04 Vertical Gap: Elevation gap of 0.8m detected between "
                    "Floor 1 top (563.0m) and Floor 2 base (563.8m)."
                ),
            )
            db.add(c2)

        c3 = db.query(Conflict).filter(
            Conflict.property_object_id == b1.id,
            Conflict.rule_code == "VR-01",
        ).first()
        if not c3:
            c3 = Conflict(
                property_object_id=b1.id,
                rule_code="VR-01",
                severity="ERROR",
                status="RESOLVED",
                description="VR-01: Boundary overhang of 0.12m on North corner resolved after re-survey.",
                resolved_at=datetime.now(timezone.utc) - timedelta(days=5),
                resolved_by=officer.id,
            )
            db.add(c3)
        db.flush()

        # -------------------------------------------------------------
        # 8. Legal & Land Registry Linkage (Phase 7 Schema)
        # -------------------------------------------------------------
        lr1 = db.query(PropertyRecord).filter(PropertyRecord.three_d_property_id == u101_id).first()
        if not lr1:
            lr1 = PropertyRecord(
                property_object_id=u101.id,
                three_d_property_id=u101_id,
                ulpin="INMH0234567",
                owner_party_id="IN-MAH-REG-2021-998812-P",
                registration_number="MH-PUN-HAV-2021/008892",
                registration_date=datetime(2021, 6, 18, 11, 30, tzinfo=timezone.utc),
                rights_type="freehold",
                encumbrances=[
                    {
                        "type": "mortgage",
                        "institution": "State Bank of India (Commercial Branch)",
                        "amount_inr": 25000000,
                        "charge_id": "SBI-CHG-2021-00441",
                        "status": "ACTIVE",
                    }
                ],
                linkage_status="LINKED",
                source_system="MAHARASHTRA_IGR_DEED_REGISTRY",
                created_by=officer.id,
            )
            db.add(lr1)

        lr2 = db.query(PropertyRecord).filter(PropertyRecord.three_d_property_id == u102_id).first()
        if not lr2:
            lr2 = PropertyRecord(
                property_object_id=u102.id,
                three_d_property_id=u102_id,
                ulpin="INMH0234567",
                owner_party_id="IN-MAH-REG-2022-774431-S",
                registration_number="MH-PUN-HAV-2022/014521",
                registration_date=datetime(2022, 11, 4, 14, 15, tzinfo=timezone.utc),
                rights_type="strata_title",
                encumbrances=[],
                linkage_status="LINKED",
                source_system="MAHARASHTRA_IGR_DEED_REGISTRY",
                created_by=officer.id,
            )
            db.add(lr2)

        lr3 = db.query(PropertyRecord).filter(PropertyRecord.three_d_property_id == b3_id).first()
        if not lr3:
            lr3 = PropertyRecord(
                property_object_id=b3.id,
                three_d_property_id=b3_id,
                ulpin="INKA0987654",
                owner_party_id="IN-KAR-REG-2024-331190-C",
                registration_number="KA-BLR-KOR-2024/003412",
                registration_date=datetime(2024, 1, 12, 10, 0, tzinfo=timezone.utc),
                rights_type="leasehold",
                encumbrances=[
                    {
                        "type": "municipal_tax_lien",
                        "amount_inr": 48200,
                        "issuing_authority": "BBMP Revenue Cell",
                        "status": "PENDING_REMEDY",
                    }
                ],
                linkage_status="PENDING",
                source_system="KARNATAKA_KAVERI_2_PORTAL",
                created_by=officer.id,
            )
            db.add(lr3)
        db.flush()

        # -------------------------------------------------------------
        # 9. Immutable ChangeEvent Audit Log
        # -------------------------------------------------------------
        events_specs = [
            (p1.id, "created", None, {"status": "SYNTHETIC", "type": "parcel"}, surveyor.id, ev1.id),
            (p1.id, "verified", {"status": "PROVISIONAL"}, {"status": "VERIFIED"}, officer.id, None),
            (b1.id, "created", None, {"status": "SYNTHETIC", "type": "building"}, surveyor.id, ev1.id),
            (b1.id, "height_updated", {"height": 27.8}, {"height": 28.0}, surveyor.id, ev1.id),
            (b1.id, "verified", {"status": "PROVISIONAL"}, {"status": "VERIFIED"}, officer.id, None),
            (u101.id, "created", None, {"status": "PROVISIONAL", "type": "unit"}, surveyor.id, ev2.id),
            (u101.id, "verified", {"status": "PROVISIONAL"}, {"status": "VERIFIED"}, officer.id, None),
            (u101.id, "legal_linked", None, {"ulpin": "INMH0234567", "rights_type": "freehold"}, officer.id, None),
            (u2101.id, "created", None, {"status": "PROVISIONAL", "type": "unit"}, surveyor.id, ev1.id),
            (b3.id, "created", None, {"status": "DERIVED", "type": "building"}, surveyor.id, None),
            (b3.id, "legal_linked", None, {"ulpin": "INKA0987654", "linkage_status": "PENDING"}, officer.id, None),
        ]
        for pobj_id, etype, old_s, new_s, act_id, evid in events_specs:
            evt = ChangeEvent(
                property_object_id=pobj_id,
                event_type=etype,
                old_state=old_s,
                new_state=new_s,
                actor_id=act_id,
                evidence_id=evid,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
            db.add(evt)

        db.commit()
        print("[SEED] Successfully completed 3D Cadastral Intelligence demo seeding!")

        summary = {
            "users": db.query(User).count(),
            "properties": db.query(PropertyObject).count(),
            "observations": db.query(SourceObservation).count(),
            "evidence": db.query(Evidence).count(),
            "conflicts": db.query(Conflict).count(),
            "legal_records": db.query(PropertyRecord).count(),
            "audit_events": db.query(ChangeEvent).count(),
        }
        print(f"[SEED] Summary: {summary}")
        return summary

    except Exception as exc:
        db.rollback()
        print(f"[SEED ERROR] Seeding failed: {exc}", file=sys.stderr)
        raise
    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo cadastral data.")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL")
    args = parser.parse_args()
    run_seed(db_url=args.db_url)
