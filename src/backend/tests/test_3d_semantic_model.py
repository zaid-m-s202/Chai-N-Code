"""Tests for Phase 3 — 3D Semantic Model, Spatial Hierarchy, and Split/Merge Lifecycle.

Acceptance Criteria:
- Sample parcels render with hierarchy (parcel -> building -> floor -> unit).
- IDs remain stable across updates.
- Split/merge never reuses old IDs.
"""

from uuid import uuid4
import pytest

from app.models.property_object import PropertyObject
from app.models.change_event import ChangeEvent
from app.services.floor_height_heuristic import (
    estimate_building_levels,
    compute_floor_vertical_extents,
    compute_unit_vertical_extent,
    get_typical_floor_height,
)
from app.services.id_generator import make_3d_property_id, parse_3d_property_id
from app.services.lifecycle import split_unit, merge_units, build_hierarchy_tree
from app.schemas.lifecycle import SplitUnitSpec


def test_floor_height_heuristic_derivation():
    # Residential heuristic: 3.0m
    assert get_typical_floor_height("residential") == 3.0
    # Commercial heuristic: 3.8m
    assert get_typical_floor_height("commercial") == 3.8

    # Derive floor count when height is given
    h, fc, fh = estimate_building_levels(total_height=24.0, floor_count=None, use_type="residential")
    assert fc == 8
    assert pytest.approx(fh, 0.01) == 3.0

    # Derive height when floor count is given
    h2, fc2, fh2 = estimate_building_levels(total_height=None, floor_count=5, use_type="commercial")
    assert pytest.approx(h2, 0.01) == 19.0
    assert fc2 == 5

    # Derive vertical extents for 4 floors
    extents = compute_floor_vertical_extents(floor_count=4, floor_height=3.0, base_z=0.0)
    assert len(extents) == 4
    assert extents[0] == {"floor_seq": 1, "z_min": 0.0, "z_max": 3.0, "height": 3.0}
    assert extents[3] == {"floor_seq": 4, "z_min": 9.0, "z_max": 12.0, "height": 3.0}

    # Unit on 3rd floor
    u_zmin, u_zmax = compute_unit_vertical_extent(floor_seq=3, floor_height=3.0, base_z=0.0)
    assert u_zmin == 6.0
    assert u_zmax == 9.0


def test_id_generator_and_parser():
    id_str = make_3d_property_id("INMH0234567", 1, 4, 402)
    assert id_str == "INMH0234567-B001-F04-U402"

    parsed = parse_3d_property_id(id_str)
    assert parsed["ulpin"] == "INMH0234567"
    assert parsed["building_seq"] == 1
    assert parsed["floor_seq"] == 4
    assert parsed["unit_seq"] == 402

    with pytest.raises(ValueError, match="Invalid 3D Property ID format"):
        parse_3d_property_id("INVALID-FORMAT")


def test_id_remains_stable_across_updates(db_session):
    """PRD Rule: 3D Property ID is immutable across updates."""
    prop = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTEST0001-B001-F01-U101",
        type="unit",
        status="PROVISIONAL",
        confidence=0.8,
        attributes={"height": 3.0, "tenant": "Alpha Corp"},
    )
    db_session.add(prop)
    db_session.commit()

    orig_id = prop.three_d_property_id

    # Simulate an update (new survey, change of occupancy, verification)
    prop.attributes = {**prop.attributes, "tenant": "Beta Corp", "height": 3.2}
    prop.confidence = 0.95
    prop.status = "VERIFIED"
    db_session.commit()
    db_session.refresh(prop)

    assert prop.three_d_property_id == orig_id
    assert prop.attributes["tenant"] == "Beta Corp"


def test_hierarchy_tree_construction(db_session):
    """PRD Acceptance: sample parcels render with hierarchy (parcel -> building -> units)."""
    # Create Parcel
    parcel = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTPARCEL01-B000-F00-U000",
        type="parcel",
        status="VERIFIED",
        confidence=1.0,
    )
    db_session.add(parcel)
    db_session.flush()

    # Create Building linked to Parcel
    building = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTPARCEL01-B001-F00-U000",
        type="building",
        parent_id=parcel.id,
        status="PROVISIONAL",
        confidence=0.9,
    )
    db_session.add(building)
    db_session.flush()

    # Create 2 Units linked to Building
    u1 = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTPARCEL01-B001-F01-U001",
        type="unit",
        parent_id=building.id,
        status="PROVISIONAL",
        confidence=0.85,
    )
    u2 = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTPARCEL01-B001-F01-U002",
        type="unit",
        parent_id=building.id,
        status="PROVISIONAL",
        confidence=0.85,
    )
    db_session.add_all([u1, u2])
    db_session.commit()

    # Build hierarchy starting from Parcel
    tree = build_hierarchy_tree(db_session, parcel)
    assert tree.three_d_property_id == parcel.three_d_property_id
    assert len(tree.children) == 1

    bldg_node = tree.children[0]
    assert bldg_node.three_d_property_id == building.three_d_property_id
    assert len(bldg_node.children) == 2
    assert bldg_node.children[0].three_d_property_id == u1.three_d_property_id
    assert bldg_node.children[1].three_d_property_id == u2.three_d_property_id


