"""AI/ML pipeline package.

This package contains the face detection, embedding extraction, quality
filtering, clustering, selfie matching, and liveness detection modules.

The package is designed to be imported by Celery GPU/CPU workers — **not**
by the FastAPI API process. The ``ModelRegistry`` lazy-loads heavy models
on first use, so importing this package does not trigger GPU allocations.

Public API
----------
- ``MLConfig``       — Pydantic settings for all ML thresholds and paths.
- ``get_ml_config``  — Cached singleton accessor for ``MLConfig``.
- ``ModelRegistry``  — Thread-safe singleton model loader and cache.
"""

from __future__ import annotations

from app.ml.config import MLConfig, get_ml_config
from app.ml.model_registry import ModelRegistry

__all__ = [
    "MLConfig",
    "ModelRegistry",
    "get_ml_config",
]
