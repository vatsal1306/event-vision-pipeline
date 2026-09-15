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

    @staticmethod
    def _ensure_guest_gallery_ready(event: Event) -> None:
        """Block guest selfie matching until the event is Ready."""
        from app.models.enums import EventStatus

        if event.status != EventStatus.READY:
            raise AuthorizationError(
                "This gallery is not ready yet. Please try again later.",
                code="EVENT_NOT_READY",
            )

    async def process_selfie(
        self, session: GuestSession, selfie_bytes: bytes, face_service: FaceService
    ) -> SelfieMatchResponse:
        """Process guest selfie, extract embedding, and find matching photos."""
        from sqlalchemy.orm.attributes import flag_modified

        from app.schemas.guest import SelfieMatchResponse
        from app.services.photo_service import PhotoService

        event = await self.db.get(Event, session.event_id)
        if event is None:
            raise NotFoundError("Event")
        self._ensure_guest_gallery_ready(event)

        match_result = await face_service.match_selfie(selfie_bytes, session.event_id)

        if match_result.selfie_embedding is not None:
            session.selfie_embedding = match_result.selfie_embedding.astype(float).tolist()
        session.matched_cluster_ids = list(match_result.matched_cluster_ids)
        flag_modified(session, "matched_cluster_ids")
        session.matched_photo_count = len(match_result.photo_ids)
        await self.db.commit()
        await self.db.refresh(session)

        photos = await self._load_photos_in_order(match_result.photo_ids)
        photo_service = PhotoService(self.db)
        status = (
            match_result.status.value
            if hasattr(match_result.status, "value")
            else str(match_result.status)
        )
        return SelfieMatchResponse(
            status=status,
            matched_photo_ids=[str(photo_id) for photo_id in match_result.photo_ids],
            matched_photo_count=len(match_result.photo_ids),
            photos=photo_service.build_photo_responses(photos),
        )

    async def get_guest_photos(
        self,
        session: GuestSession,
        offset: int = 0,
        limit: int = 50,
        folder_id: uuid.UUID | None = None,
    ) -> tuple[list[Photo], int]:
        """Get paginated photos matching the guest's face clusters."""
        import uuid as uuid_mod

        from sqlalchemy import func

        from app.models.face_embedding import FaceEmbedding
        from app.models.photo import Photo

        event = await self.db.get(Event, session.event_id)
        if event is None:
            raise NotFoundError("Event")
        self._ensure_guest_gallery_ready(event)

        cluster_ids = [
            cluster_id if isinstance(cluster_id, uuid_mod.UUID) else uuid_mod.UUID(str(cluster_id))
            for cluster_id in (session.matched_cluster_ids or [])
        ]
        if not cluster_ids:
            return [], 0

        photo_id_stmt = (
            select(FaceEmbedding.photo_id)
            .where(
                FaceEmbedding.event_id == session.event_id,
                FaceEmbedding.cluster_id.in_(cluster_ids),
            )
            .distinct()
        )
        filters = [Photo.id.in_(photo_id_stmt), Photo.event_id == session.event_id]
        if folder_id is not None:
            filters.append(Photo.folder_id == folder_id)

        count_stmt = select(func.count()).select_from(select(Photo.id).where(*filters).subquery())
        total = await self.db.scalar(count_stmt) or 0
        if total == 0:
            return [], 0

        stmt = (
            select(Photo)
            .where(*filters)
            .order_by(Photo.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), int(total)

    async def _load_photos_in_order(self, photo_ids: list[uuid.UUID]) -> list[Photo]:
        """Load photos preserving the matcher order."""
        from app.models.photo import Photo

        if not photo_ids:
            return []
        result = await self.db.execute(select(Photo).where(Photo.id.in_(photo_ids)))
        by_id = {photo.id: photo for photo in result.scalars().all()}
        return [by_id[photo_id] for photo_id in photo_ids if photo_id in by_id]

    async def get_guest_photo_download(self, session: GuestSession, photo_id: uuid.UUID) -> str:
        """Get a presigned download URL for a guest's matched photo."""
        from app.core.exceptions import NotFoundError
        from app.models.face_embedding import FaceEmbedding
        from app.models.photo import Photo

        if not session.matched_cluster_ids and not event.guest_link_active:
            raise AuthorizationError("Guest has no matched photos and highlights are unavailable", code="FORBIDDEN")

        # Get event to check download setting
        event_stmt = select(Event).where(Event.id == session.event_id)
        event_result = await self.db.execute(event_stmt)
        event = event_result.scalar_one_or_none()

        if not event or not event.download_enabled:
            raise AuthorizationError("Downloads are disabled for this event", code="FORBIDDEN")

        import sqlalchemy as sa
        
        or_conds = [Photo.shared_with_guests.is_(True)]
        if session.matched_cluster_ids:
            or_conds.append(Photo.face_embeddings.any(FaceEmbedding.cluster_id.in_(session.matched_cluster_ids)))

        # Verify photo belongs to guest's matched clusters or is shared
        stmt = (
            select(Photo)
            .where(
                Photo.id == photo_id,
                Photo.event_id == session.event_id,
                sa.or_(*or_conds),
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

        # Generate presigned URL via PhotoService
        from app.services.photo_service import PhotoService

        photo_service = PhotoService(self.db)
        return await photo_service.get_download_url(session.event_id, photo_id)

    async def get_highlights(
        self,
        session: GuestSession,
        offset: int = 0,
        limit: int = 50,
    ) -> "PhotoListResponse":
        """Get paginated photos shared with all guests for this event."""
        from sqlalchemy import func
        from app.models.photo import Photo
        from app.models.enums import ProcessingStatus
        from app.schemas.shared import PhotoListResponse
        from app.services.photo_service import PhotoService

        event = await self.db.get(Event, session.event_id)
        if event is None:
            raise NotFoundError("Event")
        self._ensure_guest_gallery_ready(event)

        filters = [
            Photo.event_id == session.event_id,
            Photo.shared_with_guests.is_(True),
            Photo.processing_status == ProcessingStatus.COMPLETED
        ]

        count_stmt = select(func.count()).select_from(Photo).where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        if total == 0:
            return PhotoListResponse(items=[], total=0, offset=offset, limit=limit)

        stmt = (
            select(Photo)
            .where(*filters)
            .order_by(Photo.uploaded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        photos = list(result.scalars().all())

        photo_service = PhotoService(self.db)
        photo_responses = photo_service.build_photo_responses(photos)

        return PhotoListResponse(
            items=photo_responses,
            total=int(total),
            offset=offset,
            limit=limit,
        )

    async def request_auth(self, slug: str, name: str, phone: str) -> None:
        """Verify the event and guest link, then send an OTP. Creates a pending session."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")

        from app.models.enums import EventStatus

        if event.status == EventStatus.ARCHIVED:
            raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

        self._ensure_guest_gallery_ready(event)

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

        from app.models.enums import EventStatus

        if event.status == EventStatus.ARCHIVED:
            raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

        self._ensure_guest_gallery_ready(event)

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
