"""Pydantic schemas for photographer authentication endpoints."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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
    """Registration response before phone and email verification complete."""

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
    """Returned after valid credentials; OTP is sent to the registered email."""

    otp_sent: bool = True
    email: str
    message: str
    expires_in: int


class SendOTPRequest(BaseModel):
    """Request to (re)send an OTP for a given purpose and channel."""

    purpose: OtpPurpose
    channel: Literal["sms", "email"] = "sms"
    phone: str | None = Field(default=None, pattern=INDIAN_PHONE_PATTERN)
    email: EmailStr | None = None

    @model_validator(mode="after")
    def require_destination_for_channel(self) -> SendOTPRequest:
        """SMS needs a phone; email needs an address."""
        if self.channel == "sms" and not self.phone:
            raise ValueError("phone is required when channel is sms")
        if self.channel == "email" and not self.email:
            raise ValueError("email is required when channel is email")
        return self


class SendOTPResponse(BaseModel):
    """OTP dispatch acknowledgement."""

    message: str
    expires_in: int


class VerifyOTPRequest(BaseModel):
    """Verify OTPs and complete photographer login or registration."""

    purpose: OtpPurpose
    phone: str | None = Field(default=None, pattern=INDIAN_PHONE_PATTERN)
    email: EmailStr | None = None
    otp: str | None = Field(default=None, min_length=6, max_length=6)
    phone_otp: str | None = Field(default=None, min_length=6, max_length=6)
    email_otp: str | None = Field(default=None, min_length=6, max_length=6)

    @model_validator(mode="after")
    def require_fields_for_purpose(self) -> VerifyOTPRequest:
        """Login uses email OTP; registration requires both channels."""
        if self.purpose == "login":
            if not self.email or not self.otp:
                raise ValueError("Login verification requires email and otp")
        elif self.purpose == "registration":
            if not self.phone or not self.email or not self.phone_otp or not self.email_otp:
                raise ValueError(
                    "Registration verification requires phone, email, phone_otp, and email_otp"
                )
        elif self.purpose == "password_reset":
            raise ValueError("Use /auth/reset-password to submit password-reset OTPs")
        return self


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
    """Forgot password step two: email OTP, SMS OTP, and new password."""

    email_or_phone: str = Field(min_length=3, max_length=255)
    phone_otp: str = Field(min_length=6, max_length=6)
    email_otp: str = Field(min_length=6, max_length=6)
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
    email_verified: bool
    logo_url: str | None
    watermark_url: str | None
    watermark_scale: float
    watermark_x: float
    watermark_y: float
    watermark_opacity: float
    storage_used_bytes: int
    storage_limit_bytes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UpdateProfileRequest(BaseModel):
    """Partial photographer profile update."""

    studio_name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = Field(None, pattern=INDIAN_PHONE_PATTERN)
    watermark_url: str | None = None
    logo_url: str | None = None


class TokenResponse(BaseModel):
    """JWT pair plus photographer profile."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    photographer: PhotographerProfile
