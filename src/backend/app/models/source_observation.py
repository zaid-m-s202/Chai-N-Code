"""SourceObservation — individual measurements/facts from a data source.

Maps to PRD §5.2 / §5.3.  Observations are *append-only*: we never
overwrite a previous observation; instead we add a new one and let the
fusion service reconcile.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Uuid, JSON

from app.database import Base


class SourceObservation(Base):
    """One measured or reported attribute value from one source."""

    __tablename__ = "source_observations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_object_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=False, index=True
    )

    attribute_name = Column(String(128), nullable=False)  # e.g. "height", "floor_count", "footprint"
    observed_value = Column(JSON, nullable=False)         # flexible — number, geometry-as-geojson, etc.

    source_confidence = Column(Float, nullable=False, default=0.5)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    source_id = Column(String(256), nullable=True)         # external system reference
    ingestion_job_id = Column(
        Uuid(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=True, index=True
    )

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Observation {self.attribute_name}={self.observed_value} conf={self.source_confidence}>"
