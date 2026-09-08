"""Pydantic schemas for ingestion jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class IngestionJobCreate(BaseModel):
    """Metadata for a new ingestion job (file is uploaded separately)."""
    source_system: Optional[str] = None


class IngestionJobResponse(BaseModel):
    """Ingestion job status response."""
    id: UUID
    filename: str
    format: str
    status: str
    record_count: Optional[int] = None
    error_detail: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
