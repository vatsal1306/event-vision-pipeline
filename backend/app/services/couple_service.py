"""Couple authentication and session management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JWTType
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.security import create_session_token
from app.models.couple_session import CoupleSession
from app.models.event import Event
from app.schemas.couple import CoupleTokenResponse

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
