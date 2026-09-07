"""Analytics service for photographer dashboard."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_event import AnalyticsEvent
from app.models.enums import AnalyticsAction
from app.models.guest_session import GuestSession
from app.models.photo import Photo
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    GuestLeadListResponse,
    GuestLeadResponse,
    TopPhotoResponse,
)
from app.utils.csv_export import generate_guest_leads_csv


class AnalyticsService:
    """Service for retrieving event analytics and guest leads."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def get_summary(self, event_id: UUID) -> AnalyticsSummaryResponse:
        """Get aggregate metrics for the event."""
        # Total guests (verified sessions)
        total_guests_stmt = select(func.count(GuestSession.id)).where(
            GuestSession.event_id == event_id,
            GuestSession.phone_verified.is_(True),
        )
        total_guests = await self.db.scalar(total_guests_stmt) or 0

        # Total views
        total_views_stmt = select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.event_id == event_id,
            AnalyticsEvent.action == AnalyticsAction.VIEW,
        )
        total_views = await self.db.scalar(total_views_stmt) or 0

        # Total downloads
        total_downloads_stmt = select(func.count(AnalyticsEvent.id)).where(
            AnalyticsEvent.event_id == event_id,
            AnalyticsEvent.action == AnalyticsAction.DOWNLOAD,
        )
        total_downloads = await self.db.scalar(total_downloads_stmt) or 0

        engagement_rate = 0.0
        if total_guests > 0:
            engagement_rate = round(total_views / total_guests, 2)

        return AnalyticsSummaryResponse(
            total_views=total_views,
            total_downloads=total_downloads,
            total_guests=total_guests,
            engagement_rate=engagement_rate,
        )

    async def get_top_photos(
        self, event_id: UUID, sort_by: str = "views", limit: int = 10
    ) -> list[TopPhotoResponse]:
        """Rank top photos by views or downloads."""
        views_subq = (
            select(func.count(AnalyticsEvent.id))
            .where(
                AnalyticsEvent.photo_id == Photo.id,
                AnalyticsEvent.action == AnalyticsAction.VIEW,
            )
            .scalar_subquery()
            .correlate(Photo)
        )

        downloads_subq = (
            select(func.count(AnalyticsEvent.id))
            .where(
                AnalyticsEvent.photo_id == Photo.id,
                AnalyticsEvent.action == AnalyticsAction.DOWNLOAD,
            )
            .scalar_subquery()
            .correlate(Photo)
        )

        order_col = views_subq.desc() if sort_by == "views" else downloads_subq.desc()

        stmt = (
            select(
                Photo.id,
                Photo.filename,
                Photo.proxy_s3_key,
                func.coalesce(views_subq, 0).label("views"),
                func.coalesce(downloads_subq, 0).label("downloads"),
            )
            .where(Photo.event_id == event_id)
            .order_by(order_col)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        photos = result.all()

        return [
            TopPhotoResponse(
                id=p.id,
                filename=p.filename,
                proxy_s3_key=p.proxy_s3_key,
                views=p.views,
                downloads=p.downloads,
            )
            for p in photos
        ]

    async def get_guest_leads(
        self, event_id: UUID, offset: int = 0, limit: int = 50
    ) -> GuestLeadListResponse:
        """Return paginated guest leads (verified sessions only)."""
        total_stmt = select(func.count(GuestSession.id)).where(
            GuestSession.event_id == event_id,
            GuestSession.phone_verified.is_(True),
        )
        total = await self.db.scalar(total_stmt) or 0

        downloads_subq = (
            select(func.count(AnalyticsEvent.id))
            .where(
                AnalyticsEvent.guest_session_id == GuestSession.id,
                AnalyticsEvent.action == AnalyticsAction.DOWNLOAD,
            )
            .scalar_subquery()
            .correlate(GuestSession)
        )

        stmt = (
            select(
                GuestSession.id,
                GuestSession.name,
                GuestSession.phone,
                GuestSession.created_at,
                GuestSession.matched_photo_count,
                func.coalesce(downloads_subq, 0).label("downloads"),
            )
            .where(
                GuestSession.event_id == event_id,
                GuestSession.phone_verified.is_(True),
            )
            .order_by(GuestSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        guests = result.all()

        items = [
            GuestLeadResponse(
                id=g.id,
                name=g.name,
                phone=g.phone,
                first_visited=g.created_at,
                photos_matched=g.matched_photo_count,
                photos_downloaded=g.downloads,
            )
            for g in guests
        ]

        return GuestLeadListResponse(items=items, total=total)

    async def export_guest_leads_csv(self, event_id: UUID) -> str:
        """Return CSV data string for all verified guest leads."""
        downloads_subq = (
            select(func.count(AnalyticsEvent.id))
            .where(
                AnalyticsEvent.guest_session_id == GuestSession.id,
                AnalyticsEvent.action == AnalyticsAction.DOWNLOAD,
            )
            .scalar_subquery()
            .correlate(GuestSession)
        )

        stmt = (
            select(
                GuestSession.id,
                GuestSession.name,
                GuestSession.phone,
                GuestSession.created_at,
                GuestSession.matched_photo_count,
                func.coalesce(downloads_subq, 0).label("downloads"),
            )
            .where(
                GuestSession.event_id == event_id,
                GuestSession.phone_verified.is_(True),
            )
            .order_by(GuestSession.created_at.desc())
        )
        result = await self.db.execute(stmt)
        guests = result.all()

        items = [
            GuestLeadResponse(
                id=g.id,
                name=g.name,
                phone=g.phone,
                first_visited=g.created_at,
                photos_matched=g.matched_photo_count,
                photos_downloaded=g.downloads,
            )
            for g in guests
        ]

        return generate_guest_leads_csv(items)
