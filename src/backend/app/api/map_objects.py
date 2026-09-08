"""Map endpoints for 2D/3D viewer GeoJSON layers."""

from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.database import get_db
from app.models.property_object import PropertyObject

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/objects")
def get_map_objects(
    bbox: Optional[str] = Query(None, description="Bounding box formatted as 'minLon,minLat,maxLon,maxLat'"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve map objects as a GeoJSON FeatureCollection for MapLibre/Cesium."""
    query = db.query(PropertyObject).filter(PropertyObject.superseded_by.is_(None))

    props = query.limit(limit).all()
    features = []

    for p in props:
        geom = None
        if p.attributes and "geojson_geometry" in p.attributes:
            geom = p.attributes.get("geojson_geometry")
        elif p.geometry is not None:
            try:
                geom = to_shape(p.geometry).__geo_interface__
            except Exception:
                geom = None

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
                "attributes": p.attributes,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
