"""Face embedding extraction (R100, AdaFace VIT-KPRPE, MBF fallback)."""

from app.ml.embedding.dual_embedder import DualEmbedder
from app.ml.embedding.mode import resolve_embedding_mode
from app.ml.embedding.types import EmbeddingResult

__all__ = [
    "DualEmbedder",
    "EmbeddingResult",
    "resolve_embedding_mode",
]
