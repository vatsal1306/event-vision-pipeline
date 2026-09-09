"""Batch inference helpers with GPU OOM retry."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def extract_batch_with_oom_retry(
    faces: list[np.ndarray],
    batch_size: int,
    extract_fn: Callable[[list[np.ndarray], int], np.ndarray],
    *,
    model_name: str,
) -> np.ndarray:
    """Run batched extraction, halving batch size on CUDA OOM.

    Args:
        faces: Face crops to embed.
        batch_size: Initial batch size (typically from ``MLConfig.embedding_batch_size``).
        extract_fn: Callable ``(faces, batch_size) -> (N, 512)`` array.
        model_name: Model label for structured logs.

    Returns:
        L2-normalized embeddings of shape ``(len(faces), 512)``.

    Raises:
        Exception: Re-raises the last error when batch size reaches 1 and still fails.
    """
    if not faces:
        return np.empty((0, 512), dtype=np.float32)

    current_batch = max(1, batch_size)

    while current_batch >= 1:
        try:
            return extract_fn(faces, current_batch)
        except Exception as exc:
            oom_error = _is_cuda_oom(exc)
            if not oom_error or current_batch == 1:
                raise

            next_batch = max(1, current_batch // 2)
            logger.warning(
                "embedding_batch_oom_retry",
                model=model_name,
                previous_batch_size=current_batch,
                new_batch_size=next_batch,
                error=str(exc),
            )
            current_batch = next_batch

            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    return np.empty((0, 512), dtype=np.float32)


def _is_cuda_oom(exc: BaseException) -> bool:
    """Return True when ``exc`` represents a CUDA out-of-memory failure."""
    try:
        import torch

        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except ImportError:
        pass

    message = str(exc).lower()
    return "out of memory" in message and "cuda" in message
