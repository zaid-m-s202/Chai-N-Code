"""Pydantic schemas for provenance and evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EvidenceResponse(BaseModel):
    """Provenance metadata record linking source file/sensor to property."""
    id: UUID
    property_object_id: Optional[UUID] = None
    evidence_type: str
    file_reference: Optional[str] = None
    file_hash: Optional[str] = None
    original_crs: Optional[str] = None
    original_format: Optional[str] = None
    source_system: Optional[str] = None
    operator_id: Optional[UUID] = None
    ingestion_job_id: Optional[UUID] = None
    captured_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
