"""Photo API routes for authenticated photographers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer, get_photographer_event
from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.core.rate_limit import rate_limit
from app.models.event import Event
from app.models.photographer import Photographer
from app.schemas.photo import (
    DownloadPhotoResponse,
    MovePhotosRequest,
    PhotoListResponse,
    PhotoResponse,
)
from app.services.photo_service import PhotoService
from app.utils.media_tokens import verify_photo_preview_signature

router = APIRouter(prefix="/events/{event_id}/photos", tags=["Photos"])


@router.get(
    "",
    response_model=PhotoListResponse,
    dependencies=[Depends(rate_limit("photo_list", limit=60, window=60))],
)
async def list_photos(
    event_id: UUID,
    folder_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> PhotoListResponse:
    """Return paginated photos for an event, optionally filtered by folder."""
    return await PhotoService(db).list_photos(event.id, folder_id, offset, limit)


@router.post(
    "",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("photo_upload", limit=60, window=60))],
)
async def upload_photo(
    event_id: UUID,
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    event: Event = Depends(get_photographer_event),
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """Accept a single original image when tusd is not used (local/dev)."""
    parsed_folder_id: UUID | None = None
    if folder_id and folder_id not in {"root", "null"}:
        try:
            parsed_folder_id = UUID(folder_id)
        except ValueError as exc:
            raise BadRequestError("Invalid folder_id") from exc

    payload = await file.read()
    return await PhotoService(db).ingest_direct_upload(
        event,
        photographer,
        filename=file.filename or "upload.jpg",
        content_type=file.content_type,
        payload=payload,
        folder_id=parsed_folder_id,
    )


@router.post("/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_photos(
    event_id: UUID,
    request: MovePhotosRequest,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Move multiple photos to a specific folder or to the root of the event."""
    await PhotoService(db).move_photos(event.id, request.photo_ids, request.folder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    event_id: UUID,
    photo_id: UUID,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a single photo and its derivatives."""
    await PhotoService(db).delete_photos(event.id, [photo_id])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{photo_id}/download",
    response_model=DownloadPhotoResponse,
    dependencies=[Depends(rate_limit("download", limit=30, window=60))],
)
async def get_photo_download_url(
    event_id: UUID,
    photo_id: UUID,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> DownloadPhotoResponse:
    """Get a short-lived presigned URL to download the original high-res photo."""
    url = await PhotoService(db).get_download_url(event.id, photo_id)
    return DownloadPhotoResponse(url=url)


@router.get(
    "/{photo_id}/preview",
    dependencies=[Depends(rate_limit("photo_preview", limit=120, window=60))],
)
async def get_photo_preview(
    event_id: UUID,
    photo_id: UUID,
    expires: int = Query(..., ge=1),
    sig: str = Query(..., min_length=16),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream a preview image using a signed URL (no Authorization header)."""
    verify_photo_preview_signature(event_id, photo_id, expires, sig)
    data, media_type = await PhotoService(db).stream_preview(event_id, photo_id)
    return Response(content=data, media_type=media_type)
