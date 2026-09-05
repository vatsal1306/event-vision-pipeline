"""Photographer authentication API routes."""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer, get_redis_dep
from app.core.database import get_db
from app.models.photographer import Photographer
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginOtpPendingResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SendOTPRequest,
    SendOTPResponse,
    TokenResponse,
    VerifyOTPRequest,
)
from app.services.auth_service import AuthService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_service(
    db: AsyncSession,
    redis_client: redis.Redis,
) -> AuthService:
    """Construct an AuthService for the current request."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return AuthService(db, otp_service, redis_client)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> RegisterResponse:
    """Register a photographer and send a phone verification OTP."""
    service = _build_auth_service(db, redis_client)
    return await service.register(request)


@router.post("/login", response_model=LoginOtpPendingResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> LoginOtpPendingResponse:
    """Validate credentials and send a login OTP to the registered phone."""
    service = _build_auth_service(db, redis_client)
    return await service.login(request.email_or_phone, request.password)


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(
    request: SendOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> SendOTPResponse:
    """Send or resend an OTP for registration, login, or password reset."""
    service = _build_auth_service(db, redis_client)
    return await service.send_otp(request.phone, request.purpose)


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> TokenResponse:
    """Verify an OTP and return JWT tokens for registration or login."""
    service = _build_auth_service(db, redis_client)
    return await service.verify_otp_and_login(request.phone, request.otp, request.purpose)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> TokenResponse:
    """Rotate refresh token and issue a new access/refresh pair."""
    service = _build_auth_service(db, redis_client)
    return await service.refresh_tokens(request.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
    _photographer: Photographer = Depends(get_current_photographer),
) -> None:
    """Revoke the supplied refresh token."""
    service = _build_auth_service(db, redis_client)
    await service.logout(request.refresh_token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> ForgotPasswordResponse:
    """Send a password-reset OTP to the account's registered phone."""
    service = _build_auth_service(db, redis_client)
    return await service.forgot_password(request.email_or_phone)


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> ResetPasswordResponse:
    """Reset password after OTP verification."""
    service = _build_auth_service(db, redis_client)
    return await service.reset_password(
        request.email_or_phone,
        request.otp,
        request.new_password,
    )
