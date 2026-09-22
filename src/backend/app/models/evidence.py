"""Evidence — provenance record for every ingested artefact.

Maps to PRD §5.7 / FR-ING-04.  Each evidence record links a source file
or observation to a property object with full provenance metadata.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Uuid

from app.database import Base


class Evidence(Base):
    """Provenance chain linking source data to property objects."""

    __tablename__ = "evidence"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_object_id = Column(
        Uuid(as_uuid=True), ForeignKey("property_objects.id"), nullable=True, index=True
    )

    evidence_type = Column(String(64), nullable=False)     # geojson, csv, geotiff, survey, plan, …
    file_reference = Column(Text, nullable=True)            # object-store key or filesystem path
    file_hash = Column(String(128), nullable=True)          # SHA-256 of original file

    original_crs = Column(String(32), nullable=True)
    original_format = Column(String(32), nullable=True)
    source_system = Column(String(128), nullable=True)      # e.g. "municipal_survey_2024"

    operator_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    ingestion_job_id = Column(Uuid(as_uuid=True), ForeignKey("ingestion_jobs.id"), nullable=True, index=True)


    captured_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Evidence {self.evidence_type} file={self.file_reference}>"
