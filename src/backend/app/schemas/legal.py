"""Pydantic schemas for Legal Linkage & Property Records (Phase 7).

Ensures explicit validation, strict typing, and separation between full
and redacted views to protect owner identity data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EncumbranceItem(BaseModel):
    """Encumbrance, mortgage, court stay, or restriction item."""
    type: str = Field(..., description="Type of encumbrance: mortgage | lien | easement | stay_order | tax_liability | other")
    description: str = Field(..., description="Description or case number of encumbrance")
    recorded_date: Optional[str] = Field(None, description="ISO date or string of record date")
    amount: Optional[float] = Field(None, description="Monetary claim or liability if applicable")
    beneficiary: Optional[str] = Field(None, description="Bank, court, or beneficiary party")
    status: str = Field("ACTIVE", description="ACTIVE | DISCHARGED | DISPUTED")


class PropertyRecordBase(BaseModel):
    """Base fields for a legal property record."""
    ulpin: str = Field(..., min_length=4, max_length=32, description="Unique Land Parcel Identification Number")
    registration_number: Optional[str] = Field(None, max_length=64, description="Deed / registration deed number")
    registration_date: Optional[datetime] = Field(None, description="Date of deed registration")
    rights_type: str = Field("freehold", description="freehold | leasehold | easement | usufruct | strata_title | occupancy_right | customary_right | other")
    encumbrances: List[Dict[str, Any]] = Field(default_factory=list, description="List of encumbrances/liens")
    linkage_status: str = Field("LINKED", description="LINKED | PENDING | DISPUTED | UNLINKED")
    source_system: str = Field("STATE_LAND_REGISTRY", max_length=64, description="Source land administration system")


class PropertyRecordCreate(PropertyRecordBase):
    """Payload to create/link a legal record to a 3D PropertyObject."""
    property_object_id: UUID = Field(..., description="Spatial PropertyObject UUID to link")
    owner_party_id: str = Field(..., min_length=1, max_length=128, description="Opaque external owner party ID (NEVER inferred)")

    @field_validator("owner_party_id")
    @classmethod
    def validate_owner_not_inferred(cls, v: str) -> str:
        clean = v.strip()
        if not clean or clean.lower() in ("unknown", "auto_generated", "inferred", "ai_inferred"):
            raise ValueError("Owner identity must be an explicit external reference and cannot be inferred or synthetic.")
        return clean


class PropertyRecordUpdate(BaseModel):
    """Payload to update an existing legal record."""
    ulpin: Optional[str] = None
    owner_party_id: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[datetime] = None
    rights_type: Optional[str] = None
    encumbrances: Optional[List[Dict[str, Any]]] = None
    linkage_status: Optional[str] = None
    source_system: Optional[str] = None
    sync_time: Optional[datetime] = None

    @field_validator("owner_party_id")
    @classmethod
    def validate_owner_not_inferred(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean or clean.lower() in ("unknown", "auto_generated", "inferred", "ai_inferred"):
                raise ValueError("Owner identity must be an explicit external reference and cannot be inferred or synthetic.")
            return clean
        return v


class PropertyRecordResponse(PropertyRecordBase):
    """Full legal record response (VERIFYING_OFFICER or ADMIN only)."""
    id: UUID
    property_object_id: UUID
    three_d_property_id: str
    owner_party_id: str
    sync_time: datetime
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    is_redacted: bool = False

    model_config = ConfigDict(from_attributes=True)


class PropertyRecordRedactedResponse(PropertyRecordBase):
    """Redacted legal record response for public viewers and surveyors."""
    id: UUID
    property_object_id: UUID
    three_d_property_id: str
    owner_party_id: Optional[str] = "[PROTECTED — OFFICER ACCESS ONLY]"
    sync_time: datetime
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    is_redacted: bool = True

    model_config = ConfigDict(from_attributes=True)


class LegalLinkageSummary(BaseModel):
    """Lightweight legal linkage summary for embedding in property responses."""
    has_legal_record: bool
    record_id: Optional[UUID] = None
    ulpin: Optional[str] = None
    linkage_status: Optional[str] = None
    rights_type: Optional[str] = None
    encumbrance_count: int = 0
    source_system: Optional[str] = None
    is_owner_redacted: bool = True
