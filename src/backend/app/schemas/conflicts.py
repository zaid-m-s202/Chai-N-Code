"""Pydantic schemas for conflicts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ConflictResponse(BaseModel):
    """Conflict record response."""
    id: UUID
    property_object_id: UUID
    rule_code: str
    description: Optional[str] = None
    severity: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None

    model_config = {"from_attributes": True}
