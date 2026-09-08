"""Service layer for event sharing and public info."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.models.event import Event
from app.schemas.event import EventPublicInfo, EventPublicInfoEvent, EventPublicInfoPhotographer
from app.services.storage_service import get_storage_service


class SharingService:
    """Service to handle sharing links and public landing page info."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def get_public_info(self, slug: str) -> EventPublicInfo:
        """Fetch public info for an event by its slug."""
        stmt = select(Event).options(joinedload(Event.photographer)).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")

        logo_presigned = None
        if event.photographer.logo_url:
            from app.config import get_settings

            settings = get_settings()
            storage = get_storage_service()
            logo_presigned = await storage.generate_presigned_url(
                settings.s3_bucket_assets,
                event.photographer.logo_url,
                expires_in=settings.s3_presigned_url_expiry,
            )

        return EventPublicInfo(
            event=EventPublicInfoEvent(
                id=event.id,
                name=event.name,
                slug=event.slug,
                status=event.status,
                download_enabled=event.download_enabled,
                date_start=event.date_start,
                date_end=event.date_end,
                guest_link_active=event.guest_link_active,
                master_link_active=event.master_link_active,
            ),
            photographer=EventPublicInfoPhotographer(
                studio_name=event.photographer.studio_name,
                logo_url=logo_presigned,
            ),
        )
