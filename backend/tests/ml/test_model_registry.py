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
    clear_model_loaders,
    get_model_registry,
    register_model_loader,
    unregister_model_loader,
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Isolate registry state between tests."""
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    clear_model_loaders()
    yield
    ModelRegistry.reset_for_tests()
    clear_model_loaders()
    get_ml_config.cache_clear()


def test_model_registry_singleton_across_threads() -> None:
    """All threads should receive the same registry instance."""
    instances: list[ModelRegistry] = []

    def _capture_instance() -> None:
        instances.append(get_model_registry())

    threads = [threading.Thread(target=_capture_instance) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(instances) == 8
    assert len({id(instance) for instance in instances}) == 1


def test_get_model_lazy_loads_and_caches() -> None:
    """Second get_model call should return the same cached object."""
    load_count = 0

    def _loader(_registry: ModelRegistry) -> dict[str, str]:
        nonlocal load_count
        load_count += 1
        return {"name": "test-model"}

    register_model_loader("test_model", _loader)
    registry = get_model_registry()

    first = registry.get_model("test_model")
    second = registry.get_model("test_model")

    assert first is second
    assert load_count == 1


def test_get_model_unknown_raises_not_registered() -> None:
    """Unregistered model names should raise ModelNotRegisteredError."""
    registry = get_model_registry()

    with pytest.raises(ModelNotRegisteredError, match="scrfd"):
        registry.get_model("scrfd")


def test_unload_all_clears_cache_and_allows_reload() -> None:
    """unload_all should drop cached models so loaders run again."""
    load_count = 0

    def _loader(_registry: ModelRegistry) -> dict[str, int]:
        nonlocal load_count
        load_count += 1
        return {"loads": load_count}

    register_model_loader("reloadable", _loader)
    registry = get_model_registry()

    first = registry.get_model("reloadable")
    registry.unload_all()
    second = registry.get_model("reloadable")

    assert first["loads"] == 1
    assert second["loads"] == 2


def test_unregister_model_loader() -> None:
    """Removing a loader prevents future loads."""
    register_model_loader("temporary", lambda _registry: {"ok": True})
    unregister_model_loader("temporary")
    registry = get_model_registry()

    with pytest.raises(ModelNotRegisteredError):
        registry.get_model("temporary")


def test_resolved_device_cpu_without_torch() -> None:
    """CPU resolution should not require torch when device is explicitly cpu."""
    config = MLConfig(device="cpu")
    registry = ModelRegistry(config=config)

    assert registry.resolved_device == "cpu"


def test_resolved_device_auto_when_torch_available() -> None:
    """Auto resolution should pick cuda, mps, or cpu based on availability."""
    pytest.importorskip("torch")
    import torch

    config = MLConfig(device="auto")
    registry = ModelRegistry(config=config)
    resolved = registry.resolved_device

    if torch.cuda.is_available():
        assert resolved == "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        assert resolved == "mps"
    else:
        assert resolved == "cpu"


def test_strict_worker_only_blocks_outside_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict mode should block model loading outside Celery workers."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(model_registry_module, "is_test_process", lambda: False)
    config = MLConfig(strict_worker_only=True, device="cpu")
    registry = ModelRegistry(config=config)
    register_model_loader("blocked", lambda _registry: {"value": 1})

    with pytest.raises(ModelLoadError, match="Celery worker"):
        registry.get_model("blocked")


def test_model_with_close_hook_is_called_on_unload() -> None:
    """unload_all should call close() when present on cached models."""

    class _ClosableModel:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    model_holder: dict[str, Any] = {}

    def _loader(_registry: ModelRegistry) -> _ClosableModel:
        model = _ClosableModel()
        model_holder["model"] = model
        return model

    register_model_loader("closable", _loader)
    registry = get_model_registry()
    registry.get_model("closable")
    registry.unload_all()

    assert model_holder["model"].closed is True
