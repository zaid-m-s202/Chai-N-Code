"""Analysis orchestration service (PRD §5.4).

Coordinates pluggable AI/GIS adapters, attaches confidence and evidence provenance,
persists SourceObservations, updates property vertical metrics, and enforces
strict AI status gating (AI cannot directly verify properties).
"""

from typing import Any, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.analysis.base import BaseAnalysisAdapter, AnalysisResult, validate_ai_status
from app.analysis.elevation_adapter import DsmDemHeightAdapter
from app.analysis.floor_estimator_adapter import FloorEstimatorAdapter
from app.analysis.footprint_adapter import PretrainedFootprintAdapter
from app.models.property_object import PropertyObject
from app.models.source_observation import SourceObservation
from app.models.evidence import Evidence
from app.models.change_event import ChangeEvent


class AnalysisService:
    """Service to register and execute AI/GIS analysis adapters."""

    def __init__(self):
        self._adapters: dict[str, BaseAnalysisAdapter] = {}
        # Register core adapters
        self.register_adapter(DsmDemHeightAdapter())
        self.register_adapter(FloorEstimatorAdapter())
        self.register_adapter(PretrainedFootprintAdapter())

    def register_adapter(self, adapter: BaseAnalysisAdapter) -> None:
        """Register a new analysis adapter."""
        self._adapters[adapter.name] = adapter

    def get_adapter(self, name: str) -> Optional[BaseAnalysisAdapter]:
        """Retrieve an adapter by identifier."""
        return self._adapters.get(name)

    def list_adapters(self) -> list[dict[str, Any]]:
        """List metadata for all registered adapters."""
        return [
            {
                "name": adapter.name,
                "version": adapter.version,
                "description": adapter.description,
                "supported_input_types": adapter.supported_input_types,
            }
            for adapter in self._adapters.values()
        ]

    def run_adapter(self, adapter_name: str, input_data: Any, **kwargs) -> AnalysisResult:
        """Execute a specific adapter by name."""
        adapter = self.get_adapter(adapter_name)
        if not adapter:
            raise KeyError(f"Analysis adapter '{adapter_name}' not found.")
        
        result = adapter.analyze(input_data, **kwargs)
        # Extra safeguard enforcing status gating
        validate_ai_status(result.status)
        return result

    def analyze_property(
        self,
        db: Session,
        property_id: uuid.UUID,
        elevation_data: Optional[dict[str, Any]] = None,
        use_type: Optional[str] = None,
        operator_id: Optional[uuid.UUID] = None,
    ) -> dict[str, Any]:
        """Execute full AI/GIS analysis pipeline on a PropertyObject.
        
        Steps:
        1. Load PropertyObject.
        2. Execute DsmDemHeightAdapter if elevation inputs are provided.
        3. Execute FloorEstimatorAdapter based on derived height or known metrics.
        4. Persist SourceObservations for height and floor levels.
        5. Persist Evidence record documenting the analysis run and confidence.
        6. Update PropertyObject z_min, z_max, confidence, and status.
           (CRITICAL: Enforce status gating - never assign VERIFIED).
        7. Record audit ChangeEvent.
        """
        prop = db.query(PropertyObject).filter(PropertyObject.id == property_id).first()
        if not prop:
            raise ValueError(f"PropertyObject with ID '{property_id}' not found.")

        results: dict[str, AnalysisResult] = {}
        old_state = {
            "z_min": prop.z_min,
            "z_max": prop.z_max,
            "confidence": prop.confidence,
            "status": prop.status,
            "attributes": dict(prop.attributes or {}),
        }

        # Step 1: Elevation analysis if elevation data is provided or present in attributes
        elev_input = elevation_data
        if not elev_input and prop.attributes and "elevation" in prop.attributes:
            elev_input = prop.attributes["elevation"]

        derived_height: Optional[float] = None
        base_elev: float = prop.z_min if prop.z_min is not None else 0.0

        if elev_input:
            height_res = self.run_adapter("dsm_dem_height", elev_input)
            results["dsm_dem_height"] = height_res
            derived_height = float(height_res.data["building_height"])
            base_elev = float(height_res.data["base_elevation"])
        elif prop.z_min is not None and prop.z_max is not None and prop.z_max > prop.z_min:
            derived_height = round(prop.z_max - prop.z_min, 2)

        # Step 2: Floor estimation
        floor_input = {
            "height": derived_height if derived_height is not None else 9.0,
            "use_type": use_type or (prop.attributes.get("use_type") if prop.attributes else "residential"),
            "base_elevation": base_elev,
        }
        if prop.attributes and "floor_count" in prop.attributes:
            floor_input["floor_count"] = prop.attributes["floor_count"]

        floor_res = self.run_adapter("floor_estimator", floor_input)
        results["floor_estimator"] = floor_res

        # Step 3: Create Evidence record for provenance
        evidence_id = uuid.uuid4()
        evidence = Evidence(
            id=evidence_id,
            property_object_id=prop.id,
            evidence_type="ai_analysis_run",
            source_system="cadastral_ai_engine",
            operator_id=operator_id,
            file_reference=f"ai_run:{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            original_format="json",
        )
        db.add(evidence)

        # Step 4: Persist SourceObservations
        obs_records = []
        if "dsm_dem_height" in results:
            h_res = results["dsm_dem_height"]
            obs_h = SourceObservation(
                id=uuid.uuid4(),
                property_object_id=prop.id,
                attribute_name="height",
                observed_value=h_res.data,
                source_confidence=h_res.confidence,
                source_id="adapter:dsm_dem_height",
            )
            db.add(obs_h)
            obs_records.append(obs_h)

        obs_f = SourceObservation(
            id=uuid.uuid4(),
            property_object_id=prop.id,
            attribute_name="floor_count",
            observed_value=floor_res.data,
            source_confidence=floor_res.confidence,
            source_id="adapter:floor_estimator",
        )
        db.add(obs_f)
        obs_records.append(obs_f)

        # Step 5: Update PropertyObject attributes, z extents, and confidence
        effective_z_min = floor_res.data["z_min"]
        effective_z_max = floor_res.data["z_max"]
        prop.z_min = effective_z_min
        prop.z_max = effective_z_max

        # Weighted confidence from executed adapters
        avg_confidence = round(
            sum(r.confidence for r in results.values()) / len(results), 3
        )
        prop.confidence = avg_confidence

        # Update attributes bag
        current_attrs = dict(prop.attributes or {})
        current_attrs["analysis"] = {
            "last_executed_at": datetime.now(timezone.utc).isoformat(),
            "adapters": {k: {"status": v.status, "confidence": v.confidence, "data": v.data} for k, v in results.items()},
            "estimated_floors": floor_res.data["floor_count"],
            "floor_levels": floor_res.data["levels"],
        }
        prop.attributes = current_attrs

        # Append evidence ID to source_list
        current_sources = list(prop.source_list or [])
        current_sources.append(str(evidence_id))
        prop.source_list = current_sources

        # Status Gating:
        # If already VERIFIED, authority decision stands — do not overwrite.
        # Otherwise, promote from SYNTHETIC to DERIVED (if height was measured) or INFERRED.
        if prop.status != "VERIFIED":
            if "dsm_dem_height" in results:
                target_status = "DERIVED"
            else:
                target_status = "INFERRED"
            prop.status = validate_ai_status(target_status)

        new_state = {
            "z_min": prop.z_min,
            "z_max": prop.z_max,
            "confidence": prop.confidence,
            "status": prop.status,
            "attributes": prop.attributes,
        }

        # Step 6: Create ChangeEvent audit record
        change_event = ChangeEvent(
            id=uuid.uuid4(),
            property_object_id=prop.id,
            event_type="height_updated",
            old_state=old_state,
            new_state=new_state,
            actor_id=operator_id,
            evidence_id=evidence_id,
        )
        db.add(change_event)

        db.commit()
        db.refresh(prop)

        return {
            "property_id": str(prop.id),
            "three_d_property_id": prop.three_d_property_id,
            "status": prop.status,
            "confidence": prop.confidence,
            "z_min": prop.z_min,
            "z_max": prop.z_max,
            "evidence_id": str(evidence_id),
            "adapters_executed": [
                {
                    "adapter": name,
                    "status": res.status,
                    "confidence": res.confidence,
                    "warnings": res.warnings,
                    "data": res.data,
                }
                for name, res in results.items()
            ],
        }


# Global singleton instance
analysis_service = AnalysisService()
