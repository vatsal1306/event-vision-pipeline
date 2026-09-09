"""Register default ML model loaders for production and tests."""

from __future__ import annotations

from app.ml.detection.registry import register_detection_loaders
from app.ml.embedding.registry import register_embedding_loaders
from app.ml.quality.registry import register_quality_loaders


def register_default_model_loaders() -> None:
    """Register all built-in model loaders (idempotent)."""
    register_detection_loaders()
    register_quality_loaders()
    register_embedding_loaders()
