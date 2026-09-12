"""Photographer-triggered face processing (ML-009)."""

from __future__ import annotations

from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, FaceProcessingDisabledError
from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE, EventClusteringLock
from app.ml.config import get_ml_config
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photo import Photo
from app.schemas.event import StartFaceProcessingResponse


class FaceProcessingService:
    """Enqueue face extraction after the photographer says uploads are done."""

    def __init__(self, db: AsyncSession, redis_client: redis.Redis) -> None:
        """Bind database and Redis used to inspect the pipeline lock."""
        self.db = db
        self._redis = redis_client
        self._config = get_ml_config()

    async def start_face_processing(self, event: Event) -> StartFaceProcessingResponse:
        """Mark the event processing and enqueue ``process_event_photos``.

        Args:
            event: Photographer-owned event.

        Returns:
            Queue acknowledgement, including ``already_running`` when a job holds
            the pipeline lock.

        Raises:
            FaceProcessingDisabledError: ``ML_FACE_PROCESSING_ENABLED`` is false.
            BadRequestError: No photos still need face extraction.
        """
        if not self._config.face_processing_enabled:
            raise FaceProcessingDisabledError()

        pending = await self._pending_face_photo_count(event.id)
        if pending == 0:
            raise BadRequestError("No photos are waiting for face processing.")

        if await self._pipeline_lock_held(event.id):
            return StartFaceProcessingResponse(
                event_id=event.id,
                status=event.status,
                already_running=True,
                photos_queued=pending,
            )

        event.status = EventStatus.PROCESSING
        await self.db.commit()

        from app.tasks.face_tasks import process_event_photos

        process_event_photos.delay(str(event.id))
        return StartFaceProcessingResponse(
            event_id=event.id,
            status=EventStatus.PROCESSING,
            already_running=False,
            photos_queued=pending,
        )

    async def _pending_face_photo_count(self, event_id: UUID) -> int:
        """Count photos that have not completed face extraction."""
        total = await self.db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(Photo.event_id == event_id, Photo.faces_processed.is_(False))
        )
        return int(total or 0)

    async def _pipeline_lock_held(self, event_id: UUID) -> bool:
        """Return True when another worker already owns the pipeline lock."""
        lock = EventClusteringLock(
            self._redis,
            event_id,
            ttl_seconds=self._config.face_pipeline_lock_ttl_seconds,
            key_template=FACE_PIPELINE_LOCK_KEY_TEMPLATE,
        )
        exists = await self._redis.exists(lock.key)
        return bool(exists)