def test_split_unit_never_reuses_old_ids(db_session):
    """PRD Acceptance: split/merge never reuses old IDs."""
    unit = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTSPLIT-B001-F01-U001",
        type="unit",
        status="PROVISIONAL",
        confidence=0.85,
        z_min=0.0,
        z_max=3.0,
        attributes={"area_sqm": 120.0},
    )
    db_session.add(unit)
    db_session.commit()

    # Split unit U001 into two: U002 and U003
    parent, new_units = split_unit(
        db=db_session,
        target_property_id="INTESTSPLIT-B001-F01-U001",
        split_specs=[
            SplitUnitSpec(unit_name="Unit 101A", z_min=0.0, z_max=3.0),
            SplitUnitSpec(unit_name="Unit 101B", z_min=0.0, z_max=3.0),
        ],
        reason="Subdivision by architectural remodel permit #2026-99",
    )

    assert parent.superseded_by is not None
    assert len(new_units) == 2
    assert new_units[0].three_d_property_id == "INTESTSPLIT-B001-F01-U002"
    assert new_units[1].three_d_property_id == "INTESTSPLIT-B001-F01-U003"
    # Never reuses U001
    assert "U001" not in [u.three_d_property_id for u in new_units]

    # Verify event sourcing logged the unit_split event
    event = db_session.query(ChangeEvent).filter(
        ChangeEvent.property_object_id == parent.id,
        ChangeEvent.event_type == "unit_split",
    ).first()
    assert event is not None
    assert event.new_state["superseded_by"] == [
        "INTESTSPLIT-B001-F01-U002",
        "INTESTSPLIT-B001-F01-U003",
    ]

    # Perform a SECOND split on U002: it must get sequences U004 and U005, NEVER reusing U001!
    parent_2, new_units_2 = split_unit(
        db=db_session,
        target_property_id="INTESTSPLIT-B001-F01-U002",
        split_specs=[
            SplitUnitSpec(unit_name="Unit 101A-East"),
            SplitUnitSpec(unit_name="Unit 101A-West"),
        ],
    )
    assert new_units_2[0].three_d_property_id == "INTESTSPLIT-B001-F01-U004"
    assert new_units_2[1].three_d_property_id == "INTESTSPLIT-B001-F01-U005"


def test_merge_units_never_reuses_old_ids(db_session):
    """PRD Acceptance: merging units supersedes old units and creates a brand-new ID."""
    u10 = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTMERGE-B001-F01-U010",
        type="unit",
        status="PROVISIONAL",
        confidence=0.9,
        z_min=0.0,
        z_max=3.2,
    )
    u11 = PropertyObject(
        id=uuid4(),
        three_d_property_id="INTESTMERGE-B001-F01-U011",
        type="unit",
        status="PROVISIONAL",
        confidence=0.88,
        z_min=0.0,
        z_max=3.2,
    )
    db_session.add_all([u10, u11])
    db_session.commit()

    old_units, merged_unit = merge_units(
        db=db_session,
        unit_ids=["INTESTMERGE-B001-F01-U010", "INTESTMERGE-B001-F01-U011"],
        merged_attributes={"use": "combined_office_suite"},
        reason="Consolidation by lease agreement",
    )

    assert len(old_units) == 2
    assert u10.superseded_by == merged_unit.id
    assert u11.superseded_by == merged_unit.id

    # The new merged ID must strictly be greater than U011, i.e., U012 (never U010 or U011)
    assert merged_unit.three_d_property_id == "INTESTMERGE-B001-F01-U012"
    assert merged_unit.attributes["merged_from"] == [
        "INTESTMERGE-B001-F01-U010",
        "INTESTMERGE-B001-F01-U011",
    ]

    # Verify event sourcing logged unit_merged event
    merge_event = db_session.query(ChangeEvent).filter(
        ChangeEvent.property_object_id == merged_unit.id,
        ChangeEvent.event_type == "created",
    ).first()
    assert merge_event is not None
    assert merge_event.new_state["event"] == "unit_merged"
