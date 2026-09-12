"""Unit tests for DualEmbedder orchestration with fake models."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.config import MLConfig
from app.ml.embedding.dual_embedder import DualEmbedder


class _FakePrimary:
    """Return a deterministic primary embedding batch."""

    model_name = "r100"

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        del batch_size
        return np.ones((len(faces), 512), dtype=np.float32)


class _FakeSecondary:
    """Return a deterministic secondary embedding batch."""

    model_name = "adaface_vit_kprpe"

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        del batch_size
        return np.full((len(faces), 512), 0.5, dtype=np.float32)


class _BrokenPrimary:
    """Simulate a CUDA OOM / runtime failure on primary extract."""

    model_name = "r100"

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        del faces, batch_size
        raise RuntimeError("CUDA out of memory")


class _FakeFallback:
    """CPU MobileFaceNet stand-in."""

    model_name = "mobilefacenet"

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        del batch_size
        return np.zeros((len(faces), 512), dtype=np.float32)


def _crop() -> np.ndarray:
    return np.zeros((112, 112, 3), dtype=np.uint8)


def test_embed_batch_empty_returns_empty_list() -> None:
    """No crops should not call the models."""
    embedder = DualEmbedder(
        primary=_FakePrimary(),  # type: ignore[arg-type]
        secondary=_FakeSecondary(),  # type: ignore[arg-type]
        fallback=None,
        config=MLConfig(embedding_model="dual", dual_model_enabled=True),
    )
    assert embedder.embed_batch([]) == []


def test_embed_single_returns_primary_and_secondary() -> None:
    """Dual mode should attach both vectors on a successful run."""
    embedder = DualEmbedder(
        primary=_FakePrimary(),  # type: ignore[arg-type]
        secondary=_FakeSecondary(),  # type: ignore[arg-type]
        fallback=None,
        config=MLConfig(embedding_model="dual", dual_model_enabled=True),
    )
    result = embedder.embed_single(_crop())
    assert result.primary.shape == (512,)
    assert result.secondary is not None
    assert result.model_primary == "r100"
    assert result.model_secondary == "adaface_vit_kprpe"


def test_primary_failure_uses_mobilefacenet_fallback() -> None:
    """Primary OOM should swap in the TFLite fallback when configured."""
    embedder = DualEmbedder(
        primary=_BrokenPrimary(),  # type: ignore[arg-type]
        secondary=None,
        fallback=_FakeFallback(),  # type: ignore[arg-type]
        config=MLConfig(embedding_model="r100", dual_model_enabled=False),
    )
    result = embedder.embed_single(_crop())
    assert result.model_primary == "mobilefacenet"
    assert result.secondary is None


def test_primary_failure_without_fallback_raises() -> None:
    """Without MobileFaceNet, primary failure must surface to the caller."""
    embedder = DualEmbedder(
        primary=_BrokenPrimary(),  # type: ignore[arg-type]
        secondary=None,
        fallback=None,
        config=MLConfig(embedding_model="r100", dual_model_enabled=False),
    )
    with pytest.raises(RuntimeError, match="out of memory"):
        embedder.embed_single(_crop())
