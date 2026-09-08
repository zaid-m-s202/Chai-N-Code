"""CSV ingestion adapter for tabular cadastral and survey records."""

import csv
import io
from datetime import datetime, timezone
from typing import Any, Optional
from shapely.geometry import Point
from shapely import wkt

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    normalize_crs,
    normalize_unit,
    validate_and_repair_geometry,
    CANONICAL_CRS,
)


class CSVAdapter(IngestionAdapter):
    """Parses tabular CSV files containing parcel/building attributes and coordinates."""

    def parse(self, file_content: bytes, filename: str, metadata: Optional[dict[str, Any]] = None) -> list[CanonicalRecord]:
        text = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        records: list[CanonicalRecord] = []
        metadata = metadata or {}
        default_crs = metadata.get("crs", "EPSG:4326")

        for idx, row in enumerate(reader):
            clean_row = {k.strip(): (v.strip() if v else None) for k, v in row.items() if k}

            ulpin = (
                clean_row.get("ulpin")
                or clean_row.get("ULPIN")
                or clean_row.get("parcel_id")
                or clean_row.get("id")
                or f"PARCEL-{idx+1:04d}"
            )
            obj_type = clean_row.get("type") or clean_row.get("object_type") or "building"

            source_crs = clean_row.get("crs") or clean_row.get("srid") or default_crs

            raw_geom = None
            if "wkt" in clean_row and clean_row["wkt"]:
                try:
                    raw_geom = wkt.loads(clean_row["wkt"])
                except Exception:
                    raw_geom = None
            elif ("latitude" in clean_row or "lat" in clean_row) and ("longitude" in clean_row or "lon" in clean_row):
                try:
                    lat = float(clean_row.get("latitude") or clean_row.get("lat"))
                    lon = float(clean_row.get("longitude") or clean_row.get("lon"))
                    raw_geom = Point(lon, lat)
                except Exception:
                    raw_geom = None

            geom = None
            if raw_geom:
                try:
                    repaired = validate_and_repair_geometry(raw_geom)
                    geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    geom = raw_geom

            building_seq = int(clean_row.get("building_seq") or clean_row.get("bldg_seq") or 1)
            floor_seq = int(clean_row.get("floor_seq") or 0)
            unit_seq = int(clean_row.get("unit_seq") or 0)

            unit_hint = clean_row.get("unit") or clean_row.get("height_unit")
            raw_height = clean_row.get("height")
            height = normalize_unit(raw_height, unit_hint) if raw_height else None

            floor_count = int(clean_row["floor_count"]) if clean_row.get("floor_count") else None

            raw_z_min = clean_row.get("z_min")
            z_min = normalize_unit(raw_z_min, unit_hint) if raw_z_min else 0.0

            raw_z_max = clean_row.get("z_max")
            z_max = normalize_unit(raw_z_max, unit_hint) if raw_z_max else (
                (z_min + height) if height is not None else None
            )

            confidence = float(clean_row.get("confidence") or 0.8)
            observed_at_str = clean_row.get("observed_at") or clean_row.get("survey_date")
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
                geometry=geom,
                geojson_geometry=geom.__geo_interface__ if geom else None,
                building_seq=building_seq,
                floor_seq=floor_seq,
                unit_seq=unit_seq,
                z_min=z_min,
                z_max=z_max,
                height=height,
                floor_count=floor_count,
                attributes=clean_row,
                source_confidence=confidence,
                observed_at=observed_at,
                source_id=clean_row.get("source_id", filename),
                original_crs=source_crs,
            )
            records.append(record)

        return records
