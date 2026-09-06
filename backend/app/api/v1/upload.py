"""tusd webhook endpoints (BE-009)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.schemas.upload import TusHookPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/hook")
async def tusd_hook(
    payload: TusHookPayload,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Accept tusd hooks for pre-create and post-finish."""
    from app.tasks.photo_tasks import process_uploaded_photo

    event_type = payload.type
    upload_info = payload.event.upload
    metadata = upload_info.metadata

    # Extract metadata
    try:
        event_id_str = metadata.get("event_id")
        photographer_id_str = metadata.get("photographer_id")
        folder_id_str = metadata.get("folder_id")

        event_id = uuid.UUID(event_id_str) if event_id_str else None
        photographer_id = uuid.UUID(photographer_id_str) if photographer_id_str else None
        folder_id = uuid.UUID(folder_id_str) if folder_id_str else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID in metadata")

    if not event_id or not photographer_id:
        raise HTTPException(status_code=400, detail="Missing required metadata")

    if event_type == "pre-create":
        # Validate quota and permissions
        photographer = await db.get(Photographer, photographer_id)
        if not photographer:
            raise HTTPException(status_code=403, detail="Photographer not found")

        event = await db.get(Event, event_id)
        if not event or event.photographer_id != photographer.id:
            raise HTTPException(status_code=403, detail="Event not found or unauthorized")

        # Check quota
        if photographer.storage_used_bytes + upload_info.size > photographer.storage_limit_bytes:
            # 402 Payment Required for quota exceeded, but HTTP 400 is safer for tusd webhook
            response.status_code = 400
            return {"detail": "Storage limit exceeded"}

        settings = get_settings()
        if upload_info.size > settings.max_upload_size_bytes:
            response.status_code = 400
            return {"detail": "File too large"}

    elif event_type == "post-finish":
        # Ensure idempotent
        stmt = select(Photo).where(Photo.tus_upload_id == upload_info.id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info("Upload %s already processed", upload_info.id)
            return {"status": "accepted", "note": "already processed"}

        s3_key = upload_info.storage.get("Key", "")
        if not s3_key:
            logger.error("Missing S3 key in storage info for upload_id=%s", upload_info.id)
            return {"status": "error"}

        photo = Photo(
            event_id=event_id,
            folder_id=folder_id,
            filename=metadata.get("filename", "unknown"),
            file_size_bytes=upload_info.size,
            mime_type=metadata.get("filetype", "application/octet-stream"),
            tus_upload_id=upload_info.id,
            original_s3_key=s3_key,
        )
        db.add(photo)

        event = await db.get(Event, event_id)
        if event:
            event.total_photos += 1
            if event.status in (EventStatus.DRAFT, EventStatus.READY):
                event.status = EventStatus.PROCESSING

        await db.commit()
        await db.refresh(photo)

        process_uploaded_photo.delay(str(photo.id), s3_key, str(event_id))

    return {"status": "accepted"}
