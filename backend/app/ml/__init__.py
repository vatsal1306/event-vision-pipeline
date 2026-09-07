"""ML pipeline package — config and model registry foundation."""

from __future__ import annotations

from app.ml.config import MLConfig, get_ml_config
from app.ml.model_registry import (
    ModelRegistry,
    get_model_registry,
    register_model_loader,
)

__all__ = [
    "MLConfig",
    "ModelRegistry",
    "get_ml_config",
    "get_model_registry",
    "register_model_loader",
]
