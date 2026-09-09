"""Embedding mode resolution from ML configuration."""

from __future__ import annotations

from typing import Literal

from app.ml.config import MLConfig

EmbeddingMode = Literal["dual", "r100"]


def resolve_embedding_mode(config: MLConfig) -> EmbeddingMode:
    """Resolve the active embedding mode from configuration.

    Rules:
    - ``ML_EMBEDDING_MODEL=dual`` with ``ML_DUAL_MODEL_ENABLED=true`` → dual
    - ``ML_EMBEDDING_MODEL=r100`` or ``ML_DUAL_MODEL_ENABLED=false`` → r100 only
    - ``adaface`` / ``mbf`` values are not standalone modes; they fall back to r100
      (AdaFace runs only as secondary in dual; MBF is OOM fallback only).

    Args:
        config: Active ML configuration.

    Returns:
        Either ``dual`` or ``r100``.
    """
    if not config.dual_model_enabled:
        return "r100"

    if config.embedding_model == "dual":
        return "dual"

    return "r100"
