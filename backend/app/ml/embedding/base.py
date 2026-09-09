"""Abstract base class and shared utilities for embedding models."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

EMBEDDING_DIM = 512


def l2_normalize(vectors: np.ndarray, axis: int = -1, eps: float = 1e-10) -> np.ndarray:
    """L2-normalize vectors along ``axis``.

    Args:
        vectors: Input array of shape ``(..., dim)``.
        axis: Axis along which to compute the norm.
        eps: Minimum norm to avoid division by zero.

    Returns:
        L2-normalized copy of ``vectors`` as float32.
    """
    norms = np.linalg.norm(vectors, axis=axis, keepdims=True)
    norms = np.maximum(norms, eps)
    normalized = vectors / norms
    return np.asarray(normalized, dtype=np.float32)


class BaseEmbeddingModel(ABC):
    """Abstract interface for 512-dimensional face embedding models."""

    EMBEDDING_DIM = EMBEDDING_DIM
    model_name: str = "base"

    @abstractmethod
    def extract_single(self, face_bgr: np.ndarray) -> np.ndarray:
        """Extract an embedding from a single 112×112 BGR face crop.

        Args:
            face_bgr: Aligned face crop in BGR uint8 or float format.

        Returns:
            L2-normalized 512-d float32 vector.
        """

    def extract_batch(
        self,
        faces: list[np.ndarray],
        batch_size: int = 64,
    ) -> np.ndarray:
        """Extract embeddings for a batch of face crops.

        Default implementation delegates to :meth:`extract_single`.
        GPU models should override with batched inference.

        Args:
            faces: List of 112×112 BGR face crops.
            batch_size: Maximum batch size per forward pass.

        Returns:
            Array of shape ``(N, 512)`` with L2-normalized rows.
        """
        if not faces:
            return np.empty((0, self.EMBEDDING_DIM), dtype=np.float32)

        embeddings = [self.extract_single(face) for face in faces]
        return np.stack(embeddings, axis=0)

    def close(self) -> None:
        """Release model resources (optional hook for registry teardown)."""
