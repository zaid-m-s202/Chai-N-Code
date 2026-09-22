"""Schema verification script for Deployment Stage 2."""

import sys
import sqlalchemy as sa
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement

def verify(db_url: str = "sqlite:///test_clean_migration.db"):
    engine = sa.create_engine(db_url)
    insp = sa.inspect(engine)
    tables = insp.get_table_names()
    print("Tables in database:", sorted(tables))

    required_tables = [
        "users",
        "ingestion_jobs",
        "property_objects",
        "property_records",
        "source_observations",
        "evidence",
        "conflicts",
        "change_events",
    ]
    for t in required_tables:
        assert t in tables, f"Missing required table: {t}"
    print("[PASS] All 8 required tables exist!")

    po_cols = {c["name"]: str(c["type"]) for c in insp.get_columns("property_objects")}
    print("\nproperty_objects columns:")
    for name, typ in po_cols.items():
        print(f"  - {name}: {typ}")

    expected_po_cols = [
        "id",
        "type",
        "parent_id",
        "three_d_property_id",
        "ulpin",
        "geometry",
        "z_min",
        "z_max",
        "stratum",
        "volume_m3",
        "attributes",
        "confidence",
        "status",
        "superseded_by",
        "source_list",
        "created_at",
    ]
    for col in expected_po_cols:
        assert col in po_cols, f"Missing column in property_objects: {col}"
    print("[PASS] All 16 expected columns present on property_objects!")

    po_idx = {idx["name"]: idx["column_names"] for idx in insp.get_indexes("property_objects")}
    print("\nproperty_objects indexes:")
    for name, cols in po_idx.items():
        print(f"  - {name}: {cols}")

    expected_po_indexes = [
        "ix_property_objects_ulpin",
        "ix_property_objects_type",
        "ix_property_objects_status",
        "ix_property_objects_stratum",
        "ix_property_objects_parent_id",
        "ix_property_objects_superseded_by",
        "ix_property_objects_3d_id",
    ]
    for idx_name in expected_po_indexes:
        assert idx_name in po_idx, f"Missing index on property_objects: {idx_name}"
    print("[PASS] All expected B-Tree indexes present on property_objects!")

    pr_cols = {c["name"]: str(c["type"]) for c in insp.get_columns("property_records")}
    print("\nproperty_records columns:")
    for name, typ in pr_cols.items():
        print(f"  - {name}: {typ}")

    expected_pr_cols = [
        "id",
        "property_object_id",
        "three_d_property_id",
        "ulpin",
        "owner_party_id",
        "registration_number",
        "registration_date",
        "rights_type",
        "encumbrances",
        "linkage_status",
        "source_system",
        "sync_time",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for col in expected_pr_cols:
        assert col in pr_cols, f"Missing column in property_records: {col}"
    print("[PASS] All 15 expected columns present on property_records!")

    pr_idx = {idx["name"]: idx["column_names"] for idx in insp.get_indexes("property_records")}
    print("\nproperty_records indexes:")
    for name, cols in pr_idx.items():
        print(f"  - {name}: {cols}")

    expected_pr_indexes = [
        "ix_property_records_property_object_id",
        "ix_property_records_three_d_property_id",
        "ix_property_records_ulpin",
        "ix_property_records_linkage_status",
        "ix_property_records_created_by",
    ]
    for idx_name in expected_pr_indexes:
        assert idx_name in pr_idx, f"Missing index on property_records: {idx_name}"
    print("[PASS] All expected indexes present on property_records!")

    # Check foreign key indexes on other tables
    ev_idx = {idx["name"] for idx in insp.get_indexes("evidence")}
    for i in ["ix_evidence_property_object_id", "ix_evidence_operator_id", "ix_evidence_ingestion_job_id"]:
        assert i in ev_idx, f"Missing index on evidence: {i}"
    print("[PASS] Evidence foreign key indexes present!")

    obs_idx = {idx["name"] for idx in insp.get_indexes("source_observations")}
    for i in ["ix_source_observations_property_object_id", "ix_source_observations_ingestion_job_id"]:
        assert i in obs_idx, f"Missing index on source_observations: {i}"
    print("[PASS] Source observations foreign key indexes present!")

    conf_idx = {idx["name"] for idx in insp.get_indexes("conflicts")}
    for i in ["ix_conflicts_property_object_id", "ix_conflicts_resolved_by"]:
        assert i in conf_idx, f"Missing index on conflicts: {i}"
    print("[PASS] Conflicts foreign key indexes present!")

    evnt_idx = {idx["name"] for idx in insp.get_indexes("change_events")}
    for i in ["ix_change_events_property_object_id", "ix_change_events_actor_id", "ix_change_events_evidence_id"]:
        assert i in evnt_idx, f"Missing index on change_events: {i}"
    print("[PASS] Change events foreign key indexes present!")

    ing_idx = {idx["name"] for idx in insp.get_indexes("ingestion_jobs")}
    for i in ["ix_ingestion_jobs_operator_id"]:
        assert i in ing_idx, f"Missing index on ingestion_jobs: {i}"
    print("[PASS] Ingestion jobs foreign key indexes present!")

    print("\n--- ALL SCHEMA SPECIFICATIONS VERIFIED ACCORDING TO STAGE 2 REQUIREMENTS ---")


if __name__ == "__main__":
    verify()
