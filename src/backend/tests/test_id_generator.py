"""Tests for 3D Property ID generator service (PRD §5.5)."""

import pytest
from app.services.id_generator import make_3d_property_id


def test_valid_3d_property_id_generation():
    prop_id = make_3d_property_id(
        ulpin="INMH0234567",
        building_seq=1,
        floor_seq=4,
        unit_seq=402,
    )
    assert prop_id == "INMH0234567-B001-F04-U402"


def test_zero_padded_sequences():
    prop_id = make_3d_property_id(
        ulpin="PARCEL99",
        building_seq=999,
        floor_seq=99,
        unit_seq=999,
    )
    assert prop_id == "PARCEL99-B999-F99-U999"


def test_invalid_ulpin_empty():
    with pytest.raises(ValueError, match="Invalid ULPIN"):
        make_3d_property_id(ulpin="", building_seq=1, floor_seq=1, unit_seq=1)


def test_invalid_ulpin_special_characters():
    with pytest.raises(ValueError, match="Invalid ULPIN"):
        make_3d_property_id(ulpin="ULPIN#123*&", building_seq=1, floor_seq=1, unit_seq=1)


def test_id_format_matches_prd_pattern():
    import re
    prop_id = make_3d_property_id("KA04PARCEL100", 2, 3, 15)
    pattern = r"^[A-Za-z0-9_-]+-B\d{3}-F\d{2}-U\d{3}$"
    assert re.match(pattern, prop_id) is not None
