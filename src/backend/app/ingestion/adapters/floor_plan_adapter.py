"""Building floor plan ingestion adapter.

Ingests CAD/DXF/BIM floor plan vector representations exported as JSON/GeoJSON.
Extracts individual strata units, floor heights, unit types (apartment, commercial, common area, parking),
and calculates vertical Z boundaries (z_min = floor_elevation, z_max = floor_elevation + ceiling_height).

Generates CanonicalRecords for floors and units with 3D ULPINs and volumetric measurements.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import shape

from app.ingestion.adapters.base import CanonicalRecord, IngestionAdapter
from app.services.normalization import (
    validate_and_repair_geometry,
    normalize_crs,
    CANONICAL_CRS,
)
from app.services.id_generator import make_3d_property_id, generate_basement_parking_ulpin


class FloorPlanAdapter(IngestionAdapter):
    """Adapter for architectural floor plans and strata subdivision diagrams."""

    DEFAULT_FLOOR_HEIGHT_M = 3.0

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

        building_id = int(data.get("building_id", metadata.get("building_id", 1)))
        base_ulpin = str(data.get("base_ulpin", metadata.get("base_ulpin", "INMH01PARCEL0001")))
        ground_elevation = float(data.get("ground_elevation_m", metadata.get("ground_elevation_m", 0.0)))

        units_data = []
        if isinstance(data, dict):
            if "units" in data:
                units_data = data["units"]
            elif data.get("type") == "FeatureCollection":
                units_data = data.get("features", [])
            elif data.get("type") == "Feature":
                units_data = [data]
        elif isinstance(data, list):
            units_data = data

        for idx, item in enumerate(units_data):
            props = item.get("properties") or item if isinstance(item, dict) else {}
            geom_dict = item.get("geometry") if isinstance(item, dict) else None

            floor_num = int(props.get("floor", props.get("floor_number", 1)))
            unit_num = int(props.get("unit_number", props.get("unit", idx + 1)))
            unit_type = str(props.get("unit_type", props.get("type", "apartment"))).lower()
            is_basement = floor_num < 0 or props.get("is_basement", False)

            ceiling_height = float(props.get("ceiling_height_m", self.DEFAULT_FLOOR_HEIGHT_M))
            
            # Compute vertical Z-extents
            if is_basement:
                basement_level = abs(floor_num)
                z_max = ground_elevation - ((basement_level - 1) * ceiling_height)
                z_min = z_max - ceiling_height
                stratum = "SUBTERRANEAN"
            else:
                z_min = ground_elevation + ((floor_num - 1) * ceiling_height)
                z_max = z_min + ceiling_height
                stratum = "ABOVE_GROUND"

            shapely_geom = None
            if geom_dict:
                try:
                    raw_geom = shape(geom_dict)
                    repaired = validate_and_repair_geometry(raw_geom)
                    shapely_geom = normalize_crs(repaired, source_crs=source_crs, target_crs=CANONICAL_CRS)
                except Exception:
                    shapely_geom = None

            area_sqm = float(props.get("carpet_area_sqm", props.get("area", 0.0)))
            if area_sqm == 0.0 and shapely_geom and not shapely_geom.is_empty:
                area_sqm = round(shapely_geom.area * (111320.0 ** 2), 2)

            volume_m3 = float(props.get("volume_m3", round(area_sqm * ceiling_height, 2)))

            # Generate appropriate 3D ULPIN
            if is_basement and "parking" in unit_type:
                ulpin = generate_basement_parking_ulpin(
                    base_ulpin=base_ulpin,
                    building_id=building_id,
                    basement_level=abs(floor_num),
                    slot_number=unit_num,
                )
                rec_type = "parking_basement"
            else:
                ulpin = make_3d_property_id(
                    ulpin=base_ulpin,
                    building_id=building_id,
                    floor_id=floor_num,
                    unit_id=unit_num,
                )
                rec_type = "unit"

            records.append(
                CanonicalRecord(
                    ulpin=ulpin,
                    object_type=rec_type,
                    geometry=shapely_geom,
                    geojson_geometry=shapely_geom.__geo_interface__ if shapely_geom else geom_dict,
                    building_seq=building_id,
                    floor_seq=floor_num,
                    unit_seq=unit_num,
                    z_min=z_min,
                    z_max=z_max,
                    height=ceiling_height,
                    status="DERIVED",
                    source_confidence=float(props.get("confidence", 0.95)),
                    attributes={
                        "sensor_modality": "building_floor_plans",
                        "raw_id": str(props.get("id") or f"fp-b{building_id}-f{floor_num}-u{unit_num}"),
                        "name": props.get("name") or f"Unit {unit_num} (Floor {floor_num})",
                        "building_id": building_id,
                        "floor_number": floor_num,
                        "unit_number": unit_num,
                        "unit_type": unit_type,
                        "carpet_area_sqm": area_sqm,
                        "built_up_area_sqm": float(props.get("built_up_area_sqm", round(area_sqm * 1.2, 2))),
                        "ceiling_height_m": ceiling_height,
                        "volume_m3": volume_m3,
                        "stratum": stratum,
                        "rooms_count": props.get("rooms_count", 3),
                        "ingested_from": filename,
                        "source_system": "floor_plan_cad_ingestion",
                    },
                    observed_at=datetime.now(timezone.utc),
                    source_id=str(props.get("id") or f"fp-b{building_id}-f{floor_num}-u{unit_num}"),
                    original_crs=source_crs,
                )
            )

        return records
