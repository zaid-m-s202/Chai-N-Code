"""Production Hardening, Security, Metrics, Audit Review, Export & Version Compatibility Tests (Phase 8)."""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.property_object import PropertyObject
from app.models.property_record import PropertyRecord
from app.models.change_event import ChangeEvent
from app.models.user import User
from app.middleware import RateLimiter
from app.services.id_generator import make_3d_property_id, parse_3d_property_id
from app.schemas.properties import PropertyDetail, PropertySummary
from app.schemas.legal import PropertyRecordResponse, PropertyRecordRedactedResponse


@pytest.fixture
def sample_hardened_property(db_session: Session) -> PropertyObject:
    """Create a sample property object for export and audit testing."""
    prop = PropertyObject(
        id=uuid.uuid4(),
        type="unit",
        three_d_property_id="IN-DL-NDLS-001-002-F03-U004",
        confidence=0.95,
        status="VERIFIED",
        z_min=9.0,
        z_max=12.0,
        attributes={"address": "Unit 304, Connaught Place, New Delhi", "carpet_area_sqm": 85.5},
    )
    db_session.add(prop)
    db_session.commit()
    db_session.refresh(prop)
    return prop


@pytest.fixture
def sample_hardened_legal_record(
    db_session: Session, sample_hardened_property: PropertyObject, verifying_officer: User
) -> PropertyRecord:
    """Create a sample legal record for PII export tests."""
    rec = PropertyRecord(
        id=uuid.uuid4(),
        property_object_id=sample_hardened_property.id,
        three_d_property_id=sample_hardened_property.three_d_property_id,
        ulpin="DL123456789099",
        owner_party_id="CONFIDENTIAL-OWNER-DL-2024",
        registration_number="REG/NDLS/2024/111",
        rights_type="freehold",
        encumbrances=[],
        linkage_status="LINKED",
        source_system="DHARANI_DELHI",
        created_by=verifying_officer.id,
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


class TestProductionHardening:
    """Test suite for Phase 8 Production Hardening requirements."""

    def test_security_headers_present(self, client: TestClient):
        """Verify OWASP-compliant security headers are injected in all responses."""
        resp = client.get("/health")
        assert resp.status_code == 200
        headers = resp.headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-XSS-Protection") == "1; mode=block"
        assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")
        assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert headers.get("X-Request-ID") is not None

    def test_metrics_prometheus_and_json(self, client: TestClient):
        """Verify telemetry metrics endpoints (/metrics) in Prometheus and JSON formats."""
        # 1. Prometheus format
        resp_prom = client.get("/metrics")
        assert resp_prom.status_code == 200
        assert "text/plain" in resp_prom.headers.get("content-type", "")
        body = resp_prom.text
        assert "cadastre_uptime_seconds" in body
        assert "cadastre_http_requests_total" in body
        assert "cadastre_properties_count" in body

        # 2. JSON format
        resp_json = client.get("/metrics?format=json")
        assert resp_json.status_code == 200
        data = resp_json.json()
        assert "uptime_seconds" in data
        assert "database_entities" in data
        assert "properties_by_status" in data["database_entities"]

    def test_rate_limiter_unit(self):
        """Test RateLimiter sliding window unit logic."""
        limiter = RateLimiter(requests_per_minute=2)
        mock_request = Request(scope={"type": "http", "client": ("192.168.1.100", 12345)})

        assert limiter.check(mock_request) is True
        assert limiter.check(mock_request) is True
        assert limiter.check(mock_request) is False  # Exceeded 2 RPM limit

    def test_audit_log_review_api(
        self,
        client: TestClient,
        officer_token: str,
        surveyor_token: str,
        sample_hardened_property: PropertyObject,
        verifying_officer: User,
        db_session: Session,
    ):
        """Test audit events query and summary aggregation API."""
        # Seed an audit event
        event = ChangeEvent(
            id=uuid.uuid4(),
            property_object_id=sample_hardened_property.id,
            event_type="verified",
            old_state={"status": "PROVISIONAL"},
            new_state={"status": "VERIFIED"},
            actor_id=verifying_officer.id,
        )
        db_session.add(event)
        db_session.commit()

        # Surveyor cannot review audit logs (403)
        resp_surveyor = client.get(
            "/api/v1/audit/events",
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp_surveyor.status_code == 403

        # Officer can review audit logs
        resp_officer = client.get(
            f"/api/v1/audit/events?property_id={sample_hardened_property.id}",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_officer.status_code == 200
        events_data = resp_officer.json()
        assert len(events_data) >= 1
        assert events_data[0]["event_type"] == "verified"

        # Officer summary endpoint
        resp_summary = client.get(
            "/api/v1/audit/summary",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_summary.status_code == 200
        summary_data = resp_summary.json()
        assert summary_data["total_audit_events"] >= 1
        assert "verified" in summary_data["event_distribution"]

    def test_data_export_pii_redaction_default(
        self,
        client: TestClient,
        sample_hardened_property: PropertyObject,
        sample_hardened_legal_record: PropertyRecord,
    ):
        """Exporting cadastral data redacts PII by default for public/surveyors."""
        resp = client.get("/api/v1/export/cadastral?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["pii_redacted"] is True
        assert len(data["records"]) >= 1

        matched = next(
            (r for r in data["records"] if r["three_d_property_id"] == sample_hardened_property.three_d_property_id),
            None,
        )
        assert matched is not None
        assert matched["owner_party_id"] == "[REDACTED]"
        assert matched["ulpin"] == "DL123456789099"

    def test_data_export_unmasked_pii_requires_officer_and_reason(
        self,
        client: TestClient,
        officer_token: str,
        surveyor_token: str,
        sample_hardened_property: PropertyObject,
        sample_hardened_legal_record: PropertyRecord,
        db_session: Session,
    ):
        """Unmasked PII export requires officer role, valid reason, and writes an audit event."""
        # 1. Non-officer attempts include_pii=true -> 403
        resp_forbidden = client.get(
            "/api/v1/export/cadastral?include_pii=true&reason=SurveyAudit",
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp_forbidden.status_code == 403

        # 2. Officer attempts include_pii=true without reason -> 400
        resp_no_reason = client.get(
            "/api/v1/export/cadastral?include_pii=true",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_no_reason.status_code == 400

        # 3. Officer attempts with valid reason -> 200 unmasked
        resp_unmasked = client.get(
            "/api/v1/export/cadastral?include_pii=true&reason=JudicialOrderCivilCourtCase991",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp_unmasked.status_code == 200
        data = resp_unmasked.json()
        assert data["metadata"]["pii_redacted"] is False

        matched = next(
            (r for r in data["records"] if r["three_d_property_id"] == sample_hardened_property.three_d_property_id),
            None,
        )
        assert matched is not None
        assert matched["owner_party_id"] == "CONFIDENTIAL-OWNER-DL-2024"

        # 4. Verify audit event was logged for PII export
        pii_events = (
            db_session.query(ChangeEvent)
            .filter(ChangeEvent.event_type == "pii_exported")
            .all()
        )
        assert len(pii_events) >= 1
        assert pii_events[0].new_state["reason"] == "JudicialOrderCivilCourtCase991"

    def test_export_csv_format(self, client: TestClient, sample_hardened_property: PropertyObject):
        """Export in CSV format returns valid text/csv content."""
        resp = client.get("/api/v1/export/cadastral?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "three_d_property_id,type,status" in resp.text

    def test_export_geojson_format(self, client: TestClient, sample_hardened_property: PropertyObject):
        """Export in GeoJSON format returns valid FeatureCollection."""
        resp = client.get("/api/v1/export/geojson")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert "metadata" in data


class TestSchemaVersionCompatibility:
    """Verify backward compatibility and schema stability across versions."""

    def test_3d_property_id_spec_stability(self):
        """Verify 3D Property ID generation format conforms to immutable PRD pattern."""
        pid = make_3d_property_id(
            ulpin="KA0123456789",
            building_seq=1,
            floor_seq=3,
            unit_seq=12,
        )
        assert pid == "KA0123456789-B001-F03-U012"

        # Test parsing backward compatibility
        parsed = parse_3d_property_id(pid)
        assert parsed["ulpin"] == "KA0123456789"
        assert parsed["building_seq"] == 1
        assert parsed["floor_seq"] == 3
        assert parsed["unit_seq"] == 12

    def test_property_detail_schema_backward_compatibility(self):
        """Verify PropertyDetail handles missing optional fields and extra attribute bag entries cleanly."""
        raw_data = {
            "id": uuid.uuid4(),
            "three_d_property_id": "IN-MH-PUN-001-001-F01-U001",
            "type": "unit",
            "confidence": 0.85,
            "status": "PROVISIONAL",
            "created_at": datetime.now(timezone.utc),
            # Legacy or future extended attributes in attribute bag
            "attributes": {
                "legacy_tax_code": "TX-1998",
                "future_smart_meter_id": "MTR-2030-88",
            },
        }
        detail = PropertyDetail.model_validate(raw_data)
        assert detail.confidence == 0.85
        assert detail.attributes["legacy_tax_code"] == "TX-1998"
        assert detail.parent_id is None
        assert detail.z_min is None

    def test_legal_redacted_schema_contract(self):
        """Verify PropertyRecordRedactedResponse guarantees owner identity is shielded."""
        raw_legal = {
            "id": uuid.uuid4(),
            "property_object_id": uuid.uuid4(),
            "three_d_property_id": "IN-KA-BLR-001-001-F01-U001",
            "ulpin": "KA123456789012",
            "rights_type": "freehold",
            "encumbrances": [],
            "linkage_status": "LINKED",
            "source_system": "BHOOMI",
            "sync_time": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        redacted = PropertyRecordRedactedResponse.model_validate(raw_legal)
        assert redacted.is_redacted is True
        assert "[PROTECTED" in redacted.owner_party_id
