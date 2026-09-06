"""Photographer profile API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.photographer import Photographer
from app.schemas.auth import PhotographerProfile, UpdateProfileRequest

router = APIRouter(prefix="/profile", tags=["profile"])


def _not_implemented_upload() -> None:
    """Raise until S3 branding uploads exist."""
    raise AppException(
        "Logo and watermark uploads are not available yet",
        "NOT_IMPLEMENTED",
        501,
    )


@router.get("", response_model=PhotographerProfile)
async def get_profile(
    photographer: Photographer = Depends(get_current_photographer),
) -> PhotographerProfile:
    """Return the authenticated photographer's profile."""
    return PhotographerProfile.model_validate(photographer)


@router.put("", response_model=PhotographerProfile)
async def update_profile(
    request: UpdateProfileRequest,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> PhotographerProfile:
    """Update studio name or phone. Logo/watermark uploads are BE-016."""
    if request.studio_name is not None:
        photographer.studio_name = request.studio_name
    if request.phone is not None and request.phone != photographer.phone:
        photographer.phone = request.phone
        photographer.phone_verified = False
    await db.flush()
    return PhotographerProfile.model_validate(photographer)


@router.get("/storage")
async def get_storage(
    photographer: Photographer = Depends(get_current_photographer),
) -> dict[str, int]:
    """Return storage used/limit for the dashboard sidebar."""
    return {
        "used": photographer.storage_used_bytes,
        "limit": photographer.storage_limit_bytes,
    }


@router.post("/logo")
async def upload_logo_not_implemented() -> None:
    """Logo upload requires S3 (BE-016)."""
    _not_implemented_upload()


@router.post("/watermark")
async def upload_watermark_not_implemented() -> None:
    """Watermark upload requires S3 (BE-016)."""
    _not_implemented_upload()
