"""Legal and Cadastral Registry Linkage API (Phase 7).

Endpoints for managing property records, ULPIN linkages, encumbrances,
and rights types. Protects owner identity behind strict RBAC and
creates immutable change_events audit logs on every mutation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_legal_access
from app.database import get_db
from app.models.change_event import ChangeEvent
from app.models.property_object import PropertyObject
from app.models.property_record import PropertyRecord
from app.models.user import User
from app.schemas.legal import (
    PropertyRecordCreate,
    PropertyRecordRedactedResponse,
    PropertyRecordResponse,
    PropertyRecordUpdate,
)

router = APIRouter(prefix="/legal", tags=["legal"])


def _is_officer_or_admin(user: Optional[User]) -> bool:
    """Check if the requesting user has elevated officer or admin permissions."""
    return user is not None and user.role in ("VERIFYING_OFFICER", "ADMIN")


def _format_record(
    record: PropertyRecord, is_officer: bool
) -> Union[PropertyRecordResponse, PropertyRecordRedactedResponse]:
    """Return full or redacted record depending on user authorization."""
    if is_officer:
        return PropertyRecordResponse.model_validate(record)
    return PropertyRecordRedactedResponse(
        id=record.id,
        property_object_id=record.property_object_id,
        three_d_property_id=record.three_d_property_id,
        ulpin=record.ulpin,
        owner_party_id="[PROTECTED — OFFICER ACCESS ONLY]",
        registration_number=record.registration_number,
        registration_date=record.registration_date,
        rights_type=record.rights_type,
        encumbrances=record.encumbrances or [],
        linkage_status=record.linkage_status,
        source_system=record.source_system,
        sync_time=record.sync_time,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        is_redacted=True,
    )


@router.post(
    "/records",
    response_model=PropertyRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or link a legal property record",
)
def create_property_record(
    payload: PropertyRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_legal_access),
):
    """Link a spatial PropertyObject with an authoritative land registry record.

    Protected: Only VERIFYING_OFFICER or ADMIN can create legal linkages.
    Produces an immutable change_event audit log entry.
    """
    # 1. Verify that the spatial PropertyObject exists
    prop = db.query(PropertyObject).filter(PropertyObject.id == payload.property_object_id).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyObject with ID {payload.property_object_id} does not exist",
        )

    # 2. Check if a record already exists with the same ULPIN and property_object_id
    existing = (
        db.query(PropertyRecord)
        .filter(
            PropertyRecord.property_object_id == payload.property_object_id,
            PropertyRecord.ulpin == payload.ulpin,
            PropertyRecord.linkage_status != "UNLINKED",
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active legal linkage already exists for ULPIN '{payload.ulpin}' on property '{prop.three_d_property_id}'",
        )

    now = datetime.now(timezone.utc)
    record = PropertyRecord(
        property_object_id=prop.id,
        three_d_property_id=prop.three_d_property_id,
        ulpin=payload.ulpin,
        owner_party_id=payload.owner_party_id,
        registration_number=payload.registration_number,
        registration_date=payload.registration_date,
        rights_type=payload.rights_type,
        encumbrances=payload.encumbrances or [],
        linkage_status=payload.linkage_status,
        source_system=payload.source_system,
        sync_time=now,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.flush()

    # 3. Create immutable audit ChangeEvent
    audit_event = ChangeEvent(
        property_object_id=prop.id,
        event_type="legal_linked",
        old_state=None,
        new_state={
            "legal_record_id": str(record.id),
            "ulpin": record.ulpin,
            "rights_type": record.rights_type,
            "linkage_status": record.linkage_status,
            "source_system": record.source_system,
            "encumbrance_count": len(record.encumbrances or []),
        },
        actor_id=current_user.id,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(record)

    return PropertyRecordResponse.model_validate(record)


@router.get(
    "/records",
    response_model=List[Union[PropertyRecordResponse, PropertyRecordRedactedResponse]],
    summary="List or search legal records with RBAC protection",
)
def list_property_records(
    ulpin: Optional[str] = Query(None, description="Filter by ULPIN"),
    three_d_property_id: Optional[str] = Query(None, description="Filter by 3D Property ID"),
    linkage_status: Optional[str] = Query(None, description="Filter by linkage status"),
    rights_type: Optional[str] = Query(None, description="Filter by rights type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List legal records.

    Role-aware: VERIFYING_OFFICER/ADMIN see full owner data; all others see redacted data.
    """
    query = db.query(PropertyRecord)
    if ulpin:
        query = query.filter(PropertyRecord.ulpin == ulpin)
    if three_d_property_id:
        query = query.filter(PropertyRecord.three_d_property_id == three_d_property_id)
    if linkage_status:
        query = query.filter(PropertyRecord.linkage_status == linkage_status)
    if rights_type:
        query = query.filter(PropertyRecord.rights_type == rights_type)

    records = query.order_by(PropertyRecord.created_at.desc()).offset(offset).limit(limit).all()
    is_officer = _is_officer_or_admin(current_user)

    return [_format_record(r, is_officer) for r in records]


