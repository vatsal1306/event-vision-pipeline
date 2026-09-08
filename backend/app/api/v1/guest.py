"""Guest authentication endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_any_session_for_slug,
    get_db,
    get_face_service,
    get_guest_session_for_slug,
    get_redis_dep,
)
from app.models.couple_session import CoupleSession
from app.models.guest_session import GuestSession
from app.schemas.guest import (
    GuestAuthRequest,
    GuestTokenResponse,
    GuestVerifyRequest,
    SelfieMatchResponse,
)
from app.schemas.photo import DownloadPhotoResponse, PhotoListResponse
from app.services.guest_service import GuestService
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

if TYPE_CHECKING:
    import redis.asyncio as redis


from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/event/{slug}", tags=["Guest"])


def get_guest_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_dep),
) -> GuestService:
    """Dependency injection for GuestService."""
    sms_service = SMSService()
    otp_service = OTPService(redis_client, sms_service)
    return GuestService(db, otp_service)


@router.post(
    "/auth",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("otp_send", limit=3, window=300))],
)
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


@router.post(
    "/auth/verify",
    response_model=GuestTokenResponse,
    dependencies=[Depends(rate_limit("otp_verify", limit=5, window=300))],
)
async def verify_guest_auth(
    slug: str,
    request: GuestVerifyRequest,
    guest_service: GuestService = Depends(get_guest_service),
) -> GuestTokenResponse:
    """Verify the guest's OTP and issue a session token."""
    return await guest_service.verify_auth(
        slug=slug,
        name=request.name,
        phone=request.phone,
        otp=request.otp,
    )


@router.post("/selfie", response_model=SelfieMatchResponse)
async def upload_selfie(
    slug: str,
    file: UploadFile = File(...),
    guest_session: GuestSession = Depends(get_guest_session_for_slug),
    guest_service: GuestService = Depends(get_guest_service),
    face_service: Any = Depends(get_face_service),
) -> SelfieMatchResponse:
    """Upload a selfie for face matching."""
    from app.core.exceptions import BadRequestError

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise BadRequestError(f"Unsupported file type. Allowed: {', '.join(allowed_types)}")

    # Validate file size (max 30MB)
    MAX_SIZE = 30 * 1024 * 1024

    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise BadRequestError("File too large. Maximum size is 30MB.")

    return await guest_service.process_selfie(
        session=guest_session,
        selfie_bytes=file_bytes,
        face_service=face_service,
    )


@router.get(
    "/guest/photos",
    response_model=PhotoListResponse,
    dependencies=[Depends(rate_limit("photo_list", limit=60, window=60))],
)
async def list_guest_photos(
    slug: str,
    folder_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    guest_session: GuestSession = Depends(get_guest_session_for_slug),
    guest_service: GuestService = Depends(get_guest_service),
) -> PhotoListResponse:
    """List matched photos for the authenticated guest."""
    photos, total = await guest_service.get_guest_photos(
        session=guest_session,
        offset=offset,
        limit=limit,
        folder_id=folder_id,
    )

    from app.services.photo_service import PhotoService

    photo_service = PhotoService(guest_service.db)
    photo_responses = photo_service.build_photo_responses(photos)

    return PhotoListResponse(
        items=photo_responses,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/photos/{photo_id}/download",
    response_model=DownloadPhotoResponse,
    dependencies=[Depends(rate_limit("download", limit=30, window=60))],
)
async def download_guest_photo(
    slug: str,
    photo_id: UUID,
    guest_session: GuestSession = Depends(get_guest_session_for_slug),
    guest_service: GuestService = Depends(get_guest_service),
) -> DownloadPhotoResponse:
    """Get a presigned download URL for a matched photo."""
    url = await guest_service.get_guest_photo_download(
        session=guest_session,
        photo_id=photo_id,
    )
    return DownloadPhotoResponse(url=url)


@router.post("/photos/{photo_id}/view", status_code=status.HTTP_204_NO_CONTENT, tags=["Analytics"])
async def record_photo_view(
    slug: str,
    photo_id: UUID,
    session: GuestSession | CoupleSession = Depends(get_any_session_for_slug),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Record a photo view for analytics. Accepts Guest or Couple session."""
    from app.services.photo_service import PhotoService

    photo_service = PhotoService(db)
    await photo_service.record_photo_view(session=session, photo_id=photo_id)
