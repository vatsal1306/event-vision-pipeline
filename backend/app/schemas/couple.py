"""Couple API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import INDIAN_PHONE_PATTERN


class CoupleAuthRequest(BaseModel):
    """Initial request for couple (master link) authentication."""

    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)


class CoupleVerifyRequest(BaseModel):
    """OTP verification request for couple authentication."""

    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., pattern=INDIAN_PHONE_PATTERN)
    otp: str = Field(..., min_length=6, max_length=6)


class CoupleTokenResponse(BaseModel):
    """Response returned upon successful couple authentication."""

    token: str
    token_type: str = "bearer"


class ToggleFavoriteRequest(BaseModel):
    """Request to toggle favorite status for a photo."""

    photo_id: UUID


class ToggleFavoriteResponse(BaseModel):
    """Response returned upon toggling favorite status."""

    is_favorite: bool
