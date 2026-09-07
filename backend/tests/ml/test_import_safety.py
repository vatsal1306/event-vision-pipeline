"""Import-safety and FastAPI boot tests for the ML package."""

from __future__ import annotations

import importlib
import sys

import pytest


def test_importing_app_ml_does_not_import_heavy_ml_libraries() -> None:
    """Importing app.ml must not pull torch, onnxruntime, or tensorflow."""
    for module_name in ("torch", "onnxruntime", "tensorflow"):
        sys.modules.pop(module_name, None)

    if "app.ml" in sys.modules:
        del sys.modules["app.ml"]

    import app.ml  # noqa: F401

    assert "torch" not in sys.modules
    assert "onnxruntime" not in sys.modules
    assert "tensorflow" not in sys.modules


def test_fastapi_starts_without_model_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI app should import even when model weights are absent."""
    monkeypatch.setenv("ML_MODELS_DIR", "/tmp/nonexistent-models-dir-ml001")

    for module_name in ("app.main", "app.ml", "app.ml.config"):
        sys.modules.pop(module_name, None)

    from app.ml.config import get_ml_config

    get_ml_config.cache_clear()

    main = importlib.import_module("app.main")

    assert main.app is not None
    assert not get_ml_config().models_path.exists()
