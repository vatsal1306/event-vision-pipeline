"""Event listing and CRUD business logic."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.folder import Folder
from app.models.guest_session import GuestSession
from app.models.photo import Photo
from app.schemas.event import (
    CreateEventRequest,
    EventDetail,
    EventListResponse,
    EventSettingsRequest,
    EventSortBy,
    EventSortOrder,
    EventSummary,
    UpdateEventRequest,
)
from app.utils.slug import unique_event_slug

ARCHIVE_MONTHS = 2
MAX_SLUG_ATTEMPTS = 5
DEFAULT_SORT_BY: EventSortBy = "created_at"
DEFAULT_SORT_ORDER: EventSortOrder = "desc"

_SORT_COLUMNS: dict[EventSortBy, InstrumentedAttribute[Any]] = {
    "created_at": Event.created_at,
    "name": Event.name,
    "date_start": Event.date_start,
    "status": Event.status,
}


def _add_months(value: datetime, months: int) -> datetime:
    """Add calendar months to a timezone-aware datetime."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _validate_date_range(date_start: date | None, date_end: date | None) -> None:
    """Reject event date ranges where the end precedes the start."""
    if date_start is not None and date_end is not None and date_end < date_start:
        raise BadRequestError("date_end must be on or after date_start")


class EventService:
    """Business logic for photographer-owned events."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with a database session."""
        self.db = db

    async def list_events(
        self,
        photographer_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        status: EventStatus | None = None,
        sort_by: EventSortBy = DEFAULT_SORT_BY,
        sort_order: EventSortOrder = DEFAULT_SORT_ORDER,
    ) -> EventListResponse:
        """Return paginated events owned by the photographer."""
        bounded_limit = min(max(limit, 1), 100)
        bounded_offset = max(offset, 0)

        filters = [Event.photographer_id == photographer_id]
        if status is not None:
            filters.append(Event.status == status)

        total = await self.db.scalar(select(func.count()).select_from(Event).where(*filters))
        total_count = int(total or 0)

        sort_column = _SORT_COLUMNS.get(sort_by, Event.created_at)
        order_clause = sort_column.desc() if sort_order == "desc" else sort_column.asc()

        result = await self.db.execute(
            select(Event)
            .where(*filters)
            .order_by(order_clause, Event.id.asc())
            .offset(bounded_offset)
            .limit(bounded_limit)
        )
        events = list(result.scalars().all())
        summaries = [await self._to_summary(event) for event in events]
        return EventListResponse(
            events=summaries,
            total=total_count,
            offset=bounded_offset,
            limit=bounded_limit,
        )

    async def create_event(
        self,
        photographer_id: UUID,
        request: CreateEventRequest,
    ) -> EventDetail:
        """Create a draft event with a unique slug and archival date."""
        event = Event(
            photographer_id=photographer_id,
            name=request.name,
            slug=await self._allocate_slug(request.name),
            date_start=request.date_start,
            date_end=request.date_end,
            event_type=request.event_type,
            description=request.description,
            status=EventStatus.DRAFT,
        )
        self.db.add(event)
        await self.db.flush()
        event.archive_at = _add_months(event.created_at, ARCHIVE_MONTHS)
        await self.db.flush()
        return await self._to_detail(event)

    async def get_event(self, event: Event) -> EventDetail:
        """Serialize an already-authorized event."""
        return await self._to_detail(event)

    async def update_event(self, event: Event, request: UpdateEventRequest) -> EventDetail:
        """Apply a partial update to an event."""
        next_start = request.date_start if request.date_start is not None else event.date_start
        next_end = request.date_end if request.date_end is not None else event.date_end
        _validate_date_range(next_start, next_end)

        if request.name is not None:
            event.name = request.name
        if request.date_start is not None or request.date_end is not None:
            if request.date_start is not None:
                event.date_start = request.date_start
            if request.date_end is not None:
                event.date_end = request.date_end
        if request.event_type is not None:
            event.event_type = request.event_type
        if request.description is not None:
            event.description = request.description
        await self.db.flush()
        return await self._to_detail(event)

    async def update_settings(self, event: Event, request: EventSettingsRequest) -> EventDetail:
        """Update download and share-link flags."""
        if request.download_enabled is not None:
            event.download_enabled = request.download_enabled
        if request.master_link_active is not None:
            event.master_link_active = request.master_link_active
        if request.guest_link_active is not None:
            event.guest_link_active = request.guest_link_active
        await self.db.flush()
        return await self._to_detail(event)

    async def toggle_link(self, event: Event, link_type: str) -> EventDetail:
        """Flip master or guest link active flag."""
        if link_type == "master":
            event.master_link_active = not event.master_link_active
        elif link_type == "guest":
            event.guest_link_active = not event.guest_link_active
        else:
            raise NotFoundError("Link type")
        await self.db.flush()
        return await self._to_detail(event)

    async def delete_event(self, event: Event) -> None:
        """Hard-delete an event; child rows cascade via FK."""
        await self.db.delete(event)
        await self.db.flush()

    async def get_owned_event(self, photographer_id: UUID, event_id: UUID) -> Event:
        """Load an event owned by the photographer, or 404."""
        event = await self.db.get(Event, event_id)
        if event is None or event.photographer_id != photographer_id:
            raise NotFoundError("Event")
        return event

    async def update_event_processing_status(self, event_id: UUID) -> None:
        """Update event status based on photo processing completion."""
        event = await self.db.get(Event, event_id)
        if not event:
            return

        stats = await self.db.execute(
            select(
                func.count(Photo.id).label("total"),
                func.count(Photo.id)
                .filter(
                    Photo.processing_status.in_(
                        [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]
                    )
                )
                .label("processed"),
            ).where(Photo.event_id == event_id)
        )
        total, processed = stats.one()

        event.total_photos = total
        event.processed_photos = processed

        previous_status = event.status

        if total == 0:
            event.status = EventStatus.DRAFT
        elif processed < total:
            event.status = EventStatus.PROCESSING
        elif processed == total:
            event.status = EventStatus.READY

            if previous_status != EventStatus.READY:
                from app.tasks.notification_tasks import notify_processing_complete_task

                notify_processing_complete_task.delay(str(event_id))

        await self.db.commit()

    async def _allocate_slug(self, name: str) -> str:
        """Retry slug generation until the unique constraint is satisfied."""
        for _ in range(MAX_SLUG_ATTEMPTS):
            candidate = unique_event_slug(name)
            existing = await self.db.scalar(select(Event.id).where(Event.slug == candidate))
            if existing is None:
                return candidate
        raise ConflictError("Could not allocate a unique event slug")

    async def _folder_and_guest_counts(self, event_id: UUID) -> tuple[int, int]:
        folder_count = await self.db.scalar(
            select(func.count()).select_from(Folder).where(Folder.event_id == event_id)
        )
        guest_count = await self.db.scalar(
            select(func.count()).select_from(GuestSession).where(GuestSession.event_id == event_id)
        )
        return int(folder_count or 0), int(guest_count or 0)

    async def _to_summary(self, event: Event) -> EventSummary:
        folder_count, guest_count = await self._folder_and_guest_counts(event.id)
        return EventSummary(
            id=event.id,
            photographer_id=event.photographer_id,
            name=event.name,
            slug=event.slug,
            date_start=event.date_start,
            date_end=event.date_end,
            event_type=event.event_type,
            status=event.status,
            description=event.description,
            cover_photo_id=event.cover_photo_id,
            download_enabled=event.download_enabled,
            master_link_active=event.master_link_active,
            guest_link_active=event.guest_link_active,
            total_photos=event.total_photos,
            total_faces=event.total_faces,
            processed_photos=event.processed_photos,
            folder_count=folder_count,
            guest_count=guest_count,
            cover_image_url=None,
            archive_at=event.archive_at,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    async def _to_detail(self, event: Event) -> EventDetail:
        folder_count, guest_count = await self._folder_and_guest_counts(event.id)
        return EventDetail.from_event(event, folder_count=folder_count, guest_count=guest_count)
