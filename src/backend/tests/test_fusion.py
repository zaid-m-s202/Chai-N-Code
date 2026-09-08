"""Tests for observation fusion service (PRD §5.3 / FR-FUS-01 to FR-FUS-05)."""

from datetime import datetime, timedelta, timezone
import pytest
from app.services.fusion import Observation, fuse, fuse_attribute, recency_weight


def test_single_observation():
    now = datetime.now(timezone.utc)
    obs = [Observation(value=15.0, source_confidence=0.9, observed_at=now)]
    val, conf = fuse(obs)
    assert pytest.approx(val, 0.01) == 15.0
    assert pytest.approx(conf, 0.01) == 0.9


def test_recency_decay_reduces_weight():
    now = datetime.now(timezone.utc)
    half_life_ago = now - timedelta(days=365)
    weight_now = recency_weight(now)
    weight_old = recency_weight(half_life_ago)

    assert pytest.approx(weight_now, 0.01) == 1.0
    assert pytest.approx(weight_old, 0.01) == 0.5


def test_multi_observation_fusion_favors_recent_confident():
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=365)

    # Old measurement: 10.0m with 0.8 conf (decayed to weight ~ 0.4)
    # New measurement: 20.0m with 0.9 conf (weight ~ 0.9)
    obs = [
        Observation(value=10.0, source_confidence=0.8, observed_at=old_date),
        Observation(value=20.0, source_confidence=0.9, observed_at=now),
    ]
    val, conf = fuse(obs)

    # The fused value should lean towards the newer, higher-confidence 20.0
    assert val > 15.0
    assert 0.0 < conf <= 1.0


def test_conflict_detection_when_observations_differ_beyond_threshold():
    now = datetime.now(timezone.utc)
    # Two observations with heights 12.0m and 28.0m (diff = 16.0m > tolerance of 3.0m)
    obs = [
        Observation(value=12.0, source_confidence=0.85, observed_at=now, source_id="SURVEY_A"),
        Observation(value=28.0, source_confidence=0.90, observed_at=now, source_id="SURVEY_B"),
    ]
    res = fuse_attribute(obs, conflict_tolerance_abs=3.0)

    assert res.has_conflict is True
    assert res.conflict_reason is not None
    assert "Contradictory observations detected" in res.conflict_reason
    assert res.delta == 16.0
    # Confidence should be penalized due to conflict
    assert res.fused_confidence < 0.85


def test_concordant_observations_boost_confidence():
    now = datetime.now(timezone.utc)
    # Three independent observations in close agreement (diff <= 0.4m)
    obs = [
        Observation(value=24.5, source_confidence=0.85, observed_at=now, source_id="DRONE"),
        Observation(value=24.8, source_confidence=0.88, observed_at=now, source_id="LIDAR"),
        Observation(value=24.6, source_confidence=0.82, observed_at=now, source_id="RADAR"),
    ]
    res = fuse_attribute(obs, conflict_tolerance_abs=3.0)

    assert res.has_conflict is False
    assert pytest.approx(res.fused_value, abs=0.2) == 24.6
    # Multi-source agreement boosts confidence above individual average
    assert res.fused_confidence >= 0.85


def test_empty_observations_raises_error():
    with pytest.raises(ValueError, match="At least one observation is required"):
        fuse([])
