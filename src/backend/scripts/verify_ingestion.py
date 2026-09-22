"""Verification script for Pune dataset ingestion."""

import os
import sys
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import setup_sqlite_mocks
from app.models.property_object import PropertyObject
from app.models.ingestion_job import IngestionJob
from app.models.evidence import Evidence


def verify_ingestion_results(db_url: str = "sqlite:///pune_cadastral.db"):
    engine = sa.create_engine(db_url)
    sa.event.listen(engine, "connect", setup_sqlite_mocks)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("=" * 70)
    print("DETAILED INGESTION AUDIT VERIFICATION")
    print("=" * 70)

    # 1. Ingestion Jobs
    jobs = session.query(IngestionJob).all()
    print(f"\n1. Ingestion Jobs Created: {len(jobs)}")
    for j in jobs:
        print(f"   - {j.filename}: status={j.status}, count={j.record_count}, hash={j.file_hash[:12]}...")
        assert j.status == "COMPLETED"
        assert j.record_count > 0

    # 2. Evidence Records
    evidence = session.query(Evidence).all()
    print(f"\n2. Evidence Provenance Records: {len(evidence)}")
    for e in evidence:
        print(f"   - {e.evidence_type} [{e.source_system}]: file={os.path.basename(e.file_reference or '')}")
        assert e.original_crs == "EPSG:4326"

    # 3. Counts & Hierarchy
    total_bldgs = session.query(PropertyObject).filter(PropertyObject.type == "building").count()
    total_units = session.query(PropertyObject).filter(PropertyObject.type == "unit").count()
    total_ug = session.query(PropertyObject).filter(
        PropertyObject.type.in_(["tunnel", "underground_utility", "subsurface_parcel", "parking_basement"])
    ).count()

    print(f"\n3. Core Entity Counts:")
    print(f"   - Buildings:   {total_bldgs} (Expected: 3,958)")
    print(f"   - 3D Units:    {total_units} (Expected: 42,952)")
    print(f"   - Underground: {total_ug} (Expected: 7)")
    assert total_bldgs == 3958
    assert total_units == 42952
    assert total_ug == 7

    # 4. Orphan Check
    orphans = session.query(PropertyObject).filter(
        PropertyObject.type == "unit",
        PropertyObject.parent_id.is_(None)
    ).count()
    print(f"\n4. Orphan Unit Check:")
    print(f"   - Orphan Units: {orphans} (Must be: 0)")
    assert orphans == 0

    # 5. Parent-Child Relationship Integrity
    sample_unit = session.query(PropertyObject).filter(PropertyObject.type == "unit").first()
    assert sample_unit is not None
    assert sample_unit.parent_id is not None
    parent_bldg = session.query(PropertyObject).filter(PropertyObject.id == sample_unit.parent_id).first()
    assert parent_bldg is not None
    assert parent_bldg.type == "building"

    print(f"\n5. Sample Parent-Child Linkage Verified:")
    print(f"   - Unit ID:       {sample_unit.three_d_property_id}")
    print(f"   - Unit ULPIN:    {sample_unit.ulpin}")
    print(f"   - Unit Stratum:  {sample_unit.stratum}")
    print(f"   - Unit Vol (m³): {sample_unit.volume_m3}")
    print(f"   - Unit Status:   {sample_unit.status}")
    print(f"   - Parent Bldg:   {parent_bldg.three_d_property_id} ({parent_bldg.attributes.get('name') or 'Unnamed'})")
    print(f"   - Bldg ULPIN:    {parent_bldg.ulpin}")
    assert sample_unit.ulpin == parent_bldg.ulpin

    # 6. Underground Infrastructure Check
    ug_sample = session.query(PropertyObject).filter(PropertyObject.type == "tunnel").first()
    assert ug_sample is not None
    print(f"\n6. Sample Underground Asset Verified:")
    print(f"   - Asset ID:      {ug_sample.three_d_property_id}")
    print(f"   - Asset Type:    {ug_sample.type}")
    print(f"   - Asset Stratum: {ug_sample.stratum}")
    print(f"   - Asset Vol(m³): {ug_sample.volume_m3}")
    print(f"   - Asset Z Range: [{ug_sample.z_min}, {ug_sample.z_max}]")
    assert ug_sample.stratum == "SUBTERRANEAN"
    assert ug_sample.z_min < 0

    # 7. ULPIN Coverage
    bldgs_with_ulpin = session.query(PropertyObject).filter(
        PropertyObject.type == "building",
        PropertyObject.ulpin.is_not(None)
    ).count()
    units_with_ulpin = session.query(PropertyObject).filter(
        PropertyObject.type == "unit",
        PropertyObject.ulpin.is_not(None)
    ).count()
    print(f"\n7. ULPIN Coverage:")
    print(f"   - Buildings: {bldgs_with_ulpin}/{total_bldgs} ({bldgs_with_ulpin/total_bldgs*100:.1f}%)")
    print(f"   - Units:     {units_with_ulpin}/{total_units} ({units_with_ulpin/total_units*100:.1f}%)")
    assert bldgs_with_ulpin == 3958
    assert units_with_ulpin == 42952

    session.close()
    print("\n--- ALL VERIFICATION AUDIT ASSERTIONS PASSED WITH 100% INTEGRITY ---")


if __name__ == "__main__":
    verify_ingestion_results()
