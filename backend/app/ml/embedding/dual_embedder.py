"""Dual-model embedding orchestrator with OOM fallback."""

from __future__ import annotations

import numpy as np
import structlog

from app.ml.config import MLConfig
from app.ml.embedding.base import BaseEmbeddingModel
from app.ml.embedding.mobilefacenet import MobileFaceNetTFLite
from app.ml.embedding.mode import resolve_embedding_mode
from app.ml.embedding.types import EmbeddingResult

logger = structlog.get_logger(__name__)


class DualEmbedder:
    """Orchestrate primary (R100) and optional secondary (AdaFace) embeddings."""

    def __init__(
        self,
        primary: BaseEmbeddingModel,
        secondary: BaseEmbeddingModel | None,
        fallback: MobileFaceNetTFLite | None,
        config: MLConfig,
    ) -> None:
        """Create a dual embedder.

        Args:
            primary: ArcFace R100 model (or MBF after fallback).
            secondary: AdaFace VIT-KPRPE model, or ``None`` in r100-only mode.
            fallback: MobileFaceNet TFLite CPU fallback for primary OOM.
            config: ML configuration (batch size, mode flags).
        """
        self.primary = primary
        self.secondary = secondary
        self.fallback = fallback
        self._config = config
        self._mode = resolve_embedding_mode(config)

    @property
    def mode(self) -> str:
        """Active embedding mode (``dual`` or ``r100``)."""
        return self._mode

    def embed_batch(self, faces: list[np.ndarray]) -> list[EmbeddingResult]:
        """Generate embeddings for a batch of 112×112 BGR face crops.

        Fallback policy:
        1. Primary (R100) with OOM batch halving.
        2. If primary still OOM at batch size 1, use MobileFaceNet for primary.
        3. Secondary (AdaFace) with OOM batch halving; on failure, omit secondary.

        Args:
            faces: Aligned BGR face crops from ``FaceCropper``.

        Returns:
            One :class:`EmbeddingResult` per input face.
        """
        if not faces:
            return []

        batch_size = self._config.embedding_batch_size
        primary_model = self.primary
        primary_name = getattr(primary_model, "model_name", "r100")

        try:
            primary_embeddings = primary_model.extract_batch(faces, batch_size=batch_size)
        except Exception as exc:
            if self.fallback is None:
                raise

            logger.warning(
                "embedding_primary_failed_using_mbf_fallback",
                model=primary_name,
                error=str(exc),
            )
            primary_embeddings = self.fallback.extract_batch(faces, batch_size=batch_size)
            primary_name = self.fallback.model_name

        secondary_embeddings: np.ndarray | None = None
        secondary_name: str | None = "adaface_vit_kprpe"

        if self.secondary is not None and self._mode == "dual":
            try:
                secondary_embeddings = self.secondary.extract_batch(faces, batch_size=batch_size)
            except Exception as exc:
                logger.warning(
                    "embedding_secondary_failed",
                    model="adaface_vit_kprpe",
                    error=str(exc),
                )
                secondary_embeddings = None
                secondary_name = None

        results: list[EmbeddingResult] = []
        for index in range(len(faces)):
            secondary_vector = None
            if secondary_embeddings is not None:
                secondary_vector = secondary_embeddings[index]

            results.append(
                EmbeddingResult(
                    primary=primary_embeddings[index],
                    secondary=secondary_vector,
                    model_primary=primary_name,
                    model_secondary=secondary_name if secondary_vector is not None else None,
                )
            )

        return results

    def embed_single(self, face: np.ndarray) -> EmbeddingResult:
        """Generate embeddings for one 112×112 BGR face crop.

        Args:
            face: Aligned BGR crop from ``FaceCropper``.

        Returns:
            Primary embedding and optional secondary embedding.
        """
        results = self.embed_batch([face])
        if not results:
            raise ValueError("DualEmbedder.embed_single received an empty embedding result.")
        return results[0]

    def close(self) -> None:
        """Release all underlying models."""
        for model in (self.primary, self.secondary, self.fallback):
            if model is not None:
                model.close()
