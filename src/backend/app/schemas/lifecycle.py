"""Pydantic schemas for 3D Property lifecycle operations (split, merge, hierarchy)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.properties import PropertyDetail


class SplitUnitSpec(BaseModel):
    """Specification for a new unit resulting from a split."""
    unit_name: Optional[str] = None
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    attributes: Optional[dict[str, Any]] = None


class SplitRequest(BaseModel):
    """Request payload for splitting an existing unit into two or more units."""
    split_units: list[SplitUnitSpec] = Field(..., min_length=2, description="At least 2 new units must be defined")
    reason: Optional[str] = Field(None, description="Official justification or permit reference for the split")
    evidence_id: Optional[UUID] = None


class MergeRequest(BaseModel):
    """Request payload for merging two or more existing units into one combined unit."""
    unit_ids: list[str] = Field(..., min_length=2, description="At least 2 unit 3D Property IDs to merge")
    merged_attributes: Optional[dict[str, Any]] = None
    reason: Optional[str] = Field(None, description="Official justification or permit reference for the merge")
    evidence_id: Optional[UUID] = None


class SplitResult(BaseModel):
    """Result of unit split operation."""
    superseded_unit_id: str
    new_units: list[PropertyDetail]


class MergeResult(BaseModel):
    """Result of unit merge operation."""
    superseded_unit_ids: list[str]
    merged_unit: PropertyDetail


class HierarchyNode(BaseModel):
    """Node in the spatial hierarchy tree (parcel -> building -> floor -> unit)."""
    id: UUID
    three_d_property_id: str
    type: str
    status: str
    confidence: float
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    attributes: Optional[dict[str, Any]] = None
    children: list[HierarchyNode] = Field(default_factory=list)


class PropertyHierarchyResponse(BaseModel):
    """Full hierarchical spatial tree starting from the queried property object."""
    root: HierarchyNode
