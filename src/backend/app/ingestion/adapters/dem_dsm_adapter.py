"""DEM (Digital Elevation Model) & DSM (Digital Surface Model) ingestion adapter.

Ingests terrain elevation raster metadata, GeoTIFF headers, or elevation grid samples.
Extracts ground elevation (DEM), canopy/structure elevation (DSM), and calculates
normalized Digital Surface Model (nDSM = DSM - DEM) to determine building heights.

Produces CanonicalRecords with true bare-earth z_min (DEM) and structure top z_max (DSM).
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import box, shape

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    validate_and_repair_geometry,
    normalize_crs,
    CANONICAL_CRS,
)
from app.services.id_generator import generate_base_ulpin


class DemDsmAdapter(IngestionAdapter):
    """Adapter for DEM/DSM elevation models and height grid metadata."""

    def parse(
        self,
        file_content: bytes,
        filename: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[CanonicalRecord]:
        raw_text = file_content.decode("utf-8")
        data = json.loads(raw_text)
        metadata = metadata or {}

        records: list[CanonicalRecord] = []
        source_crs = metadata.get("crs") or "EPSG:4326"

        tiles = []
        if isinstance(data, dict):
            if "tiles" in data:
                tiles = data["tiles"]
            elif data.get("type") == "FeatureCollection":
                tiles = data.get("features", [])
            elif data.get("type") == "Feature":
                tiles = [data]
            else:
                tiles = [data]
        elif isinstance(data, list):
            tiles = data

        for idx, item in enumerate(tiles):
            props = item.get("properties") or item if isinstance(item, dict) else {}
            geom_dict = item.get("geometry") if isinstance(item, dict) else None

            # Elevation metrics: DEM (bare earth), DSM (surface top)
            dem_elevation = float(props.get("dem_elevation_m", props.get("terrain_z", props.get("z_min", 14.5))))
            dsm_elevation = float(props.get("dsm_elevation_m", props.get("surface_z", props.get("z_max", 38.5))))
            ndsm_height = float(props.get("ndsm_height_m", max(0.0, dsm_elevation - dem_elevation)))

            slope_deg = float(props.get("slope_deg", 1.2))
            vertical_datum = props.get("vertical_datum", "EGM2008")
            resolution_m = float(props.get("resolution_m", 0.5))

            shapely_geom = None
            if geom_dict:
                try:
                    raw_geom = shape(geom_dict)
                    repaired = validate_and_repair_geometry(raw_geom)
                    shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    shapely_geom = None
            elif "bbox" in props or "bbox" in item or "bounds" in props:
                bbox = props.get("bbox") or item.get("bbox") or props.get("bounds")
                if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    try:
                        raw_geom = box(bbox[0], bbox[1], bbox[2], bbox[3])
                        repaired = validate_and_repair_geometry(raw_geom)
                        shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                    except Exception:
                        shapely_geom = None

            area_sqm = 0.0
            if shapely_geom and not shapely_geom.is_empty:
                area_sqm = round(shapely_geom.area * (111320.0 ** 2), 2)

            centroid_x = shapely_geom.centroid.x if shapely_geom else 72.85
            centroid_y = shapely_geom.centroid.y if shapely_geom else 19.05
            base_ulpin = generate_base_ulpin("MH", "MUM", centroid_x, centroid_y)

            # Determine whether this tile/feature represents a building (ndsm > 2.5m) or terrain parcel
            is_building = ndsm_height >= 2.5

            records.append(
                CanonicalRecord(
                    ulpin=f"{base_ulpin}-B001-F01-U001" if is_building else f"{base_ulpin}-SURF",
                    object_type="building" if is_building else "parcel",
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else None,
                    z_min=dem_elevation,
                    z_max=dsm_elevation,
                    height=ndsm_height,
                    status="DERIVED",
                    source_confidence=float(props.get("confidence", 0.92)),
                    attributes={
                        "sensor_modality": "dem_dsm_elevation_model",
                        "raw_id": str(props.get("id") or f"dem-tile-{idx + 1}"),
                        "name": props.get("name") or f"Elevation Grid Cell {idx + 1} (H={ndsm_height:.1f}m)",
                        "dem_bare_earth_m": dem_elevation,
                        "dsm_surface_m": dsm_elevation,
                        "ndsm_structure_height_m": ndsm_height,
                        "slope_deg": slope_deg,
                        "vertical_datum": vertical_datum,
                        "grid_resolution_m": resolution_m,
                        "area": area_sqm,
                        "units": "sq_meters",
                        "stratum": "ABOVE_GROUND" if is_building else "SURFACE",
                        "ingested_from": filename,
                        "source_system": "dem_dsm_elevation_analysis",
                    },
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(props.get("id") or f"dem-tile-{idx + 1}"),
                    original_crs=source_crs,
                )
            )

        return records
