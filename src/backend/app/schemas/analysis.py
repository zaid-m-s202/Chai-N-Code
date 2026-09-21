"""Pydantic schemas for AI/GIS analysis endpoints (PRD §5.4)."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AdapterInfoResponse(BaseModel):
    name: str
    version: str
    description: str
    supported_input_types: list[str]


class DsmDemHeightRequest(BaseModel):
    dsm: Optional[float] = Field(None, description="Single surface elevation value (m)")
    dem: Optional[float] = Field(None, description="Single bare-earth terrain elevation value (m)")
    dsm_samples: Optional[list[float]] = Field(None, description="List of surface elevation samples")
    dem_samples: Optional[list[float]] = Field(None, description="List of terrain elevation samples")
    samples: Optional[list[dict[str, float]]] = Field(None, description="List of {'dsm': ..., 'dem': ...} points")
    sensor_type: Optional[str] = Field("photogrammetry_or_lidar", description="LiDAR, Stereo-Satellite, Drone, etc.")


class FloorEstimatorRequest(BaseModel):
    height: Optional[float] = Field(None, description="Total building height in meters")
    building_height: Optional[float] = Field(None, description="Alternative key for height")
    floor_count: Optional[int] = Field(None, description="Optional known floor count")
    use_type: Optional[str] = Field("residential", description="residential, commercial, office, etc.")
    base_elevation: Optional[float] = Field(0.0, description="Base ground elevation datum (m)")


class FootprintExtractionRequest(BaseModel):
    parcel_geometry: Optional[dict[str, Any]] = Field(None, description="GeoJSON parcel polygon")
    bbox: Optional[list[float]] = Field(None, description="[min_x, min_y, max_x, max_y]")
    coordinates: Optional[list[Any]] = Field(None, description="Raw coordinate array")
    mask_grid: Optional[list[list[int]]] = Field(None, description="Binary grid mask")
    scale_factor: Optional[float] = Field(0.75, description="Setback scale ratio within parcel")
    tolerance: Optional[float] = Field(0.00002, description="Douglas-Peucker simplification tolerance")
    model_name: Optional[str] = Field("CadastralMaskRCNN-V2", description="AI extraction model tag")
    drone_imagery: Optional[dict[str, Any]] = Field(None, description="Drone orthomosaic coverage or metadata")
    lidar_cluster: Optional[dict[str, Any]] = Field(None, description="LiDAR 3D point cloud cluster or bounds")


class FloorSegmentationRequest(BaseModel):
    footprint: Optional[dict[str, Any]] = Field(None, description="Building footprint GeoJSON geometry")
    units_count: Optional[int] = Field(4, description="Target units per floor")
    floor_number: Optional[int] = Field(1, description="Floor index")
    building_id: Optional[int] = Field(1, description="Building numerical ID")
    base_ulpin: Optional[str] = Field("INMH01PARCEL0001", description="Parent parcel base ULPIN")
    ceiling_height_m: Optional[float] = Field(3.0, description="Floor-to-ceiling height in meters")
    ground_elevation_m: Optional[float] = Field(0.0, description="Base ground elevation in meters")
    corridor_ratio: Optional[float] = Field(0.12, description="Common circulation hallway ratio")


class VerticalParcelDelineationRequest(BaseModel):
    footprint: Optional[dict[str, Any]] = Field(None, description="Base parcel GeoJSON geometry")
    base_ulpin: Optional[str] = Field(None, description="Base 14-character parcel ULPIN")
    state: Optional[str] = Field("MH", description="2-letter state code")
    district: Optional[str] = Field("MUM", description="3-letter district code")
    floor_count: Optional[int] = Field(5, description="Number of above-ground floors")
    units_per_floor: Optional[int] = Field(4, description="Number of units per floor")
    basement_levels: Optional[int] = Field(1, description="Number of basement levels")
    ceiling_height_m: Optional[float] = Field(3.0, description="Floor-to-ceiling height in meters")
    ground_elevation_m: Optional[float] = Field(12.0, description="Ground elevation datum (m)")
    include_underground_utilities: Optional[bool] = Field(True, description="Include metro tunnel & utility corridors")


class TopologyValidationRequest(BaseModel):
    parcels: Optional[list[dict[str, Any]]] = Field(None, description="List of 3D property objects/units with bounds")
    features: Optional[list[dict[str, Any]]] = Field(None, description="Alternative key: GeoJSON feature array")
    parent_footprint: Optional[dict[str, Any]] = Field(None, description="Parent cadastral parcel boundary polygon")


class AnalysisResultResponse(BaseModel):
    adapter_name: str
    adapter_version: str
    status: str
    confidence: float
    data: dict[str, Any]
    evidence: dict[str, Any]
    warnings: list[str] = []
    executed_at: str


class PropertyAnalysisRequest(BaseModel):
    elevation_data: Optional[dict[str, Any]] = Field(
        None, description="Optional elevation profile {'dsm': ..., 'dem': ...} or samples"
    )
    use_type: Optional[str] = Field(None, description="Override property use type (residential, commercial, etc.)")


class PropertyAnalysisResponse(BaseModel):
    property_id: str
    three_d_property_id: str
    status: str
    confidence: float
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    evidence_id: str
    adapters_executed: list[dict[str, Any]]
