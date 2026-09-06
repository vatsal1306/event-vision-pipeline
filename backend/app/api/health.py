"""Liveness and readiness health checks."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import async_session_factory

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return OK when the API process is running."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
async def ready() -> JSONResponse | dict[str, str]:
    """Return ready when PostgreSQL accepts a connection."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "detail": "database unreachable"},
        )
    return {"status": "ready"}
