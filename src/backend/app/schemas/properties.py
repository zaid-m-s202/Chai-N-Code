"""Pydantic schemas for property objects."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


PropertyType = Literal[
    "parcel", "building", "floor", "unit",
    "underground_utility", "subsurface_parcel", "tunnel", "parking_basement",
]
PropertyStatus = Literal["SYNTHETIC", "INFERRED", "DERIVED", "PROVISIONAL", "VERIFIED"]



class PropertySummary(BaseModel):
    """Lightweight property representation for list endpoints."""
    three_d_property_id: str
    type: PropertyType
    status: PropertyStatus
    confidence: float = Field(ge=0.0, le=1.0)


class PropertyDetail(BaseModel):
    """Full property object response."""
    id: UUID
    three_d_property_id: str
    type: PropertyType
    parent_id: Optional[UUID] = None
    geometry: Optional[Any] = None  # GeoJSON dict
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    attributes: Optional[dict[str, Any]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: PropertyStatus
    source_list: Optional[list[str]] = None
    created_at: datetime
    superseded_by: Optional[UUID] = None
    ulpin: Optional[str] = None
    stratum: Optional[str] = "SURFACE"
    volume_m3: Optional[float] = None

    model_config = {"from_attributes": True}



class ChangeEventResponse(BaseModel):
    """Single history event."""
    id: UUID
    event_type: str
    old_state: Optional[dict[str, Any]] = None
    new_state: Optional[dict[str, Any]] = None
    actor_id: Optional[UUID] = None
    evidence_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PropertyHistoryResponse(BaseModel):
    """History for a property object."""
    three_d_property_id: str
    events: list[ChangeEventResponse]


class VerifyRequest(BaseModel):
    """Payload for verify/reject actions."""
    evidence_id: Optional[UUID] = None
    notes: Optional[str] = None


class ObservationResponse(BaseModel):
    """Raw source observation response."""
    id: UUID
    property_object_id: UUID
    attribute_name: str
    observed_value: Any
    source_confidence: float
    observed_at: datetime
    source_id: Optional[str] = None
    ingestion_job_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class RefuseResponse(BaseModel):
    """Response from re-running observation fusion."""
    three_d_property_id: str
    fused_height: Optional[float] = None
    fused_confidence: float
    has_conflict: bool
    conflict_reason: Optional[str] = None
    observations_count: int
