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
    proxy_s3_key: str | None
    views: int = 0
    downloads: int = 0


class GuestLeadResponse(BaseModel):
    """A single guest lead."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    first_visited: datetime
    photos_matched: int
    photos_downloaded: int


class GuestLeadListResponse(BaseModel):
    """Paginated guest leads."""

    items: list[GuestLeadResponse]
    total: int
