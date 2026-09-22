"""ChangeEvent — immutable event-sourced history.

Maps to PRD §5.9.  Rows are *never* updated or deleted.  The current
state of any property object can be reconstructed by replaying its
events.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Uuid, JSON

from app.database import Base


# Event types from PRD §5.9 and Phase 7
EVENT_TYPES = (
    "created",
    "height_updated",
    "floor_added",
    "unit_split",
    "unit_merged",
    "status_changed",
    "verified",
    "rejected",
    "superseded",
    "demolished",
    "legal_linked",
    "legal_updated",
    "legal_unlinked",
    "pii_exported",
)


class ChangeEvent(Base):
    """Immutable audit / history record."""

    __tablename__ = "change_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_object_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=False, index=True
    )

    event_type = Column(String(32), nullable=False)  # one of EVENT_TYPES
    old_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)

    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    evidence_id = Column(Uuid(as_uuid=True), ForeignKey("evidence.id"), nullable=True, index=True)


    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<ChangeEvent {self.event_type} on {self.property_object_id}>"
