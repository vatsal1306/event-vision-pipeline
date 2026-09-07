"""Guest authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis_dep
from app.schemas.guest import GuestAuthRequest, GuestTokenResponse, GuestVerifyRequest
from app.services.guest_service import GuestService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

if TYPE_CHECKING:
    import redis.asyncio as redis


router = APIRouter(prefix="/event/{slug}/auth", tags=["Guest"])


def get_guest_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> GuestService:
    """Dependency injection for GuestService."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return GuestService(db, otp_service)


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def request_guest_auth(
    slug: str,
    request: GuestAuthRequest,
    guest_service: GuestService = Depends(get_guest_service),
) -> None:
    """Send an OTP to the guest's phone for authentication."""
    await guest_service.request_auth(
        slug=slug,
        name=request.name,
        phone=request.phone,
    )


@router.post("/verify", response_model=GuestTokenResponse)
async def verify_guest_auth(
    slug: str,
    request: GuestVerifyRequest,
    guest_service: GuestService = Depends(get_guest_service),
) -> GuestTokenResponse:
    """Verify the guest's OTP and issue a session token."""
    return await guest_service.verify_auth(
        slug=slug,
        phone=request.phone,
        otp=request.otp,
    )
