"""Tests for the ML model registry."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from app.ml import model_registry as model_registry_module
from app.ml.config import MLConfig, get_ml_config
from app.ml.exceptions import ModelLoadError, ModelNotRegisteredError
from app.ml.model_registry import (
    ModelRegistry,
    get_model_registry,
    register_model_loader,
    restore_model_loaders,
    snapshot_model_loaders,
    unregister_model_loader,
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
