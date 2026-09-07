"""Analytics response schemas (BE-015)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsSummaryResponse(BaseModel):
    """Aggregate analytics for an event."""

    total_views: int
    total_downloads: int
    total_guests: int
    engagement_rate: float


class TopPhotoResponse(BaseModel):
    """A photo with its analytics counts."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    proxy_url: str | None
    views: int = 0
    downloads: int = 0


class TopPhotosListResponse(BaseModel):
    """Wrapper for top photos."""

    photos: list[TopPhotoResponse]


class GuestLeadResponse(BaseModel):
    """A single guest lead."""

    model_config = ConfigDict(from_attributes=True)

    guest_id: UUID
    guest_name: str
    guest_phone: str
    first_visit: datetime | None
    photos_matched_count: int
    download_count: int


class GuestLeadListResponse(BaseModel):
    """Paginated guest leads."""

    guests: list[GuestLeadResponse]
    total: int
    page: int
    limit: int
