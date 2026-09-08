"""Search endpoints for 3D Property IDs and ULPIN."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.property_object import PropertyObject
from app.schemas.properties import PropertySummary

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[PropertySummary])
def search_properties(
    q: str = Query(..., min_length=1, description="Search term (ULPIN, 3D Property ID, or type)"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Search for property objects matching query string."""
    term = f"%{q.strip()}%"
    results = db.query(PropertyObject).filter(
        PropertyObject.superseded_by.is_(None),
        (
            PropertyObject.three_d_property_id.ilike(term)
            | PropertyObject.type.ilike(term)
        )
    ).limit(limit).all()

    return [
        PropertySummary(
            three_d_property_id=r.three_d_property_id,
            type=r.type,
            status=r.status,
            confidence=r.confidence,
        )
        for r in results
    ]
