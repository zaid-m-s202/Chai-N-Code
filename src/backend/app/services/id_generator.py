"""Immutable 3D Property ID generator and parser.

Pattern specified in PRD §5.5:
    {ULPIN}-{building_seq:03d}-F{floor_seq:02d}-U{unit_seq:03d}
Example:
    INMH0234567-B001-F04-U402
"""

import re
from typing import Any


ID_REGEX = re.compile(
    r"^(?P<ulpin>[A-Za-z0-9_-]+)-B(?P<building>\d{3,4})-F(?P<floor>\d{2,3})-U(?P<unit>\d{3,4})$"
)


def make_3d_property_id(ulpin: str, building_seq: int, floor_seq: int, unit_seq: int) -> str:
    """Generate canonical 3D Property ID conforming to PRD §5.5."""
    if not ulpin or not re.match(r"^[A-Za-z0-9_-]+$", ulpin):
        raise ValueError(f"Invalid ULPIN: '{ulpin}'. Must be alphanumeric.")
    if building_seq < 0 or floor_seq < 0 or unit_seq < 0:
        raise ValueError("Sequences must be non-negative integers.")
    return f"{ulpin}-B{building_seq:03d}-F{floor_seq:02d}-U{unit_seq:03d}"


def parse_3d_property_id(three_d_property_id: str) -> dict[str, Any]:
    """Parse a 3D Property ID into its component parts."""
    match = ID_REGEX.match(three_d_property_id.strip())
    if not match:
        raise ValueError(f"Invalid 3D Property ID format: '{three_d_property_id}'")
    return {
        "ulpin": match.group("ulpin"),
        "building_seq": int(match.group("building")),
        "floor_seq": int(match.group("floor")),
        "unit_seq": int(match.group("unit")),
    }