@router.get(
    "/records/{id}",
    response_model=Union[PropertyRecordResponse, PropertyRecordRedactedResponse],
    summary="Get single legal record by ID",
)
def get_property_record(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Retrieve a single legal record.

    Protected: Full owner data returned only to VERIFYING_OFFICER or ADMIN.
    """
    record = db.query(PropertyRecord).filter(PropertyRecord.id == id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyRecord with ID {id} not found",
        )
    is_officer = _is_officer_or_admin(current_user)
    return _format_record(record, is_officer)


@router.get(
    "/by-property/{property_id}",
    response_model=List[Union[PropertyRecordResponse, PropertyRecordRedactedResponse]],
    summary="Get all legal records associated with a 3D Property",
)
def get_legal_records_by_property(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Retrieve legal records for a specific PropertyObject.

    Role-aware: Officers see full data, non-officers see redacted owner identity.
    """
    records = (
        db.query(PropertyRecord)
        .filter(PropertyRecord.property_object_id == property_id)
        .order_by(PropertyRecord.created_at.desc())
        .all()
    )
    is_officer = _is_officer_or_admin(current_user)
    return [_format_record(r, is_officer) for r in records]


@router.put(
    "/records/{id}",
    response_model=PropertyRecordResponse,
    summary="Update an existing legal property record",
)
def update_property_record(
    id: UUID,
    payload: PropertyRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_legal_access),
):
    """Update legal record metadata, encumbrances, or linkage status.

    Protected: Only VERIFYING_OFFICER or ADMIN can update legal linkages.
    Generates an immutable change_event audit log entry.
    """
    record = db.query(PropertyRecord).filter(PropertyRecord.id == id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyRecord with ID {id} not found",
        )

    old_state = {
        "ulpin": record.ulpin,
        "rights_type": record.rights_type,
        "linkage_status": record.linkage_status,
        "encumbrance_count": len(record.encumbrances or []),
        "source_system": record.source_system,
    }

    if payload.ulpin is not None:
        record.ulpin = payload.ulpin
    if payload.owner_party_id is not None:
        record.owner_party_id = payload.owner_party_id
    if payload.registration_number is not None:
        record.registration_number = payload.registration_number
    if payload.registration_date is not None:
        record.registration_date = payload.registration_date
    if payload.rights_type is not None:
        record.rights_type = payload.rights_type
    if payload.encumbrances is not None:
        record.encumbrances = payload.encumbrances
    if payload.linkage_status is not None:
        record.linkage_status = payload.linkage_status
    if payload.source_system is not None:
        record.source_system = payload.source_system

    now = datetime.now(timezone.utc)
    record.sync_time = payload.sync_time or now
    record.updated_at = now

    # Audit log
    audit_event = ChangeEvent(
        property_object_id=record.property_object_id,
        event_type="legal_updated",
        old_state=old_state,
        new_state={
            "ulpin": record.ulpin,
            "rights_type": record.rights_type,
            "linkage_status": record.linkage_status,
            "encumbrance_count": len(record.encumbrances or []),
            "source_system": record.source_system,
        },
        actor_id=current_user.id,
    )
    db.add(audit_event)
    db.commit()
    db.refresh(record)

    return PropertyRecordResponse.model_validate(record)


@router.delete(
    "/records/{id}",
    summary="Unlink a legal property record",
)
def unlink_property_record(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_legal_access),
):
    """Mark a legal linkage as UNLINKED (soft-delete).

    Protected: Only VERIFYING_OFFICER or ADMIN can unlink legal records.
    Generates an immutable change_event audit log entry.
    """
    record = db.query(PropertyRecord).filter(PropertyRecord.id == id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyRecord with ID {id} not found",
        )

    old_status = record.linkage_status
    record.linkage_status = "UNLINKED"
    record.updated_at = datetime.now(timezone.utc)

    audit_event = ChangeEvent(
        property_object_id=record.property_object_id,
        event_type="legal_unlinked",
        old_state={"linkage_status": old_status},
        new_state={"linkage_status": "UNLINKED"},
        actor_id=current_user.id,
    )
    db.add(audit_event)
    db.commit()

    return {
        "detail": "Property record unlinked successfully",
        "id": str(record.id),
        "three_d_property_id": record.three_d_property_id,
        "linkage_status": "UNLINKED",
    }
