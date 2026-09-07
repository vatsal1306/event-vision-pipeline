"""Couple authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis_dep
from app.schemas.couple import CoupleAuthRequest, CoupleTokenResponse, CoupleVerifyRequest
from app.services.couple_service import CoupleService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

if TYPE_CHECKING:
    import redis.asyncio as redis


router = APIRouter(prefix="/event/{slug}/master", tags=["Couple"])


def get_couple_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> CoupleService:
    """Dependency injection for CoupleService."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return CoupleService(db, otp_service)


@router.post("/auth", status_code=status.HTTP_204_NO_CONTENT)
async def request_couple_auth(
    slug: str,
    request: CoupleAuthRequest,
    couple_service: CoupleService = Depends(get_couple_service),
) -> None:
    """Send an OTP to the couple's phone for authentication."""
    await couple_service.request_auth(
        slug=slug,
        name=request.name,
        phone=request.phone,
    )


@router.post("/verify", response_model=CoupleTokenResponse)
async def verify_couple_auth(
    slug: str,
    request: CoupleVerifyRequest,
    couple_service: CoupleService = Depends(get_couple_service),
) -> CoupleTokenResponse:
    """Verify the couple's OTP and issue a session token."""
    return await couple_service.verify_auth(
        slug=slug,
        phone=request.phone,
        otp=request.otp,
    )
