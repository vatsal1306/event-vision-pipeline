"""tusd webhook endpoints (stub until BE-009)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/create")
async def create_upload_not_implemented() -> None:
    """Resumable upload init requires tusd + S3 (BE-008/BE-009)."""
    from app.core.exceptions import AppException

    raise AppException(
        "Photo upload is not available yet",
        "NOT_IMPLEMENTED",
        501,
    )


@router.post("/hook")
async def tusd_post_finish_hook(request: Request) -> dict[str, str]:
    """Accept tusd post-finish / post-terminate hooks.

    BE-009 will parse the payload, create Photo rows, and enqueue Celery work.
    """
    body: dict[str, Any] = await request.json()
    event_type = body.get("Type", "unknown")
    upload_id = body.get("Event", {}).get("Upload", {}).get("ID", "unknown")
    logger.info(
        "tusd hook received type=%s upload_id=%s (stub — no DB write yet)",
        event_type,
        upload_id,
    )
    return {"status": "accepted"}
