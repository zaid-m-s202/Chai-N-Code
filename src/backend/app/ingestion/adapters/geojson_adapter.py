"""GeoJSON ingestion adapter for spatial parcel and building footprints."""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from shapely.geometry import shape

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    normalize_crs,
    normalize_unit,
    validate_and_repair_geometry,
    CANONICAL_CRS,
)


class GeoJSONAdapter(IngestionAdapter):
    """Parses GeoJSON FeatureCollection or Features into CanonicalRecords with GIS normalization."""

    def parse(self, file_content: bytes, filename: str, metadata: Optional[dict[str, Any]] = None) -> list[CanonicalRecord]:
        raw_text = file_content.decode("utf-8")
        data = json.loads(raw_text)

        features = []
        source_crs = "EPSG:4326"
        # Check if GeoJSON specifies a top-level CRS
        if isinstance(data, dict) and "crs" in data and isinstance(data["crs"], dict):
            crs_props = data["crs"].get("properties", {})
            crs_name = crs_props.get("name")
            if crs_name:
                source_crs = str(crs_name).strip()

        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        elif "coordinates" in data:
            features = [{"type": "Feature", "geometry": data, "properties": {}}]

        records: list[CanonicalRecord] = []
        metadata = metadata or {}
        source_crs = metadata.get("crs") or source_crs

        for idx, feat in enumerate(features):
            props = feat.get("properties") or {}
            geom_dict = feat.get("geometry")

            shapely_geom = None
            if geom_dict:
                try:
                    raw_geom = shape(geom_dict)
                    # 1. Validate & repair topology
                    repaired_geom = validate_and_repair_geometry(raw_geom)
                    # 2. Normalize CRS to EPSG:4326
                    shapely_geom = normalize_crs(repaired_geom, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    shapely_geom = None

            ulpin = (
                props.get("ulpin")
                or props.get("ULPIN")
                or props.get("parcel_id")
                or props.get("id")
                or f"PARCEL-{idx+1:04d}"
            )
            obj_type = props.get("type") or props.get("object_type") or ("building" if "height" in props else "parcel")
            building_seq = int(props.get("building_seq") or props.get("bldg_seq") or 1)
            floor_seq = int(props.get("floor_seq") or 0)
            unit_seq = int(props.get("unit_seq") or 0)

            unit_hint = props.get("unit") or props.get("height_unit")
            raw_height = props.get("height")
            height = normalize_unit(raw_height, unit_hint) if raw_height is not None else None

            floor_count = int(props["floor_count"]) if "floor_count" in props and props["floor_count"] is not None else None

            raw_z_min = props.get("z_min")
            z_min = normalize_unit(raw_z_min, unit_hint) if raw_z_min is not None else 0.0

            raw_z_max = props.get("z_max")
            z_max = normalize_unit(raw_z_max, unit_hint) if raw_z_max is not None else (
                (z_min + height) if height is not None else None
            )

            confidence = float(props.get("confidence", 0.85))
            observed_at_str = props.get("observed_at") or props.get("survey_date")
            if observed_at_str:
                try:
                    observed_at = datetime.fromisoformat(observed_at_str.replace("Z", "+00:00"))
                except Exception:
                    observed_at = datetime.now(timezone.utc)
            else:
                observed_at = datetime.now(timezone.utc)

            record = CanonicalRecord(
                ulpin=str(ulpin),
                object_type=str(obj_type).lower(),
                geometry=shapely_geom,
                geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else geom_dict,
                building_seq=building_seq,
                floor_seq=floor_seq,
                unit_seq=unit_seq,
                z_min=z_min,
                z_max=z_max,
                height=height,
                floor_count=floor_count,
                attributes={k: v for k, v in props.items() if k not in ("ulpin", "ULPIN")},
                source_confidence=confidence,
                observed_at=observed_at,
                source_id=props.get("source_id", filename),
                original_crs=source_crs,
            )
            records.append(record)

        return records
