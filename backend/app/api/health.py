"""Liveness and readiness health checks."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Return OK when the API process is running."""
    return {"status": "ok"}
