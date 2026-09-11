"""Tests for the ML model registry."""

from __future__ import annotations

import pytest

from app.ml.config import get_ml_config
from app.ml.model_registry import (
    ModelRegistry,
    get_model_registry,
    register_model_loader,
    restore_model_loaders,
    snapshot_model_loaders,
)
from app.ml.registry_bootstrap import register_default_model_loaders
from app.ml.torch_process_cache import clear_pinned_registry_model, get_or_create


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


def test_get_or_create_runs_factory_once() -> None:
    """Process cache must return the same object on later lookups."""
    calls = {"n": 0}

    def factory() -> str:
        calls["n"] += 1
        return "vit-weights"

    first = get_or_create("test:torch-cache-once", factory)
    second = get_or_create("test:torch-cache-once", factory)
    assert first == "vit-weights"
    assert second == "vit-weights"
    assert calls["n"] == 1


def test_pinned_torch_models_survive_registry_reset() -> None:
    """R100 / age / AdaFace must not be reconstructed after unload_all."""
    calls = {"n": 0}
    dummy = object()

    def loader(_registry: ModelRegistry) -> object:
        calls["n"] += 1
        return dummy

    clear_pinned_registry_model("age_detector")
    register_model_loader("age_detector", loader)
    ModelRegistry.reset_for_tests()

    first = get_model_registry().get_model("age_detector")
    ModelRegistry.reset_for_tests()
    second = get_model_registry().get_model("age_detector")

    assert first is dummy
    assert second is dummy
    assert calls["n"] == 1
    clear_pinned_registry_model("age_detector")
