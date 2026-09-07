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
    from app.utils.otp import OTPService


class GuestService:
    """Service for handling guest authentication."""

    def __init__(self, db_session: AsyncSession, otp_service: OTPService) -> None:
        self.db = db_session
        self.otp_service = otp_service

    async def request_auth(self, slug: str, name: str, phone: str) -> None:
        """Verify the event and guest link, then send an OTP. Creates a pending session."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")
        if not event.guest_link_active:
            raise AuthorizationError("Guest link is inactive")

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
                name=name,
                phone=phone,
                phone_verified=False,
            )
            self.db.add(session)
        else:
            # Update name if requested by the same phone
            session.name = name

        await self.db.commit()
        await self.otp_service.send_otp(phone, purpose="guest_auth")

    async def verify_auth(self, slug: str, phone: str, otp: str) -> GuestTokenResponse:
        """Verify OTP, retrieve GuestSession, and issue a JWT."""
        stmt = select(Event).where(Event.slug == slug)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        if not event:
            raise NotFoundError(f"Event with slug '{slug}'")
        if not event.guest_link_active:
            raise AuthorizationError("Guest link is inactive")

        # Verify OTP (raises appropriate exceptions if invalid)
        await self.otp_service.verify_otp(phone, purpose="guest_auth", otp=otp)

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
