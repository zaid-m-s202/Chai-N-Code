"""Base architecture for pluggable AI/GIS analysis adapters (PRD §5.4, FR-AI-01).

Core principle:
- AI derives; evidence supports; authority verifies.
- Status gating: AI outputs must NEVER be given VERIFIED status directly.
  They are strictly tagged as INFERRED or DERIVED.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


ALLOWED_AI_STATUSES = {"INFERRED", "DERIVED", "PROVISIONAL"}


def validate_ai_status(status: str) -> str:
    """Enforce strict status gating on AI outputs.
    
    Raises ValueError if status is VERIFIED or invalid.
    """
    normalized = status.upper().strip()
    if normalized == "VERIFIED":
        raise ValueError(
            "Status Gating Violation (PRD §5.4 / §5.7): AI analysis outputs cannot "
            "directly produce 'VERIFIED' status. AI derives or infers; only authorized "
            "verifying officers may promote records to VERIFIED."
        )
    if normalized not in ALLOWED_AI_STATUSES:
        raise ValueError(
            f"Invalid AI analysis status '{status}'. Must be one of: {ALLOWED_AI_STATUSES}"
        )
    return normalized


@dataclass
class AnalysisResult:
    """Standardized output contract for all AI/GIS analysis adapters."""
    adapter_name: str
    adapter_version: str
    status: str  # Must be INFERRED or DERIVED
    confidence: float  # 0.0 to 1.0
    data: dict[str, Any]
    evidence: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        # Validate status gating
        self.status = validate_ai_status(self.status)
        # Validate confidence bounds
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence score {self.confidence} must be between 0.0 and 1.0"
            )
        # Ensure evidence metadata is attached
        if "adapter" not in self.evidence:
            self.evidence["adapter"] = self.adapter_name
        if "version" not in self.evidence:
            self.evidence["version"] = self.adapter_version
        if "executed_at" not in self.evidence:
            self.evidence["executed_at"] = self.executed_at


class BaseAnalysisAdapter(ABC):
    """Abstract contract for pluggable AI/GIS analysis adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter identifier."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Adapter semantic version."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable adapter description."""
        pass

    @property
    @abstractmethod
    def supported_input_types(self) -> list[str]:
        """List of supported input types (e.g. ['elevation', 'raster', 'tabular', 'polygon'])."""
        pass

    @abstractmethod
    def analyze(self, input_data: Any, **kwargs) -> AnalysisResult:
        """Execute analysis and return standardized AnalysisResult.
        
        Must attach confidence and evidence references (FR-AI-05).
        Must NOT output VERIFIED status (status gating).
        """
        pass
