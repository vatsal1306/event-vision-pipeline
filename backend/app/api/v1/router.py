"""Aggregated API v1 router.

Include sub-routers for each domain (auth, events, photos, etc.)
as they are implemented in subsequent stories.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# Future sub-routers will be included here:
# router.include_router(auth.router)       # BE-004
# router.include_router(events.router)     # BE-005
# router.include_router(folders.router)    # BE-006
# router.include_router(photos.router)     # BE-007
# router.include_router(upload.router)     # BE-009
# router.include_router(sharing.router)    # BE-011
# router.include_router(guest.router)      # BE-012
# router.include_router(couple.router)     # BE-014
# router.include_router(analytics.router)  # BE-015
# router.include_router(profile.router)    # BE-016
