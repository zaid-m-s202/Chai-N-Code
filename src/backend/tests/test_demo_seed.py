"""Tests for demo seed data execution."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.seeds.seed_demo_data import run_seed, setup_sqlite_mocks
from app.models.user import User
from app.models.property_object import PropertyObject
from app.models.conflict import Conflict
from app.models.property_record import PropertyRecord
from app.models.change_event import ChangeEvent


def test_demo_seed_execution():
    """Verify that run_seed populates all entity hierarchies without error."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", setup_sqlite_mocks)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()

    try:
        summary = run_seed(db=session)
        assert summary["users"] >= 4
        assert summary["properties"] >= 10
        assert summary["conflicts"] >= 2
        assert summary["legal_records"] >= 2
        assert summary["audit_events"] >= 5

        # Verify specific Indian urban pilot properties
        p1 = session.query(PropertyObject).filter(PropertyObject.three_d_property_id == "INMH0234567-B000-F00-U000").first()
        assert p1 is not None
        assert p1.type == "parcel"
        assert p1.attributes["city"] == "Pune"

        # Verify intentional VR-02 conflict
        c = session.query(Conflict).filter(Conflict.rule_code == "VR-02").first()
        assert c is not None
        assert c.status == "OPEN"

        # Verify legal record with encumbrance
        rec = session.query(PropertyRecord).filter(PropertyRecord.three_d_property_id == "INMH0234567-B001-F01-U001").first()
        assert rec is not None
        assert rec.rights_type == "freehold"
        assert len(rec.encumbrances) > 0
        assert rec.encumbrances[0]["type"] == "mortgage"

    finally:
        session.close()
