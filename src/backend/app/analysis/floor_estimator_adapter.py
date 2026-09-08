"""Floor estimation adapter using occupancy-calibrated height heuristics (PRD §5.4, FR-AI-04).

Estimates floor counts and computes 3D vertical intervals [z_min, z_max] for
each floor/level from building height and use type.

Outputs status INFERRED with residual-based confidence score and evidence metadata.
Strictly subject to AI status gating: never VERIFIED.
"""

from typing import Any, Optional
import math

from app.analysis.base import BaseAnalysisAdapter, AnalysisResult
from app.services.floor_height_heuristic import (
    DEFAULT_FLOOR_HEIGHTS_BY_USE,
    DEFAULT_FALLBACK_FLOOR_HEIGHT,
    get_typical_floor_height,
    estimate_building_levels,
    compute_floor_vertical_extents,
)


class FloorEstimatorAdapter(BaseAnalysisAdapter):
    """Adapter to estimate floor count and vertical extents from height and use type."""

    @property
    def name(self) -> str:
        return "floor_estimator"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Estimates floor count, per-level heights, and vertical intervals [z_min, z_max] "
            "from building height and occupancy use type using calibrated heuristics."
        )

    @property
    def supported_input_types(self) -> list[str]:
        return ["height", "building_height", "analysis_result", "property_object"]

    def analyze(self, input_data: Any, **kwargs) -> AnalysisResult:
        """Estimate floor levels from height and use type.
        
        Accepted input structures:
        1. {"height": 18.5, "use_type": "residential", "base_elevation": 25.0}
        2. {"building_height": 18.5, "floor_count": 6}
        3. Raw float: 18.5
        """
        warnings = []
        total_height: Optional[float] = None
        known_floors: Optional[int] = None
        use_type: Optional[str] = kwargs.get("use_type") or "residential"
        base_elevation: float = float(kwargs.get("base_elevation") or 0.0)

        # Parse input data
        if isinstance(input_data, (int, float)):
            total_height = float(input_data)
        elif isinstance(input_data, dict):
            # Check for direct height keys or nested data from elevation adapter
            if "height" in input_data:
                total_height = float(input_data["height"])
            elif "building_height" in input_data:
                total_height = float(input_data["building_height"])
            elif "total_height" in input_data:
                total_height = float(input_data["total_height"])
            elif "data" in input_data and isinstance(input_data["data"], dict):
                inner = input_data["data"]
                total_height = float(inner.get("building_height") or inner.get("height") or 0.0)
                if "base_elevation" in inner and not kwargs.get("base_elevation"):
                    base_elevation = float(inner["base_elevation"])

            if "floor_count" in input_data and input_data["floor_count"] is not None:
                known_floors = int(input_data["floor_count"])
            if "use_type" in input_data and input_data["use_type"]:
                use_type = str(input_data["use_type"])
            if "base_elevation" in input_data and not kwargs.get("base_elevation"):
                base_elevation = float(input_data["base_elevation"])
        else:
            raise ValueError(
                "Input data must be a numeric height or dictionary containing 'height' or 'building_height'."
            )

        if total_height is None or total_height <= 0:
            if known_floors is not None and known_floors > 0:
                heuristic_floor_h = get_typical_floor_height(use_type)
                total_height = round(known_floors * heuristic_floor_h, 2)
                warnings.append(
                    f"No total height provided; synthesized total height {total_height}m "
                    f"from {known_floors} floors × {heuristic_floor_h}m ({use_type})."
                )
            else:
                raise ValueError("Must provide positive 'height' or 'floor_count' for floor estimation.")

        # Execute heuristic derivation
        effective_height, floor_count, floor_height = estimate_building_levels(
            total_height=total_height,
            floor_count=known_floors,
            use_type=use_type,
            base_elevation=base_elevation,
        )

        # Compute vertical extents for each floor
        levels = compute_floor_vertical_extents(
            floor_count=floor_count,
            floor_height=floor_height,
            base_z=base_elevation,
        )

        # Calibrate confidence score
        typical_h = get_typical_floor_height(use_type)
        if known_floors is not None:
            # If floor count was known and used, high confidence
            confidence = 0.92
        else:
            # Residual-based confidence: how closely does total_height / typical_h fit an integer?
            ideal_floors = total_height / typical_h
            fractional_error = abs(ideal_floors - round(ideal_floors))
            # fractional_error ranges from 0.0 (perfect fit) to 0.5 (worst fit)
            confidence = 0.88 - (fractional_error * 0.25)
            confidence = max(0.55, min(0.90, confidence))

        confidence = round(confidence, 3)

        result_data = {
            "building_height": effective_height,
            "floor_count": floor_count,
            "floor_height": floor_height,
            "base_elevation": base_elevation,
            "z_min": round(base_elevation, 2),
            "z_max": round(base_elevation + effective_height, 2),
            "levels": levels,
        }

        evidence = {
            "heuristic_use_type": use_type,
            "typical_floor_height": typical_h,
            "known_floor_count_provided": known_floors is not None,
            "unit": "meters",
        }

        return AnalysisResult(
            adapter_name=self.name,
            adapter_version=self.version,
            status="INFERRED",  # Status gating: AI heuristic output must be INFERRED, never VERIFIED
            confidence=confidence,
            data=result_data,
            evidence=evidence,
            warnings=warnings,
        )
