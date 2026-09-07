"""Guest authentication and session management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JWTType
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.security import create_session_token
from app.models.event import Event
from app.models.guest_session import GuestSession
from app.schemas.guest import GuestTokenResponse

if TYPE_CHECKING:
    import uuid

    from app.models.photo import Photo
    from app.schemas.guest import SelfieMatchResponse
    from app.services.face_service import FaceService
    from app.utils.otp import OTPService


class GuestService:
    """Service for handling guest authentication."""

    def __init__(self, db_session: AsyncSession, otp_service: OTPService) -> None:
        self.db = db_session
        self.otp_service = otp_service

    async def process_selfie(
        self, session: GuestSession, selfie_bytes: bytes, face_service: FaceService
    ) -> SelfieMatchResponse:
        """Process guest selfie, extract embedding, and find matching photos."""
        from app.schemas.guest import SelfieMatchResponse

        match_result = await face_service.match_selfie(selfie_bytes, session.event_id)

        session.matched_cluster_ids = match_result.clusters
        session.matched_photo_count = len(match_result.photo_ids)
        await self.db.commit()

        return SelfieMatchResponse(
            matched_photo_ids=[str(p) for p in match_result.photo_ids],
            match_count=len(match_result.photo_ids),
        )

    async def get_guest_photos(
        self,
        session: GuestSession,
        offset: int = 0,
        limit: int = 50,
        folder_id: uuid.UUID | None = None,
    ) -> tuple[list[Photo], int]:
        """Get paginated photos matching the guest's face clusters."""
        from sqlalchemy import func

        from app.models.enums import ProcessingStatus
        from app.models.face_embedding import FaceEmbedding
        from app.models.photo import Photo

        if not session.matched_cluster_ids:
            return [], 0

        where_clause = [
            Photo.event_id == session.event_id,
            Photo.processing_status == ProcessingStatus.COMPLETED,
            FaceEmbedding.cluster_id.in_(session.matched_cluster_ids),
        ]
        if folder_id:
            where_clause.append(Photo.folder_id == folder_id)

        # Base statement to find distinct photo IDs
        base_stmt = select(Photo.id).join(Photo.face_embeddings).where(*where_clause).distinct()

        # Count total
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        if total == 0:
            return [], 0

        # Get photos
        stmt = (
            select(Photo)
            .where(Photo.id.in_(base_stmt))
            .order_by(Photo.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        photos = list(result.scalars().all())

        return photos, total

    async def get_guest_photo_download(self, session: GuestSession, photo_id: uuid.UUID) -> str:
        """Get a presigned download URL for a guest's matched photo."""
        from app.core.exceptions import NotFoundError
        from app.models.face_embedding import FaceEmbedding
        from app.models.photo import Photo

        if not session.matched_cluster_ids:
            raise AuthorizationError("Guest has no matched photos", code="FORBIDDEN")

        # Get event to check download setting
        event_stmt = select(Event).where(Event.id == session.event_id)
        event_result = await self.db.execute(event_stmt)
        event = event_result.scalar_one_or_none()

        if not event or not event.download_enabled:
            raise AuthorizationError("Downloads are disabled for this event", code="FORBIDDEN")

        # Verify photo belongs to guest's matched clusters
        stmt = (
            select(Photo)
            .join(Photo.face_embeddings)
            .where(
                Photo.id == photo_id,
                Photo.event_id == session.event_id,
                FaceEmbedding.cluster_id.in_(session.matched_cluster_ids),
            )
        )
        result = await self.db.execute(stmt)
        photo = result.scalar_one_or_none()

        if not photo:
            raise NotFoundError(f"Photo with id '{photo_id}'")

        # Record analytics
        from app.models.analytics_event import AnalyticsEvent
        from app.models.enums import AnalyticsAction

        analytics = AnalyticsEvent(
            event_id=session.event_id,
            guest_session_id=session.id,
            photo_id=photo.id,
            action=AnalyticsAction.DOWNLOAD,
        )
        self.db.add(analytics)
        await self.db.commit()

        # Generate presigned URL
        return f"https://mock-s3.local/download/{photo.original_s3_key}?expires=3600"

    async def request_auth(self, slug: str, name: str, phone: str) -> None:
        """Verify the event and guest link, then send an OTP. Creates a pending session."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")
        if not event.guest_link_active:
            raise AuthorizationError("Guest link is inactive", code="LINK_INACTIVE")

        # Get or create session
        session_stmt = select(GuestSession).where(
            GuestSession.event_id == event.id,
            GuestSession.phone == phone,
        )
        session_result = await self.db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            session = GuestSession(
                event_id=event.id,
                name="",
                phone=phone,
                phone_verified=False,
            )
            self.db.add(session)

        await self.db.commit()
        await self.otp_service.send_otp(phone, purpose="guest_auth")

    async def verify_auth(self, slug: str, name: str, phone: str, otp: str) -> GuestTokenResponse:
        """Verify OTP, retrieve GuestSession, and issue a JWT."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")
        if not event.guest_link_active:
            raise AuthorizationError("Guest link is inactive", code="LINK_INACTIVE")

        # Verify OTP (raises appropriate exceptions if invalid)
        verified = await self.otp_service.verify_otp(phone, purpose="guest_auth", otp=otp)
        from app.core.exceptions import AuthenticationError

        if not verified:
            raise AuthenticationError("Invalid OTP")

        # Get session
        session_stmt = select(GuestSession).where(
            GuestSession.event_id == event.id,
            GuestSession.phone == phone,
        )
        session_result = await self.db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            raise AuthorizationError("Session not found. Please request a new OTP.")

        session.phone_verified = True
        session.name = name
        await self.db.commit()

        # Check if guest needs selfie (has no selfie URL and no matched clusters)
        needs_selfie = not bool(session.selfie_s3_key) and not bool(session.matched_cluster_ids)

        token, _ = create_session_token(
            subject=str(session.id),
            event_id=str(event.id),
            token_type=JWTType.GUEST,
        )

        return GuestTokenResponse(
            access_token=token,
            needs_selfie=needs_selfie,
        )
