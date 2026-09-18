"""Celery tasks for photo processing (BE-010)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pillow_heif import register_heif_opener  # type: ignore[attr-defined]
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.core.exceptions import ProcessingError, StorageError
from app.core.logging import get_logger
from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.event_service import EventService
from app.services.image_processing_service import ImageProcessingService
from app.services.storage_service import close_storage_service, get_storage_service
from app.services.watermark_service import WatermarkService
from app.tasks.celery_app import celery_app

logger = get_logger()
register_heif_opener()


@dataclass(frozen=True)
class BackfillOutcome:
    """Result of one derivative-backfill batch."""

    processed: int
    failed: int
    remaining: int


@asynccontextmanager
async def _task_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session scoped to a single Celery task invocation.

    Celery prefork workers reuse the same process for multiple tasks, but
    ``asyncio.run()`` creates a **new** event loop each time. A module-level
    engine keeps its connection pool attached to the *first* loop, causing
    ``RuntimeError: got Future attached to a different loop`` on subsequent
    tasks. A per-invocation engine avoids that, and ``NullPool`` plus an
    explicit dispose stops each task from stranding pooled sockets on a loop
    that is about to close — thousands of photos would otherwise exhaust the
    PostgreSQL connection limit shared with the API.

    Yields:
        A session bound to a short-lived engine.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        async with async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )() as session:
            yield session
    finally:
        await close_storage_service()
        await engine.dispose()


async def _process_uploaded_photo_async(
    photo_id: str, s3_key: str, event_id: str, is_unarchive: bool = False
) -> None:
    """Async implementation of photo processing."""
    start_time = time.perf_counter()
    storage = get_storage_service()
    image_service = ImageProcessingService(storage)
    watermark_service = WatermarkService(storage)

    async with _task_session() as db:
        photo = await db.get(Photo, UUID(photo_id))
        if not photo:
            logger.error("Photo %s not found", photo_id, photo_id=photo_id, event_id=event_id)
            # Update event status even if photo is missing, to not leave event hanging
            event_service = EventService(db)
            await event_service.update_event_processing_status(
                UUID(event_id), skip_notification=is_unarchive
            )
            return

        try:
            # Step 1: Generate web-proxy
            proxy_s3_key, proxy_size_bytes = await image_service.generate_web_proxy(
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

            # Step 3: Grid renditions (thumb + micro-thumb). Derived from the
            # proxy so any watermark applied above is already burned in.
            derivatives = await image_service.generate_derivatives(proxy_s3_key, event_id)

            # Step 4: Generate blurhash and get dimensions
            blurhash, width, height = await image_service.generate_blurhash_and_dimensions(
                proxy_s3_key
            )

            # Step 5: Update photo record
            photo.proxy_s3_key = proxy_s3_key
            photo.proxy_file_size_bytes = proxy_size_bytes
            photo.thumb_s3_key = derivatives.thumb_s3_key
            photo.micro_thumb_s3_key = derivatives.micro_thumb_s3_key
            photo.derivative_file_size_bytes = derivatives.total_bytes
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

            # Face extraction is photographer-triggered (ML-009). Do not enqueue here.
            logger.info(
                "proxy_complete_waiting_for_face_processing",
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
        await event_service.update_event_processing_status(
            UUID(event_id), skip_notification=is_unarchive
        )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "Processed uploaded photo",
            photo_id=photo_id,
            event_id=event_id,
            duration_ms=duration_ms,
        )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def process_uploaded_photo(
    self: Any, photo_id: str, s3_key: str, event_id: str, is_unarchive: bool = False
) -> None:
    """Orchestrates the full processing chain for an uploaded photo."""
    logger.info("Starting task process_uploaded_photo", photo_id=photo_id, event_id=event_id)
    try:
        asyncio.run(
            _process_uploaded_photo_async(photo_id, s3_key, event_id, is_unarchive=is_unarchive)
        )
    except StorageError as exc:
        raise self.retry(exc=exc)


async def _backfill_event_derivatives_async(event_id: str, batch_size: int) -> BackfillOutcome:
    """Generate missing gallery renditions for one event.

    Photos uploaded before the derivative ladder existed have only the 2048px
    proxy. Renditions are derived from that proxy, so no original is pulled out
    of Infrequent Access and no watermark is lost.

    Args:
        event_id: Event whose photos should be backfilled.
        batch_size: Maximum photos to process in this invocation.

    Returns:
        Counts of processed, failed, and still-pending photos.
    """
    storage = get_storage_service()
    image_service = ImageProcessingService(storage)
    processed = 0
    failed = 0

    async with _task_session() as db:
        stmt = (
            select(Photo)
            .where(
                Photo.event_id == UUID(event_id),
                Photo.thumb_s3_key.is_(None),
                Photo.proxy_s3_key.is_not(None),
            )
            .order_by(Photo.created_at.desc())
            .limit(batch_size)
        )
        photos = list((await db.execute(stmt)).scalars().all())

        for photo in photos:
            proxy_s3_key = photo.proxy_s3_key
            if proxy_s3_key is None:
                # Excluded by the query; re-checked so a concurrent archival
                # that cleared the key cannot crash the batch.
                continue
            try:
                derivatives = await image_service.generate_derivatives(proxy_s3_key, event_id)
            except (StorageError, ProcessingError) as exc:
                failed += 1
                logger.warning(
                    "photo_derivative_backfill_failed",
                    photo_id=str(photo.id),
                    event_id=event_id,
                    exc_info=exc,
                )
                continue

            photo.thumb_s3_key = derivatives.thumb_s3_key
            photo.micro_thumb_s3_key = derivatives.micro_thumb_s3_key
            photo.derivative_file_size_bytes = derivatives.total_bytes
            processed += 1

        await db.commit()

        remaining = await db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(
                Photo.event_id == UUID(event_id),
                Photo.thumb_s3_key.is_(None),
                Photo.proxy_s3_key.is_not(None),
            )
        )

    return BackfillOutcome(processed=processed, failed=failed, remaining=remaining or 0)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)  # type: ignore[untyped-decorator]
def backfill_event_derivatives(
    self: Any, event_id: str, batch_size: int = 200, continue_until_done: bool = True
) -> dict[str, int]:
    """Backfill gallery renditions for an event, one batch per invocation.

    Re-queues itself while photos remain so a large event does not occupy a
    worker slot for hours, which would stall proxy generation for live uploads.

    Args:
        event_id: Event to backfill.
        batch_size: Photos to convert per invocation.
        continue_until_done: Re-queue automatically while photos remain.

    Returns:
        Counts of processed, failed, and remaining photos for this batch.
    """
    logger.info("photo_derivative_backfill_started", event_id=event_id, batch_size=batch_size)
    try:
        outcome = asyncio.run(_backfill_event_derivatives_async(event_id, batch_size))
    except StorageError as exc:
        raise self.retry(exc=exc)

    logger.info(
        "photo_derivative_backfill_batch_complete",
        event_id=event_id,
        processed=outcome.processed,
        failed=outcome.failed,
        remaining=outcome.remaining,
    )

    # Only re-queue when the batch made progress, otherwise a permanently
    # undecodable proxy would loop forever.
    if continue_until_done and outcome.remaining > 0 and outcome.processed > 0:
        backfill_event_derivatives.delay(event_id, batch_size, continue_until_done)

    return {
        "processed": outcome.processed,
        "failed": outcome.failed,
        "remaining": outcome.remaining,
    }
