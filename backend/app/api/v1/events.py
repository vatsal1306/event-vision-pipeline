"""Event API routes for authenticated photographers."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer, get_photographer_event
from app.core.database import get_db
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photographer import Photographer
from app.schemas.analytics import AnalyticsSummary, AnalyticsTopPhotosResponse, GuestListResponse
from app.schemas.event import (
    CreateEventRequest,
    EventDetail,
    EventListResponse,
    EventSettingsRequest,
    EventSortBy,
    EventSortOrder,
    UpdateEventRequest,
)
from app.schemas.folder import (
    CreateFolderRequest,
    FolderNode,
    FolderTreeResponse,
    UpdateFolderRequest,
)
from app.services.event_service import EventService
from app.services.folder_service import FolderService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventListResponse)
async def list_events(
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: EventStatus | None = Query(None, alias="status"),
    sort_by: EventSortBy = Query("created_at"),
    sort_order: EventSortOrder = Query("desc"),
) -> EventListResponse:
    """List events owned by the authenticated photographer."""
    service = EventService(db)
    return await service.list_events(
        photographer.id,
        offset=offset,
        limit=limit,
        status=status_filter,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=EventDetail, status_code=status.HTTP_201_CREATED)
async def create_event(
    request: CreateEventRequest,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    """Create a draft event for the authenticated photographer."""
    service = EventService(db)
    return await service.create_event(photographer.id, request)


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    """Return one event owned by the photographer."""
    return await EventService(db).get_event(event)


@router.put("/{event_id}", response_model=EventDetail)
async def update_event(
    request: UpdateEventRequest,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    """Partially update an event."""
    return await EventService(db).update_event(event, request)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Hard-delete an event and cascaded child rows."""
    await EventService(db).delete_event(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{event_id}/settings", response_model=EventDetail)
async def update_event_settings(
    request: EventSettingsRequest,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    """Update download and share-link flags."""
    return await EventService(db).update_settings(event, request)


@router.put("/{event_id}/links/{link_type}/toggle", response_model=EventDetail)
async def toggle_event_link(
    link_type: str,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    """Toggle master or guest share link."""
    return await EventService(db).toggle_link(event, link_type)


@router.get("/{event_id}/folders", response_model=FolderTreeResponse)
async def list_folders(
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> FolderTreeResponse:
    """Return the nested folder tree for an event."""
    return await FolderService(db).list_tree(event.id)


@router.post("/{event_id}/folders", response_model=FolderNode, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: CreateFolderRequest,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> FolderNode:
    """Create a folder in the event."""
    return await FolderService(db).create_folder(event.id, request)


@router.put("/{event_id}/folders/{folder_id}", response_model=FolderNode)
async def update_folder(
    folder_id: UUID,
    request: UpdateFolderRequest,
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> FolderNode:
    """Rename, reorder, or reparent a folder."""
    return await FolderService(db).update_folder(event.id, folder_id, request)


@router.delete("/{event_id}/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: UUID,
    delete_photos: bool = Query(False),
    event: Event = Depends(get_photographer_event),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a folder; photos move to root or are deleted based on the flag."""
    await FolderService(db).delete_folder(event.id, folder_id, delete_photos=delete_photos)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{event_id}/analytics/summary", response_model=AnalyticsSummary)
async def analytics_summary(event: Event = Depends(get_photographer_event)) -> AnalyticsSummary:
    """Return analytics summary (zeros until BE-015)."""
    return AnalyticsSummary()


@router.get("/{event_id}/analytics/top-photos", response_model=AnalyticsTopPhotosResponse)
async def analytics_top_photos(
    event: Event = Depends(get_photographer_event),
) -> AnalyticsTopPhotosResponse:
    """Return top photos placeholder."""
    return AnalyticsTopPhotosResponse()


@router.get("/{event_id}/analytics/guests", response_model=GuestListResponse)
async def analytics_guests(event: Event = Depends(get_photographer_event)) -> GuestListResponse:
    """Return guest analytics placeholder."""
    return GuestListResponse()
