"""Upload service for handling tusd webhooks (BE-009)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AuthorizationError, BadRequestError, StorageLimitError
from app.core.logging import get_logger
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.schemas.upload import TusUploadInfo
from app.tasks.photo_tasks import process_uploaded_photo

logger = get_logger()

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/tiff",
    "image/webp",
}


class UploadService:
    """Service for handling chunked upload lifecycles via tusd."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def handle_pre_create(self, upload_info: TusUploadInfo) -> dict[str, Any]:
        """Validate an upload before tusd accepts the first chunk.

        Returns:
            Hook body telling tusd to store the object as originals/{event_id}-{uuid}.

        Raises:
            BadRequestError: If metadata UUIDs are invalid or MIME type is not allowed.
            AuthorizationError: If photographer or event is not found, or ownership mismatch.
            StorageLimitError: If photographer quota is exceeded.
        """
        metadata = upload_info.metadata
        event_id, photographer_id, _folder_id = self._parse_metadata_uuids(metadata)

        filetype = metadata.get("filetype", "application/octet-stream")
        if filetype not in ALLOWED_MIME_TYPES:
            raise BadRequestError(f"File type {filetype} is not allowed")

        photographer = await self.db.get(Photographer, photographer_id)
        if not photographer:
            raise AuthorizationError("Photographer not found")

        event = await self.db.get(Event, event_id)
        if not event or event.photographer_id != photographer.id:
            raise AuthorizationError("Event not found or unauthorized")

        if photographer.storage_used_bytes + upload_info.size > photographer.storage_limit_bytes:
            raise StorageLimitError()

        if event.status in (EventStatus.DRAFT, EventStatus.READY):
            event.status = EventStatus.UPLOADING
            await self.db.commit()

        # Slash-free ID so the tus URL stays a single path segment; prefix is originals/.
        object_id = f"{event_id}-{uuid.uuid4()}"
        return {"ChangeFileInfo": {"ID": object_id}}

    async def handle_post_finish(self, upload_info: TusUploadInfo) -> dict[str, str]:
        """Process a completed upload from tusd.

        Returns:
            dict: Status dictionary (e.g. {"status": "accepted", "note": "already processed"}).
        Raises:
            BadRequestError: If metadata UUIDs are invalid, missing S3 key,
                             or MIME type not allowed.
        """
        metadata = upload_info.metadata
        event_id, photographer_id, folder_id = self._parse_metadata_uuids(metadata)

        filetype = metadata.get("filetype", "application/octet-stream")
        if filetype not in ALLOWED_MIME_TYPES:
            raise BadRequestError(f"File type {filetype} is not allowed")

        # Ensure idempotent
        stmt = select(Photo).where(Photo.tus_upload_id == upload_info.id)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info("Upload %s already processed", upload_info.id)
            return {"status": "accepted", "note": "already processed"}

        s3_key = upload_info.storage.get("Key", "")
        if not s3_key:
            logger.error("Missing S3 key in storage info for upload_id=%s", upload_info.id)
            raise BadRequestError("Missing S3 key")

        # Start transaction block explicitly or just use the session
        photographer = await self.db.get(Photographer, photographer_id)
        if not photographer:
            raise AuthorizationError("Photographer not found")

        event = await self.db.get(Event, event_id)
        if not event or event.photographer_id != photographer.id:
            raise AuthorizationError("Event not found or unauthorized")

        photo = Photo(
            event_id=event_id,
            folder_id=folder_id,
            filename=metadata.get("filename", "unknown"),
            file_size_bytes=upload_info.size,
            mime_type=filetype,
            tus_upload_id=upload_info.id,
            original_s3_key=s3_key,
        )
        self.db.add(photo)

        photographer.storage_used_bytes += upload_info.size
        event.total_photos += 1

        if event.status in (EventStatus.DRAFT, EventStatus.READY, EventStatus.UPLOADING):
            event.status = EventStatus.PROCESSING

        await self.db.commit()
        await self.db.refresh(photo)

        process_uploaded_photo.delay(str(photo.id), s3_key, str(event_id))

        return {"status": "accepted"}

    def _parse_metadata_uuids(
        self, metadata: dict[str, str]
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
        """Extract and validate UUIDs from metadata."""
        try:
            event_id_str = metadata.get("event_id")
            photographer_id_str = metadata.get("photographer_id")
            folder_id_str = metadata.get("folder_id")

            event_id = uuid.UUID(event_id_str) if event_id_str else None
            photographer_id = uuid.UUID(photographer_id_str) if photographer_id_str else None
            folder_id = uuid.UUID(folder_id_str) if folder_id_str else None
        except ValueError as e:
            raise BadRequestError("Invalid UUID in metadata") from e

        if not event_id or not photographer_id:
            raise BadRequestError("Missing required metadata")

        return event_id, photographer_id, folder_id
