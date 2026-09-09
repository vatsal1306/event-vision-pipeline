"""Tests for the ML model registry."""

from __future__ import annotations

import pytest

from app.ml.config import get_ml_config
from app.ml.model_registry import (
    ModelRegistry,
    restore_model_loaders,
    snapshot_model_loaders,
)
from app.ml.registry_bootstrap import register_default_model_loaders


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Isolate registry state between tests without dropping production loaders."""
    saved_loaders = snapshot_model_loaders()
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    yield
    restore_model_loaders(saved_loaders)
    ModelRegistry.reset_for_tests()
    get_ml_config.cache_clear()
