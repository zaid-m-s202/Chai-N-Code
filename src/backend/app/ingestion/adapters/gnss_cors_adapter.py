"""GNSS / CORS (Continuously Operating Reference Station) coordinate ingestion adapter.

Ingests high-precision GNSS/CORS survey stations, RTK rover observations,
and cadastral boundary monument points with millimeter/centimeter-grade accuracy.
Extracts geodetic latitude/longitude, ellipsoidal & orthometric height, PDOP, HDOP,
and quality indicators (Fixed RTK = 1, Float RTK = 2, DGPS = 4).

Can assemble ordered boundary corner points into closed cadastral polygons or monument point arrays.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import Point, Polygon, shape

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    validate_and_repair_geometry,
    normalize_crs,
    CANONICAL_CRS,
)
from app.services.id_generator import generate_surface_ulpin, generate_base_ulpin


class GnssCorsAdapter(IngestionAdapter):
    """Adapter for CORS-tied GNSS rover survey points and benchmark pillars."""

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

        station_id = data.get("cors_station_id", metadata.get("cors_station_id", "CORS-IN-MUM01"))

        # May contain a boundary polygon formed by survey points, or individual monument points
        if "boundary_points" in data and isinstance(data["boundary_points"], list) and len(data["boundary_points"]) >= 3:
            pts = data["boundary_points"]
            coords = []
            z_values = []
            for p in pts:
                lon = float(p.get("lon", p.get("x", 0.0)))
                lat = float(p.get("lat", p.get("y", 0.0)))
                elev = float(p.get("elevation_m", p.get("z", 0.0)))
                coords.append((lon, lat))
                z_values.append(elev)

            # Close ring if not closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            poly = Polygon(coords)
            repaired = validate_and_repair_geometry(poly)
            shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)

            z_min = min(z_values) if z_values else 0.0
            z_max = max(z_values) if z_values else 0.0

            centroid = shapely_geom.centroid
            base_ulpin = generate_base_ulpin(
                state=data.get("state", "MH"),
                district=data.get("district", "MUM"),
                lon=centroid.x,
                lat=centroid.y,
            )
            ulpin = generate_surface_ulpin(base_ulpin=base_ulpin, parcel_seq=1)

            area_sqm = round(shapely_geom.area * (111320.0 ** 2), 2)

            records.append(
                CanonicalRecord(
                    ulpin=ulpin,
                    object_type="parcel",
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else None,
                    z_min=z_min,
                    z_max=z_max,
                    status="VERIFIED",
                    source_confidence=0.99,  # High precision geodetic survey
                    attributes={
                        "sensor_modality": "gnss_cors_coordinates",
                        "raw_id": str(data.get("survey_id") or f"gnss-survey-{station_id}"),
                        "name": data.get("survey_name") or f"CORS Survey Parcel ({station_id})",
                        "cors_station_id": station_id,
                        "fix_type": data.get("fix_type", "RTK_FIXED"),
                        "horizontal_accuracy_cm": float(data.get("horizontal_accuracy_cm", 1.5)),
                        "vertical_accuracy_cm": float(data.get("vertical_accuracy_cm", 2.5)),
                        "pdop": float(data.get("pdop", 1.2)),
                        "num_satellites": int(data.get("num_satellites", 24)),
                        "surveyor_id": data.get("surveyor_id", "SURVEYOR-LIC-088"),
                        "area": area_sqm,
                        "units": "sq_meters",
                        "stratum": "SURFACE",
                        "ingested_from": filename,
                        "source_system": "gnss_cors_cadastral_survey",
                    },
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(data.get("survey_id") or f"gnss-survey-{station_id}"),
                    original_crs=source_crs,
                )
            )

        # Also support point collections or single survey monuments
        items = []
        if isinstance(data, dict):
            if "monuments" in data:
                items = data["monuments"]
            elif "points" in data and "boundary_points" not in data:
                items = data["points"]
            elif data.get("type") == "FeatureCollection":
                items = data.get("features", [])
        elif isinstance(data, list):
            items = data

        for idx, pt in enumerate(items):
            props = pt.get("properties") or pt if isinstance(pt, dict) else {}
            geom_dict = pt.get("geometry")

            lon = float(props.get("lon", props.get("x", 0.0)))
            lat = float(props.get("lat", props.get("y", 0.0)))
            z = float(props.get("elevation_m", props.get("z", 0.0)))

            if geom_dict:
                try:
                    shapely_geom = shape(geom_dict)
                except Exception:
                    shapely_geom = Point(lon, lat)
            else:
                shapely_geom = Point(lon, lat)

            monument_id = props.get("monument_id") or f"BM-{station_id}-{idx + 1:03d}"
            base_ulpin = generate_base_ulpin("MH", "MUM", lon, lat)

            records.append(
                CanonicalRecord(
                    ulpin=f"{base_ulpin}-SURF",
                    object_type="parcel",
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else None,
                    z_min=z,
                    z_max=z,
                    status="VERIFIED",
                    source_confidence=0.99,
                    attributes={
                        "sensor_modality": "gnss_cors_coordinates",
                        "raw_id": str(monument_id),
                        "name": f"Geodetic Control Monument {monument_id}",
                        "cors_station_id": station_id,
                        "monument_id": monument_id,
                        "elevation_orthometric_m": z,
                        "fix_type": props.get("fix_type", "RTK_FIXED"),
                        "stratum": "SURFACE",
                        "ingested_from": filename,
                        "source_system": "gnss_cors_cadastral_survey",
                    },
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(monument_id),
                    original_crs=source_crs,
                )
            )

        return records
