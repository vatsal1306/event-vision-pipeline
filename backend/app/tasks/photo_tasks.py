"""Celery tasks for photo processing (BE-010)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from pillow_heif import register_heif_opener  # type: ignore[attr-defined]

from app.config import get_settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.event_service import EventService
from app.services.image_processing_service import ImageProcessingService
from app.services.storage_service import LocalStorageService, S3StorageService
from app.services.watermark_service import WatermarkService
from app.tasks.celery_app import celery_app

logger = get_logger()
register_heif_opener()


def get_storage_service() -> Any:
    """Return appropriate storage service."""
    settings = get_settings()
    if settings.aws_access_key_id:
        return S3StorageService()
    return LocalStorageService()


async def _process_uploaded_photo_async(photo_id: str, s3_key: str, event_id: str) -> None:
    """Async implementation of photo processing."""
    storage = get_storage_service()
    image_service = ImageProcessingService(storage)
    watermark_service = WatermarkService(storage)

    async with async_session_factory() as db:
        photo = await db.get(Photo, UUID(photo_id))
        if not photo:
            logger.error("Photo %s not found", photo_id)
            return

        try:
            # Step 1: Generate web-proxy
            proxy_s3_key = await image_service.generate_web_proxy(s3_key, event_id)

            # Step 2: Apply watermark to web-proxy (if configured)
            event = await db.get(Event, UUID(event_id))
            if event:
                photographer = await db.get(Photographer, event.photographer_id)
                if photographer and photographer.watermark_url:
                    # In production, watermark_url might be a full URL, but here we
                    # assume it's an S3 key in the assets bucket or extract it.
                    # Profile API returns URL, but we need the S3 key.
                    # For now, let's assume it's just the key (e.g. `watermarks/{id}.png`).
                    # If it's a full URL, we would extract the key.
                    # Let's extract key if it's a URL, otherwise use as is.
                    wm_key = photographer.watermark_url
                    if "amazonaws.com/" in wm_key:
                        wm_key = wm_key.split("amazonaws.com/")[-1]
                    await watermark_service.apply_watermark(proxy_s3_key, wm_key)

            # Step 3 & 4: Generate blurhash and get dimensions
            blurhash, width, height = await image_service.generate_blurhash_and_dimensions(
                proxy_s3_key
            )

            # Step 5: Update photo record
            photo.proxy_s3_key = proxy_s3_key
            photo.blurhash = blurhash
            photo.width = width
            photo.height = height
            photo.processing_status = ProcessingStatus.COMPLETED
            await db.commit()

            # Set original to IA (if S3)
            settings = get_settings()
            if settings.aws_access_key_id:
                await storage.change_storage_class(
                    settings.s3_bucket_originals, s3_key, "STANDARD_IA"
                )

            # Step 6: Dispatch face detection (stubbed for now)
            logger.info("TODO: Enqueue detect_faces_task for photo %s", photo_id)

        except Exception as exc:
            logger.exception("Error processing photo %s", photo_id)
            photo.processing_status = ProcessingStatus.FAILED
            photo.processing_error = str(exc)
            await db.commit()
            raise

        # Step 7: Update event processing status
        event_service = EventService(db)
        await event_service.update_event_processing_status(UUID(event_id))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def process_uploaded_photo(self: Any, photo_id: str, s3_key: str, event_id: str) -> None:
    """Orchestrates the full processing chain for an uploaded photo."""
    logger.info("Processing uploaded photo %s from s3_key %s", photo_id, s3_key)
    try:
        asyncio.run(_process_uploaded_photo_async(photo_id, s3_key, event_id))
    except Exception as exc:
        raise self.retry(exc=exc)
