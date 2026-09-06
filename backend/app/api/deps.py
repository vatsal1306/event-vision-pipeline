"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import JWTType
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.redis_client import get_redis
from app.core.security import decode_jwt
from app.models.event import Event
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


def build_auth_service(db: AsyncSession, redis_client: redis.Redis) -> AuthService:
    """Construct an AuthService (exported for tests)."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return AuthService(db, otp_service, redis_client)
