"""Audit Log Review & Compliance API (Phase 8).

Provides structured query and aggregation capabilities across the
immutable change_events event-sourced history.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import require_verifying_officer
from app.database import get_db
from app.models.change_event import ChangeEvent
from app.models.user import User
from app.schemas.properties import ChangeEventResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/events",
    response_model=List[ChangeEventResponse],
    summary="Query audit change events with compliance filters",
)
def list_audit_events(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. verified, legal_linked)"),
    property_id: Optional[UUID] = Query(None, description="Filter by target property UUID"),
    actor_id: Optional[UUID] = Query(None, description="Filter by actor UUID"),
    date_from: Optional[datetime] = Query(None, description="Filter events on or after ISO timestamp"),
    date_to: Optional[datetime] = Query(None, description="Filter events on or before ISO timestamp"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verifying_officer),
):
    """Retrieve immutable audit logs.

    Protected: Only authenticated Verifying Officers or Admins can review full audit logs.
    """
    query = db.query(ChangeEvent)

    if event_type:
        query = query.filter(ChangeEvent.event_type == event_type)
    if property_id:
        query = query.filter(ChangeEvent.property_object_id == property_id)
    if actor_id:
        query = query.filter(ChangeEvent.actor_id == actor_id)
    if date_from:
        query = query.filter(ChangeEvent.created_at >= date_from)
    if date_to:
        query = query.filter(ChangeEvent.created_at <= date_to)

    events = query.order_by(ChangeEvent.created_at.desc()).offset(offset).limit(limit).all()

    return [
        ChangeEventResponse(
            id=e.id,
            property_object_id=e.property_object_id,
            event_type=e.event_type,
            old_state=e.old_state,
            new_state=e.new_state,
            actor_id=e.actor_id,
            evidence_id=e.evidence_id,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get(
    "/summary",
    summary="Aggregate summary of audit events and compliance metrics",
)
def get_audit_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verifying_officer),
):
    """Return aggregated audit event statistics.

    Protected: Verifying Officer or Admin only.
    """
    # Group by event_type
    type_counts = (
        db.query(ChangeEvent.event_type, func.count(ChangeEvent.id))
        .group_by(ChangeEvent.event_type)
        .all()
    )
    event_distribution = {etype: count for etype, count in type_counts}
    total_events = sum(event_distribution.values())

    # Count distinct active actors
    distinct_actors = (
        db.query(func.count(func.distinct(ChangeEvent.actor_id)))
        .filter(ChangeEvent.actor_id != None)
        .scalar()
        or 0
    )

    # Most recent 5 events
    latest = (
        db.query(ChangeEvent)
        .order_by(ChangeEvent.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "total_audit_events": total_events,
        "distinct_actors_count": distinct_actors,
        "event_distribution": event_distribution,
        "latest_events": [
            {
                "id": str(e.id),
                "property_object_id": str(e.property_object_id),
                "event_type": e.event_type,
                "actor_id": str(e.actor_id) if e.actor_id else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in latest
        ],
    }
