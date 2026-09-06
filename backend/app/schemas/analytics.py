"""Analytics list/summary schemas for dashboard placeholders."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyticsSummary(BaseModel):
    """Zeroed analytics until BE-015 records real visits."""

    total_views: int = 0
    total_downloads: int = 0
    total_guests: int = 0
    engagement_rate: float = 0.0


class AnalyticsTopPhotosResponse(BaseModel):
    """Top photos placeholder."""

    photos: list[dict[str, object]] = Field(default_factory=list)


class GuestListResponse(BaseModel):
    """Guest analytics placeholder."""

    guests: list[dict[str, object]] = Field(default_factory=list)
    total: int = 0
