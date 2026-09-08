"""Photo API routes for authenticated photographers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_photographer_event
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.models.event import Event
from app.schemas.photo import DownloadPhotoResponse, MovePhotosRequest, PhotoListResponse
from app.services.photo_service import PhotoService

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
