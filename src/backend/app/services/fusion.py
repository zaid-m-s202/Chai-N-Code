"""Observation fusion service with recency decay, source reliability, and conflict detection.

Maps to PRD §5.3:
- FR-FUS-01: Store all observations for attributes such as footprint, height and floor count.
- FR-FUS-02: Compute fused values using source reliability × recency decay.
- FR-FUS-03: Flag conflicts when values differ beyond a configurable tolerance.
- FR-FUS-04: Never hide conflicts by silently averaging contradictory evidence.
- FR-FUS-05: Allow re-fusion later from preserved observations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import exp
from typing import Optional


@dataclass
class Observation:
    value: float
    source_confidence: float
    observed_at: datetime
    source_id: Optional[str] = None
    observation_id: Optional[str] = None


@dataclass
class FusionResult:
    fused_value: float
    fused_confidence: float
    has_conflict: bool = False
    conflict_reason: Optional[str] = None
    delta: float = 0.0
    relative_delta: float = 0.0
    observations_count: int = 0
    weights: list[float] = field(default_factory=list)


def recency_weight(observed_at: datetime, half_life_days: float = 365.0) -> float:
    """Compute exponential decay weight based on observation age."""
    if observed_at.tzinfo is not None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.now()
    age_days = max(0.0, (now - observed_at).total_seconds() / 86400)
    return exp(-0.69314718056 * age_days / half_life_days)


def fuse_attribute(
    observations: list[Observation],
    conflict_tolerance_abs: float = 3.0,
    conflict_tolerance_rel: float = 0.25,
    half_life_days: float = 365.0,
) -> FusionResult:
    """Fuse multiple numeric observations into a weighted consensus, flagging conflicts.
    
    Args:
        observations: List of observations with value, confidence, and timestamp.
        conflict_tolerance_abs: Absolute threshold beyond which values conflict (e.g. 3m).
        conflict_tolerance_rel: Relative percentage threshold beyond which values conflict (e.g. 25%).
        half_life_days: Half-life for temporal recency decay in days.
    """
    if not observations:
        raise ValueError("At least one observation is required for fusion")

    if len(observations) == 1:
        obs = observations[0]
        w = max(0.0, min(1.0, obs.source_confidence)) * recency_weight(obs.observed_at, half_life_days)
        return FusionResult(
            fused_value=round(obs.value, 4),
            fused_confidence=round(obs.source_confidence, 4),
            has_conflict=False,
            conflict_reason=None,
            delta=0.0,
            relative_delta=0.0,
            observations_count=1,
            weights=[round(w, 4)],
        )

    # Compute weights = source reliability * recency decay
    weights = [
        max(0.01, min(1.0, o.source_confidence)) * recency_weight(o.observed_at, half_life_days)
        for o in observations
    ]
    total_weight = sum(weights)

    if total_weight == 0:
        fused_val = observations[-1].value
        raw_conf = 0.1
    else:
        fused_val = sum(o.value * w for o, w in zip(observations, weights)) / total_weight
        # Base confidence is the weighted mean confidence of contributing sources
        raw_conf = min(1.0, total_weight / len(observations))

    # Evaluate conflict thresholds:
    values = [o.value for o in observations]
    min_val = min(values)
    max_val = max(values)
    delta = round(max_val - min_val, 4)
    ref_val = max(abs(fused_val), 1.0)
    relative_delta = round(delta / ref_val, 4)

    has_conflict = False
    conflict_reason = None

    if delta > conflict_tolerance_abs or relative_delta > conflict_tolerance_rel:
        has_conflict = True
        conflict_reason = (
            f"Contradictory observations detected: range [{min_val}, {max_val}], "
            f"discrepancy {delta:.2f} exceeds absolute threshold {conflict_tolerance_abs} "
            f"or relative tolerance {conflict_tolerance_rel * 100:.0f}%"
        )
        # FR-FUS-04: Never hide conflicts by silently averaging contradictory evidence;
        # Penalize the fused confidence when sources actively contradict each other
        fused_confidence = round(max(0.1, raw_conf * 0.5), 4)
    else:
        # Agreement between multiple independent sources boosts confidence
        agreement_bonus = min(0.15, 0.05 * (len(observations) - 1))
        fused_confidence = round(min(0.99, raw_conf + agreement_bonus), 4)

    return FusionResult(
        fused_value=round(fused_val, 4),
        fused_confidence=fused_confidence,
        has_conflict=has_conflict,
        conflict_reason=conflict_reason,
        delta=delta,
        relative_delta=relative_delta,
        observations_count=len(observations),
        weights=[round(w, 4) for w in weights],
    )


def fuse(observations: list[Observation]) -> tuple[float, float]:
    """Backward-compatible wrapper returning (fused_value, fused_confidence)."""
    res = fuse_attribute(observations)
    return res.fused_value, res.fused_confidence
