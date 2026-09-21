"""Immutable 3D ULPIN generator and parser.

Supports three spatial identity classes per the 3D Cadastral PRD:

1.  Surface land parcels:
        {ULPIN}-SURF  or  {ULPIN}-P{seq:03d}
2.  Multi-storey apartments (strata units):
        {ULPIN}-B{bldg:03d}-F{floor:02d}-U{unit:03d}
3.  Underground infrastructure:
        {ULPIN}-UG-{category}-{id}          (e.g. UG-METRO-T01, UG-UTIL-GAS01)
        {ULPIN}-B{bldg:03d}-B{basement:02d}-P{slot:03d}   (basement parking)

Base ULPIN derivation (14-char):
    {state:2}{district:3}{geocode:9}
    where geocode is derived from the parcel centroid (lon, lat) via a
    deterministic spatial hashing scheme aligned with DILRMP standards.

Backward compatibility:
    The original ``make_3d_property_id`` and ``parse_3d_property_id`` functions
    are fully preserved and remain the canonical interface for apartment-type IDs.

Example IDs:
    INMH0234567890-SURF
    INMH0234567890-B001-F04-U402
    INMH0234567890-UG-METRO-T01
    INMH0234567890-B001-B01-P001
"""

import hashlib
import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Regex patterns for all 3D ULPIN variants
# ---------------------------------------------------------------------------

# Original apartment pattern (backward compat)
ID_REGEX = re.compile(
    r"^(?P<ulpin>[A-Za-z0-9_-]+)-B(?P<building>\d{3,4})-F(?P<floor>\d{2,3})-U(?P<unit>\d{3,4})$"
)

# Surface parcel: {ULPIN}-SURF or {ULPIN}-P{seq:03d}
SURFACE_REGEX = re.compile(
    r"^(?P<ulpin>[A-Za-z0-9_-]+)-(?:SURF|P(?P<parcel_seq>\d{3,4}))$"
)

# Underground infrastructure: {ULPIN}-UG-{CATEGORY}-{ID}
UNDERGROUND_REGEX = re.compile(
    r"^(?P<ulpin>[A-Za-z0-9_-]+)-UG-(?P<category>[A-Z]+)-(?P<infra_id>[A-Za-z0-9]+)$"
)

# Basement parking: {ULPIN}-B{bldg:03d}-B{basement:02d}-P{slot:03d}
BASEMENT_REGEX = re.compile(
    r"^(?P<ulpin>[A-Za-z0-9_-]+)-B(?P<building>\d{3,4})-B(?P<basement>\d{2,3})-P(?P<slot>\d{3,4})$"
)


# ---------------------------------------------------------------------------
# Indian state codes (ISO 3166-2:IN numeric → 2-char alpha)
# ---------------------------------------------------------------------------

INDIAN_STATE_CODES = {
    "27": "MH", "29": "KA", "33": "TN", "36": "TS", "09": "UP",
    "07": "DL", "24": "GJ", "06": "HR", "22": "CT", "21": "OR",
    "10": "BR", "23": "MP", "20": "JH", "32": "KL", "08": "RJ",
    "03": "PB", "19": "WB", "18": "AS", "02": "HP", "01": "JK",
    "11": "SK", "12": "AR", "13": "NL", "14": "MN", "15": "MZ",
    "16": "TR", "17": "ML", "30": "GA", "04": "CH", "05": "UK",
    "28": "AP", "34": "PY", "25": "DD", "26": "DN", "31": "LK",
    "35": "AN", "37": "LA", "38": "LD",
}


# ---------------------------------------------------------------------------
# Base ULPIN generation (14-char coordinate-derived)
# ---------------------------------------------------------------------------

def _geocode_from_coords(lon: float, lat: float) -> str:
    """Derive a 9-character deterministic spatial geocode from centroid coordinates.

    Uses a truncated SHA-256 hash of the coordinate pair, base-36 encoded
    and zero-padded to 9 characters.  This provides a collision-resistant,
    deterministic, and compact spatial identifier.
    """
    coord_str = f"{lon:.7f},{lat:.7f}"
    digest = hashlib.sha256(coord_str.encode("utf-8")).hexdigest()[:12]
    # Convert hex to base-36 alphanumeric and truncate to 9 chars
    numeric = int(digest, 16)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    while numeric > 0 and len(result) < 9:
        result.append(chars[numeric % 36])
        numeric //= 36
    geocode = "".join(reversed(result)).zfill(9)[:9]
    return geocode.upper()


