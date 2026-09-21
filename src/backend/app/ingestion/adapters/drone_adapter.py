"""Drone imagery metadata ingestion adapter.

Ingests drone orthomosaic metadata, flight parameters, and Ground Control Points (GCPs)
from JSON/GeoJSON exports. Extracts building footprint boundaries from drone flight
coverage polygons with Ground Sampling Distance (GSD) and camera metadata.

Produces CanonicalRecords with status INFERRED and provenance metadata.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import shape, mapping

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import validate_and_repair_geometry, normalize_crs, CANONICAL_CRS


class DroneImageryAdapter(IngestionAdapter):
    """Adapter for drone imagery metadata and flight coverage ingestion."""

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

        # Support both a single flight object and a list/FeatureCollection
        flights = []
        if isinstance(data, dict):
            if data.get("type") == "FeatureCollection":
                flights = data.get("features", [])
            elif data.get("type") == "Feature":
                flights = [data]
            elif "flight_id" in data or "coverage" in data:
                flights = [{"type": "Feature", "geometry": data.get("coverage"), "properties": data}]
            else:
                flights = [{"type": "Feature", "geometry": data.get("geometry"), "properties": data}]
        elif isinstance(data, list):
            flights = data

        source_crs = metadata.get("crs") or "EPSG:4326"

        for idx, feat in enumerate(flights):
            props = feat.get("properties") or feat if isinstance(feat, dict) else {}
            geom_dict = feat.get("geometry") if isinstance(feat, dict) else None

            shapely_geom = None
            if geom_dict:
                try:
                    raw_geom = shape(geom_dict)
                    repaired = validate_and_repair_geometry(raw_geom)
                    shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    shapely_geom = None

            ulpin = (
                props.get("ulpin") or props.get("ULPIN")
                or props.get("parcel_id") or props.get("flight_id")
                or f"DRONE-{idx+1:04d}"
            )

            # Extract drone-specific metadata
            gsd_cm = props.get("gsd_cm_per_pixel")
            gsd_m = props.get("gsd") or props.get("ground_sampling_distance") or (float(gsd_cm) / 100.0 if gsd_cm is not None else None)
            flight_altitude = props.get("altitude") or props.get("flight_altitude") or props.get("flight_altitude_agl_m")
            camera_model = props.get("camera") or props.get("camera_model")
            gcp_count = props.get("gcp_count") or props.get("ground_control_points")
            resolution = props.get("resolution") or props.get("image_resolution")
            capture_date = props.get("capture_date") or props.get("flight_date")

            # Higher GSD precision → higher confidence
            base_confidence = 0.75
            if gsd_m is not None:
                try:
                    gsd_val = float(gsd_m)
                    if gsd_val <= 0.02:
                        base_confidence = 0.95  # Sub-2cm: survey-grade
                    elif gsd_val <= 0.05:
                        base_confidence = 0.90
                    elif gsd_val <= 0.10:
                        base_confidence = 0.85
                except (ValueError, TypeError):
                    pass

            observed_at = datetime.now(timezone.utc)
            if capture_date:
                try:
                    observed_at = datetime.fromisoformat(str(capture_date).replace("Z", "+00:00"))
                except Exception:
                    pass

            height = None
            raw_h = props.get("height") or props.get("building_height")
            if raw_h is not None:
                try:
                    height = float(raw_h)
                except (ValueError, TypeError):
                    pass

            record = CanonicalRecord(
                ulpin=str(ulpin),
                object_type=props.get("type", "building").lower(),
                geometry=shapely_geom,
                geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else geom_dict,
                building_seq=int(props.get("building_seq", 1)),
                floor_seq=int(props.get("floor_seq", 0)),
                unit_seq=int(props.get("unit_seq", 0)),
                z_min=float(props["z_min"]) if props.get("z_min") is not None else None,
                z_max=float(props["z_max"]) if props.get("z_max") is not None else None,
                height=height,
                floor_count=int(props["floor_count"]) if props.get("floor_count") is not None else None,
                attributes={
                    **{k: v for k, v in props.items() if k not in ("ulpin", "ULPIN")},
                    "sensor_type": "drone_imagery",
                    "sensor_modality": "drone_imagery_orthomosaic",
                    "gsd_meters": gsd_m,
                    "gsd_cm_per_pixel": float(gsd_cm) if gsd_cm is not None else (round(gsd_m * 100.0, 2) if gsd_m is not None else None),
                    "flight_altitude_m": flight_altitude,
                    "camera_model": camera_model,
                    "gcp_count": gcp_count,
                    "image_resolution": resolution,
                },
                source_confidence=base_confidence,
                observed_at=observed_at,
                source_id=props.get("source_id", f"drone:{filename}"),
                original_crs=source_crs,
                status="INFERRED",
            )
            records.append(record)

        return records
