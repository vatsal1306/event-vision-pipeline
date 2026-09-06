"""Photo business logic and operations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.schemas.photo import PhotoListResponse, PhotoResponse


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
            func.coalesce(func.sum(Photo.file_size_bytes), 0).label("total_bytes"),
        ).where(Photo.id.in_(photo_ids), Photo.event_id == event_id)

        result = await self.db.execute(stmt)
        row = result.first()
        if not row or row.photo_count == 0:
            from app.core.exceptions import NotFoundError

            if len(photo_ids) == 1:
                raise NotFoundError("Photo not found")
            return

        photo_count = row.photo_count
        face_count = row.face_count
        processed_count = row.processed_count or 0
        total_bytes = row.total_bytes

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

        # Update photographer storage usage
        from app.models.photographer import Photographer

        event = await self.db.get(Event, event_id)
        if event:
            await self.db.execute(
                update(Photographer)
                .where(Photographer.id == event.photographer_id)
                .values(storage_used_bytes=Photographer.storage_used_bytes - total_bytes)
            )

    async def list_photos(
        self, event_id: UUID, folder_id: UUID | None = None, offset: int = 0, limit: int = 50
    ) -> PhotoListResponse:
        """List photos for an event, optionally filtered by folder."""
        # Ensure we cap the limit
        limit = min(limit, 100)

        # Build query
        stmt = select(Photo).where(Photo.event_id == event_id)
        if folder_id:
            stmt = stmt.where(Photo.folder_id == folder_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        # Fetch paginated items
        stmt = stmt.order_by(Photo.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        photos = result.scalars().all()

        items = []
        for photo in photos:
            # Mock proxy URL for now
            proxy_url = None
            if photo.processing_status == ProcessingStatus.COMPLETED and photo.proxy_s3_key:
                proxy_url = f"https://mock-s3.local/proxy/{photo.proxy_s3_key}"

            items.append(
                PhotoResponse(
                    id=photo.id,
                    event_id=photo.event_id,
                    folder_id=photo.folder_id,
                    filename=photo.filename,
                    proxy_url=proxy_url,
                    blurhash=photo.blurhash,
                    width=photo.width,
                    height=photo.height,
                    file_size_bytes=photo.file_size_bytes,
                    mime_type=photo.mime_type,
                    face_count=photo.face_count,
                    processing_status=photo.processing_status,
                    processing_error=photo.processing_error,
                    uploaded_at=photo.uploaded_at,
                    created_at=photo.created_at,
                )
            )

        return PhotoListResponse(items=items, total=total, offset=offset, limit=limit)

    async def move_photos(
        self, event_id: UUID, photo_ids: list[UUID], folder_id: UUID | None
    ) -> None:
        """Move multiple photos to a new folder or to the root of the event."""
        if not photo_ids:
            return

        if folder_id is not None:
            from app.core.exceptions import NotFoundError
            from app.models.folder import Folder

            # Verify folder exists and belongs to the event
            folder = await self.db.get(Folder, folder_id)
            if not folder or folder.event_id != event_id:
                raise NotFoundError("Target folder not found")

        stmt = (
            update(Photo)
            .where(Photo.event_id == event_id, Photo.id.in_(photo_ids))
            .values(folder_id=folder_id)
        )
        result = await self.db.execute(stmt)
        if result.rowcount != len(photo_ids):
            from app.core.exceptions import NotFoundError

            raise NotFoundError("One or more photos not found")

    async def get_download_url(self, event_id: UUID, photo_id: UUID) -> str:
        """Generate a short-lived presigned URL for downloading the original photo."""
        from app.core.exceptions import NotFoundError

        photo = await self.db.get(Photo, photo_id)
        if not photo or photo.event_id != event_id:
            raise NotFoundError("Photo not found")

        # Mock download URL (BE-008 will implement proper S3 presigning)
        return f"https://mock-s3.local/download/{photo.original_s3_key}?expires=3600"