def generate_base_ulpin(
    *args: Any,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate a standardized 14-character base ULPIN from coordinates.

    Supports:
    - generate_base_ulpin(state="MH", district="PUN", lon=73.8567, lat=18.5204)
    - generate_base_ulpin("MH", "MUM", 73.8455, 18.5115)
    - generate_base_ulpin(18.5204, 73.8567, "27", "PUN")
    """
    final_lat = lat
    final_lon = lon
    st = state or state_code
    dt = district or district_code

    if len(args) == 4:
        if isinstance(args[0], str) and isinstance(args[1], str):
            st, dt = args[0], args[1]
            final_lon = float(args[2])
            final_lat = float(args[3])
        else:
            final_lat = float(args[0])
            final_lon = float(args[1])
            st = str(args[2])
            dt = str(args[3])
    elif len(args) == 2:
        if isinstance(args[0], str) and isinstance(args[1], str):
            st, dt = args[0], args[1]
        else:
            final_lat = float(args[0])
            final_lon = float(args[1])

    if final_lat is None:
        final_lat = float(kwargs.get("lat", 18.5204))
    if final_lon is None:
        final_lon = float(kwargs.get("lon", 73.8567))
    if not st:
        st = kwargs.get("state") or kwargs.get("state_code") or "MH"
    if not dt:
        dt = kwargs.get("district") or kwargs.get("district_code") or "MUM"

    state_alpha = INDIAN_STATE_CODES.get(str(st), str(st)[:2].upper())
    dist_alpha = str(dt)[:3].upper()
    geocode = _geocode_from_coords(final_lon, final_lat)
    ulpin = f"{state_alpha}{dist_alpha}{geocode}"
    return ulpin[:14].upper()


# ---------------------------------------------------------------------------
# 3D ULPIN constructors (all three spatial identity classes)
# ---------------------------------------------------------------------------

def _validate_ulpin(ulpin: str) -> None:
    """Validate base ULPIN format."""
    if not ulpin or not re.match(r"^[A-Za-z0-9_-]+$", ulpin):
        raise ValueError(f"Invalid ULPIN: '{ulpin}'. Must be alphanumeric/underscore/hyphen.")


def make_3d_property_id(
    ulpin: str = "",
    building_seq: int = 1,
    floor_seq: int = 0,
    unit_seq: int = 0,
    building_id: Optional[int] = None,
    floor_id: Optional[int] = None,
    unit_id: Optional[int] = None,
    floor_number: Optional[int] = None,
    unit_number: Optional[int] = None,
    base_ulpin: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate canonical 3D Property ID for multi-storey apartment units.

    Pattern (PRD §5.5):
        {ULPIN}-B{bldg:03d}-F{floor:02d}-U{unit:03d}
    Example:
        INMH0234567-B001-F04-U402
    """
    final_ulpin = base_ulpin or ulpin or kwargs.get("base_ulpin", "")
    _validate_ulpin(final_ulpin)
    b = building_id if building_id is not None else kwargs.get("building_id", building_seq)
    f = floor_number if floor_number is not None else (
        floor_id if floor_id is not None else kwargs.get("floor_number", kwargs.get("floor_id", floor_seq))
    )
    u = unit_number if unit_number is not None else (
        unit_id if unit_id is not None else kwargs.get("unit_number", kwargs.get("unit_id", unit_seq))
    )

    if b < 0 or f < 0 or u < 0:
        raise ValueError("Sequences must be non-negative integers.")
    return f"{final_ulpin}-B{b:03d}-F{f:02d}-U{u:03d}"


def make_surface_ulpin(
    ulpin: str = "",
    parcel_seq: Optional[int] = None,
    base_ulpin: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate 3D ULPIN for a surface land parcel.

    Pattern:
        {ULPIN}-SURF           (single parcel / default)
        {ULPIN}-P{seq:03d}     (when multiple surface parcels share a ULPIN, seq > 1)
    """
    final_ulpin = base_ulpin or ulpin or kwargs.get("base_ulpin", "")
    _validate_ulpin(final_ulpin)
    seq = parcel_seq if parcel_seq is not None else kwargs.get("parcel_seq")
    if seq is not None and seq > 1:
        return f"{final_ulpin}-P{seq:03d}"
    return f"{final_ulpin}-SURF"


def make_underground_ulpin(
    ulpin: str = "",
    category: str = "",
    infra_id: str = "",
    base_ulpin: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate 3D ULPIN for underground infrastructure.

    Pattern:
        {ULPIN}-UG-{CATEGORY}-{ID}
    Examples:
        INMH0234567-UG-METRO-T01
        INMH0234567-UG-UTIL-SEW01
        INMH0234567-UG-FIBER-OPT03
    """
    final_ulpin = base_ulpin or ulpin or kwargs.get("base_ulpin", "")
    _validate_ulpin(final_ulpin)
    cat = (category or kwargs.get("category", "")).upper().strip()
    iid = (infra_id or kwargs.get("infra_id", "")).upper().strip()
    if not re.match(r"^[A-Z]+$", cat):
        raise ValueError(f"Category must be uppercase alpha: '{category}'")
    if not re.match(r"^[A-Za-z0-9]+$", iid):
        raise ValueError(f"Infrastructure ID must be alphanumeric: '{infra_id}'")
    return f"{final_ulpin}-UG-{cat}-{iid}"


def make_basement_ulpin(
    ulpin: str = "",
    building_seq: int = 1,
    basement_level: int = 1,
    slot_seq: int = 1,
    building_id: Optional[int] = None,
    slot_number: Optional[int] = None,
    base_ulpin: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Generate 3D ULPIN for basement/underground parking slots.

    Pattern:
        {ULPIN}-B{bldg:03d}-B{basement:02d}-P{slot:03d}
    Example:
        INMH0234567-B001-B01-P001  (Building 1, Basement Level 1, Parking Slot 1)
    """
    final_ulpin = base_ulpin or ulpin or kwargs.get("base_ulpin", "")
    _validate_ulpin(final_ulpin)
    b = building_id if building_id is not None else kwargs.get("building_id", building_seq)
    bl = basement_level if basement_level is not None else kwargs.get("basement_level", 1)
    s = slot_number if slot_number is not None else (
        slot_seq if slot_seq is not None else kwargs.get("slot_number", kwargs.get("slot_seq", 1))
    )

    if b < 0 or bl < 0 or s < 0:
        raise ValueError("All sequences must be non-negative integers.")
    return f"{final_ulpin}-B{b:03d}-B{bl:02d}-P{s:03d}"


# ---------------------------------------------------------------------------
# Universal 3D ULPIN generator
# ---------------------------------------------------------------------------

# Valid stratum types
STRATUM_TYPES = ("SURFACE", "ABOVE_GROUND", "SUBTERRANEAN")

# Valid underground infrastructure categories
UNDERGROUND_CATEGORIES = (
    "METRO", "UTIL", "FIBER", "WATER", "GAS", "SEWER", "TUNNEL",
    "ELECTRIC", "TELECOM", "STORM", "PARKING",
)


def make_3d_ulpin(
    ulpin: str,
    entity_type: str,
    *,
    building_seq: int = 0,
    floor_seq: int = 0,
    unit_seq: int = 0,
    parcel_seq: Optional[int] = None,
    category: Optional[str] = None,
    infra_id: Optional[str] = None,
    basement_level: Optional[int] = None,
    slot_seq: Optional[int] = None,
) -> str:
    """Universal 3D ULPIN generator supporting all spatial identity classes.

    Parameters
    ----------
    entity_type : str
        One of: "surface", "parcel", "building", "floor", "unit",
        "underground_utility", "subsurface_parcel", "tunnel",
        "parking_basement".

    Returns
    -------
    str
        Fully qualified 3D ULPIN.
    """
    et = entity_type.lower().strip()

    if et in ("surface", "parcel"):
        return make_surface_ulpin(ulpin, parcel_seq)
    elif et in ("building", "floor", "unit"):
        return make_3d_property_id(ulpin, building_seq, floor_seq, unit_seq)
    elif et in ("underground_utility", "subsurface_parcel", "tunnel"):
        if not category or not infra_id:
            raise ValueError(
                f"Underground entity '{et}' requires 'category' and 'infra_id'."
            )
        return make_underground_ulpin(ulpin, category, infra_id)
    elif et == "parking_basement":
        if basement_level is None or slot_seq is None:
            raise ValueError(
                "Parking basement requires 'basement_level' and 'slot_seq'."
            )
        return make_basement_ulpin(ulpin, building_seq, basement_level, slot_seq)
    else:
        raise ValueError(
            f"Unsupported entity type: '{entity_type}'. "
            f"Supported: surface, parcel, building, floor, unit, "
            f"underground_utility, subsurface_parcel, tunnel, parking_basement."
        )


# ---------------------------------------------------------------------------
# Universal 3D ULPIN parser
# ---------------------------------------------------------------------------

def parse_3d_property_id(three_d_property_id: str) -> dict[str, Any]:
    """Parse a 3D Property ID into its component parts.

    Backward-compatible: apartment-type IDs return the original dict structure.
    """
    tid = three_d_property_id.strip()

    # 1. Apartment: {ULPIN}-B{bldg}-F{floor}-U{unit}
    match = ID_REGEX.match(tid)
    if match:
        return {
            "ulpin": match.group("ulpin"),
            "building_seq": int(match.group("building")),
            "floor_seq": int(match.group("floor")),
            "unit_seq": int(match.group("unit")),
            "building": int(match.group("building")),
            "floor": int(match.group("floor")),
            "unit": int(match.group("unit")),
            "entity_type": "unit",
            "stratum": "ABOVE_GROUND",
        }

    # 2. Basement parking: {ULPIN}-B{bldg}-B{basement}-P{slot}
    match = BASEMENT_REGEX.match(tid)
    if match:
        return {
            "ulpin": match.group("ulpin"),
            "building_seq": int(match.group("building")),
            "building": int(match.group("building")),
            "basement_level": int(match.group("basement")),
            "slot_seq": int(match.group("slot")),
            "slot_number": int(match.group("slot")),
            "entity_type": "parking_basement",
            "stratum": "SUBTERRANEAN",
        }

    # 3. Underground infrastructure: {ULPIN}-UG-{CAT}-{ID}
    match = UNDERGROUND_REGEX.match(tid)
    if match:
        return {
            "ulpin": match.group("ulpin"),
            "category": match.group("category"),
            "infra_id": match.group("infra_id"),
            "entity_type": "underground_utility",
            "stratum": "SUBTERRANEAN",
        }

    # 4. Surface: {ULPIN}-SURF or {ULPIN}-P{seq}
    match = SURFACE_REGEX.match(tid)
    if match:
        return {
            "ulpin": match.group("ulpin"),
            "parcel_seq": int(match.group("parcel_seq")) if match.group("parcel_seq") else None,
            "entity_type": "surface",
            "stratum": "SURFACE",
        }

    raise ValueError(f"Invalid 3D Property ID format: '{three_d_property_id}'")


def parse_3d_ulpin(three_d_property_id: str) -> dict[str, Any]:
    """Alias for parse_3d_property_id — universal 3D ULPIN parser."""
    return parse_3d_property_id(three_d_property_id)


# ---------------------------------------------------------------------------
# Convenience and semantic aliases for 3D Cadastral pipelines
# ---------------------------------------------------------------------------

generate_surface_ulpin = make_surface_ulpin
generate_underground_ulpin = make_underground_ulpin
generate_basement_parking_ulpin = make_basement_ulpin
generate_apartment_3d_ulpin = make_3d_property_id


def parse_any_3d_ulpin(three_d_property_id: str) -> dict[str, Any]:
    """Parse 3D ULPIN gracefully returning dict with 'type' key."""
    if not three_d_property_id:
        return {"type": "unknown", "raw": three_d_property_id}
    try:
        res = parse_3d_property_id(three_d_property_id)
        # normalize 'type'
        ent = res.get("entity_type", "unknown")
        type_norm = {
            "surface": "surface",
            "unit": "apartment",
            "underground_utility": "underground",
            "parking_basement": "basement_parking",
        }.get(ent, ent)
        return {
            **res,
            "type": type_norm,
            "building": res.get("building_seq"),
            "floor": res.get("floor_seq"),
            "unit": res.get("unit_seq"),
            "slot_number": res.get("slot_number", res.get("slot_seq")),
        }
    except Exception:
        return {"type": "unknown", "raw": three_d_property_id}
