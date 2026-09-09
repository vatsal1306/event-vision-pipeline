"""Unit tests for embedding utilities (no model weights required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from app.ml.config import MLConfig
from app.ml.embedding.base import l2_normalize
from app.ml.embedding.batch_utils import extract_batch_with_oom_retry
from app.ml.embedding.mode import resolve_embedding_mode


def test_l2_normalize_unit_vectors() -> None:
    """L2 normalization should produce unit norm along the last axis."""
    vectors = np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)
    normalized = l2_normalize(vectors, axis=1)

    norms = np.linalg.norm(normalized, axis=1)
    np.testing.assert_allclose(norms, [1.0, 1.0], rtol=1e-5)
    np.testing.assert_allclose(normalized[0], [0.6, 0.8], rtol=1e-5)


def test_resolve_embedding_mode_dual_default() -> None:
    """Default config should resolve to dual mode."""
    config = MLConfig(embedding_model="dual", dual_model_enabled=True)
    assert resolve_embedding_mode(config) == "dual"


def test_resolve_embedding_mode_r100_only() -> None:
    """r100 mode or disabled dual flag should resolve to r100."""
    assert resolve_embedding_mode(MLConfig(embedding_model="r100")) == "r100"
    config = MLConfig(embedding_model="dual", dual_model_enabled=False)
    assert resolve_embedding_mode(config) == "r100"


def test_resolve_embedding_mode_adaface_maps_to_r100() -> None:
    """AdaFace is not a standalone mode — falls back to r100-only."""
    config = MLConfig(embedding_model="adaface", dual_model_enabled=True)
    assert resolve_embedding_mode(config) == "r100"


def test_extract_batch_with_oom_retry_halves_batch_size() -> None:
    """CUDA OOM should trigger batch halving before succeeding."""
    calls: list[int] = []

    class FakeCudaOomError(Exception):
        pass

    def extract_fn(faces: list[np.ndarray], batch_size: int) -> np.ndarray:
        calls.append(batch_size)
        if batch_size > 1:
            raise FakeCudaOomError("CUDA out of memory")
        return np.ones((len(faces), 512), dtype=np.float32)

    faces = [np.zeros((112, 112, 3), dtype=np.uint8) for _ in range(4)]

    with patch("app.ml.embedding.batch_utils._is_cuda_oom", return_value=True):
        result = extract_batch_with_oom_retry(
            faces,
            batch_size=64,
            extract_fn=extract_fn,
            model_name="test_model",
        )

    assert calls == [64, 32, 16, 8, 4, 2, 1]
    assert result.shape == (4, 512)


def test_extract_batch_with_oom_retry_empty_input() -> None:
    """Empty face list should return an empty array."""
    result = extract_batch_with_oom_retry(
        [],
        batch_size=64,
        extract_fn=MagicMock(),
        model_name="test_model",
    )
    assert result.shape == (0, 512)
