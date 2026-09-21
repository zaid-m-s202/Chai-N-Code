"""Comprehensive unit tests for 3D ULPIN, Multi-Sensor Ingestion, and AI Cadastral Studio."""

import json
import pytest
from shapely.geometry import box, mapping, Polygon

from app.services.id_generator import (
    generate_base_ulpin,
    generate_surface_ulpin,
    generate_apartment_3d_ulpin,
    generate_underground_ulpin,
    generate_basement_parking_ulpin,
    parse_any_3d_ulpin,
    make_3d_property_id,
    parse_3d_property_id,
)
from app.ingestion.adapters.drone_adapter import DroneImageryAdapter
from app.ingestion.adapters.lidar_adapter import LidarPointCloudAdapter
from app.ingestion.adapters.gis_parcel_adapter import GisParcelAdapter
from app.ingestion.adapters.floor_plan_adapter import FloorPlanAdapter
from app.ingestion.adapters.gnss_cors_adapter import GnssCorsAdapter
from app.ingestion.adapters.dem_dsm_adapter import DemDsmAdapter
from app.ingestion.pipeline import get_adapter_for_format
from app.analysis.floor_segmentation_adapter import FloorSegmentationAdapter
from app.analysis.vertical_parcel_delineator import VerticalParcelDelineator
from app.analysis.intelligent_topology_validator import IntelligentTopologyValidator
from app.analysis.service import analysis_service


# ===========================================================================
# 1. 3D ULPIN GENERATOR & PARSER TESTS
# ===========================================================================

def test_base_ulpin_generation_from_coordinates():
    base_ulpin = generate_base_ulpin(state="MH", district="PUN", lon=73.8567, lat=18.5204)
    assert len(base_ulpin) == 14
    assert base_ulpin.startswith("MH")
    assert base_ulpin[2:5] == "PUN"


def test_surface_parcel_ulpin():
    base = "INMHPUN1234567"
    surf_id = generate_surface_ulpin(base, parcel_seq=1)
    assert surf_id == "INMHPUN1234567-SURF"
    
    parsed = parse_any_3d_ulpin(surf_id)
    assert parsed["type"] == "surface"
    assert parsed["ulpin"] == base


def test_apartment_strata_ulpin():
    base = "INMHPUN1234567"
    unit_id = generate_apartment_3d_ulpin(base, building_id=1, floor_number=4, unit_number=402)
    assert unit_id == "INMHPUN1234567-B001-F04-U402"
    
    parsed = parse_any_3d_ulpin(unit_id)
    assert parsed["type"] == "apartment"
    assert parsed["building"] == 1
    assert parsed["floor"] == 4
    assert parsed["unit"] == 402


def test_underground_infrastructure_ulpin():
    base = "INMHPUN1234567"
    metro_id = generate_underground_ulpin(base, category="METRO", infra_id="T01")
    assert metro_id == "INMHPUN1234567-UG-METRO-T01"

    parsed = parse_any_3d_ulpin(metro_id)
    assert parsed["type"] == "underground"
    assert parsed["category"] == "METRO"
    assert parsed["infra_id"] == "T01"


def test_basement_parking_ulpin():
    base = "INMHPUN1234567"
    parking_id = generate_basement_parking_ulpin(base, building_id=1, basement_level=2, slot_number=15)
    assert parking_id == "INMHPUN1234567-B001-B02-P015"

    parsed = parse_any_3d_ulpin(parking_id)
    assert parsed["type"] == "basement_parking"
    assert parsed["basement_level"] == 2
    assert parsed["slot_number"] == 15


# ===========================================================================
# 2. MULTI-SENSOR INGESTION ADAPTER TESTS (6 MODALITIES)
# ===========================================================================

def test_drone_imagery_adapter():
    adapter = DroneImageryAdapter()
    payload = {
        "flight_id": "UAV-PUN-01",
        "gsd_cm_per_pixel": 1.25,
        "flight_altitude_agl_m": 80.0,
        "coverage": {
            "type": "Polygon",
            "coordinates": [[[73.845, 18.512], [73.846, 18.512], [73.846, 18.511], [73.845, 18.511], [73.845, 18.512]]],
        },
    }
    records = adapter.parse(json.dumps(payload).encode(), "drone_flight.json")
    assert len(records) == 1
    assert records[0].status == "INFERRED"
    assert records[0].attributes["sensor_modality"] == "drone_imagery_orthomosaic"
    assert records[0].attributes["gsd_cm_per_pixel"] == 1.25


