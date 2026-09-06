"""Aggregate v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.upload import router as upload_router

router = APIRouter()
router.include_router(upload_router)
