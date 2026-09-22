"""Property endpoints: CRUD, history, verification and rejection."""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.api.deps import require_verifying_officer
from app.database import get_db
from app.models.property_object import PropertyObject
from app.models.change_event import ChangeEvent
from app.models.conflict import Conflict
from app.models.evidence import Evidence
from app.models.source_observation import SourceObservation
from app.models.user import User
from app.schemas.properties import (
    PropertySummary,
    PropertyDetail,
    PropertyHistoryResponse,
    ChangeEventResponse,
    VerifyRequest,
    ObservationResponse,
    RefuseResponse,
)
from app.schemas.evidence import EvidenceResponse
from app.schemas.lifecycle import (
    SplitRequest,
    MergeRequest,
    SplitResult,
    MergeResult,
    PropertyHierarchyResponse,
)
from app.services.fusion import Observation as FusionObservation, fuse_attribute
from app.services.lifecycle import split_unit, merge_units, build_hierarchy_tree

router = APIRouter(tags=["properties"])


def _property_to_detail(prop: PropertyObject) -> PropertyDetail:
    geom_geojson = None
    if prop.attributes and "geojson_geometry" in prop.attributes:
        geom_geojson = prop.attributes.get("geojson_geometry")
    elif prop.geometry is not None:
        try:
            geom_geojson = to_shape(prop.geometry).__geo_interface__
        except Exception:
            geom_geojson = None

    return PropertyDetail(
        id=prop.id,
        three_d_property_id=prop.three_d_property_id,
        type=prop.type,
        parent_id=prop.parent_id,
        geometry=geom_geojson,
        z_min=prop.z_min,
        z_max=prop.z_max,
        attributes=prop.attributes,
        confidence=prop.confidence,
        status=prop.status,
        source_list=prop.source_list,
        created_at=prop.created_at,
        superseded_by=prop.superseded_by,
        ulpin=getattr(prop, "ulpin", None),
        stratum=getattr(prop, "stratum", "SURFACE"),
        volume_m3=getattr(prop, "volume_m3", None),
    )