def test_lidar_point_cloud_adapter():
    adapter = LidarPointCloudAdapter()
    payload = {
        "clusters": [{
            "id": "lidar-101",
            "classification": "building",
            "z_min": 10.0,
            "z_max": 35.0,
            "point_density_pts_m2": 32.0,
            "bbox": [73.815, 18.600, 73.816, 18.601],
        }]
    }
    records = adapter.parse(json.dumps(payload).encode(), "lidar_sample.json")
    assert len(records) == 1
    assert records[0].z_min == 10.0
    assert records[0].z_max == 35.0
    assert records[0].attributes["sensor_modality"] == "lidar_3d_point_cloud"
    assert records[0].attributes["volume_m3"] > 0


def test_gis_parcel_adapter():
    adapter = GisParcelAdapter()
    payload = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "khasra_no": "112/4",
                "village": "Sadashiv",
                "area": 1500.0,
                "units": "sq_meters",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.845, 18.512], [73.846, 18.512], [73.846, 18.511], [73.845, 18.511], [73.845, 18.512]]],
            },
        }]
    }
    records = adapter.parse(json.dumps(payload).encode(), "gis_parcels.json")
    assert len(records) == 1
    assert records[0].status == "VERIFIED"
    assert records[0].attributes["khasra_no"] == "112/4"
    assert "-SURF" in records[0].ulpin


def test_floor_plan_adapter():
    adapter = FloorPlanAdapter()
    payload = {
        "building_id": 1,
        "base_ulpin": "INMHPUN001",
        "units": [
            {"floor": 2, "unit": 201, "carpet_area_sqm": 90.0, "ceiling_height_m": 3.0},
            {"floor": -1, "unit": 1, "unit_type": "parking_basement", "carpet_area_sqm": 15.0},
        ],
    }
    records = adapter.parse(json.dumps(payload).encode(), "floor_plan.json")
    assert len(records) == 2
    # Upper floor
    assert records[0].type == "unit"
    assert records[0].z_min == 3.0
    assert records[0].z_max == 6.0
    assert records[0].attributes["stratum"] == "ABOVE_GROUND"
    # Basement parking
    assert records[1].type == "parking_basement"
    assert records[1].z_max == 0.0
    assert records[1].z_min == -3.0
    assert records[1].attributes["stratum"] == "SUBTERRANEAN"


def test_gnss_cors_adapter():
    adapter = GnssCorsAdapter()
    payload = {
        "cors_station_id": "CORS-PUN01",
        "boundary_points": [
            {"lon": 73.845, "lat": 18.511, "elevation_m": 558.0},
            {"lon": 73.846, "lat": 18.511, "elevation_m": 558.0},
            {"lon": 73.846, "lat": 18.512, "elevation_m": 558.0},
            {"lon": 73.845, "lat": 18.512, "elevation_m": 558.0},
        ],
    }
    records = adapter.parse(json.dumps(payload).encode(), "gnss_survey.json")
    assert len(records) == 1
    assert records[0].status == "VERIFIED"
    assert records[0].attributes["cors_station_id"] == "CORS-PUN01"


def test_dem_dsm_adapter():
    adapter = DemDsmAdapter()
    payload = {
        "tiles": [{
            "dem_elevation_m": 558.0,
            "dsm_elevation_m": 573.0,
            "bbox": [73.845, 18.511, 73.846, 18.512],
        }]
    }
    records = adapter.parse(json.dumps(payload).encode(), "dem_dsm.json")
    assert len(records) == 1
    assert records[0].z_min == 558.0
    assert records[0].z_max == 573.0
    assert records[0].attributes["ndsm_structure_height_m"] == 15.0


