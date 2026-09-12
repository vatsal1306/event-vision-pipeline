"""Photographer profile API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer
from app.config import get_settings
from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.models.photographer import Photographer
from app.schemas.auth import PhotographerProfile, UpdateProfileRequest
from app.schemas.profile import StorageInfo
from app.services.photographer_service import PhotographerService
from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/profile", tags=["profile"])


async def _presign_profile_urls(profile: PhotographerProfile) -> PhotographerProfile:
    """Dynamically generate presigned URLs for S3 keys in the profile."""
    settings = get_settings()
    storage = get_storage_service()

    if profile.logo_url and not profile.logo_url.startswith("http"):
        profile.logo_url = await storage.generate_presigned_url(
            settings.s3_bucket_assets, profile.logo_url
        )
    if profile.watermark_url and not profile.watermark_url.startswith("http"):
        profile.watermark_url = await storage.generate_presigned_url(
            settings.s3_bucket_assets, profile.watermark_url
        )
    return profile


@router.get("", response_model=PhotographerProfile)
async def get_profile(
    photographer: Photographer = Depends(get_current_photographer),
) -> PhotographerProfile:
    """Return the authenticated photographer's profile."""
    profile = PhotographerProfile.model_validate(photographer)
    return await _presign_profile_urls(profile)


@router.put("", response_model=PhotographerProfile)
async def update_profile(
    request: UpdateProfileRequest,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> PhotographerProfile:
    """Update studio name, phone, logo, or watermark."""
    update_data = request.model_dump(exclude_unset=True)

    if "studio_name" in update_data:
        photographer.studio_name = update_data["studio_name"]
    if "phone" in update_data and update_data["phone"] != photographer.phone:
        photographer.phone = update_data["phone"]
        photographer.phone_verified = False
    if "logo_url" in update_data:
        photographer.logo_url = update_data["logo_url"]
    if "watermark_url" in update_data:
        photographer.watermark_url = update_data["watermark_url"]

    await db.commit()
    await db.refresh(photographer)

    profile = PhotographerProfile.model_validate(photographer)
    return await _presign_profile_urls(profile)


@router.get("/storage", response_model=StorageInfo)
async def get_storage(
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> StorageInfo:
    """Return detailed storage usage for the dashboard sidebar."""
    service = PhotographerService(db)
    return await service.get_storage_info(photographer)


@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Upload a studio logo to the assets bucket."""
    if not file.content_type or file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise BadRequestError("Invalid file type. Must be JPEG, PNG, or WEBP")

    header = await file.read(12)
    await file.seek(0)

    if not (
        header.startswith(b"\xff\xd8")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or (header[:4] == b"RIFF" and header[8:12] == b"WEBP")
    ):
        raise BadRequestError("Invalid image signature")

    settings = get_settings()
    storage = get_storage_service()

    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "img"
    key = f"profiles/{photographer.id}/logo_{uuid.uuid4().hex[:8]}.{ext}"

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise BadRequestError("File too large. Maximum size is 10MB.")

    old_key = photographer.logo_url
    await storage.put_object(
        bucket=settings.s3_bucket_assets,
        key=key,
        data=data,
        content_type=file.content_type,
    )
    if old_key:
        await storage.delete_object(settings.s3_bucket_assets, old_key)

    photographer.logo_url = key
    await db.commit()

    url = await storage.generate_presigned_url(settings.s3_bucket_assets, key)
    return {"url": url}


@router.post("/watermark")
async def upload_watermark(
    file: UploadFile = File(...),
    scale: float | None = Form(None),
    x: float | None = Form(None),
    y: float | None = Form(None),
    opacity: float | None = Form(None),
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Upload a watermark to the assets bucket (must be PNG)."""
    if file.content_type != "image/png":
        raise BadRequestError("Watermark must be a PNG image")

    header = await file.read(8)
    await file.seek(0)
    if not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BadRequestError("Invalid image signature, must be PNG")

    settings = get_settings()
    storage = get_storage_service()

    key = f"profiles/{photographer.id}/watermark_{uuid.uuid4().hex[:8]}.png"

    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise BadRequestError("File too large. Maximum size is 10MB.")

    old_key = photographer.watermark_url
    await storage.put_object(
        bucket=settings.s3_bucket_assets,
        key=key,
        data=data,
        content_type=file.content_type,
    )
    if old_key:
        await storage.delete_object(settings.s3_bucket_assets, old_key)

    photographer.watermark_url = key
    if scale is not None:
        photographer.watermark_scale = scale
    if x is not None:
        photographer.watermark_x = x
    if y is not None:
        photographer.watermark_y = y
    if opacity is not None:
        photographer.watermark_opacity = opacity

    await db.commit()

    url = await storage.generate_presigned_url(settings.s3_bucket_assets, key)
    return {"url": url}
