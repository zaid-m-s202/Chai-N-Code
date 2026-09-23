"""PropertyObject — the central spatial entity.

Maps to PRD §5.5 / §7.  Each row is a parcel, building, floor or unit.
Soft-delete via ``superseded_by``; rows are never physically deleted
(event-sourced history in ``change_events``).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, Index, Text, Uuid, JSON,
)
from geoalchemy2 import Geometry

from app.database import Base


# ----- enumerations kept as plain strings for SQLite test compat -----
PROPERTY_TYPES = (
    "parcel", "building", "floor", "unit",
    # Underground / subterranean infrastructure types
    "underground_utility", "subsurface_parcel", "tunnel", "parking_basement",
)
PROPERTY_STATUSES = ("SYNTHETIC", "INFERRED", "DERIVED", "PROVISIONAL", "VERIFIED")
STRATUM_TYPES = ("SURFACE", "ABOVE_GROUND", "SUBTERRANEAN")


class PropertyObject(Base):
    """Core spatial entity — identifies *space*, never an owner."""

    __tablename__ = "property_objects"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(32), nullable=False)  # parcel | building | floor | unit | underground types
    parent_id = Column(Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=True)

    # Immutable 3D Property ID  (PRD §5.5)
    three_d_property_id = Column(String(64), unique=True, nullable=False, index=True)

    # Unique Land Parcel Identification Number (Bhu-Aadhaar / ULPIN) where applicable
    ulpin = Column(String(32), nullable=True, index=True)

    # PostGIS geometry — nullable so tests can run on plain SQLite
    geometry = Column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)

    z_min = Column(Float, nullable=True)
    z_max = Column(Float, nullable=True)

    # Stratum classification (SURFACE, ABOVE_GROUND, SUBTERRANEAN)
    stratum = Column(String(20), nullable=True, default="SURFACE")

    # 3D volumetric extent in cubic meters
    volume_m3 = Column(Float, nullable=True)

    # Flexible attribute bag (PRD §7)
    attributes = Column(JSON, nullable=True, default=dict)

    # Evidence / quality fields
    confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(16), nullable=False, default="SYNTHETIC")
    source_list = Column(JSON, nullable=True, default=list)  # list of evidence IDs

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Soft-delete: once superseded, the row is historical
    superseded_by = Column(Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=True)

    __table_args__ = (
        Index("ix_property_objects_type", "type"),
        Index("ix_property_objects_status", "status"),
        Index("ix_property_objects_stratum", "stratum"),
        Index("ix_property_objects_parent_id", "parent_id"),
        Index("ix_property_objects_superseded_by", "superseded_by"),
        Index("idx_property_objects_geometry", "geometry", postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return f"<PropertyObject {self.three_d_property_id} [{self.type}/{self.status}]>"

