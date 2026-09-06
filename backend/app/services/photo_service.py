"""Photo business logic and operations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo


class PhotoService:
    """Service for photo operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def delete_photos(self, event_id: UUID, photo_ids: Sequence[UUID]) -> None:
        """Delete photos, decrement event counters, and eventually cleanup S3 storage."""
        if not photo_ids:
            return

        # Get counts for the photos being deleted
        stmt = select(
            func.count(Photo.id).label("photo_count"),
            func.coalesce(func.sum(Photo.face_count), 0).label("face_count"),
            func.sum(
                case((Photo.processing_status == ProcessingStatus.COMPLETED, 1), else_=0)
            ).label("processed_count"),
        ).where(Photo.id.in_(photo_ids), Photo.event_id == event_id)

        result = await self.db.execute(stmt)
        row = result.first()
        if not row or row.photo_count == 0:
            return

        photo_count = row.photo_count
        face_count = row.face_count
        processed_count = row.processed_count or 0

        # TODO(BE-008): Delete physical files from S3 here or enqueue a Celery task

        # Delete from DB
        await self.db.execute(delete(Photo).where(Photo.id.in_(photo_ids)))

        # Update event counters
        await self.db.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(
                total_photos=Event.total_photos - photo_count,
                total_faces=Event.total_faces - face_count,
                processed_photos=Event.processed_photos - processed_count,
            )
        )