@router.get("/properties", response_model=list[PropertySummary])
def list_properties(
    status: Optional[str] = Query(None, description="Filter by status (e.g. PROVISIONAL, VERIFIED)"),
    type: Optional[str] = Query(None, description="Filter by type (parcel, building, floor, unit)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List property objects with optional filters."""
    query = db.query(PropertyObject).filter(PropertyObject.superseded_by.is_(None))
    if status:
        query = query.filter(PropertyObject.status == status.upper())
    if type:
        query = query.filter(PropertyObject.type == type.lower())
    records = query.order_by(PropertyObject.created_at.desc()).offset(offset).limit(limit).all()

    return [
        PropertySummary(
            three_d_property_id=r.three_d_property_id,
            type=r.type,
            status=r.status,
            confidence=r.confidence,
        )
        for r in records
    ]


@router.get("/verification-queue", response_model=list[PropertySummary])
@router.get("/properties/verification-queue", response_model=list[PropertySummary])
def get_verification_queue(
    limit: int = Query(50, ge=1, le=200),
    has_conflicts: Optional[bool] = Query(None, description="Filter by presence of open conflicts (True/False/None)"),
    db: Session = Depends(get_db),
):
    """Officer review queue: PROVISIONAL records awaiting verification (PRD §5.10).

    Lists PROVISIONAL records, optionally filtered by whether they have open conflicts.
    """
    from sqlalchemy import select

    conflict_subq = (
        select(Conflict.property_object_id)
        .filter(Conflict.status == "OPEN")
    )

    query = db.query(PropertyObject).filter(
        PropertyObject.status == "PROVISIONAL",
        PropertyObject.superseded_by.is_(None),
    )

    if has_conflicts is True:
        query = query.filter(PropertyObject.id.in_(conflict_subq))
    elif has_conflicts is False:
        query = query.filter(PropertyObject.id.notin_(conflict_subq))

    props = query.order_by(PropertyObject.created_at.desc()).limit(limit).all()

    return [
        PropertySummary(
            three_d_property_id=p.three_d_property_id,
            type=p.type,
            status=p.status,
            confidence=p.confidence,
        )
        for p in props
    ]


@router.get("/properties/{three_d_property_id}", response_model=PropertyDetail)
def get_property(three_d_property_id: str, db: Session = Depends(get_db)):
    """Retrieve full spatial and semantic details of a property object."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {three_d_property_id} not found",
        )
    return _property_to_detail(prop)


@router.get("/properties/{three_d_property_id}/history", response_model=PropertyHistoryResponse)
def property_history(three_d_property_id: str, db: Session = Depends(get_db)):
    """Retrieve immutable event-sourced audit trail for a property object (PRD §5.9)."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {three_d_property_id} not found",
        )

    events = db.query(ChangeEvent).filter(
        ChangeEvent.property_object_id == prop.id
    ).order_by(ChangeEvent.created_at.asc()).all()

    return PropertyHistoryResponse(
        three_d_property_id=three_d_property_id,
        events=[
            ChangeEventResponse(
                id=e.id,
                event_type=e.event_type,
                old_state=e.old_state,
                new_state=e.new_state,
                actor_id=e.actor_id,
                evidence_id=e.evidence_id,
                created_at=e.created_at,
            )
            for e in events
        ],
    )


@router.get("/properties/{three_d_property_id}/evidence", response_model=list[EvidenceResponse])
def get_property_evidence(three_d_property_id: str, db: Session = Depends(get_db)):
    """Retrieve all provenance evidence records linked to a property object (Phase 1 Acceptance)."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {three_d_property_id} not found",
        )

    evidence_records = db.query(Evidence).filter(
        Evidence.property_object_id == prop.id
    ).order_by(Evidence.created_at.desc()).all()

    return evidence_records


@router.post("/properties/{three_d_property_id}/verify", response_model=PropertyDetail)
def verify_property(
    three_d_property_id: str,
    payload: Optional[VerifyRequest] = None,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Verifying officer confirms provisional record against authoritative evidence.

    VR-09: Unresolved conflicts block VERIFIED status.
    PRD §5.7: AI derives, evidence supports, authority verifies.
    """
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {three_d_property_id} not found")

    # Check for active blocking conflicts (PRD VR-09)
    open_conflicts = db.query(Conflict).filter(
        Conflict.property_object_id == prop.id,
        Conflict.status == "OPEN",
    ).count()
    if open_conflicts > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot verify property with {open_conflicts} open conflict(s). Resolve conflicts first.",
        )

    old_status = prop.status
    prop.status = "VERIFIED"
    prop.confidence = 1.0  # Officer verification grants full authoritative confidence

    # Record immutable audit event
    evidence_id = payload.evidence_id if payload else None
    audit_event = ChangeEvent(
        property_object_id=prop.id,
        event_type="verified",
        old_state={"status": old_status},
        new_state={"status": "VERIFIED", "notes": payload.notes if payload else None},
        actor_id=officer.id,
        evidence_id=evidence_id,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(prop)
    return _property_to_detail(prop)


@router.post("/properties/{three_d_property_id}/reject", response_model=PropertyDetail)
def reject_property(
    three_d_property_id: str,
    payload: Optional[VerifyRequest] = None,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Verifying officer rejects a provisional record."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {three_d_property_id} not found")

    old_status = prop.status
    prop.status = "PROVISIONAL"  # Kept provisional or flagged

    audit_event = ChangeEvent(
        property_object_id=prop.id,
        event_type="rejected",
        old_state={"status": old_status},
        new_state={"status": "PROVISIONAL", "notes": payload.notes if payload else None},
        actor_id=officer.id,
        evidence_id=payload.evidence_id if payload else None,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(prop)
    return _property_to_detail(prop)


@router.get("/properties/{three_d_property_id}/observations", response_model=list[ObservationResponse])
def get_property_observations(three_d_property_id: str, db: Session = Depends(get_db)):
    """Retrieve all preserved raw source observations for a property (FR-FUS-01 / Phase 2 Acceptance)."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {three_d_property_id} not found")

    observations = db.query(SourceObservation).filter(
        SourceObservation.property_object_id == prop.id
    ).order_by(SourceObservation.observed_at.desc()).all()
    return observations


@router.post("/properties/{three_d_property_id}/refuse", response_model=RefuseResponse)
def refuse_property_observations(three_d_property_id: str, db: Session = Depends(get_db)):
    """Re-execute multi-source observation fusion across all preserved raw observations (FR-FUS-05)."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {three_d_property_id} not found")

    obs_records = db.query(SourceObservation).filter(
        SourceObservation.property_object_id == prop.id,
        SourceObservation.attribute_name == "height",
    ).all()

    if not obs_records:
        return RefuseResponse(
            three_d_property_id=three_d_property_id,
            fused_height=prop.attributes.get("height") if prop.attributes else None,
            fused_confidence=prop.confidence,
            has_conflict=False,
            conflict_reason=None,
            observations_count=0,
        )

    fusion_list = [
        FusionObservation(
            value=float(o.observed_value.get("value", 0.0) if isinstance(o.observed_value, dict) else o.observed_value),
            source_confidence=o.source_confidence,
            observed_at=o.observed_at.replace(tzinfo=None) if o.observed_at else datetime.utcnow(),
            source_id=o.source_id,
        )
        for o in obs_records
    ]

    fusion_result = fuse_attribute(fusion_list)
    old_height = prop.attributes.get("height") if prop.attributes else None
    if prop.attributes is None:
        prop.attributes = {}
    prop.attributes["height"] = fusion_result.fused_value
    prop.confidence = fusion_result.fused_confidence

    if fusion_result.has_conflict:
        existing_conflict = db.query(Conflict).filter(
            Conflict.property_object_id == prop.id,
            Conflict.rule_code == "VR-FUS-01",
            Conflict.status == "OPEN",
        ).first()
        if not existing_conflict:
            conflict = Conflict(
                property_object_id=prop.id,
                rule_code="VR-FUS-01",
                description=fusion_result.conflict_reason,
                severity="WARNING",
                status="OPEN",
            )
            db.add(conflict)

    change_event = ChangeEvent(
        property_object_id=prop.id,
        event_type="refused",
        old_state={"height": old_height},
        new_state={
            "height": fusion_result.fused_value,
            "confidence": fusion_result.fused_confidence,
            "has_conflict": fusion_result.has_conflict,
            "observations_count": fusion_result.observations_count,
        },
    )
    db.add(change_event)
    db.commit()
    db.refresh(prop)

    return RefuseResponse(
        three_d_property_id=three_d_property_id,
        fused_height=fusion_result.fused_value,
        fused_confidence=fusion_result.fused_confidence,
        has_conflict=fusion_result.has_conflict,
        conflict_reason=fusion_result.conflict_reason,
        observations_count=fusion_result.observations_count,
    )


@router.get("/properties/{three_d_property_id}/hierarchy", response_model=PropertyHierarchyResponse)
def get_property_hierarchy(three_d_property_id: str, db: Session = Depends(get_db)):
    """Retrieve the full 3D spatial hierarchy tree (parcel -> building -> floor -> unit)."""
    prop = db.query(PropertyObject).filter(
        PropertyObject.three_d_property_id == three_d_property_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property '{three_d_property_id}' not found")

    tree = build_hierarchy_tree(db, prop)
    return PropertyHierarchyResponse(root=tree)


@router.post("/properties/{three_d_property_id}/split", response_model=SplitResult)
def split_property_unit(
    three_d_property_id: str,
    payload: SplitRequest,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Split an existing unit into multiple new units.
    
    Rule FR-3D-06: Never reuses old IDs.
    Rule FR-3D-07: Split creates new IDs and soft-retires original unit.
    """
    try:
        parent_unit, new_units = split_unit(
            db=db,
            target_property_id=three_d_property_id,
            split_specs=payload.split_units,
            actor_id=officer.id,
            evidence_id=payload.evidence_id,
            reason=payload.reason,
        )
        return SplitResult(
            superseded_unit_id=parent_unit.three_d_property_id,
            new_units=[_property_to_detail(u) for u in new_units],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/properties/merge", response_model=MergeResult)
def merge_property_units(
    payload: MergeRequest,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Merge two or more existing units into one combined unit.
    
    Rule FR-3D-06: Never reuses old IDs.
    Rule FR-3D-07: Merge creates new ID and soft-retires original units.
    """
    try:
        old_units, merged_unit = merge_units(
            db=db,
            unit_ids=payload.unit_ids,
            merged_attributes=payload.merged_attributes,
            actor_id=officer.id,
            evidence_id=payload.evidence_id,
            reason=payload.reason,
        )
        return MergeResult(
            superseded_unit_ids=[u.three_d_property_id for u in old_units],
            merged_unit=_property_to_detail(merged_unit),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


