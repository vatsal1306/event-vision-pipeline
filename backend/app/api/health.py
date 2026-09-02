"""Health check endpoint.

Liveness probe that does not depend on database or external services.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return service liveness status.

    This endpoint is intentionally lightweight — it confirms the ASGI
    process is alive and accepting HTTP traffic. It does **not** verify
    database connectivity (use ``/health/ready`` once BE-003 lands).
    """
    return {"status": "ok"}
