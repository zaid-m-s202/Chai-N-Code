"""GIS Parcel Layer ingestion adapter.

Ingests cadastral GIS boundary layers (Shapefile/GeoPackage GeoJSON exports, WFS parcel layers)
containing formal land parcel boundaries, Khasra/Survey numbers, village/tehsil/district codes,
and land use classifications.

Produces CanonicalRecords with status VERIFIED or PROVISIONAL and full cadastral lineage.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import shape

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    validate_and_repair_geometry,
    normalize_crs,
    normalize_unit,
    CANONICAL_CRS,
)
from app.services.id_generator import generate_surface_ulpin, generate_base_ulpin


class GisParcelAdapter(IngestionAdapter):
    """Adapter for official GIS cadastral parcel layers."""

    def parse(
        self,
        file_content: bytes,
        filename: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[CanonicalRecord]:
        raw_text = file_content.decode("utf-8")
        data = json.loads(raw_text)
        metadata = metadata or {}

        features = []
        source_crs = "EPSG:4326"

        if isinstance(data, dict):
            if "crs" in data and isinstance(data["crs"], dict):
                crs_props = data["crs"].get("properties", {})
                if "name" in crs_props:
                    source_crs = str(crs_props["name"]).strip()
            if data.get("type") == "FeatureCollection":
                features = data.get("features", [])
            elif data.get("type") == "Feature":
                features = [data]
            elif "parcels" in data:
                features = data.get("parcels", [])
        elif isinstance(data, list):
            features = data

        source_crs = metadata.get("crs") or source_crs
        records: list[CanonicalRecord] = []

        for idx, feat in enumerate(features):
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

            # Cadastral survey identifiers
            khasra_no = props.get("khasra_no") or props.get("survey_no") or props.get("parcel_id")
            village = props.get("village") or props.get("village_name", "")
            tehsil = props.get("tehsil") or props.get("taluk", "")
            district = props.get("district", "MUM")
            state = props.get("state", "MH")
            land_use = props.get("land_use") or props.get("category", "Residential")

            # Deterministic 3D ULPIN derivation if centroid exists
            ulpin = props.get("ulpin")
            if not ulpin and shapely_geom and not shapely_geom.is_empty:
                centroid = shapely_geom.centroid
                base_ulpin = generate_base_ulpin(
                    state=state,
                    district=district,
                    lon=centroid.x,
                    lat=centroid.y,
                )
                ulpin = generate_surface_ulpin(base_ulpin=base_ulpin, parcel_seq=idx + 1)
            elif not ulpin:
                ulpin = f"GIS-PARCEL-{idx + 1:04d}-SURF"

            area = float(props.get("area", 0.0))
            raw_unit = str(props.get("units", "sq_meters"))
            normalized_area = normalize_unit(area, raw_unit) or area
            norm_unit = "sq_meters"

            if normalized_area == 0.0 and shapely_geom is not None and not shapely_geom.is_empty:
                normalized_area = round(shapely_geom.area * (111320.0 ** 2), 2)
                norm_unit = "sq_meters"

            records.append(
                CanonicalRecord(
                    ulpin=ulpin,
                    object_type="parcel",
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else geom_dict,
                    z_min=float(props.get("z_min", 0.0)),
                    z_max=float(props.get("z_max", 0.0)),
                    status="VERIFIED" if props.get("verified", True) else "PROVISIONAL",
                    source_confidence=float(props.get("confidence", 0.98)),
                    attributes={
                        "sensor_modality": "gis_parcel_layers",
                        "raw_id": str(props.get("id") or khasra_no or f"gis-parcel-{idx + 1}"),
                        "name": props.get("name") or f"Parcel {khasra_no or idx + 1} ({village})",
                        "khasra_no": khasra_no,
                        "survey_no": props.get("survey_no"),
                        "village": village,
                        "tehsil": tehsil,
                        "district": district,
                        "state": state,
                        "land_use": land_use,
                        "stratum": "SURFACE",
                        "area": normalized_area,
                        "units": norm_unit,
                        "ingested_from": filename,
                        "source_system": "gis_parcel_ingestion",
                    },
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(props.get("id") or khasra_no or f"gis-parcel-{idx + 1}"),
                    original_crs=source_crs,
                )
            )

        return records
