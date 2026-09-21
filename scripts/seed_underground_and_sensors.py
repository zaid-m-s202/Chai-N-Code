#!/usr/bin/env python3
"""
Seed Underground Cadastre & Multi-Sensor Datasets
Generates:
1. `src/frontend/public/underground_infrastructure.geojson` containing:
   - Metro Transit Tunnels (z_min: -25m, z_max: -18m)
   - High-Pressure Water Mains (z_min: -8m, z_max: -5m)
   - Underground Telecom & Power Duct Banks (z_min: -4m, z_max: -2m)
   - Stormwater Drainage Vaults (z_min: -14m, z_max: -10m)
   - Multi-level Basement Parking complexes (B1: -3m to 0m, B2: -6m to -3m) with standardized 3D ULPINs
2. Sample multi-sensor files in `data/samples/` for all 6 modalities:
   - drone_imagery_sample.json
   - lidar_point_cloud_sample.json
   - gis_cadastral_parcels.json
   - building_floor_plan_cad.json
   - gnss_cors_survey.json
   - dem_dsm_elevation_grid.json
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_PUBLIC = os.path.join(BASE_DIR, "src", "frontend", "public")
DATA_SAMPLES = os.path.join(BASE_DIR, "data", "samples")

os.makedirs(FRONTEND_PUBLIC, exist_ok=True)
os.makedirs(DATA_SAMPLES, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. UNDERGROUND INFRASTRUCTURE GEOJSON
# ---------------------------------------------------------------------------

underground_features = [
    # Pune Metro underground tunnel section (Sadashiv Peth to Civil Court)
    {
        "type": "Feature",
        "properties": {
            "id": "ug-metro-tunnel-01",
            "three_d_property_id": "27-21-11-719-UG-METRO-T01",
            "name": "Pune Metro Underground Corridor (Line 1 - Sadashiv Section)",
            "type": "tunnel",
            "category": "METRO",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Transit Tunnel",
            "z_min": -24.0,
            "z_max": -18.0,
            "depth_below_surface_m": 18.0,
            "thickness_m": 6.0,
            "volume_m3": 14400.0,
            "color": "#ef4444",  # Bright Red for Subsurface Transit
            "status": "VERIFIED",
            "confidence": 0.99,
            "easement_status": "STATUTORY_TRANSIT_EASEMENT",
            "diameter_m": 5.8,
            "owner": "Maharashtra Metro Rail Corporation (MahaMetro)",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.8440, 18.5110],
                [73.8475, 18.5125],
                [73.8476, 18.5122],
                [73.8441, 18.5107],
                [73.8440, 18.5110],
            ]],
        },
    },
    # High-pressure water supply trunk main
    {
        "type": "Feature",
        "properties": {
            "id": "ug-util-water-01",
            "three_d_property_id": "27-21-11-719-UG-WATER-M100",
            "name": "PMC Primary Water Trunk Main (1200mm M.S.)",
            "type": "underground_utility",
            "category": "WATER",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Water Trunk Corridor",
            "z_min": -7.5,
            "z_max": -5.0,
            "depth_below_surface_m": 5.0,
            "thickness_m": 2.5,
            "volume_m3": 3750.0,
            "color": "#06b6d4",  # Cyan for Water
            "status": "VERIFIED",
            "confidence": 0.96,
            "easement_status": "MUNICIPAL_RIGHT_OF_WAY",
            "pressure_bar": 12.0,
            "owner": "Pune Municipal Corporation (Water Supply Dept)",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.8435, 18.5128],
                [73.8480, 18.5132],
                [73.8480, 18.5130],
                [73.8435, 18.5126],
                [73.8435, 18.5128],
            ]],
        },
    },
    # Subterranean 110kV electrical power transmission cable tunnel
    {
        "type": "Feature",
        "properties": {
            "id": "ug-util-power-01",
            "three_d_property_id": "27-21-11-719-UG-POWER-C88",
            "name": "MSEDCL 110kV EHV Underground Cable Duct Bank",
            "type": "underground_utility",
            "category": "POWER",
            "stratum": "SUBTERRANEAN",
            "utility_type": "High Voltage Power Vault",
            "z_min": -4.2,
            "z_max": -2.0,
            "depth_below_surface_m": 2.0,
            "thickness_m": 2.2,
            "volume_m3": 2200.0,
            "color": "#eab308",  # Amber/Yellow for Power
            "status": "VERIFIED",
            "confidence": 0.98,
            "easement_status": "UTILITY_CORRIDOR_RIGHT",
            "voltage_kv": 110.0,
            "owner": "Maharashtra State Electricity Distribution Co.",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.8445, 18.5102],
                [73.8470, 18.5140],
                [73.8471, 18.5139],
                [73.8446, 18.5101],
                [73.8445, 18.5102],
            ]],
        },
    },
    # Optical fiber and telecom consolidated duct
    {
        "type": "Feature",
        "properties": {
            "id": "ug-util-telecom-01",
            "three_d_property_id": "27-21-11-719-UG-UTIL-FIBER01",
            "name": "National Telecom & Smart City OFC Trench",
            "type": "underground_utility",
            "category": "UTIL",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Telecom Conduit",
            "z_min": -2.5,
            "z_max": -1.2,
            "depth_below_surface_m": 1.2,
            "thickness_m": 1.3,
            "volume_m3": 1300.0,
            "color": "#a855f7",  # Purple for Telecom
            "status": "VERIFIED",
            "confidence": 0.95,
            "easement_status": "TELECOM_WAYLEAVE",
            "conduits_count": 12,
            "owner": "Smart City Development Corporation",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.8438, 18.5115],
                [73.8472, 18.5118],
                [73.8472, 18.5117],
                [73.8438, 18.5114],
                [73.8438, 18.5115],
            ]],
        },
    },
    # Deep stormwater relief tunnel
    {
        "type": "Feature",
        "properties": {
            "id": "ug-util-drain-01",
            "three_d_property_id": "27-21-11-719-UG-SEWER-SW01",
            "name": "Sadashiv Peth Deep Stormwater Relief Conduit",
            "type": "underground_utility",
            "category": "SEWER",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Stormwater Vault",
            "z_min": -13.0,
            "z_max": -9.5,
            "depth_below_surface_m": 9.5,
            "thickness_m": 3.5,
            "volume_m3": 5250.0,
            "color": "#3b82f6",  # Blue
            "status": "DERIVED",
            "confidence": 0.91,
            "easement_status": "MUNICIPAL_DRAINAGE_RESERVE",
            "owner": "Pune Municipal Drainage Department",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.8448, 18.5135],
                [73.8465, 18.5105],
                [73.8467, 18.5106],
                [73.8450, 18.5136],
                [73.8448, 18.5135],
            ]],
        },
    },
    # Basement 1 Parking under Regency Meadows
    {
        "type": "Feature",
        "properties": {
            "id": "ug-basement-b01-p01",
            "three_d_property_id": "27-21-02-876-B001-B01-P001",
            "name": "Regency Meadows - Basement Level B1 Parking Slot P-01",
            "type": "parking_basement",
            "category": "PARKING",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Dedicated Resident Parking",
            "z_min": -3.0,
            "z_max": 0.0,
            "depth_below_surface_m": 0.0,
            "thickness_m": 3.0,
            "volume_m3": 37.5,
            "color": "#64748b",  # Slate
            "status": "VERIFIED",
            "confidence": 0.98,
            "rights_type": "strata_title",
            "building_id": 1,
            "basement_level": 1,
            "slot_number": 1,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.90485, 18.60220],
                [73.90495, 18.60220],
                [73.90495, 18.60210],
                [73.90485, 18.60210],
                [73.90485, 18.60220],
            ]],
        },
    },
    # Basement 2 Parking under Regency Meadows
    {
        "type": "Feature",
        "properties": {
            "id": "ug-basement-b02-p01",
            "three_d_property_id": "27-21-02-876-B001-B02-P001",
            "name": "Regency Meadows - Basement Level B2 Mechanical Parking P-01",
            "type": "parking_basement",
            "category": "PARKING",
            "stratum": "SUBTERRANEAN",
            "utility_type": "Subsurface Stack Parking",
            "z_min": -6.0,
            "z_max": -3.0,
            "depth_below_surface_m": 3.0,
            "thickness_m": 3.0,
            "volume_m3": 37.5,
            "color": "#475569",  # Darker Slate
            "status": "VERIFIED",
            "confidence": 0.97,
            "rights_type": "strata_title",
            "building_id": 1,
            "basement_level": 2,
            "slot_number": 1,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [73.90485, 18.60220],
                [73.90495, 18.60220],
                [73.90495, 18.60210],
                [73.90485, 18.60210],
                [73.90485, 18.60220],
            ]],
        },
    },
]

ug_geojson = {
    "type": "FeatureCollection",
    "metadata": {
        "title": "National 3D Cadastre - Subterranean Infrastructure Registry",
        "crs": "EPSG:4326",
        "vertical_datum": "EGM2008",
        "stratum": "SUBTERRANEAN",
        "count": len(underground_features),
    },
    "features": underground_features,
}

ug_path = os.path.join(FRONTEND_PUBLIC, "underground_infrastructure.geojson")
with open(ug_path, "w", encoding="utf-8") as f:
    json.dump(ug_geojson, f, indent=2)
print(f"Generated {ug_path} with {len(underground_features)} subterranean features.")


# ---------------------------------------------------------------------------
# 2. MULTI-SENSOR SAMPLE DATASETS (6 MODALITIES)
# ---------------------------------------------------------------------------

# 1. Drone Imagery Sample
drone_sample = {
    "flight_id": "UAV-SURVEY-2026-09A",
    "sensor": "Zenmuse P1 35mm Full-Frame",
    "flight_altitude_agl_m": 85.0,
    "gsd_cm_per_pixel": 1.25,
    "overlap_forward_pct": 80,
    "overlap_side_pct": 75,
    "crs": "EPSG:4326",
    "ground_control_points": [
        {"id": "GCP-01", "lon": 73.8453, "lat": 18.5119, "z_m": 558.2, "residual_cm": 0.8},
        {"id": "GCP-02", "lon": 73.8457, "lat": 18.5116, "z_m": 558.1, "residual_cm": 0.6},
    ],
    "coverage": {
        "type": "Polygon",
        "coordinates": [[
            [73.8450, 18.5122],
            [73.8462, 18.5122],
            [73.8462, 18.5113],
            [73.8450, 18.5113],
            [73.8450, 18.5122],
        ]],
    },
    "extracted_features": [
        {"id": "bldg-drone-01", "name": "Sadashiv Educational Complex Block A", "height_m": 15.2, "levels": 5}
    ],
}
with open(os.path.join(DATA_SAMPLES, "drone_imagery_sample.json"), "w", encoding="utf-8") as f:
    json.dump(drone_sample, f, indent=2)

# 2. LiDAR / 3D Point Cloud Sample
lidar_sample = {
    "dataset_name": "Pune City Aerial LiDAR Survey 2026",
    "scan_system": "RIEGL VQ-1560 II-S",
    "point_density_pts_m2": 32.5,
    "pulse_rate_khz": 800,
    "crs": "EPSG:4326",
    "clusters": [
        {
            "id": "lidar-cluster-101",
            "classification": "building",
            "class_code": 6,
            "elevation_min": 558.0,
            "elevation_max": 588.0,
            "height_m": 30.0,
            "z_min": 0.0,
            "z_max": 30.0,
            "point_density_pts_m2": 35.2,
            "points_count": 48200,
            "volume_m3": 18500.0,
            "bbox": [73.8155, 18.6008, 73.8166, 18.6014],
            "name": "Kalpataru Estate High-Rise Cluster",
        },
        {
            "id": "lidar-cluster-102",
            "classification": "ground",
            "class_code": 2,
            "elevation_min": 557.5,
            "elevation_max": 558.2,
            "z_min": 0.0,
            "z_max": 0.7,
            "point_density_pts_m2": 28.0,
            "points_count": 82000,
            "bbox": [73.8150, 18.6000, 73.8170, 18.6020],
            "name": "Bare Earth Cadastral Ground Plane",
        },
    ],
}
with open(os.path.join(DATA_SAMPLES, "lidar_point_cloud_sample.json"), "w", encoding="utf-8") as f:
    json.dump(lidar_sample, f, indent=2)

# 3. Official GIS Cadastral Parcels Sample
gis_sample = {
    "type": "FeatureCollection",
    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
    "features": [
        {
            "type": "Feature",
            "properties": {
                "id": "GIS-MH-PUN-001",
                "khasra_no": "112/4",
                "survey_no": "271",
                "village": "Sadashiv Peth",
                "tehsil": "Haveli",
                "district": "Pune",
                "state": "MH",
                "land_use": "Residential Commercial Mixed",
                "area": 1240.5,
                "units": "sq_meters",
                "ulpin": "INMH01PUN001124-SURF",
                "verified": True,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [73.8450, 18.5120],
                    [73.8458, 18.5121],
                    [73.8457, 18.5114],
                    [73.8451, 18.5113],
                    [73.8450, 18.5120],
                ]],
            },
        }
    ],
}
with open(os.path.join(DATA_SAMPLES, "gis_cadastral_parcels.json"), "w", encoding="utf-8") as f:
    json.dump(gis_sample, f, indent=2)

# 4. Building Floor Plan CAD Sample
cad_sample = {
    "building_id": 1,
    "building_name": "Regency Meadows Tower A",
    "base_ulpin": "INMH01PUN001124",
    "ground_elevation_m": 0.0,
    "units": [
        {
            "floor": 1,
            "unit": 101,
            "name": "Flat 101 (2BHK Luxury)",
            "carpet_area_sqm": 88.5,
            "built_up_area_sqm": 105.0,
            "ceiling_height_m": 3.0,
            "rooms_count": 4,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.9048, 18.6020], [73.9050, 18.6020], [73.9050, 18.6018], [73.9048, 18.6018], [73.9048, 18.6020]]],
            },
        },
        {
            "floor": 2,
            "unit": 201,
            "name": "Flat 201 (2BHK Luxury)",
            "carpet_area_sqm": 88.5,
            "built_up_area_sqm": 105.0,
            "ceiling_height_m": 3.0,
            "rooms_count": 4,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.9048, 18.6020], [73.9050, 18.6020], [73.9050, 18.6018], [73.9048, 18.6018], [73.9048, 18.6020]]],
            },
        },
        {
            "floor": -1,
            "unit": 1,
            "unit_type": "parking_basement",
            "name": "Basement B1 Reserved Slot 01",
            "carpet_area_sqm": 12.5,
            "ceiling_height_m": 2.8,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[73.9048, 18.6020], [73.9049, 18.6020], [73.9049, 18.6019], [73.9048, 18.6019], [73.9048, 18.6020]]],
            },
        },
    ],
}
with open(os.path.join(DATA_SAMPLES, "building_floor_plan_cad.json"), "w", encoding="utf-8") as f:
    json.dump(cad_sample, f, indent=2)

# 5. High-Precision GNSS / CORS Survey Sample
gnss_sample = {
    "survey_id": "CORS-SVY-2026-088",
    "survey_name": "Sadashiv Cadastral CORS High-Precision Survey",
    "cors_station_id": "CORS-IN-MH-PUN01",
    "state": "MH",
    "district": "PUN",
    "fix_type": "RTK_FIXED",
    "horizontal_accuracy_cm": 1.2,
    "vertical_accuracy_cm": 1.8,
    "pdop": 1.1,
    "num_satellites": 28,
    "surveyor_id": "SURVEYOR-GOV-MH449",
    "boundary_points": [
        {"id": "P1", "lon": 73.845100, "lat": 18.511300, "elevation_m": 558.12},
        {"id": "P2", "lon": 73.845750, "lat": 18.511350, "elevation_m": 558.15},
        {"id": "P3", "lon": 73.845700, "lat": 18.511980, "elevation_m": 558.18},
        {"id": "P4", "lon": 73.845050, "lat": 18.511940, "elevation_m": 558.14},
        {"id": "P1", "lon": 73.845100, "lat": 18.511300, "elevation_m": 558.12},
    ],
}
with open(os.path.join(DATA_SAMPLES, "gnss_cors_survey.json"), "w", encoding="utf-8") as f:
    json.dump(gnss_sample, f, indent=2)

# 6. DEM/DSM Elevation Grid Sample
dem_sample = {
    "tiles": [
        {
            "id": "tile-dem-dsm-01",
            "name": "Sadashiv Terrain Elevation Cell",
            "dem_elevation_m": 558.0,
            "dsm_elevation_m": 573.0,
            "ndsm_height_m": 15.0,
            "slope_deg": 0.8,
            "vertical_datum": "EGM2008",
            "resolution_m": 0.5,
            "bbox": [73.8452, 18.5115, 73.8458, 18.5121],
        }
    ]
}
with open(os.path.join(DATA_SAMPLES, "dem_dsm_elevation_grid.json"), "w", encoding="utf-8") as f:
    json.dump(dem_sample, f, indent=2)

print("Generated all 6 multi-sensor sample files in data/samples/ successfully.")
