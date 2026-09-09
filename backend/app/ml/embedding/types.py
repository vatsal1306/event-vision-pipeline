"""Shared types for face embedding extraction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EmbeddingResult:
    """Dual-model embedding output for a single face crop."""

    primary: np.ndarray
    secondary: np.ndarray | None
    model_primary: str = "r100"
    model_secondary: str | None = "adaface_vit_kprpe"
