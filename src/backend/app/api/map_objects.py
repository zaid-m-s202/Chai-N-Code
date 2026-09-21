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


@router.get("/units")
def get_map_units(
    type: Optional[str] = Query(None, description="Filter by object type: building, floor, unit"),
    limit: int = Query(50000, ge=1, le=100000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return unit-level GeoJSON FeatureCollection for 3D MapLibre rendering.

    Produces features with the exact properties the frontend fill-extrusion
    layer expects: height, z_min, z_max, floor_number, building_id, ULPIN, etc.
    """
    query = db.query(PropertyObject).filter(
        PropertyObject.superseded_by.is_(None),
        PropertyObject.type.in_(("building", "floor", "unit") if type is None else (type,)),
        PropertyObject.attributes.like("%geojson_geometry%"),
    )

    props = query.limit(limit).all()
    features = []

    for p in props:
        # Extract geometry — prefer the stored GeoJSON dict over WKB
        geom = None
        if p.attributes and "geojson_geometry" in p.attributes:
            geom = p.attributes.get("geojson_geometry")
        elif p.geometry is not None:
            try:
                geom = to_shape(p.geometry).__geo_interface__
            except Exception:
                geom = None

        if geom is None:
            continue  # skip features without displayable geometry

        attrs = p.attributes or {}

        # Merge all stored attributes and override with authoritative columns
        feature_props: dict[str, Any] = {
            **attrs,
            "id": str(p.id),
            "three_d_property_id": p.three_d_property_id,
            "type": p.type,
            "status": p.status,
            "confidence": p.confidence,
            "z_min": p.z_min if p.z_min is not None else attrs.get("z_min"),
            "z_max": p.z_max if p.z_max is not None else attrs.get("z_max"),
            "height": attrs.get("height", 3.0),
            "floor_number": attrs.get("floor_number", 1),
            "building_id": attrs.get("building_id") or attrs.get("parent_building_id"),
            "ULPIN": attrs.get("ULPIN") or attrs.get("ulpin"),
            "UIPIN": attrs.get("UIPIN") or p.three_d_property_id,
        }

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": feature_props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "database",
            "count": len(features),
        },
    }


@router.get("/underground")
def get_underground_map_objects(
    category: Optional[str] = Query(None, description="Filter by utility category: METRO, UTIL, SEWER, WATER, GAS, POWER, PARKING"),
    limit: int = Query(5000, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return subterranean / underground infrastructure features for 3D subsurface mapping.

    Includes tunnels, utility conduits, basement parking, and subsurface easements.
    """
    underground_types = ("underground_utility", "subsurface_parcel", "tunnel", "parking_basement")
    query = db.query(PropertyObject).filter(
        PropertyObject.superseded_by.is_(None),
        (
            PropertyObject.type.in_(underground_types)
            | (PropertyObject.stratum == "SUBTERRANEAN")
            | (PropertyObject.z_max < 0)
        ),
    )

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

        if geom is None:
            continue

        attrs = p.attributes or {}
        z_min = p.z_min if p.z_min is not None else float(attrs.get("z_min", -10.0))
        z_max = p.z_max if p.z_max is not None else float(attrs.get("z_max", -5.0))
        depth_m = abs(z_max) if z_max <= 0 else 0.0
        thickness_m = abs(z_max - z_min)

        infra_category = attrs.get("category", "UTILITY")
        if category and infra_category.upper() != category.upper():
            continue

        feature_props = {
            **attrs,
            "id": str(p.id),
            "three_d_property_id": p.three_d_property_id,
            "type": p.type,
            "stratum": "SUBTERRANEAN",
            "status": p.status,
            "confidence": p.confidence,
            "z_min": z_min,
            "z_max": z_max,
            "depth_below_surface_m": depth_m,
            "thickness_m": thickness_m,
            "volume_m3": p.volume_m3 or attrs.get("volume_m3", round(thickness_m * 100.0, 2)),
            "category": infra_category,
            "utility_type": attrs.get("utility_type", p.type),
            "easement_status": attrs.get("easement_status", "RECORDED"),
        }

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": feature_props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "underground_cadastre",
            "count": len(features),
        },
    }


@router.get("/volumetric")
def get_volumetric_cadastre(
    stratum: Optional[str] = Query(None, description="Filter by stratum: SURFACE, ABOVE_GROUND, SUBTERRANEAN"),
    limit: int = Query(10000, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return all volumetric cadastre parcels across surface, above-ground, and subterranean strata.

    Includes cubic volume measurements (m³), 3D ULPINs, vertical Z-bands, and legal rights.
    """
    query = db.query(PropertyObject).filter(
        PropertyObject.superseded_by.is_(None)
    )
    if stratum:
        query = query.filter(PropertyObject.stratum == stratum.upper())

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

        if geom is None:
            continue

        attrs = p.attributes or {}
        z_min = p.z_min if p.z_min is not None else float(attrs.get("z_min", 0.0))
        z_max = p.z_max if p.z_max is not None else float(attrs.get("z_max", 0.0))
        
        detected_stratum = p.stratum or attrs.get("stratum")
        if not detected_stratum:
            if z_max < 0:
                detected_stratum = "SUBTERRANEAN"
            elif z_min > 0 or p.type in ("building", "floor", "unit"):
                detected_stratum = "ABOVE_GROUND"
            else:
                detected_stratum = "SURFACE"

        feature_props = {
            **attrs,
            "id": str(p.id),
            "three_d_property_id": p.three_d_property_id,
            "type": p.type,
            "stratum": detected_stratum,
            "status": p.status,
            "confidence": p.confidence,
            "z_min": z_min,
            "z_max": z_max,
            "height": max(0.0, z_max - z_min),
            "volume_m3": p.volume_m3 or attrs.get("volume_m3", 0.0),
            "floor_number": attrs.get("floor_number", 1),
            "building_id": attrs.get("building_id") or attrs.get("parent_building_id"),
        }

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": feature_props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "volumetric_cadastre",
            "stratum_filter": stratum,
            "count": len(features),
        },
    }

