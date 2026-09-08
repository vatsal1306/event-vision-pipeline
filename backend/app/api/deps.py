"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JWTType
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.redis_client import get_redis
from app.core.security import decode_jwt
from app.models.couple_session import CoupleSession
from app.models.event import Event
from app.models.guest_session import GuestSession
from app.models.photographer import Photographer
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

__all__ = [
    "get_db",
    "get_redis_dep",
    "get_current_photographer",
    "get_photographer_event",
    "get_current_guest_session",
    "get_current_couple_session",
    "oauth2_scheme",
]


async def get_redis_dep() -> AsyncIterator[redis.Redis]:
    """FastAPI dependency that yields the shared Redis client."""
    async for client in get_redis():
        yield client


async def get_current_photographer(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Photographer:
    """Extract and validate the authenticated photographer from an access JWT."""
    try:
        payload = decode_jwt(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid access token") from exc

    if payload.get("type") != JWTType.ACCESS.value:
        raise AuthenticationError("Invalid token type")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Invalid access token")

    photographer = await db.get(Photographer, UUID(str(subject)))
    if photographer is None or not photographer.is_active:
        raise AuthenticationError("Account not found or inactive")
    return photographer


async def get_photographer_event(
    event_id: UUID,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Return an event owned by the caller, or 404 if it does not exist."""
    return await EventService(db).get_owned_event(photographer.id, event_id)


async def get_current_guest_session(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> GuestSession:
    """Extract and validate the guest session from a guest JWT."""
    try:
        payload = decode_jwt(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid access token") from exc

    if payload.get("type") != JWTType.GUEST.value:
        raise AuthenticationError("Invalid token type. Expected guest token.")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Invalid access token")

    session = await db.get(GuestSession, UUID(str(subject)))
    if session is None or not session.phone_verified:
        raise AuthenticationError("Session not found or invalid")
    return session


async def get_guest_session_for_slug(
    slug: str,
    guest_session: GuestSession = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> GuestSession:
    """Validate that the guest session belongs to the event specified by the slug."""
    from sqlalchemy import select

    from app.core.exceptions import NotFoundError
    from app.models.event import Event

    stmt = select(Event).where(Event.slug == slug)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise NotFoundError(f"Event with slug '{slug}' not found")

    if guest_session.event_id != event.id:
        raise AuthorizationError("Session does not belong to this event", code="FORBIDDEN")

    from app.models.enums import EventStatus

    if event.status == EventStatus.ARCHIVED:
        raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

    if not event.guest_link_active:
        raise AuthorizationError("Guest link is inactive", code="LINK_INACTIVE")

    return guest_session


async def get_current_couple_session(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CoupleSession:
    """Extract and validate the couple session from a couple JWT."""
    try:
        payload = decode_jwt(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid access token") from exc

    if payload.get("type") != JWTType.COUPLE.value:
        raise AuthenticationError("Invalid token type. Expected couple token.")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Invalid access token")

    session = await db.get(CoupleSession, UUID(str(subject)))
    if session is None or not session.phone_verified:
        raise AuthenticationError("Session not found or invalid")
    return session


async def get_couple_session_for_slug(
    slug: str,
    couple_session: CoupleSession = Depends(get_current_couple_session),
    db: AsyncSession = Depends(get_db),
) -> CoupleSession:
    """Validate that the couple session belongs to the event specified by the slug."""
    from sqlalchemy import select

    from app.core.exceptions import NotFoundError
    from app.models.event import Event

    stmt = select(Event).where(Event.slug == slug)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise NotFoundError(f"Event with slug '{slug}' not found")

    if couple_session.event_id != event.id:
        raise AuthorizationError("Session does not belong to this event", code="FORBIDDEN")

    from app.models.enums import EventStatus

    if event.status == EventStatus.ARCHIVED:
        raise AuthorizationError("Event is archived", code="EVENT_ARCHIVED")

    if not event.master_link_active:
        raise AuthorizationError("Master link is inactive", code="LINK_INACTIVE")

    return couple_session


async def get_any_session_for_slug(
    slug: str,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> GuestSession | CoupleSession:
    """Extract and validate either a guest or couple session for the given event."""
    try:
        payload = decode_jwt(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid access token") from exc

    token_type = payload.get("type")
    if token_type == JWTType.GUEST.value:
        guest_session = await get_current_guest_session(token, db)
        return await get_guest_session_for_slug(slug, guest_session, db)
    elif token_type == JWTType.COUPLE.value:
        couple_session = await get_current_couple_session(token, db)
        return await get_couple_session_for_slug(slug, couple_session, db)
    else:
        raise AuthenticationError("Invalid token type. Expected guest or couple token.")


def build_auth_service(db: AsyncSession, redis_client: redis.Redis) -> AuthService:
    """Construct an AuthService (exported for tests)."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return AuthService(db, otp_service, redis_client)


def get_face_service(db: AsyncSession = Depends(get_db)) -> Any:
    """Dependency injection for FaceService."""
    from app.services.face_service import FaceService

    return FaceService(db)
