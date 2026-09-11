"""Face matching facade used by the guest selfie API."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.config import get_ml_config
from app.ml.matching.pipeline import SelfieMatchPipeline, decode_selfie_bytes
from app.ml.matching.types import MatchResult, MatchStatus
from app.ml.registry_bootstrap import register_default_model_loaders

logger = structlog.get_logger(__name__)

__all__ = ["FaceService", "MatchResult", "MatchStatus"]


class FaceService:
    """Backend bridge to the ML selfie matching pipeline.

    Upload clustering stays on the ML host (ML-009). Guest selfie matching is
    a synchronous API call. Production app hosts should keep
    ``ML_FACE_PROCESSING_ENABLED=false`` so PyTorch is not loaded on the CPU
    EC2. Local development sets it to true.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Create a service bound to the request database session."""
        self.db = db
        self._config = get_ml_config()

    async def match_selfie(self, selfie_image_bytes: bytes, event_id: uuid.UUID) -> MatchResult:
        """Decode a guest selfie and match it against event clusters.

        Args:
            selfie_image_bytes: Raw uploaded image bytes.
            event_id: Event whose face clusters are searched.

        Returns:
            ``MatchResult`` with status, cluster IDs, and photo IDs when matched.
        """
        if not self._config.face_processing_enabled:
            logger.info(
                "selfie_match_skipped_face_processing_disabled",
                event_id=str(event_id),
            )
            return MatchResult(status=MatchStatus.NO_MATCH)

        image = decode_selfie_bytes(selfie_image_bytes)
        if image is None:
            return MatchResult(status=MatchStatus.INVALID_IMAGE)

        register_default_model_loaders()
        pipeline = SelfieMatchPipeline(self.db, config=self._config)
        return await pipeline.run(image, event_id)
