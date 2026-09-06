"""Photo schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProcessingStatus


class PhotoResponse(BaseModel):
    """Photo response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    folder_id: UUID | None = None
    filename: str
    proxy_url: str | None = None
    blurhash: str | None = None
    width: int | None = None
    height: int | None = None
    file_size_bytes: int
    mime_type: str
    face_count: int
    processing_status: ProcessingStatus
    processing_error: str | None = None
    uploaded_at: datetime
    created_at: datetime


class PhotoListResponse(BaseModel):
    """Paginated photo list."""

    items: list[PhotoResponse]
    total: int
    offset: int
    limit: int


class MovePhotosRequest(BaseModel):
    """Request to move multiple photos to a new folder (or root)."""

    photo_ids: list[UUID] = Field(..., min_length=1, max_length=1000)
    folder_id: UUID | None = None


class DownloadPhotoResponse(BaseModel):
    """Response containing a short-lived download URL."""

    url: str
