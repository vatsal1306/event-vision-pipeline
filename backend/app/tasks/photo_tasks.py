"""Celery tasks for photo processing (BE-010)."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from pillow_heif import register_heif_opener  # type: ignore[attr-defined]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.event_service import EventService
from app.services.image_processing_service import ImageProcessingService
from app.services.storage_service import get_storage_service
from app.services.watermark_service import WatermarkService
from app.tasks.celery_app import celery_app

logger = get_logger()
register_heif_opener()


def _build_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create a fresh engine + session factory bound to the current event loop.

    Celery prefork workers reuse the same process for multiple tasks, but
    ``asyncio.run()`` creates a **new** event loop each time.  A module-level
    engine keeps its connection pool attached to the *first* loop, causing
    ``RuntimeError: got Future attached to a different loop`` on subsequent
    tasks.  Building a fresh engine per invocation avoids this entirely.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _process_uploaded_photo_async(photo_id: str, s3_key: str, event_id: str) -> None:
    """Async implementation of photo processing."""
    start_time = time.perf_counter()
    storage = get_storage_service()
    image_service = ImageProcessingService(storage)
    watermark_service = WatermarkService(storage)

    session_factory = _build_session_factory()
    async with session_factory() as db:
        photo = await db.get(Photo, UUID(photo_id))
        if not photo:
            logger.error("Photo %s not found", photo_id, photo_id=photo_id, event_id=event_id)
            # Update event status even if photo is missing, to not leave event hanging
            event_service = EventService(db)
            await event_service.update_event_processing_status(UUID(event_id))
            return

        try:
            # Step 1: Generate web-proxy
            proxy_s3_key = await image_service.generate_web_proxy(
                s3_key, event_id, original_filename=photo.filename, mime_type=photo.mime_type
            )

            # Step 2: Apply watermark to web-proxy and original (if configured)
            event = await db.get(Event, UUID(event_id))
            if event:
                photographer = await db.get(Photographer, event.photographer_id)
                if photographer and photographer.watermark_url:
                    # Apply to web-proxy (.webp, lower quality)
                    await watermark_service.apply_watermark(
                        proxy_s3_key,
                        str(photographer.watermark_url),
                        watermark_scale=photographer.watermark_scale,
                        watermark_x=photographer.watermark_x,
                        watermark_y=photographer.watermark_y,
                        watermark_opacity=photographer.watermark_opacity,
                    )
                    await watermark_service.apply_watermark(
                        s3_key,
                        str(photographer.watermark_url),
                        bucket=get_settings().s3_bucket_originals,
                        output_format=".jpg",
                        watermark_scale=photographer.watermark_scale,
                        watermark_x=photographer.watermark_x,
                        watermark_y=photographer.watermark_y,
                        watermark_opacity=photographer.watermark_opacity,
                    )

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
            logger.info(
                "TODO: Enqueue detect_faces_task for photo %s",
                photo_id,
                photo_id=photo_id,
                event_id=event_id,
            )

        except StorageError as exc:
            logger.warning(
                "Transient storage error for photo %s, will retry",
                photo_id,
                exc_info=exc,
                photo_id=photo_id,
                event_id=event_id,
            )
            raise  # Let it bubble up to trigger retry

        except Exception as exc:
            logger.exception(
                "Fatal error processing photo %s",
                photo_id,
                exc_info=exc,
                photo_id=photo_id,
                event_id=event_id,
            )
            photo.processing_status = ProcessingStatus.FAILED
            photo.processing_error = str(exc)
            await db.commit()
            # Do NOT raise here, we want it to fail permanently without Celery retry

        # Step 7: Update event processing status
        event_service = EventService(db)
        await event_service.update_event_processing_status(UUID(event_id))

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "Processed uploaded photo",
            photo_id=photo_id,
            event_id=event_id,
            duration_ms=duration_ms,
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def process_uploaded_photo(self: Any, photo_id: str, s3_key: str, event_id: str) -> None:
    """Orchestrates the full processing chain for an uploaded photo."""
    logger.info("Starting task process_uploaded_photo", photo_id=photo_id, event_id=event_id)
    try:
        asyncio.run(_process_uploaded_photo_async(photo_id, s3_key, event_id))
    except StorageError as exc:
        raise self.retry(exc=exc)
