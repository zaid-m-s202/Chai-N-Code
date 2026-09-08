"""Base contract for sensor-agnostic ingestion adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from shapely.geometry.base import BaseGeometry


@dataclass
class CanonicalRecord:
    """Standardized property observation extracted by an adapter."""
    ulpin: str
    object_type: str  # parcel | building | floor | unit
    geometry: Optional[BaseGeometry] = None
    geojson_geometry: Optional[dict[str, Any]] = None
    building_seq: int = 1
    floor_seq: int = 0
    unit_seq: int = 0
    z_min: Optional[float] = None
    z_max: Optional[float] = None
    height: Optional[float] = None
    floor_count: Optional[int] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    source_confidence: float = 0.7
    observed_at: Optional[datetime] = None
    source_id: Optional[str] = None
    original_crs: str = "EPSG:4326"


class IngestionAdapter(ABC):
    """Abstract base class for all file and sensor format adapters."""

    @abstractmethod
    def parse(self, file_content: bytes, filename: str, metadata: Optional[dict[str, Any]] = None) -> list[CanonicalRecord]:
        """Parse raw content into canonical records with provenance."""
        pass
