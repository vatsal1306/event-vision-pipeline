"""Data retention and archival service."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.storage_service import get_storage_service

logger = get_logger()


class ArchivalService:
    """Service to handle event archival, restore, and deletion."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db
        self.storage = get_storage_service()
        self.settings = get_settings()

    async def archive_event(self, event_id: UUID) -> None:
        """Archive an event: move originals to Glacier, delete proxies, clean DB."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        if event.status == EventStatus.ARCHIVED:
            return

        photos = (
            (await self.db.execute(select(Photo).where(Photo.event_id == event_id))).scalars().all()
        )

        original_bucket = self.settings.s3_bucket_originals
        proxy_bucket = self.settings.s3_bucket_proxies

        # 1. Move originals to GLACIER_IR
        failed_photos = []

        async def move_to_glacier(photo: Photo) -> None:
            try:
                await self.storage.change_storage_class(
                    bucket=original_bucket,
                    key=photo.original_s3_key,
                    storage_class="GLACIER_IR",
                )
            except Exception as exc:
                logger.error("archival.glacier_move_failed", photo_id=str(photo.id), error=str(exc))
                failed_photos.append(photo.id)

        # Run in parallel batches (e.g. 50 at a time)
        chunk_size = 50
        for i in range(0, len(photos), chunk_size):
            chunk = photos[i : i + chunk_size]
            await asyncio.gather(*(move_to_glacier(p) for p in chunk))

        if failed_photos:
            logger.error("archival.glacier_move_aborted", event_id=str(event_id), failed_count=len(failed_photos))
            raise RuntimeError(f"Failed to move {len(failed_photos)} photos to Glacier. Aborting archival.")

        # 2. Delete web proxies from S3
        proxy_keys = [p.proxy_s3_key for p in photos if p.proxy_s3_key]
        if proxy_keys:
            await self.storage.delete_objects(bucket=proxy_bucket, keys=proxy_keys)

        # 3 & 4. Delete face embeddings and clusters from DB
        await self.db.execute(delete(FaceEmbedding).where(FaceEmbedding.event_id == event_id))
        await self.db.execute(delete(FaceCluster).where(FaceCluster.event_id == event_id))

        # 5. Update event and photos status
        event.status = EventStatus.ARCHIVED
        for photo in photos:
            photo.proxy_s3_key = None
            photo.blurhash = None
            photo.face_count = 0
            photo.processing_status = ProcessingStatus.PENDING

        await self.db.commit()
        logger.info("archival.event_archived", event_id=str(event_id))

        # 6. Notify photographer
        from app.tasks.notification_tasks import notify_archival_complete_task

        notify_archival_complete_task.delay(str(event_id))

    async def restore_event(self, event_id: UUID) -> None:
        """Restore an archived event."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        if event.status != EventStatus.ARCHIVED:
            return

        photos = (
            (await self.db.execute(select(Photo).where(Photo.event_id == event_id))).scalars().all()
        )

        original_bucket = self.settings.s3_bucket_originals

        # 1. Move originals back to STANDARD
        async def move_to_standard(photo: Photo) -> None:
            try:
                await self.storage.change_storage_class(
                    bucket=original_bucket,
                    key=photo.original_s3_key,
                    storage_class="STANDARD",
                )
            except Exception as exc:
                logger.error(
                    "archival.standard_move_failed", photo_id=str(photo.id), error=str(exc)
                )

        chunk_size = 50
        for i in range(0, len(photos), chunk_size):
            chunk = photos[i : i + chunk_size]
            await asyncio.gather(*(move_to_standard(p) for p in chunk))

        # 2. Update status and trigger proxy generation (Option A)
        event.status = EventStatus.PROCESSING
        event.processed_photos = 0
        await self.db.commit()

        from app.tasks.photo_tasks import process_uploaded_photo

        for photo in photos:
            process_uploaded_photo.delay(str(photo.id), photo.original_s3_key, str(event_id))

        logger.info("archival.event_restored", event_id=str(event_id))

    async def delete_event_permanently(self, event_id: UUID) -> None:
        """Permanently delete an event, all its data, and S3 objects."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        photographer_id = event.photographer_id

        photos = (
            (await self.db.execute(select(Photo).where(Photo.event_id == event_id))).scalars().all()
        )

        original_bucket = self.settings.s3_bucket_originals
        proxy_bucket = self.settings.s3_bucket_proxies

        original_keys = [p.original_s3_key for p in photos]
        proxy_keys = [p.proxy_s3_key for p in photos if p.proxy_s3_key]

        if original_keys:
            await self.storage.delete_objects(bucket=original_bucket, keys=original_keys)
        if proxy_keys:
            await self.storage.delete_objects(bucket=proxy_bucket, keys=proxy_keys)

        # Database cascade delete covers photos, folders, sessions, analytics, embeddings, etc.
        await self.db.delete(event)
        await self.db.commit()

        # Recalculate quota
        await self.recalculate_photographer_storage(photographer_id)
        logger.info("archival.event_permanently_deleted", event_id=str(event_id))

    async def recalculate_photographer_storage(self, photographer_id: UUID) -> None:
        """Recalculate total storage used by a photographer."""
        total = await self.db.scalar(
            select(func.coalesce(func.sum(Photo.file_size_bytes), 0))
            .join(Event, Photo.event_id == Event.id)
            .where(Event.photographer_id == photographer_id)
        )
        await self.db.execute(
            update(Photographer)
            .where(Photographer.id == photographer_id)
            .values(storage_used_bytes=total)
        )
        await self.db.commit()
