"""Analytics API endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_photographer_event
from app.models.event import Event
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    GuestLeadListResponse,
    TopPhotoResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/event/{slug}/analytics", tags=["Analytics"])


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    """Dependency injection for AnalyticsService."""
    return AnalyticsService(db)


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_summary(
    slug: str,
    event: Event = Depends(get_photographer_event),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    """Get aggregate metrics for an event."""
    return await analytics_service.get_summary(event.id)


@router.get("/photos/top", response_model=list[TopPhotoResponse])
async def get_top_photos(
    slug: str,
    sort_by: Literal["views", "downloads"] = Query("views"),
    limit: int = Query(10, ge=1, le=50),
    event: Event = Depends(get_photographer_event),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> list[TopPhotoResponse]:
    """Get top photos by views or downloads."""
    return await analytics_service.get_top_photos(event.id, sort_by=sort_by, limit=limit)


@router.get("/guests", response_model=GuestLeadListResponse)
async def get_guest_leads(
    slug: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    event: Event = Depends(get_photographer_event),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> GuestLeadListResponse:
    """Get paginated guest leads."""
    return await analytics_service.get_guest_leads(event.id, offset=offset, limit=limit)


@router.get("/guests/export", response_class=Response)
async def export_guest_leads(
    slug: str,
    event: Event = Depends(get_photographer_event),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> Response:
    """Export all guest leads as CSV."""
    csv_data = await analytics_service.export_guest_leads_csv(event.id)
    headers = {"Content-Disposition": f'attachment; filename="{event.slug}_guests.csv"'}
    return Response(content=csv_data, media_type="text/csv", headers=headers)
