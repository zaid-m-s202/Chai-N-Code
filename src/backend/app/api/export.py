"""Cadastral & Geospatial Data Export API with PII Redaction (Phase 8).

Provides bulk export capabilities in JSON, CSV, and GeoJSON formats.
Enforces automatic PII redaction by default.
Unmasked PII exports require elevated authorization, mandatory justification,
and create immutable audit event logs.
"""

from datetime import datetime, timezone
import io
import csv
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.api.deps import get_current_user, require_auth
from app.database import get_db
from app.middleware import export_rate_limiter
from app.models.change_event import ChangeEvent
from app.models.property_object import PropertyObject
from app.models.property_record import PropertyRecord
from app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])


def _is_officer_or_admin(user: Optional[User]) -> bool:
    return user is not None and user.role in ("VERIFYING_OFFICER", "ADMIN")


@router.get(
    "/cadastral",
    summary="Bulk export cadastral properties with automatic PII redaction",
    dependencies=[Depends(export_rate_limiter)],
)
def export_cadastral_data(
    format: str = Query("json", pattern="^(json|csv)$", description="Export format: json | csv"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    type_filter: Optional[str] = Query(None, alias="type", description="Filter by property type"),
    include_pii: bool = Query(False, description="Request unmasked owner data (Officers only, requires reason)"),
    reason: Optional[str] = Query(None, description="Official justification for unmasked PII export"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export tabular cadastral property records.

    PII Protection:
    - Default: `owner_party_id` is masked as `[REDACTED]` and sensitive metadata stripped.
    - Unmasked PII requires `VERIFYING_OFFICER`/`ADMIN` role and a non-empty `reason`.
    - Unmasked exports write an immutable audit log entry.
    """
    allow_unmasked = False
    if include_pii:
        if not _is_officer_or_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Unmasked PII export requires VERIFYING_OFFICER or ADMIN role.",
            )
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid official justification 'reason' (min 5 characters) is mandatory for PII export.",
            )
        allow_unmasked = True

    # Query active properties
    query = db.query(PropertyObject).filter(PropertyObject.superseded_by == None)
    if status_filter:
        query = query.filter(PropertyObject.status == status_filter)
    if type_filter:
        query = query.filter(PropertyObject.type == type_filter)

    properties = query.order_by(PropertyObject.three_d_property_id.asc()).limit(1000).all()

    # Pre-fetch legal records
    prop_ids = [p.id for p in properties]
    legal_map: Dict[UUID, PropertyRecord] = {}
    if prop_ids:
        records = db.query(PropertyRecord).filter(PropertyRecord.property_object_id.in_(prop_ids)).all()
        for r in records:
            legal_map[r.property_object_id] = r

    export_rows = []
    for p in properties:
        legal = legal_map.get(p.id)
        owner_id = "[REDACTED]"
        if allow_unmasked and legal:
            owner_id = legal.owner_party_id
        elif not legal:
            owner_id = "UNLINKED"

        row = {
            "three_d_property_id": p.three_d_property_id,
            "type": p.type,
            "status": p.status,
            "confidence": round(p.confidence, 4),
            "z_min": p.z_min,
            "z_max": p.z_max,
            "ulpin": legal.ulpin if legal else "UNLINKED",
            "rights_type": legal.rights_type if legal else "NONE",
            "owner_party_id": owner_id,
            "linkage_status": legal.linkage_status if legal else "UNLINKED",
            "source_system": legal.source_system if legal else "NONE",
            "created_at": p.created_at.isoformat(),
        }
        export_rows.append(row)

    # Log PII access in audit events if unmasked
    if allow_unmasked and properties:
        audit_event = ChangeEvent(
            property_object_id=properties[0].id,
            event_type="pii_exported",
            old_state=None,
            new_state={
                "exported_records_count": len(export_rows),
                "reason": reason.strip(),
                "format": format,
            },
            actor_id=current_user.id,
        )
        db.add(audit_event)
        db.commit()

    if format == "csv":
        output = io.StringIO()
        if export_rows:
            writer = csv.DictWriter(output, fieldnames=list(export_rows[0].keys()))
            writer.writeheader()
            writer.writerows(export_rows)
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=cadastral_export_{int(datetime.now(timezone.utc).timestamp())}.csv"},
        )

    return {
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(export_rows),
            "pii_redacted": not allow_unmasked,
            "format": format,
        },
        "records": export_rows,
    }


@router.get(
    "/geojson",
    summary="Bulk export 3D spatial features as GeoJSON with PII sanitization",
    dependencies=[Depends(export_rate_limiter)],
)
def export_geojson_features(
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    db: Session = Depends(get_db),
):
    """Export 3D cadastral spatial layers as a standard GeoJSON FeatureCollection.

    Sanitized: All sensitive owner data is excluded.
    """
    query = db.query(PropertyObject).filter(PropertyObject.superseded_by == None)
    if status_filter:
        query = query.filter(PropertyObject.status == status_filter)
    if type_filter:
        query = query.filter(PropertyObject.type == type_filter)

    properties = query.limit(1000).all()

    features = []
    for p in properties:
        geom = None
        if p.attributes and "geojson_geometry" in p.attributes:
            geom = p.attributes.get("geojson_geometry")
        elif p.geometry is not None:
            try:
                geom = to_shape(p.geometry).__geo_interface__
            except Exception:
                geom = None

        if geom:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": str(p.id),
                    "three_d_property_id": p.three_d_property_id,
                    "type": p.type,
                    "status": p.status,
                    "confidence": p.confidence,
                    "z_min": p.z_min,
                    "z_max": p.z_max,
                    "height": ((p.z_max or 0) - (p.z_min or 0)) if p.z_max is not None else None,
                },
            })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
            "crs": "urn:ogc:def:crs:OGC:1.3:CRS84",
        },
        "features": features,
    }
