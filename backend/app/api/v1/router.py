"""Aggregate v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.couple import router as couple_router
from app.api.v1.events import router as events_router
from app.api.v1.guest import router as guest_router
from app.api.v1.photos import router as photos_router
from app.api.v1.profile import router as profile_router
from app.api.v1.sharing import router as sharing_router
from app.api.v1.upload import router as upload_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(events_router)
router.include_router(photos_router)
router.include_router(sharing_router)
router.include_router(guest_router)
router.include_router(couple_router)
router.include_router(upload_router)
router.include_router(analytics_router)
