"""Aggregate v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.profile import router as profile_router
from app.api.v1.upload import router as upload_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(events_router)
router.include_router(upload_router)
