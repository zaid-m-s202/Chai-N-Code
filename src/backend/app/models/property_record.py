"""PropertyRecord — Legal and Cadastral Registry Linkage.

Maps to PRD §5.5, §7, and Phase 7 specs.
Links a spatial PropertyObject (identified by three_d_property_id)
to external land registry records (ULPIN, registration deed, rights, encumbrances).

CRITICAL NON-NEGOTIABLE:
- Spatial objects identify SPACE, never an owner.
- Owner identity is NEVER inferred by the system.
- owner_party_id is an opaque reference to an external identity system
  and is strictly protected behind verifying officer/admin RBAC and audit logging.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Index, Uuid, JSON
)

from app.database import Base


# Enumerations for legal record attributes
RIGHTS_TYPES = (
    "freehold",
    "leasehold",
    "easement",
    "usufruct",
    "strata_title",
    "occupancy_right",
    "customary_right",
    # 3D Strata and Subterranean Ownership Rights
    "air_rights",
    "surface_freehold",
    "subterranean_easement",
    "common_property_share",
    "utility_corridor_right",
    "other",
)

LINKAGE_STATUSES = (
    "LINKED",
    "PENDING",
    "DISPUTED",
    "UNLINKED",
)


class PropertyRecord(Base):
    """Legal linkage entity connecting spatial properties to land registries."""

    __tablename__ = "property_records"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_object_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=False, index=True
    )

    # Denormalized 3D property identifier for fast spatial-legal lookups
    three_d_property_id = Column(String(64), nullable=False, index=True)

    # Unique Land Parcel Identification Number (Bhu-Aadhaar / ULPIN)
    ulpin = Column(String(32), nullable=False)

    # Opaque external party identifier (NEVER inferred, strictly protected)
    owner_party_id = Column(String(128), nullable=False)

    # Deed / title registration details
    registration_number = Column(String(64), nullable=True)
    registration_date = Column(DateTime(timezone=True), nullable=True)

    # Type of ownership or tenure rights
    rights_type = Column(String(32), nullable=False, default="freehold")

    # List of encumbrances, mortgages, court stays, or easements (JSON array of dicts)
    encumbrances = Column(JSON, nullable=False, default=list)

    # Linkage verification status (LINKED | PENDING | DISPUTED | UNLINKED)
    linkage_status = Column(String(16), nullable=False, default="LINKED")

    # External source authority/system and sync timestamp
    source_system = Column(String(64), nullable=False, default="STATE_LAND_REGISTRY")
    sync_time = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Creator / Officer attribution and timestamps
    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_property_records_ulpin", "ulpin"),
        Index("ix_property_records_linkage_status", "linkage_status"),
    )

    def __repr__(self) -> str:
        return f"<PropertyRecord {self.id} ULPIN={self.ulpin} 3D_ID={self.three_d_property_id} status={self.linkage_status}>"
