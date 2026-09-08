"""Tests for Phase 4 — Deterministic topology validation rules.

Covers:
  VR-01 / VR-05: Building containment inside parcel
  VR-02: Unit overlap on same floor
  VR-03: Gap detection between units
  VR-04: Vertical overlap between floors
  VR-06: Near-duplicate geometry detection
  VR-07: Orphan detection
  VR-08: Failed validation creates Conflict records
  VR-09: Conflicts block VERIFIED status (integration)
"""

import pytest
from shapely.geometry import box, Polygon

from app.services.validation import (
    containment_ok,
    check_containment,
    check_boundary_violation,
    check_unit_overlap,
    check_floor_gap,
    check_vertical_overlap,
    check_near_duplicate,
    check_orphan,
    overlap_ratio,
)


# ---- VR-01 / VR-05: Containment and Boundary Violation ----

class TestBoundaryViolation:
    def test_building_inside_parcel_has_no_violation(self):
        parcel = box(0, 0, 100, 100)
        building = box(10, 10, 50, 50)
        passed, detail = check_boundary_violation(building, parcel, "B001", "P001")
        assert passed is True
        assert detail == ""

    def test_building_protruding_violates_boundary(self):
        parcel = box(0, 0, 100, 100)
        building = box(80, 80, 120, 120)
        passed, detail = check_boundary_violation(building, parcel, "B001", "P001")
        assert passed is False
        assert "VR-05" in detail
        assert "protrudes beyond" in detail

class TestContainment:
    def test_building_inside_parcel_passes(self):
        parcel = box(0, 0, 100, 100)
        building = box(10, 10, 50, 50)
        assert containment_ok(building, parcel) is True

    def test_building_protruding_fails(self):
        parcel = box(0, 0, 100, 100)
        building = box(80, 80, 120, 120)  # extends beyond parcel
        assert containment_ok(building, parcel) is False

    def test_containment_with_tolerance_passes(self):
        parcel = box(0, 0, 100, 100)
        building = box(-1, -1, 50, 50)  # slightly outside
        assert containment_ok(building, parcel, tolerance=2.0) is True

    def test_check_containment_returns_detail_on_failure(self):
        parcel = box(0, 0, 100, 100)
        building = box(80, 80, 120, 120)
        passed, detail = check_containment(building, parcel, "B001", "P001")
        assert passed is False
        assert "VR-01" in detail
        assert "B001" in detail
        assert "P001" in detail

    def test_check_containment_passes_cleanly(self):
        parcel = box(0, 0, 100, 100)
        building = box(10, 10, 50, 50)
        passed, detail = check_containment(building, parcel, "B001", "P001")
        assert passed is True
        assert detail == ""


# ---- VR-02: Unit overlap ----

