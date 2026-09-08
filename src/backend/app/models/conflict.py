"""Conflict — topology / data-quality violation record.

Maps to PRD §5.6.  A conflict is created when a validation rule fails.
Conflicts *block* VERIFIED status but do *not* block ingestion (VR-09).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Uuid

from app.database import Base


class Conflict(Base):
    """A recorded violation of a validation rule."""

    __tablename__ = "conflicts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_object_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=False, index=True
    )

    rule_code = Column(String(16), nullable=False)     # e.g. VR-01
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="ERROR")  # ERROR | WARNING

    status = Column(String(16), nullable=False, default="OPEN")  # OPEN | RESOLVED | WAIVED
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<Conflict {self.rule_code} [{self.status}]>"
