"""Photo business logic and operations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    AuthorizationError,
    BadRequestError,
    NotFoundError,
    StorageError,
    StorageLimitError,
)
from app.core.logging import get_logger
from app.models.analytics_event import AnalyticsEvent
from app.models.couple_session import CoupleSession
from app.models.enums import AnalyticsAction, EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.face_embedding import FaceEmbedding
from app.models.folder import Folder
from app.models.guest_session import GuestSession
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services.storage_service import get_storage_service
from app.services.upload_service import ALLOWED_MIME_TYPES
from app.utils.media_tokens import build_photo_preview_url

logger = get_logger()

_EXTENSION_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heic",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
    ".arw": "image/x-sony-arw",
}


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

        # Update event counters (total_photos and processed_photos will be handled by update_event_processing_status)
        await self.db.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(
                total_faces=Event.total_faces - face_count,
            )
        )
        
        from app.services.event_service import EventService
        await EventService(self.db).update_event_processing_status(event_id)

        # Update photographer storage usage
        from app.models.photographer import Photographer

        event = await self.db.get(Event, event_id)
        if event:
            await self.db.execute(
                update(Photographer)
                .where(Photographer.id == event.photographer_id)
                .values(storage_used_bytes=Photographer.storage_used_bytes - total_bytes)
            )

    async def ingest_direct_upload(
        self,
        event: Event,
        photographer: Photographer,
        *,
        filename: str,
        content_type: str | None,
        payload: bytes,
        folder_id: UUID | None,
    ) -> PhotoResponse:
        """Store an original on the object store and create a Photo row.

        Used when tusd is not in front of the browser (local uvicorn). Production
        still prefers tusd for large batches; this path is authenticated and
        quota-checked the same way as the tusd pre-create hook.

        Args:
            event: Event owned by the calling photographer.
            photographer: Authenticated photographer.
            filename: Original client filename.
            content_type: Declared MIME type, which may be empty on some browsers.
            payload: Raw file bytes.
            folder_id: Optional destination folder.

        Returns:
            API representation including a signed preview URL.

        Raises:
            BadRequestError: Invalid type, empty body, or file too large.
            StorageLimitError: Photographer quota would be exceeded.
            NotFoundError: Folder does not belong to the event.
        """
        safe_name = Path(filename).name or "upload.jpg"
        mime_type = self._resolve_mime_type(safe_name, content_type)
        if mime_type not in ALLOWED_MIME_TYPES:
            raise BadRequestError(f"File type {mime_type} is not allowed")

        if not payload:
            raise BadRequestError("Uploaded file is empty")

        settings = get_settings()
        size = len(payload)
        if size > settings.max_upload_size_bytes:
            raise BadRequestError("File too large")

        if photographer.storage_used_bytes + size > photographer.storage_limit_bytes:
            raise StorageLimitError()

        if folder_id is not None:
            folder = await self.db.get(Folder, folder_id)
            if folder is None or folder.event_id != event.id:
                raise NotFoundError("Target folder")

        photo_id = uuid.uuid4()
        original_key = f"events/{event.id}/originals/{photo_id}/{safe_name}"
        storage = get_storage_service()
        await storage.put_object(
            bucket=settings.s3_bucket_originals,
            key=original_key,
            data=payload,
            content_type=mime_type,
        )

        photo = Photo(
            id=photo_id,
            event_id=event.id,
            folder_id=folder_id,
            filename=safe_name,
            file_size_bytes=size,
            mime_type=mime_type,
            tus_upload_id=f"direct-{photo_id}",
            original_s3_key=original_key,
        )
        self.db.add(photo)
        photographer.storage_used_bytes += size
        event.total_photos += 1
        if event.status in (EventStatus.DRAFT, EventStatus.READY, EventStatus.UPLOADING):
            event.status = EventStatus.PROCESSING

        await self.db.commit()
        await self.db.refresh(photo)
        self._enqueue_photo_processing(photo, original_key, event.id)
        return self.build_photo_responses([photo])[0]

    async def stream_preview(self, event_id: UUID, photo_id: UUID) -> tuple[bytes, str]:
        """Load proxy bytes when available, otherwise the original.

        Args:
            event_id: Event that must own the photo.
            photo_id: Photo to stream.

        Returns:
            Tuple of file bytes and MIME type for the HTTP response.

        Raises:
            NotFoundError: Photo is missing or the object is not in storage.
        """
        photo = await self.db.get(Photo, photo_id)
        if photo is None or photo.event_id != event_id:
            raise NotFoundError("Photo")

        settings = get_settings()
        storage = get_storage_service()
        try:
            if photo.proxy_s3_key:
                data = await storage.get_object(settings.s3_bucket_proxies, photo.proxy_s3_key)
                return data, "image/webp"
            data = await storage.get_object(settings.s3_bucket_originals, photo.original_s3_key)
            return data, photo.mime_type
        except StorageError as exc:
            raise NotFoundError("Photo file") from exc

    def _enqueue_photo_processing(self, photo: Photo, original_key: str, event_id: UUID) -> None:
        """Dispatch Celery processing; log and continue if the broker is down."""
        from app.tasks.photo_tasks import process_uploaded_photo

        try:
            process_uploaded_photo.delay(str(photo.id), original_key, str(event_id))
        except Exception:
            logger.warning(
                "Celery unavailable; photo %s stored but not processed",
                photo.id,
                photo_id=str(photo.id),
                event_id=str(event_id),
            )

    @staticmethod
    def _resolve_mime_type(filename: str, content_type: str | None) -> str:
        """Prefer a real image MIME type over generic browser fallbacks."""
        declared = (content_type or "").split(";")[0].strip().lower()
        if declared in ALLOWED_MIME_TYPES:
            return declared
        extension = Path(filename).suffix.lower()
        return _EXTENSION_MIME_TYPES.get(extension, declared or "application/octet-stream")

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
        photos = list(result.scalars().all())

        items = self.build_photo_responses(photos)

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
        from typing import Any, cast

        from sqlalchemy import CursorResult

        result = cast(CursorResult[Any], await self.db.execute(stmt))
        if result.rowcount != len(photo_ids):
            from app.core.exceptions import NotFoundError

            raise NotFoundError("One or more photos not found")

    async def get_download_url(self, event_id: UUID, photo_id: UUID) -> str:
        """Generate a short-lived presigned URL for downloading the original photo."""
        from app.core.exceptions import NotFoundError

        photo = await self.db.get(Photo, photo_id)
        if not photo or photo.event_id != event_id:
            raise NotFoundError("Photo not found")
            
        settings = get_settings()
        storage = get_storage_service()
        
        url = await storage.generate_presigned_url(
            bucket=settings.s3_bucket_originals,
            key=photo.original_s3_key,
            client_method="get_object",
            expires_in=settings.s3_presigned_url_expiry,
            extra_params={
                "ResponseContentDisposition": f'attachment; filename="{photo.filename}"'
            }
        )
        return url

    def build_photo_responses(self, photos: list[Photo]) -> list[PhotoResponse]:
        """Convert Photo models to PhotoResponse with signed preview URLs."""
        items = []
        for photo in photos:
            proxy_url = None
            if photo.original_s3_key or photo.proxy_s3_key:
                proxy_url = build_photo_preview_url(photo.event_id, photo.id)

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
        return items

    async def record_photo_view(
        self, session: GuestSession | CoupleSession, photo_id: UUID
    ) -> None:
        """Record a photo view, verifying access rules."""
        if isinstance(session, GuestSession):
            if not session.matched_cluster_ids:
                raise AuthorizationError("Guest has no matched photos", code="FORBIDDEN")

            # Check if photo exists and belongs to event and matches guest's clusters
            stmt = (
                select(Photo)
                .join(Photo.face_embeddings)
                .where(
                    Photo.id == photo_id,
                    Photo.event_id == session.event_id,
                    FaceEmbedding.cluster_id.in_(session.matched_cluster_ids),
                )
            )
            result = await self.db.execute(stmt)
            photo = result.scalar_one_or_none()
            if not photo:
                raise NotFoundError(f"Photo with id '{photo_id}'")
        else:
            # CoupleSession
            stmt = select(Photo).where(Photo.id == photo_id, Photo.event_id == session.event_id)
            result = await self.db.execute(stmt)
            photo = result.scalar_one_or_none()
            if not photo:
                raise NotFoundError(f"Photo with id '{photo_id}'")

        analytics = AnalyticsEvent(
            event_id=session.event_id,
            guest_session_id=session.id if isinstance(session, GuestSession) else None,
            couple_session_id=session.id if isinstance(session, CoupleSession) else None,
            photo_id=photo.id,
            action=AnalyticsAction.VIEW,
        )
        self.db.add(analytics)
        await self.db.commit()
