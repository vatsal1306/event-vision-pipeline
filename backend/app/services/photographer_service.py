"""Photographer business logic and operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.schemas.profile import StorageInfo


class PhotographerService:
    """Service for photographer profile and storage operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def recalculate_photographer_storage(self, photographer_id: UUID) -> None:
        """Recalculate total storage used across all events (active + archived)."""
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

    async def get_storage_info(self, photographer: Photographer) -> StorageInfo:
        """Get detailed storage usage breakdown for a photographer."""
        stmt = (
            select(
                Event.status,
                func.coalesce(func.sum(Photo.file_size_bytes), 0),
            )
            .select_from(Event)
            .outerjoin(Photo, Photo.event_id == Event.id)
            .where(Event.photographer_id == photographer.id)
            .group_by(Event.status)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        active = 0
        archived = 0
        for status, size in rows:
            if status == EventStatus.ARCHIVED:
                archived += size
            else:
                active += size

        used = active + archived
        limit = photographer.storage_limit_bytes
        pct = round((used / limit) * 100, 2) if limit else 0.0

        if used != photographer.storage_used_bytes:
            photographer.storage_used_bytes = used
            await self.db.commit()

        return StorageInfo(
            used_bytes=used,
            limit_bytes=limit,
            active_bytes=active,
            archived_bytes=archived,
            used_percentage=pct,
        )
