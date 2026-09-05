"""Pydantic schemas for photographer authentication endpoints."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import (
    INDIAN_PHONE_PATTERN,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_PATTERN,
)

OtpPurpose = Literal["registration", "login", "password_reset"]


class PasswordFieldMixin(BaseModel):
    """Shared password validation for auth requests."""

    @field_validator("password", "new_password", check_fields=False)
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Ensure password meets complexity requirements."""
        if not re.fullmatch(PASSWORD_PATTERN, value):
            raise ValueError(
                "Password must be 8-16 characters and include uppercase, "
                "lowercase, digit, and special character."
            )
        return value


class RegisterRequest(PasswordFieldMixin):
    """Photographer registration payload."""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    studio_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(pattern=INDIAN_PHONE_PATTERN)


class RegisterResponse(BaseModel):
    """Registration response before phone verification completes."""

    id: UUID
    email: str
    studio_name: str
    phone: str
    message: str


class LoginRequest(BaseModel):
    """Photographer login step one: email or phone plus password."""

    email_or_phone: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class LoginOtpPendingResponse(BaseModel):
    """Returned after valid credentials; OTP is sent to the registered phone."""

    otp_sent: bool = True
    phone: str
    message: str
    expires_in: int


class SendOTPRequest(BaseModel):
    """Request to (re)send an OTP for a given purpose."""

    phone: str = Field(pattern=INDIAN_PHONE_PATTERN)
    purpose: OtpPurpose


class SendOTPResponse(BaseModel):
    """OTP dispatch acknowledgement."""

    message: str
    expires_in: int


class VerifyOTPRequest(BaseModel):
    """Verify an OTP and optionally complete auth flows."""

    phone: str = Field(pattern=INDIAN_PHONE_PATTERN)
    otp: str = Field(min_length=6, max_length=6)
    purpose: OtpPurpose


class RefreshTokenRequest(BaseModel):
    """Refresh token rotation payload."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout payload used to revoke the refresh token."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password step one."""

    email_or_phone: str = Field(min_length=3, max_length=255)


class ForgotPasswordResponse(BaseModel):
    """Generic forgot-password response to avoid account enumeration."""

    message: str


class ResetPasswordRequest(PasswordFieldMixin):
    """Forgot password step two: OTP plus new password."""

    email_or_phone: str = Field(min_length=3, max_length=255)
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ResetPasswordResponse(BaseModel):
    """Password reset success response."""

    message: str


class PhotographerProfile(BaseModel):
    """Public photographer account profile returned after authentication."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    studio_name: str
    phone: str
    phone_verified: bool
    logo_url: str | None
    watermark_url: str | None
    storage_used_bytes: int
    storage_limit_bytes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """JWT pair plus photographer profile."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    photographer: PhotographerProfile
