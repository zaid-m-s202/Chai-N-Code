"""DSM minus DEM building height extraction adapter (PRD §5.4, FR-AI-01).

Calculates building height and vertical extents from Digital Surface Model (DSM)
and Digital Elevation Model (DEM) inputs:
    nDSM = DSM - DEM (Normalized Digital Surface Model)

Outputs status DERIVED with confidence score and sensor provenance evidence.
Strictly subject to AI status gating: never VERIFIED.
"""

from typing import Any, Optional
import math

from app.analysis.base import BaseAnalysisAdapter, AnalysisResult


class DsmDemHeightAdapter(BaseAnalysisAdapter):
    """Adapter to calculate building height from DSM (surface) and DEM (terrain)."""

    @property
    def name(self) -> str:
        return "dsm_dem_height"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Derives building height and vertical datum extents from Digital Surface Model (DSM) "
            "minus Digital Elevation Model (DEM) elevation profiles (nDSM = DSM - DEM)."
        )

    @property
    def supported_input_types(self) -> list[str]:
        return ["elevation_profile", "raster_points", "dsm_dem_pair", "samples"]

    def analyze(self, input_data: Any, **kwargs) -> AnalysisResult:
        """Derive building height from elevation inputs.
        
        Supported input structures:
        1. {"dsm": 45.2, "dem": 30.0, "sensor_type": "LiDAR"}
        2. {"dsm_samples": [45.1, 45.3, 44.9], "dem_samples": [30.0, 30.1, 29.9]}
        3. {"samples": [{"dsm": 45.0, "dem": 30.0}, ...]}
        """
        warnings = []
        dsm_vals: list[float] = []
        dem_vals: list[float] = []
        sensor_type = kwargs.get("sensor_type") or "photogrammetry_or_lidar"

        if isinstance(input_data, dict):
            if "sensor_type" in input_data and not kwargs.get("sensor_type"):
                sensor_type = str(input_data["sensor_type"])

            # Format 1: Direct scalars
            if "dsm" in input_data and "dem" in input_data:
                try:
                    dsm_vals = [float(input_data["dsm"])]
                    dem_vals = [float(input_data["dem"])]
                except (ValueError, TypeError):
                    raise ValueError("DSM and DEM values must be numeric numbers.")

            # Format 2: Sample lists
            elif "dsm_samples" in input_data and "dem_samples" in input_data:
                dsm_raw = input_data["dsm_samples"]
                dem_raw = input_data["dem_samples"]
                if not isinstance(dsm_raw, list) or not isinstance(dem_raw, list):
                    raise ValueError("dsm_samples and dem_samples must be lists of floats.")
                if len(dsm_raw) == 0 or len(dem_raw) == 0:
                    raise ValueError("Elevation sample lists cannot be empty.")
                dsm_vals = [float(v) for v in dsm_raw]
                dem_vals = [float(v) for v in dem_raw]

            # Format 3: Paired samples
            elif "samples" in input_data:
                samples = input_data["samples"]
                if not isinstance(samples, list) or len(samples) == 0:
                    raise ValueError("'samples' must be a non-empty list of {dsm, dem} pairs.")
                for s in samples:
                    if isinstance(s, dict) and "dsm" in s and "dem" in s:
                        dsm_vals.append(float(s["dsm"]))
                        dem_vals.append(float(s["dem"]))
                    elif isinstance(s, (list, tuple)) and len(s) >= 2:
                        dsm_vals.append(float(s[0]))
                        dem_vals.append(float(s[1]))
                    else:
                        raise ValueError(f"Invalid sample pair format: {s}")
            else:
                raise ValueError(
                    "Input dictionary must contain either ('dsm', 'dem'), "
                    "('dsm_samples', 'dem_samples'), or 'samples'."
                )
        else:
            raise ValueError("Input data must be a dictionary with elevation data.")

        if not dsm_vals or not dem_vals:
            raise ValueError("No valid elevation samples extracted from input.")

        # Compute nDSM = DSM - DEM
        # If lengths differ, pair up to minimum length or broadcast scalar DEM
        if len(dem_vals) == 1 and len(dsm_vals) > 1:
            dem_vals = dem_vals * len(dsm_vals)
        elif len(dsm_vals) == 1 and len(dem_vals) > 1:
            dsm_vals = dsm_vals * len(dem_vals)

        n = min(len(dsm_vals), len(dem_vals))
        ndsm_raw = [dsm_vals[i] - dem_vals[i] for i in range(n)]

        # Check for anomalies (e.g. DEM > DSM meaning negative height)
        negative_count = sum(1 for val in ndsm_raw if val < -0.2)
        if negative_count > 0:
            pct = (negative_count / n) * 100.0
            warnings.append(
                f"Negative elevation delta observed in {negative_count} samples ({pct:.1f}%). "
                "Clipped negative values to zero; terrain may occlude or sensor noise present."
            )

        # Non-negative clipped values
        ndsm_clean = [max(0.0, v) for v in ndsm_raw]

        # Calculate statistics
        sorted_ndsm = sorted(ndsm_clean)
        min_h = sorted_ndsm[0]
        max_h = sorted_ndsm[-1]
        mean_h = sum(sorted_ndsm) / n

        # Median
        if n % 2 == 1:
            median_h = sorted_ndsm[n // 2]
        else:
            median_h = (sorted_ndsm[n // 2 - 1] + sorted_ndsm[n // 2]) / 2.0

        # 90th percentile (standard GIS rooftop metric rejecting antennas/chimneys)
        p90_idx = int(math.ceil(0.90 * n)) - 1
        p90_idx = max(0, min(p90_idx, n - 1))
        p90_h = sorted_ndsm[p90_idx]

        # Base elevation (median DEM)
        sorted_dem = sorted(dem_vals)
        dem_median = sorted_dem[len(sorted_dem) // 2]

        # Effective building height: use p90 for multiple samples, or single delta
        building_height = p90_h if n >= 5 else max_h
        building_height = round(building_height, 2)
        base_elevation = round(dem_median, 2)
        z_min = base_elevation
        z_max = round(base_elevation + building_height, 2)

        # Confidence calibration
        # Base confidence for sensor type
        base_conf = 0.85
        if "lidar" in sensor_type.lower():
            base_conf = 0.90
        elif "satellite" in sensor_type.lower():
            base_conf = 0.78

        # Penalize if high negative delta percentage or high variance
        penalty = 0.0
        if negative_count > 0:
            penalty += min(0.30, (negative_count / n) * 0.5)

        # Penalize if sample count is tiny
        if n < 3:
            penalty += 0.05

        confidence = max(0.1, min(0.95, base_conf - penalty))
        confidence = round(confidence, 3)

        # Assemble standardized result
        result_data = {
            "building_height": building_height,
            "base_elevation": base_elevation,
            "z_min": z_min,
            "z_max": z_max,
            "statistics": {
                "sample_count": n,
                "min_height": round(min_h, 2),
                "max_height": round(max_h, 2),
                "mean_height": round(mean_h, 2),
                "median_height": round(median_h, 2),
                "p90_height": round(p90_h, 2),
            },
        }

        evidence = {
            "sensor_type": sensor_type,
            "method": "nDSM (DSM minus DEM)",
            "sample_count": n,
            "negative_samples_count": negative_count,
            "unit": "meters",
        }

        return AnalysisResult(
            adapter_name=self.name,
            adapter_version=self.version,
            status="DERIVED",  # Status gating: AI output must be DERIVED, never VERIFIED
            confidence=confidence,
            data=result_data,
            evidence=evidence,
            warnings=warnings,
        )