class TestUnitOverlap:
    def test_non_overlapping_units_pass(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(20, 20, 30, 30)
        passed, detail = check_unit_overlap(unit_a, unit_b, "U001", "U002")
        assert passed is True

    def test_overlapping_units_fail(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(5, 5, 15, 15)  # significant overlap
        passed, detail = check_unit_overlap(unit_a, unit_b, "U001", "U002")
        assert passed is False
        assert "VR-02" in detail
        assert "U001" in detail
        assert "U002" in detail

    def test_identical_units_fail(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(0, 0, 10, 10)
        passed, detail = check_unit_overlap(unit_a, unit_b, "U001", "U002")
        assert passed is False

    def test_touching_units_pass(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(10, 0, 20, 10)  # adjacent, touching edge
        passed, detail = check_unit_overlap(unit_a, unit_b, "U001", "U002")
        assert passed is True

    def test_overlap_ratio_computation(self):
        a = box(0, 0, 10, 10)
        b = box(0, 0, 10, 10)
        assert overlap_ratio(a, b) == pytest.approx(1.0)

        c = box(100, 100, 110, 110)
        assert overlap_ratio(a, c) == pytest.approx(0.0)


# ---- VR-03: Gap detection ----

class TestFloorGap:
    def test_contiguous_units_no_gap(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(10, 0, 20, 10)
        passed, detail = check_floor_gap([unit_a, unit_b], None, "F01")
        assert passed is True

    def test_disjoint_units_create_gap(self):
        unit_a = box(0, 0, 10, 10)
        unit_b = box(50, 50, 60, 60)
        passed, detail = check_floor_gap([unit_a, unit_b], None, "F01")
        assert passed is False
        assert "VR-03" in detail

    def test_single_unit_no_gap_check(self):
        unit_a = box(0, 0, 10, 10)
        passed, detail = check_floor_gap([unit_a], None, "F01")
        assert passed is True

    def test_gap_with_floor_geometry(self):
        floor_geom = box(0, 0, 100, 100)
        unit_a = box(0, 0, 10, 10)  # tiny unit in big floor
        unit_b = box(90, 90, 100, 100)
        passed, detail = check_floor_gap([unit_a, unit_b], floor_geom, "F01")
        assert passed is False
        assert "uncovered" in detail.lower() or "VR-03" in detail


# ---- VR-04: Vertical overlap ----

class TestVerticalOverlap:
    def test_non_overlapping_floors(self):
        passed, detail = check_vertical_overlap(0.0, 3.0, 3.0, 6.0, "F01", "F02")
        assert passed is True

    def test_overlapping_floors(self):
        passed, detail = check_vertical_overlap(0.0, 3.5, 3.0, 6.0, "F01", "F02")
        assert passed is False
        assert "VR-04" in detail
        assert "F01" in detail
        assert "F02" in detail

    def test_identical_floor_extents_overlap(self):
        passed, detail = check_vertical_overlap(0.0, 3.0, 0.0, 3.0, "F01", "F02")
        assert passed is False

    def test_tiny_overlap_within_tolerance(self):
        passed, detail = check_vertical_overlap(0.0, 3.0, 2.995, 6.0, "F01", "F02", tolerance=0.01)
        assert passed is True

    def test_separated_floors_pass(self):
        passed, detail = check_vertical_overlap(0.0, 3.0, 6.0, 9.0, "F01", "F02")
        assert passed is True


# ---- VR-06: Near-duplicate detection ----

class TestNearDuplicate:
    def test_identical_geometries_are_duplicates(self):
        geom = box(0, 0, 10, 10)
        passed, detail = check_near_duplicate(geom, geom, "A", "B")
        assert passed is False
        assert "VR-06" in detail

    def test_different_geometries_pass(self):
        geom_a = box(0, 0, 10, 10)
        geom_b = box(100, 100, 200, 200)
        passed, detail = check_near_duplicate(geom_a, geom_b, "A", "B")
        assert passed is True

    def test_similar_but_shifted_geometries(self):
        geom_a = box(0, 0, 10, 10)
        geom_b = box(0.1, 0.1, 10.1, 10.1)  # very slight shift
        passed, detail = check_near_duplicate(
            geom_a, geom_b, "A", "B",
            hausdorff_threshold=0.5,
            area_ratio_threshold=0.95,
        )
        assert passed is False  # close enough to be a near-duplicate

    def test_empty_geometry_passes(self):
        from shapely.geometry import Point
        empty = Point()  # empty geometry
        geom = box(0, 0, 10, 10)
        passed, _ = check_near_duplicate(empty, geom, "A", "B")
        assert passed is True


# ---- VR-07: Orphan detection ----

class TestOrphanDetection:
    def test_parcel_is_never_orphan(self):
        passed, _ = check_orphan("parcel", None, "P001")
        assert passed is True

    def test_building_without_parent_is_orphan(self):
        passed, detail = check_orphan("building", None, "B001")
        assert passed is False
        assert "VR-07" in detail
        assert "orphan" in detail.lower()
        assert "parcel" in detail.lower()

    def test_floor_without_parent_is_orphan(self):
        passed, detail = check_orphan("floor", None, "F001")
        assert passed is False
        assert "building" in detail.lower()

    def test_unit_without_parent_is_orphan(self):
        passed, detail = check_orphan("unit", None, "U001")
        assert passed is False
        assert "floor" in detail.lower()

    def test_building_with_parent_passes(self):
        passed, _ = check_orphan("building", "some-uuid", "B001")
        assert passed is True

    def test_floor_with_parent_passes(self):
        passed, _ = check_orphan("floor", "some-uuid", "F001")
        assert passed is True

    def test_unit_with_parent_passes(self):
        passed, _ = check_orphan("unit", "some-uuid", "U001")
        assert passed is True


# ---- VR-08 / VR-09: Integration with Conflict creation and verification blocking ----

class TestTopologyIntegration:
    """Integration tests using the FastAPI test client to verify that:
    - Topology runner creates Conflict records (VR-08)
    - Conflicts block VERIFIED status (VR-09)
    - Verification creates audit events
    - Only authorized officers can verify
    """

    def _seed_provisional_property(self, db_session):
        """Helper: insert a PROVISIONAL property object directly into the DB."""
        from app.models.property_object import PropertyObject
        prop = PropertyObject(
            three_d_property_id="INMH0000001-B001-F01-U001",
            type="unit",
            status="PROVISIONAL",
            confidence=0.75,
            z_min=0.0,
            z_max=3.0,
            attributes={"name": "Test Unit", "height": 10},
            source_list=["test-source"],
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)
        return prop

    def _seed_with_conflict(self, db_session):
        """Helper: insert a PROVISIONAL property with an OPEN conflict."""
        from app.models.property_object import PropertyObject
        from app.models.conflict import Conflict as ConflictModel

        prop = PropertyObject(
            three_d_property_id="INMH0000002-B001-F01-U001",
            type="unit",
            status="PROVISIONAL",
            confidence=0.60,
            z_min=0.0,
            z_max=3.0,
            attributes={"name": "Conflicted Unit"},
            source_list=[],
        )
        db_session.add(prop)
        db_session.flush()

        conflict = ConflictModel(
            property_object_id=prop.id,
            rule_code="VR-02",
            description="Test conflict: unit overlaps sibling",
            severity="ERROR",
            status="OPEN",
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(prop)
        db_session.refresh(conflict)
        return prop, conflict

    def test_topology_run_requires_auth(self, client):
        """Unauthenticated user cannot trigger topology validation."""
        resp = client.post("/api/v1/conflicts/run-topology")
        assert resp.status_code in (401, 403)

    def test_topology_run_with_officer(self, client, officer_token):
        """Officer can trigger topology validation and get a summary."""
        resp = client.post(
            "/api/v1/conflicts/run-topology",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_violations" in data
        assert "violations_by_rule" in data
        assert "checked_at" in data

    def test_verification_queue_returns_provisional(self, client, db_session):
        """Verification queue lists PROVISIONAL properties."""
        self._seed_provisional_property(db_session)

        resp = client.get("/api/v1/conflicts/verification-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert item["status"] == "PROVISIONAL"

    def test_conflict_blocks_verification(self, client, db_session, officer_token):
        """VR-09: Open conflicts block VERIFIED status."""
        prop, conflict = self._seed_with_conflict(db_session)

        # Attempt verification — should fail due to open conflict
        resp = client.post(
            f"/api/v1/properties/{prop.three_d_property_id}/verify",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"notes": "Phase 4 test verification"},
        )
        assert resp.status_code == 409
        assert "conflict" in resp.json()["detail"].lower()

    def test_resolve_conflict_then_verify(self, client, db_session, officer_token):
        """After resolving all conflicts, verification succeeds and creates an audit event."""
        prop, conflict = self._seed_with_conflict(db_session)

        # Resolve the conflict
        resp = client.post(
            f"/api/v1/conflicts/{conflict.id}/resolve",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "RESOLVED"

        # Now verify — should succeed
        resp = client.post(
            f"/api/v1/properties/{prop.three_d_property_id}/verify",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"notes": "Verified after resolving conflict"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "VERIFIED"

        # Check audit event was created
        hist = client.get(f"/api/v1/properties/{prop.three_d_property_id}/history").json()
        assert any(e["event_type"] == "verified" for e in hist["events"])

    def test_field_surveyor_cannot_verify(self, client, db_session, surveyor_token):
        """Only authorized verifying officers can verify (PRD §9 Acceptance Criterion 8)."""
        prop = self._seed_provisional_property(db_session)

        resp = client.post(
            f"/api/v1/properties/{prop.three_d_property_id}/verify",
            headers={"Authorization": f"Bearer {surveyor_token}"},
        )
        assert resp.status_code == 403

    def test_waive_conflict_endpoint(self, client, db_session, officer_token):
        """Waiving a conflict changes its status to WAIVED."""
        _, conflict = self._seed_with_conflict(db_session)

        resp = client.post(
            f"/api/v1/conflicts/{conflict.id}/waive",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "WAIVED"

    def test_topology_runner_creates_conflicts_for_orphans(self, client, db_session, officer_token):
        """VR-07/VR-08: Topology runner detects orphan buildings and creates conflict records."""
        from app.models.property_object import PropertyObject

        # Create an orphan building (no parent parcel)
        orphan = PropertyObject(
            three_d_property_id="INMH0000003-B001-F00-U000",
            type="building",
            parent_id=None,  # orphan!
            status="PROVISIONAL",
            confidence=0.5,
            attributes={"name": "Orphan Building"},
        )
        db_session.add(orphan)
        db_session.commit()

        # Run topology checks
        resp = client.post(
            "/api/v1/conflicts/run-topology",
            headers={"Authorization": f"Bearer {officer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_violations"] >= 1
        assert "VR-07" in data["violations_by_rule"]

        # Verify conflict was persisted
        conflicts_resp = client.get("/api/v1/conflicts?rule_code=VR-07")
        conflicts = conflicts_resp.json()
        assert len(conflicts) >= 1
        assert any("orphan" in (c.get("description") or "").lower() for c in conflicts)

    def test_officer_can_reject_provisional_property(self, client, db_session, officer_token):
        """Officer can reject a provisional property, creating an audit event."""
        prop = self._seed_provisional_property(db_session)

        resp = client.post(
            f"/api/v1/properties/{prop.three_d_property_id}/reject",
            headers={"Authorization": f"Bearer {officer_token}"},
            json={"notes": "Rejected: boundary survey discrepancy"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PROVISIONAL"

        # Check audit event was created
        hist = client.get(f"/api/v1/properties/{prop.three_d_property_id}/history").json()
        assert any(e["event_type"] == "rejected" for e in hist["events"])

    def test_field_surveyor_cannot_reject(self, client, db_session, surveyor_token):
        """Field surveyor cannot reject a property record."""
        prop = self._seed_provisional_property(db_session)

        resp = client.post(
            f"/api/v1/properties/{prop.three_d_property_id}/reject",
            headers={"Authorization": f"Bearer {surveyor_token}"},
            json={"notes": "Surveyor trying to reject"},
        )
        assert resp.status_code == 403

    def test_verification_queue_conflict_filter(self, client, db_session):
        """Verification queue filters by has_conflicts parameter."""
        clean_prop = self._seed_provisional_property(db_session)
        conflicted_prop, _ = self._seed_with_conflict(db_session)

        # has_conflicts=False (ready to verify)
        resp_clean = client.get("/api/v1/conflicts/verification-queue?has_conflicts=false")
        assert resp_clean.status_code == 200
        clean_ids = [p["three_d_property_id"] for p in resp_clean.json()]
        assert clean_prop.three_d_property_id in clean_ids
        assert conflicted_prop.three_d_property_id not in clean_ids

        # has_conflicts=True (blocked by conflicts)
        resp_conflicted = client.get("/api/v1/conflicts/verification-queue?has_conflicts=true")
        assert resp_conflicted.status_code == 200
        conflicted_ids = [p["three_d_property_id"] for p in resp_conflicted.json()]
        assert conflicted_prop.three_d_property_id in conflicted_ids
        assert clean_prop.three_d_property_id not in conflicted_ids

    def test_properties_verification_queue_alias(self, client, db_session):
        """Both /api/v1/verification-queue and /api/v1/properties/verification-queue work."""
        self._seed_provisional_property(db_session)

        resp1 = client.get("/api/v1/verification-queue")
        assert resp1.status_code == 200
        assert len(resp1.json()) >= 1

        resp2 = client.get("/api/v1/properties/verification-queue")
        assert resp2.status_code == 200
        assert len(resp2.json()) >= 1
