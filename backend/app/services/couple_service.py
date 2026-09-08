"""Couple authentication and session management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JWTType
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.security import create_session_token
from app.models.couple_session import CoupleSession
from app.models.event import Event
from app.schemas.couple import CoupleTokenResponse
from app.schemas.folder import FolderTreeResponse
from app.schemas.photo import PhotoListResponse

if TYPE_CHECKING:
    from app.utils.otp import OTPService


class CoupleService:
    """Service for handling couple (master link) authentication."""

    def __init__(self, db_session: AsyncSession, otp_service: OTPService) -> None:
        self.db = db_session
        self.otp_service = otp_service

    async def request_auth(self, slug: str, name: str, phone: str) -> None:
        """Verify the event and master link, then send an OTP. Creates a pending session."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")

        from app.models.enums import EventStatus

        if event.status == EventStatus.ARCHIVED:
            raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

        if not event.master_link_active:
            raise AuthorizationError("Master link is inactive", code="LINK_INACTIVE")

        # Get or create session
        session_stmt = select(CoupleSession).where(
            CoupleSession.event_id == event.id,
            CoupleSession.phone == phone,
        )
        session_result = await self.db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            session = CoupleSession(
                event_id=event.id,
                name="",
                phone=phone,
                phone_verified=False,
            )
            self.db.add(session)

        await self.db.commit()
        await self.otp_service.send_otp(phone, purpose="couple_auth")

    async def verify_auth(self, slug: str, name: str, phone: str, otp: str) -> CoupleTokenResponse:
        """Verify OTP, retrieve CoupleSession, and issue a JWT."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")

        from app.models.enums import EventStatus

        if event.status == EventStatus.ARCHIVED:
            raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

        if not event.master_link_active:
            raise AuthorizationError("Master link is inactive", code="LINK_INACTIVE")

        # Verify OTP (raises appropriate exceptions if invalid)
        verified = await self.otp_service.verify_otp(phone, purpose="couple_auth", otp=otp)
        from app.core.exceptions import AuthenticationError

        if not verified:
            raise AuthenticationError("Invalid OTP")

        # Get session
        session_stmt = select(CoupleSession).where(
            CoupleSession.event_id == event.id,
            CoupleSession.phone == phone,
        )
        session_result = await self.db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            raise AuthorizationError("Session not found. Please request a new OTP.")

        session.phone_verified = True
        session.name = name
        await self.db.commit()

        token, _ = create_session_token(
            subject=str(session.id),
            event_id=str(event.id),
            token_type=JWTType.COUPLE,
        )

        return CoupleTokenResponse(
            token=token,
        )

    async def get_photos(
        self,
        session: CoupleSession,
        folder_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PhotoListResponse:
        """Get paginated completed photos for the event."""
        from sqlalchemy import func

        from app.models.enums import ProcessingStatus
        from app.models.photo import Photo
        from app.schemas.photo import PhotoListResponse

        # Build query
        stmt = select(Photo).where(
            Photo.event_id == session.event_id,
            Photo.processing_status == ProcessingStatus.COMPLETED,
        )
        if folder_id:
            stmt = stmt.where(Photo.folder_id == folder_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        # Fetch paginated items
        stmt = stmt.order_by(Photo.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        photos = result.scalars().all()

        from app.services.photo_service import PhotoService

        photo_service = PhotoService(self.db)
        items = photo_service.build_photo_responses(list(photos))

        return PhotoListResponse(items=items, total=total, offset=offset, limit=limit)

    async def get_folders(self, session: CoupleSession) -> FolderTreeResponse:
        """Get the folder tree for the event."""
        from app.services.folder_service import FolderService

        folder_service = FolderService(self.db)
        return await folder_service.list_tree(session.event_id)

    async def toggle_favorite(self, session: CoupleSession, photo_id: uuid.UUID) -> bool:
        """Toggle favorite status for a photo. Returns True if now favorited, False if removed."""
        from app.models.enums import ProcessingStatus
        from app.models.favorite import Favorite
        from app.models.photo import Photo

        # Check if photo exists, belongs to the event, and is completed
        stmt = select(Photo).where(
            Photo.id == photo_id,
            Photo.event_id == session.event_id,
            Photo.processing_status == ProcessingStatus.COMPLETED,
        )
        result = await self.db.execute(stmt)
        if not result.scalar_one_or_none():
            raise NotFoundError("Completed photo not found in this event")

        # Check existing favorite
        fav_stmt = select(Favorite).where(
            Favorite.couple_session_id == session.id, Favorite.photo_id == photo_id
        )
        fav_result = await self.db.execute(fav_stmt)
        favorite = fav_result.scalar_one_or_none()

        if favorite:
            await self.db.delete(favorite)
            await self.db.commit()
            return False
        else:
            new_fav = Favorite(couple_session_id=session.id, photo_id=photo_id)
            self.db.add(new_fav)
            await self.db.commit()
            return True

    async def get_favorites(
        self, session: CoupleSession, offset: int = 0, limit: int = 50
    ) -> PhotoListResponse:
        """List favorited photos."""
        from sqlalchemy import func

        from app.models.favorite import Favorite
        from app.models.photo import Photo
        from app.schemas.photo import PhotoListResponse

        stmt = (
            select(Photo)
            .join(Favorite, Favorite.photo_id == Photo.id)
            .where(Favorite.couple_session_id == session.id, Photo.event_id == session.event_id)
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(Favorite.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        photos = result.scalars().all()

        from app.services.photo_service import PhotoService

        photo_service = PhotoService(self.db)
        items = photo_service.build_photo_responses(list(photos))

        return PhotoListResponse(items=items, total=total, offset=offset, limit=limit)

    async def get_download_url(self, session: CoupleSession, photo_id: uuid.UUID) -> str:
        """Get a presigned download URL for a photo and record analytics."""
        from app.models.photo import Photo

        # Verify event download enabled
        event_stmt = select(Event).where(Event.id == session.event_id)
        event_result = await self.db.execute(event_stmt)
        event = event_result.scalar_one_or_none()

        if not event or not event.download_enabled:
            raise AuthorizationError("Downloads are disabled for this event", code="FORBIDDEN")

        stmt = select(Photo).where(Photo.id == photo_id, Photo.event_id == session.event_id)
        result = await self.db.execute(stmt)
        photo = result.scalar_one_or_none()

        if not photo:
            raise NotFoundError("Photo not found")

        # Record analytics
        from app.models.analytics_event import AnalyticsEvent
        from app.models.enums import AnalyticsAction

        analytics = AnalyticsEvent(
            event_id=session.event_id,
            couple_session_id=session.id,
            photo_id=photo.id,
            action=AnalyticsAction.DOWNLOAD,
        )
        self.db.add(analytics)
        await self.db.commit()

        # Generate download URL via PhotoService
        from app.services.photo_service import PhotoService

        photo_service = PhotoService(self.db)
        return await photo_service.get_download_url(session.event_id, photo_id)
