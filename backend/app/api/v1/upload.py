"""tusd webhook endpoints (BE-009)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.schemas.upload import TusHookPayload
from app.services.upload_service import UploadService

logger = get_logger()

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post(
    "/hook",
    dependencies=[Depends(rate_limit("webhook", limit=1000, window=60))],
)
async def tusd_hook(
    payload: TusHookPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Accept tusd hooks for pre-create and post-finish."""
    event_type = payload.type
    upload_info = payload.event.upload

    upload_service = UploadService(db)

    if event_type == "pre-create":
        return await upload_service.handle_pre_create(upload_info)
    if event_type == "post-finish":
        return await upload_service.handle_post_finish(upload_info)

    logger.info("Ignoring tusd hook type %s", event_type, hook_type=event_type)
    return {"status": "accepted"}
