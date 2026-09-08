"""IngestionJob — tracks file import lifecycle.

Maps to PRD §5.1 (FR-ING-02, FR-ING-07).  Each upload creates a job
whose status progresses through PENDING → RUNNING → COMPLETED/FAILED.
Idempotency is enforced via ``file_hash``.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Uuid

from app.database import Base


class IngestionJob(Base):
    """Asynchronous ingestion job record."""

    __tablename__ = "ingestion_jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    filename = Column(String(512), nullable=False)
    format = Column(String(32), nullable=False)  # geojson | csv | shapefile | geotiff
    file_hash = Column(String(128), nullable=True, index=True)  # SHA-256 for idempotency

    status = Column(String(16), nullable=False, default="PENDING")  # PENDING | RUNNING | COMPLETED | FAILED
    record_count = Column(Integer, nullable=True)
    error_detail = Column(Text, nullable=True)

    operator_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<IngestionJob {self.filename} [{self.status}]>"
