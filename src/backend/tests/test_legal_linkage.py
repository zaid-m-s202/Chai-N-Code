"""Tests for Phase 7 Legal Linkage, RBAC, owner identity protection, and audit logging."""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.property_object import PropertyObject
from app.models.property_record import PropertyRecord
from app.models.change_event import ChangeEvent
from app.models.user import User


@pytest.fixture
def test_property(db_session: Session) -> PropertyObject:
    """Create a sample 3D PropertyObject."""
    prop = PropertyObject(
        id=uuid.uuid4(),
        type="building",
        three_d_property_id="IN-KA-BLR-001-001-F01-U001",
        confidence=0.92,
        status="PROVISIONAL",
        attributes={"address": "Plot 42, Brigade Road, Bengaluru"},
    )
    db_session.add(prop)
    db_session.commit()
    db_session.refresh(prop)
    return prop


class TestLegalLinkage:
    """Test suite for Phase 7 legal linkage endpoints and RBAC."""

    def test_officer_can_create_legal_linkage(
        self, client: TestClient, officer_token: str, test_property: PropertyObject, db_session: Session
    ):
        """Verifying officer can link an authoritative property record and trigger audit event."""
        payload = {
            "property_object_id": str(test_property.id),
            "ulpin": "KA123456789012",
            "owner_party_id": "PARTY-IND-KA-2024-9988",
            "registration_number": "REG/BLR/2023/88921",
            "registration_date": "2023-04-15T10:30:00Z",
            "rights_type": "freehold",
            "encumbrances": [
                {
                    "type": "mortgage",
                    "description": "Housing loan charge registered with SBI",
                    "amount": 4500000.0,
                    "beneficiary": "State Bank of India",
                    "status": "ACTIVE",
                }
            ],
            "linkage_status": "LINKED",
            "source_system": "BHOOMI_KAVERI",
        }

        resp = client.post(
            "/api/v1/legal/records",
            json=payload,
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["three_d_property_id"] == test_property.three_d_property_id
        assert data["ulpin"] == "KA123456789012"
        assert data["owner_party_id"] == "PARTY-IND-KA-2024-9988"
        assert data["is_redacted"] is False
        assert len(data["encumbrances"]) == 1

        # Verify audit change event was generated
        events = (
            db_session.query(ChangeEvent)
            .filter(
                ChangeEvent.property_object_id == test_property.id,
                ChangeEvent.event_type == "legal_linked",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].new_state["ulpin"] == "KA123456789012"
        assert events[0].new_state["encumbrance_count"] == 1

    def test_surveyor_cannot_create_legal_linkage(
        self, client: TestClient, surveyor_token: str, test_property: PropertyObject
    ):
        """Field surveyor role is forbidden from creating legal records."""
        payload = {
            "property_object_id": str(test_property.id),
            "ulpin": "KA123456789013",
            "owner_party_id": "PARTY-KA-1122",
            "rights_type": "freehold",
        }
        resp = client.post(
            "/api/v1/legal/records",
            json=payload,
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_legal_linkage(
        self, client: TestClient, test_property: PropertyObject
    ):
        """Unauthenticated request is rejected."""
        payload = {
            "property_object_id": str(test_property.id),
            "ulpin": "KA123456789014",
            "owner_party_id": "PARTY-KA-1122",
            "rights_type": "freehold",
        }
        resp = client.post("/api/v1/legal/records", json=payload)
        assert resp.status_code == 401

    def test_cannot_infer_owner_identity(
        self, client: TestClient, officer_token: str, test_property: PropertyObject
    ):
        """System rejects synthetic, unknown, or AI-inferred owner IDs."""
        for invalid_id in ["unknown", "INFERRED", "ai_inferred", "auto_generated", "  "]:
            payload = {
                "property_object_id": str(test_property.id),
                "ulpin": "KA123456789015",
                "owner_party_id": invalid_id,
                "rights_type": "freehold",
            }
            resp = client.post(
                "/api/v1/legal/records",
                json=payload,
                headers={"Authorization": f"Bearer {officer_token}"},
            )
            assert resp.status_code == 422, f"Failed to reject invalid owner ID: {invalid_id}"

    def test_rbac_redaction_on_read(
        self,
        client: TestClient,
        officer_token: str,
        surveyor_token: str,
        test_property: PropertyObject,
        db_session: Session,
        verifying_officer: User,
    ):
        """Verifying officers see full owner identity; surveyors and public viewers receive redacted views."""
        record = PropertyRecord(
            id=uuid.uuid4(),
            property_object_id=test_property.id,
            three_d_property_id=test_property.three_d_property_id,
            ulpin="KA987654321098",
            owner_party_id="CONFIDENTIAL-OWNER-AADHAAR-TOKEN-991",
            registration_number="REG/KA/9921",
            rights_type="leasehold",
            encumbrances=[],
            linkage_status="LINKED",
            source_system="KAVERI_2",
            created_by=verifying_officer.id,
        )
        db_session.add(record)
        db_session.commit()

        # 1. Verifying Officer request -> Unredacted
        resp_officer = client.get(
            f"/api/v1/legal/records/{record.id}",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_officer.status_code == 200
        data_officer = resp_officer.json()
        assert data_officer["is_redacted"] is False
        assert data_officer["owner_party_id"] == "CONFIDENTIAL-OWNER-AADHAAR-TOKEN-991"

        # 2. Field Surveyor request -> Redacted
        resp_surveyor = client.get(
            f"/api/v1/legal/records/{record.id}",
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp_surveyor.status_code == 200
        data_surveyor = resp_surveyor.json()
        assert data_surveyor["is_redacted"] is True
        assert data_surveyor["owner_party_id"] == "[PROTECTED — OFFICER ACCESS ONLY]"

        # 3. Public / unauthenticated request -> Redacted
        resp_public = client.get(f"/api/v1/legal/records/{record.id}")
        assert resp_public.status_code == 200
        data_public = resp_public.json()
        assert data_public["is_redacted"] is True
        assert data_public["owner_party_id"] == "[PROTECTED — OFFICER ACCESS ONLY]"

    def test_get_legal_records_by_property(
        self,
        client: TestClient,
        officer_token: str,
        surveyor_token: str,
        test_property: PropertyObject,
        db_session: Session,
        verifying_officer: User,
    ):
        """Retrieve legal linkages associated with a spatial property."""
        record = PropertyRecord(
            id=uuid.uuid4(),
            property_object_id=test_property.id,
            three_d_property_id=test_property.three_d_property_id,
            ulpin="KA777788889999",
            owner_party_id="PARTY-SECRET-777",
            rights_type="freehold",
            encumbrances=[{"type": "tax_lien", "description": "Municipal property tax arrears"}],
            linkage_status="DISPUTED",
            created_by=verifying_officer.id,
        )
        db_session.add(record)
        db_session.commit()

        # Officer query by property ID
        resp_officer = client.get(
            f"/api/v1/legal/by-property/{test_property.id}",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_officer.status_code == 200
        items_officer = resp_officer.json()
        assert len(items_officer) == 1
        assert items_officer[0]["owner_party_id"] == "PARTY-SECRET-777"
        assert items_officer[0]["linkage_status"] == "DISPUTED"

        # Surveyor query by property ID
        resp_surveyor = client.get(
            f"/api/v1/legal/by-property/{test_property.id}",
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp_surveyor.status_code == 200
        items_surveyor = resp_surveyor.json()
        assert len(items_surveyor) == 1
        assert items_surveyor[0]["owner_party_id"] == "[PROTECTED — OFFICER ACCESS ONLY]"
        assert items_surveyor[0]["is_redacted"] is True

    def test_officer_can_update_legal_record(
        self,
        client: TestClient,
        officer_token: str,
        surveyor_token: str,
        test_property: PropertyObject,
        db_session: Session,
        verifying_officer: User,
    ):
        """Updating encumbrances or linkage status triggers audit logging and requires officer permissions."""
        record = PropertyRecord(
            id=uuid.uuid4(),
            property_object_id=test_property.id,
            three_d_property_id=test_property.three_d_property_id,
            ulpin="KA444455556666",
            owner_party_id="PARTY-ORIGINAL-44",
            rights_type="leasehold",
            encumbrances=[],
            linkage_status="PENDING",
            created_by=verifying_officer.id,
        )
        db_session.add(record)
        db_session.commit()

        # Surveyor forbidden from updating
        resp_forbidden = client.put(
            f"/api/v1/legal/records/{record.id}",
            json={"linkage_status": "LINKED"},
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp_forbidden.status_code == 403

        # Officer updates status and adds encumbrance
        update_payload = {
            "linkage_status": "LINKED",
            "rights_type": "freehold",
            "encumbrances": [{"type": "easement", "description": "Public right of way access easement"}],
        }
        resp_update = client.put(
            f"/api/v1/legal/records/{record.id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_update.status_code == 200
        data = resp_update.json()
        assert data["linkage_status"] == "LINKED"
        assert data["rights_type"] == "freehold"
        assert len(data["encumbrances"]) == 1

        # Check audit event
        events = (
            db_session.query(ChangeEvent)
            .filter(
                ChangeEvent.property_object_id == test_property.id,
                ChangeEvent.event_type == "legal_updated",
            )
            .all()
        )
        assert len(events) == 1
        assert events[0].old_state["linkage_status"] == "PENDING"
        assert events[0].new_state["linkage_status"] == "LINKED"

    def test_officer_can_unlink_record(
        self,
        client: TestClient,
        officer_token: str,
        test_property: PropertyObject,
        db_session: Session,
        verifying_officer: User,
    ):
        """Unlinking a record sets status to UNLINKED and writes an audit event."""
        record = PropertyRecord(
            id=uuid.uuid4(),
            property_object_id=test_property.id,
            three_d_property_id=test_property.three_d_property_id,
            ulpin="KA000011112222",
            owner_party_id="PARTY-UNLINK-00",
            linkage_status="LINKED",
            created_by=verifying_officer.id,
        )
        db_session.add(record)
        db_session.commit()

        resp = client.delete(
            f"/api/v1/legal/records/{record.id}",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["linkage_status"] == "UNLINKED"

        # Check in DB
        db_session.refresh(record)
        assert record.linkage_status == "UNLINKED"

        # Check audit event
        events = (
            db_session.query(ChangeEvent)
            .filter(
                ChangeEvent.property_object_id == test_property.id,
                ChangeEvent.event_type == "legal_unlinked",
            )
            .all()
        )
        assert len(events) == 1
