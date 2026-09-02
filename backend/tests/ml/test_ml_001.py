"""Unit tests for ML-001 (MLConfig & ModelRegistry skeleton)."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.ml.config import MLConfig, get_ml_config
from app.ml.model_registry import ModelRegistry


def test_ml_config_default_values() -> None:
    """Verify default MLConfig values from spec."""
    config = MLConfig()
    assert config.blur_threshold == 0.5
    assert config.yaw_threshold == 45.0
    assert config.pitch_threshold == 35.0
    assert config.roll_threshold == 45.0
    assert config.dbscan_eps == 0.45
    assert config.agglo_threshold == 0.45
    assert config.selfie_match_threshold == 0.55
    assert config.max_cluster_matches == 5
    assert config.embedding_batch_size == 64


def test_ml_config_env_override() -> None:
    """Verify environment variables override default values."""
    with patch.dict(os.environ, {"ML_BLUR_THRESHOLD": "0.7", "ML_DEVICE": "cpu"}):
        config = MLConfig()
        assert config.blur_threshold == 0.7
        assert config.device == "cpu"


def test_model_registry_singleton() -> None:
    """Verify ModelRegistry returns the exact same instance."""
    ModelRegistry.reset()
    reg1 = ModelRegistry.get_instance()
    reg2 = ModelRegistry.get_instance()
    assert reg1 is reg2
    ModelRegistry.reset()


def test_get_ml_config_cached() -> None:
    """Verify get_ml_config returns cached singleton."""
    cfg1 = get_ml_config()
    cfg2 = get_ml_config()
    assert cfg1 is cfg2
