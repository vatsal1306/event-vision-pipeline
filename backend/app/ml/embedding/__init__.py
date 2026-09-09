"""Face embedding extraction (R100, AdaFace VIT-KPRPE, MBF fallback)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ml.embedding.mode import resolve_embedding_mode
from app.ml.embedding.types import EmbeddingResult

if TYPE_CHECKING:
    from app.ml.embedding.dual_embedder import DualEmbedder

__all__ = [
    "DualEmbedder",
    "EmbeddingResult",
    "resolve_embedding_mode",
]


def __getattr__(name: str) -> object:
    """Lazy-load heavy embedding classes so ``app.ml`` stays import-safe."""
    if name == "DualEmbedder":
        from app.ml.embedding.dual_embedder import DualEmbedder

        return DualEmbedder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
