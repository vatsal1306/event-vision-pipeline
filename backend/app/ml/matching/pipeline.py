"""Synchronous guest-selfie pipeline: liveness → crop → quality → embed → match."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import cv2
import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.config import MLConfig, get_ml_config
from app.ml.matching.liveness import BasicLivenessDetector
from app.ml.matching.selfie_matcher import SelfieMatcher
from app.ml.matching.types import MatchResult, MatchStatus
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.models.face_embedding import FaceEmbedding

if TYPE_CHECKING:
    from app.ml.detection.face_cropper import FaceCropper
    from app.ml.detection.scrfd import SCRFDDetector
    from app.ml.embedding.dual_embedder import DualEmbedder
    from app.ml.quality.quality_filter import QualityFilter

logger = structlog.get_logger(__name__)


class SelfieMatchPipeline:
    """Run the full guest selfie matching path for one event.

    Detects once, then reuses that face for liveness and cropping.
    Selfie quality skips age and sunglasses and uses 30° YPR limits.
    """

    def __init__(
        self,
        db: AsyncSession,
        config: MLConfig | None = None,
        registry: ModelRegistry | None = None,
        *,
        detector: SCRFDDetector | None = None,
        cropper: FaceCropper | None = None,
        liveness: BasicLivenessDetector | None = None,
        quality_filter: QualityFilter | None = None,
        embedder: DualEmbedder | None = None,
        matcher: SelfieMatcher | None = None,
    ) -> None:
        """Create a pipeline. Model arguments are optional test overrides."""
        self._db = db
        self._config = config or get_ml_config()
        self._registry = registry
        self._detector = detector
        self._cropper = cropper
        self._liveness = liveness or BasicLivenessDetector(self._config)
        self._quality_filter = quality_filter
        self._embedder = embedder
        self._matcher = matcher or SelfieMatcher(db, config=self._config)

    async def run(self, image_bgr: np.ndarray, event_id: uuid.UUID) -> MatchResult:
        """Execute matching for a decoded BGR selfie.

        Args:
            image_bgr: Decoded OpenCV image.
            event_id: Event whose clusters are searched.

        Returns:
            ``MatchResult`` including cluster IDs; photo IDs are filled when matched.
        """
        detector, cropper = self._resolve_detector()

        faces = detector.detect(image_bgr)
        if not faces:
            return MatchResult(status=MatchStatus.NO_FACE_DETECTED)

        primary = cropper.select_primary(image_bgr, faces)
        if primary is None:
            return MatchResult(status=MatchStatus.NO_FACE_DETECTED)

        liveness = self._liveness.check(image_bgr, primary)
        if not liveness.passed:
            logger.info(
                "selfie_liveness_failed",
                event_id=str(event_id),
                failed_checks=liveness.failed_checks,
                face_size_ratio=liveness.face_size_ratio,
                sharpness=liveness.sharpness,
                saturation=liveness.saturation,
            )
            return MatchResult(status=MatchStatus.LIVENESS_FAILED)

        crop = cropper.crop_primary(image_bgr, [primary])
        if crop is None:
            return MatchResult(status=MatchStatus.CROP_FAILED)

        quality_filter, embedder = self._resolve_quality_and_embedder()
        quality = quality_filter.filter(
            crop,
            skip_age=True,
            skip_sunglasses=True,
            yaw_threshold=self._config.selfie_yaw_threshold,
            pitch_threshold=self._config.selfie_pitch_threshold,
            roll_threshold=self._config.selfie_roll_threshold,
        )
        if not quality.passed:
            return MatchResult(
                status=MatchStatus.LOW_QUALITY,
                quality_issue=quality.reject_reason,
            )

        embedding = embedder.embed_single(crop.aligned_face)
        result = await self._matcher.match(
            embedding.primary,
            event_id,
            secondary_embedding=embedding.secondary,
        )
        if result.status == MatchStatus.MATCHED:
            result.photo_ids = await self._load_photo_ids(result.matched_cluster_ids)
        return result

    def _registry_or_default(self) -> ModelRegistry:
        """Return the injected registry or the process singleton."""
        return self._registry or get_model_registry()

    def _resolve_detector(self) -> tuple[SCRFDDetector, FaceCropper]:
        """Load SCRFD and the cropper (needed before liveness)."""
        from app.ml.detection.face_cropper import FaceCropper
        from app.ml.detection.scrfd import SCRFDDetector

        detector = self._detector or self._registry_or_default().get_model("scrfd")
        cropper = self._cropper or FaceCropper(detector=detector)
        if self._detector is None and not isinstance(detector, SCRFDDetector):
            raise TypeError("Expected SCRFDDetector from the model registry.")
        return detector, cropper

    def _resolve_quality_and_embedder(self) -> tuple[QualityFilter, DualEmbedder]:
        """Load quality + embedding models only after liveness passes."""
        from app.ml.embedding.dual_embedder import DualEmbedder
        from app.ml.quality.quality_filter import QualityFilter

        registry = self._registry_or_default()
        quality_filter = self._quality_filter or registry.get_model("quality_filter")
        embedder = self._embedder or registry.get_model("dual_embedder")
        if self._quality_filter is None and not isinstance(quality_filter, QualityFilter):
            raise TypeError("Expected QualityFilter from the model registry.")
        if self._embedder is None and not isinstance(embedder, DualEmbedder):
            raise TypeError("Expected DualEmbedder from the model registry.")
        return quality_filter, embedder

    async def _load_photo_ids(self, cluster_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        """Return distinct photo IDs belonging to the matched clusters."""
        if not cluster_ids:
            return []
        result = await self._db.execute(
            select(FaceEmbedding.photo_id)
            .where(FaceEmbedding.cluster_id.in_(cluster_ids))
            .distinct()
        )
        return [row[0] for row in result.all()]


def decode_selfie_bytes(image_bytes: bytes) -> np.ndarray | None:
    """Decode image bytes to a BGR ndarray, or None when the file is invalid."""
    if not image_bytes:
        return None
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    if buffer.size == 0:
        return None
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image
