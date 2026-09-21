"""LiDAR and 3D Point Cloud ingestion adapter.

Ingests LiDAR point cloud metadata, LAS/LAZ headers, EPT (Entwine Point Tile) metadata,
or classified point cloud summary JSON/GeoJSON.
Extracts 3D bounding boxes, vertical extent (z_min, z_max), point density (pts/m²),
and classified feature clusters (Ground=2, Building=6, Vegetation=3-5, Unassigned=1).

Produces CanonicalRecords with status INFERRED, stratum classification, and 3D volumes.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import box, shape, Polygon

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    validate_and_repair_geometry,
    normalize_crs,
    CANONICAL_CRS,
)


class LidarPointCloudAdapter(IngestionAdapter):
    """Adapter for LiDAR / 3D point cloud dataset ingestion."""

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

        # Points or clusters can be supplied as:
        # 1. FeatureCollection of classified clusters / tiles
        # 2. Dict containing "clusters" or "tiles" list
        # 3. LAS/LAZ metadata dict with bounds and classification summaries
        items: list[dict[str, Any]] = []

        if isinstance(data, dict):
            if data.get("type") == "FeatureCollection":
                items = data.get("features", [])
            elif "clusters" in data:
                items = data.get("clusters", [])
            elif "tiles" in data:
                items = data.get("tiles", [])
            elif "bounds" in data or "bbox" in data:
                # Single LAS header / point cloud metadata
                items = [data]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data

        for idx, item in enumerate(items):
            props = item.get("properties") or item if isinstance(item, dict) else {}
            geom_dict = item.get("geometry") if isinstance(item, dict) else None

            # Extract 3D elevation parameters
            z_min = float(props.get("z_min", item.get("z_min", 0.0)))
            z_max = float(props.get("z_max", item.get("z_max", 0.0)))
            if z_max == 0.0 and "height_m" in props:
                z_max = z_min + float(props["height_m"])
            elif z_max == 0.0 and "elevation_max" in props:
                z_max = float(props["elevation_max"])
                z_min = float(props.get("elevation_min", z_min))

            # Point density and classification
            point_density = float(props.get("point_density_pts_m2", props.get("density", 15.0)))
            classification = str(props.get("classification", props.get("class", "building"))).lower()
            return_count = int(props.get("return_count", props.get("points_count", 5000)))

            shapely_geom = None
            if geom_dict:
                try:
                    raw_geom = shape(geom_dict)
                    repaired = validate_and_repair_geometry(raw_geom)
                    shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    shapely_geom = None
            elif "bbox" in item or "bounds" in item:
                bbox = item.get("bbox") or item.get("bounds")
                if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    minx, miny, maxx, maxy = bbox[0], bbox[1], bbox[2], bbox[3]
                    try:
                        raw_geom = box(minx, miny, maxx, maxy)
                        repaired = validate_and_repair_geometry(raw_geom)
                        shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                    except Exception:
                        shapely_geom = None

            # Calculate footprint area and 3D volume
            area_m2 = float(props.get("area_m2", 0.0))
            if area_m2 == 0.0 and shapely_geom is not None and not shapely_geom.is_empty:
                # Approximate area in m²: 1 deg ≈ 111,320m
                area_m2 = round(shapely_geom.area * (111320.0 ** 2), 2)

            height_diff = max(0.0, z_max - z_min)
            volume_m3 = float(props.get("volume_m3", round(area_m2 * height_diff, 2)))

            stratum = "SUBTERRANEAN" if z_max < 0 else ("ABOVE_GROUND" if z_min >= 0 and classification in ("building", "structure") else "SURFACE")

            record_type = "building" if classification in ("building", "structure", "6") else "parcel"
            ulpin = props.get("ulpin") or props.get("point_cloud_id") or f"LIDAR-{idx + 1:04d}"

            records.append(
                CanonicalRecord(
                    ulpin=ulpin,
                    object_type=record_type,
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else None,
                    building_seq=int(props.get("building_seq", 1)),
                    floor_seq=int(props.get("floor_seq", 0)),
                    unit_seq=int(props.get("unit_seq", 0)),
                    z_min=z_min,
                    z_max=z_max,
                    height=height_diff if height_diff > 0 else None,
                    floor_count=int(props["floor_count"]) if "floor_count" in props else None,
                    attributes={
                        **{k: v for k, v in props.items() if k not in ("ulpin", "point_cloud_id")},
                        "sensor_modality": "lidar_3d_point_cloud",
                        "point_density_pts_m2": point_density,
                        "classification": classification,
                        "return_count": return_count,
                        "volume_m3": volume_m3,
                        "stratum": stratum,
                        "scan_system": props.get("scan_system", "Aerial/Terrestrial LiDAR"),
                        "pulse_rate_khz": props.get("pulse_rate_khz", 400),
                        "ingested_from": filename,
                    },
                    source_confidence=float(props.get("confidence", 0.90)),
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(props.get("id") or f"lidar-{idx + 1}"),
                    original_crs=source_crs,
                )
            )

        return records
