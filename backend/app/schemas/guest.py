"""Guest API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import INDIAN_PHONE_PATTERN


class GuestAuthRequest(BaseModel):
    """Initial request for guest authentication."""

    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)


class GuestVerifyRequest(BaseModel):
    """OTP verification request for guest authentication."""

    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)
    otp: str = Field(..., min_length=6, max_length=6)


class GuestTokenResponse(BaseModel):
    """Response returned upon successful guest authentication."""

    access_token: str
    token_type: str = "bearer"
    needs_selfie: bool


class SelfieMatchResponse(BaseModel):
    """Response from guest selfie match."""

    matched_photo_ids: list[str]
    match_count: int
