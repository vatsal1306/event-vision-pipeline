"""Couple authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_couple_session_for_slug, get_db, get_redis_dep
from app.models.couple_session import CoupleSession
from app.schemas.couple import (
    CoupleAuthRequest,
    CoupleTokenResponse,
    CoupleVerifyRequest,
    ToggleFavoriteRequest,
    ToggleFavoriteResponse,
)
from app.schemas.folder import FolderTreeResponse
from app.schemas.photo import DownloadPhotoResponse, PhotoListResponse
from app.services.couple_service import CoupleService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

if TYPE_CHECKING:
    import redis.asyncio as redis


from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/event/{slug}/master", tags=["Couple"])


def get_couple_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> CoupleService:
    """Dependency injection for CoupleService."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return CoupleService(db, otp_service)


@router.post(
    "/auth",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("otp_send", limit=3, window=300))],
)
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


@router.post(
    "/verify",
    response_model=CoupleTokenResponse,
    dependencies=[Depends(rate_limit("otp_verify", limit=5, window=300))],
)
async def verify_couple_auth(
    slug: str,
    request: CoupleVerifyRequest,
    couple_service: CoupleService = Depends(get_couple_service),
) -> CoupleTokenResponse:
    """Verify the couple's OTP and issue a session token."""
    return await couple_service.verify_auth(
        slug=slug,
        name=request.name,
        phone=request.phone,
        otp=request.otp,
    )


@router.get(
    "/photos",
    response_model=PhotoListResponse,
    dependencies=[Depends(rate_limit("photo_list", limit=60, window=60))],
)
async def list_master_photos(
    slug: str,
    folder_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: CoupleSession = Depends(get_couple_session_for_slug),
    couple_service: CoupleService = Depends(get_couple_service),
) -> PhotoListResponse:
    """List completed photos for the event (master link)."""
    return await couple_service.get_photos(session, folder_id, offset, limit)


@router.get("/folders", response_model=FolderTreeResponse)
async def list_master_folders(
    slug: str,
    session: CoupleSession = Depends(get_couple_session_for_slug),
    couple_service: CoupleService = Depends(get_couple_service),
) -> FolderTreeResponse:
    """List the folder tree for the event."""
    return await couple_service.get_folders(session)


@router.post("/favorite", response_model=ToggleFavoriteResponse)
async def toggle_favorite(
    slug: str,
    request: ToggleFavoriteRequest,
    session: CoupleSession = Depends(get_couple_session_for_slug),
    couple_service: CoupleService = Depends(get_couple_service),
) -> ToggleFavoriteResponse:
    """Toggle the favorite status of a photo."""
    is_favorite = await couple_service.toggle_favorite(session, request.photo_id)
    return ToggleFavoriteResponse(is_favorite=is_favorite)


@router.get(
    "/favorites",
    response_model=PhotoListResponse,
    dependencies=[Depends(rate_limit("photo_list", limit=60, window=60))],
)
async def list_favorites(
    slug: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: CoupleSession = Depends(get_couple_session_for_slug),
    couple_service: CoupleService = Depends(get_couple_service),
) -> PhotoListResponse:
    """List favorited photos."""
    return await couple_service.get_favorites(session, offset, limit)


@router.get(
    "/photos/{photo_id}/download",
    response_model=DownloadPhotoResponse,
    dependencies=[Depends(rate_limit("download", limit=30, window=60))],
)
async def download_master_photo(
    slug: str,
    photo_id: UUID,
    session: CoupleSession = Depends(get_couple_session_for_slug),
    couple_service: CoupleService = Depends(get_couple_service),
) -> DownloadPhotoResponse:
    """Get a presigned download URL for a photo and record analytics."""
    url = await couple_service.get_download_url(session, photo_id)
    return DownloadPhotoResponse(url=url)
