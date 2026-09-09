"""Import-safety and FastAPI boot tests for the ML package."""

from __future__ import annotations

import sys

import pytest

from app.main import app
from app.ml.config import MLConfig, get_ml_config


def test_importing_app_ml_does_not_import_heavy_ml_libraries() -> None:
    """Importing app.ml must not pull torch, onnxruntime, or ai-edge-litert."""
    for module_name in ("torch", "onnxruntime", "ai_edge_litert"):
        sys.modules.pop(module_name, None)

    if "app.ml" in sys.modules:
        del sys.modules["app.ml"]

    import app.ml  # noqa: F401

    assert "torch" not in sys.modules
    assert "onnxruntime" not in sys.modules
    assert "ai_edge_litert" not in sys.modules


def test_fastapi_starts_without_model_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI app should boot when model weight files are absent on disk."""
    monkeypatch.setenv("ML_MODELS_DIR", "/tmp/nonexistent-models-dir-ml001")
    get_ml_config.cache_clear()

    config = MLConfig()
    assert not config.models_path.exists()
    assert app is not None
