"""Conflict dashboard, topology validation runner, and officer verification queue.

Maps to PRD §5.6 (VR-01 through VR-09) and §5.10 (Verification queue).
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_verifying_officer
from app.database import get_db
from app.models.conflict import Conflict
from app.models.property_object import PropertyObject
from app.models.user import User
from app.schemas.conflicts import ConflictResponse
from app.schemas.properties import PropertySummary
from app.services.topology_runner import run_all_topology_checks

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("", response_model=list[ConflictResponse])
def list_conflicts(
    status: Optional[str] = Query("OPEN", description="Filter by status (OPEN, RESOLVED, WAIVED, ALL)"),
    rule_code: Optional[str] = Query(None, description="Filter by rule code (e.g. VR-01)"),
    db: Session = Depends(get_db),
):
    """Retrieve conflicts across ingested properties for officer review."""
    query = db.query(Conflict)
    if status and status.upper() != "ALL":
        query = query.filter(Conflict.status == status.upper())
    if rule_code:
        query = query.filter(Conflict.rule_code == rule_code.upper())
    return query.order_by(Conflict.created_at.desc()).limit(200).all()


@router.post("/run-topology")
def run_topology_validation(
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute all deterministic topology rules (VR-01 through VR-07).

    VR-08: Failed rules create Conflict records.
    VR-09: Conflicts block VERIFIED status but do not block ingestion.
    """
    result = run_all_topology_checks(db)
    return result


@router.post("/{conflict_id}/resolve", response_model=ConflictResponse)
def resolve_conflict(
    conflict_id: UUID,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Resolve an active conflict record after officer review."""
    conflict = db.query(Conflict).filter(Conflict.id == conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")
    if conflict.status != "OPEN":
        raise HTTPException(
            status_code=400,
            detail=f"Conflict is already {conflict.status}",
        )

    conflict.status = "RESOLVED"
    conflict.resolved_at = datetime.now(timezone.utc)
    conflict.resolved_by = officer.id
    db.commit()
    db.refresh(conflict)
    return conflict


@router.post("/{conflict_id}/waive", response_model=ConflictResponse)
def waive_conflict(
    conflict_id: UUID,
    officer: User = Depends(require_verifying_officer),
    db: Session = Depends(get_db),
):
    """Waive a conflict (acknowledge but mark as non-blocking)."""
    conflict = db.query(Conflict).filter(Conflict.id == conflict_id).first()
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id} not found")
    if conflict.status != "OPEN":
        raise HTTPException(
            status_code=400,
            detail=f"Conflict is already {conflict.status}",
        )

    conflict.status = "WAIVED"
    conflict.resolved_at = datetime.now(timezone.utc)
    conflict.resolved_by = officer.id
    db.commit()
    db.refresh(conflict)
    return conflict


@router.get("/verification-queue", response_model=list[PropertySummary])
def verification_queue(
    limit: int = Query(50, ge=1, le=200),
    has_conflicts: Optional[bool] = Query(None, description="Filter by presence of open conflicts"),
    db: Session = Depends(get_db),
):
    """Officer review queue: PROVISIONAL records awaiting verification (PRD §5.10).

    Returns properties that are PROVISIONAL, optionally filtered by open conflicts.
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
