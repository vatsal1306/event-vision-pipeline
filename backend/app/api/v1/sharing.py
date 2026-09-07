"""API routes for public event landing pages."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.event import EventPublicInfo
from app.services.sharing_service import SharingService

router = APIRouter(prefix="/event", tags=["sharing"])


@router.get("/{slug}/info", response_model=EventPublicInfo)
async def get_public_event_info(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> EventPublicInfo:
    """Retrieve public event details (name, studio, link status) without auth."""
    return await SharingService(db).get_public_info(slug)