def test_pipeline_adapter_registry():
    assert isinstance(get_adapter_for_format("drone"), DroneImageryAdapter)
    assert isinstance(get_adapter_for_format("lidar"), LidarPointCloudAdapter)
    assert isinstance(get_adapter_for_format("gis"), GisParcelAdapter)
    assert isinstance(get_adapter_for_format("floor_plan"), FloorPlanAdapter)
    assert isinstance(get_adapter_for_format("cors"), GnssCorsAdapter)
    assert isinstance(get_adapter_for_format("dem"), DemDsmAdapter)


# ===========================================================================
# 3. AI CADASTRAL ANALYSIS ADAPTER TESTS
# ===========================================================================

def test_floor_segmentation_adapter():
    adapter = FloorSegmentationAdapter()
    footprint = box(72.8500, 19.0500, 72.8504, 19.0504)
    res = adapter.analyze({
        "footprint": mapping(footprint),
        "units_count": 4,
        "floor_number": 2,
        "base_ulpin": "INMH01PUN001",
    })
    assert res.status == "DERIVED"
    assert len(res.data["units"]) == 4
    assert res.data["units"][0]["stratum"] == "ABOVE_GROUND"
    assert res.data["units"][0]["volume_m3"] > 0


def test_vertical_parcel_delineator():
    adapter = VerticalParcelDelineator()
    footprint = box(72.8520, 19.0550, 72.8528, 19.0558)
    res = adapter.analyze({
        "footprint": mapping(footprint),
        "base_ulpin": "INMH01PUN001",
        "floor_count": 4,
        "units_per_floor": 2,
        "basement_levels": 1,
        "include_underground_utilities": True,
    })
    assert res.status == "DERIVED"
    parcels = res.data["parcels"]
    
    # Check strata presence
    strata = {p["stratum"] for p in parcels}
    assert "SURFACE" in strata
    assert "ABOVE_GROUND" in strata
    assert "SUBTERRANEAN" in strata

    # Check volumetric envelope
    assert res.data["total_volumetric_envelope_m3"] > 0


def test_intelligent_topology_validator_pass():
    validator = IntelligentTopologyValidator()
    # Non-overlapping units in vertical stack
    parcels = [
        {
            "three_d_property_id": "INMH01PUN001-SURF",
            "type": "parcel",
            "stratum": "SURFACE",
            "z_min": 0.0,
            "z_max": 0.0,
            "geometry": mapping(box(0, 0, 1, 1)),
        },
        {
            "three_d_property_id": "INMH01PUN001-B001-B01-P001",
            "type": "parking_basement",
            "stratum": "SUBTERRANEAN",
            "z_min": -3.0,
            "z_max": 0.0,
            "geometry": mapping(box(0, 0, 1, 1)),
        },
        {
            "three_d_property_id": "INMH01PUN001-B001-F01-U001",
            "type": "unit",
            "stratum": "ABOVE_GROUND",
            "z_min": 0.0,
            "z_max": 3.0,
            "geometry": mapping(box(0, 0, 1, 1)),
        },
    ]
    res = validator.analyze({"parcels": parcels})
    assert res.data["is_valid"] is True
    assert res.data["error_count"] == 0


def test_intelligent_topology_validator_volumetric_collision():
    validator = IntelligentTopologyValidator()
    # Overlapping 3D units in both horizontal polygon and vertical Z-band!
    parcels = [
        {
            "three_d_property_id": "INMH01PUN001-B001-F01-U001",
            "type": "unit",
            "stratum": "ABOVE_GROUND",
            "z_min": 0.0,
            "z_max": 3.0,
            "geometry": mapping(box(0, 0, 1, 1)),
        },
        {
            "three_d_property_id": "INMH01PUN001-B001-F01-U002",
            "type": "unit",
            "stratum": "ABOVE_GROUND",
            "z_min": 1.0,  # Clashing!
            "z_max": 4.0,
            "geometry": mapping(box(0, 0, 1, 1)),
        },
    ]
    res = validator.analyze({"parcels": parcels})
    assert res.data["is_valid"] is False
    assert any(v["rule_code"] == "VR-3D-01" for v in res.data["violations"])


def test_analysis_service_has_all_adapters():
    adapters = [a["name"] for a in analysis_service.list_adapters()]
    assert "floor_plan_unit_segmenter" in adapters
    assert "vertical_parcel_delineator" in adapters
    assert "intelligent_topology_validator" in adapters
