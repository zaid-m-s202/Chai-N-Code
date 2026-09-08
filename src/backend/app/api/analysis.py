"""AI/GIS analysis endpoints (PRD §5.4).

Provides REST interfaces for:
- Discovering registered analysis adapters
- Standalone execution of DSM-DEM height, floor estimation, and footprint vectorization
- On-demand property analysis pipeline triggering with status gating and provenance logging
"""

import uuid
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.analysis.service import analysis_service
from app.api.deps import get_db, get_current_user
from app.models.property_object import PropertyObject
from app.models.user import User
from app.schemas.analysis import (
    AdapterInfoResponse,
    DsmDemHeightRequest,
    FloorEstimatorRequest,
    FootprintExtractionRequest,
    AnalysisResultResponse,
    PropertyAnalysisRequest,
    PropertyAnalysisResponse,
)

router = APIRouter(tags=["analysis"])


@router.get("/analysis/adapters", response_model=list[AdapterInfoResponse])
def list_analysis_adapters():
    """List all available AI/GIS analysis adapters and their input capabilities."""
    return analysis_service.list_adapters()


@router.post("/analysis/dsm-dem-height", response_model=AnalysisResultResponse)
def execute_dsm_dem_height(payload: DsmDemHeightRequest):
    """Calculate building height from DSM (surface) minus DEM (terrain).
    
    Status gating: Returns status DERIVED, never VERIFIED.
    """
    try:
        input_data = payload.model_dump(exclude_none=True)
        result = analysis_service.run_adapter("dsm_dem_height", input_data)
        return AnalysisResultResponse(
            adapter_name=result.adapter_name,
            adapter_version=result.adapter_version,
            status=result.status,
            confidence=result.confidence,
            data=result.data,
            evidence=result.evidence,
            warnings=result.warnings,
            executed_at=result.executed_at,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/analysis/estimate-floors", response_model=AnalysisResultResponse)
def execute_floor_estimator(payload: FloorEstimatorRequest):
    """Infer floor count and vertical intervals [z_min, z_max] from height heuristic.
    
    Status gating: Returns status INFERRED, never VERIFIED.
    """
    try:
        input_data = payload.model_dump(exclude_none=True)
        result = analysis_service.run_adapter("floor_estimator", input_data)
        return AnalysisResultResponse(
            adapter_name=result.adapter_name,
            adapter_version=result.adapter_version,
            status=result.status,
            confidence=result.confidence,
            data=result.data,
            evidence=result.evidence,
            warnings=result.warnings,
            executed_at=result.executed_at,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/analysis/extract-footprints", response_model=AnalysisResultResponse)
def execute_footprint_extraction(payload: FootprintExtractionRequest):
    """Infers building footprint polygon from parcel geometry, bbox, or raster mask.
    
    Status gating: Returns status INFERRED, never VERIFIED.
    """
    try:
        input_data = payload.model_dump(exclude_none=True)
        result = analysis_service.run_adapter("pretrained_footprint_extractor", input_data)
        return AnalysisResultResponse(
            adapter_name=result.adapter_name,
            adapter_version=result.adapter_version,
            status=result.status,
            confidence=result.confidence,
            data=result.data,
            evidence=result.evidence,
            warnings=result.warnings,
            executed_at=result.executed_at,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/properties/{property_id}/analyze", response_model=PropertyAnalysisResponse)
def analyze_property_endpoint(
    property_id: str,
    payload: PropertyAnalysisRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute full AI/GIS analysis pipeline on a target property.
    
    Updates vertical metrics (z_min, z_max) and attaches observation provenance.
    Strict status gating: Never upgrades property to VERIFIED.
    """
    # Lookup by UUID or three_d_property_id
    prop = None
    try:
        prop_uuid = uuid.UUID(property_id)
        prop = db.query(PropertyObject).filter(PropertyObject.id == prop_uuid).first()
    except ValueError:
        pass

    if not prop:
        prop = db.query(PropertyObject).filter(
            PropertyObject.three_d_property_id == property_id
        ).first()

    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property '{property_id}' not found",
        )

    try:
        operator_id = current_user.id if current_user else None
        res = analysis_service.analyze_property(
            db=db,
            property_id=prop.id,
            elevation_data=payload.elevation_data,
            use_type=payload.use_type,
            operator_id=operator_id,
        )
        return PropertyAnalysisResponse(**res)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
