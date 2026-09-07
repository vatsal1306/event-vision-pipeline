"""Pydantic schemas for event API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import get_settings
from app.models.enums import EventStatus, EventType
from app.models.event import Event

EventSortBy = Literal["created_at", "name", "date_start", "status"]
EventSortOrder = Literal["asc", "desc"]


class EventSummary(BaseModel):
    """Compact event payload for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    photographer_id: UUID
    name: str
    slug: str
    date_start: date | None
    date_end: date | None
    event_type: EventType
    status: EventStatus
    description: str | None = None
    cover_photo_id: UUID | None = None
    download_enabled: bool = True
    master_link_active: bool = True
    guest_link_active: bool = True
    total_photos: int
    total_faces: int = 0
    processed_photos: int = 0
    folder_count: int
    guest_count: int
    cover_image_url: str | None = None
    archive_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class EventListResponse(BaseModel):
    """Paginated list of events owned by the authenticated photographer."""

    events: list[EventSummary]
    total: int
    offset: int
    limit: int


class CreateEventRequest(BaseModel):
    """Payload for creating a new event."""

    name: str = Field(min_length=3, max_length=255)
    date_start: date | None = None
    date_end: date | None = None
    event_type: EventType = EventType.WEDDING
    description: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_date_range(self) -> CreateEventRequest:
        """Ensure the event end date is not before the start date."""
        if (
            self.date_start is not None
            and self.date_end is not None
            and self.date_end < self.date_start
        ):
            raise ValueError("date_end must be on or after date_start")
        return self


class UpdateEventRequest(BaseModel):
    """Partial update for an event."""

    name: str | None = Field(None, min_length=3, max_length=255)
    date_start: date | None = None
    date_end: date | None = None
    event_type: EventType | None = None
    description: str | None = Field(None, max_length=500)


class EventSettingsRequest(BaseModel):
    """Toggle download and link flags for an event."""

    download_enabled: bool | None = None
    master_link_active: bool | None = None
    guest_link_active: bool | None = None


class EventDetail(BaseModel):
    """Full event payload including share URLs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    photographer_id: UUID
    name: str
    slug: str
    date_start: date | None
    date_end: date | None
    event_type: EventType
    status: EventStatus
    description: str | None
    cover_photo_id: UUID | None = None
    download_enabled: bool
    master_link_active: bool
    guest_link_active: bool
    master_link_url: str
    guest_link_url: str
    total_photos: int
    total_faces: int
    processed_photos: int
    folder_count: int = 0
    guest_count: int = 0
    archive_at: datetime | None
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def from_event(
        cls,
        event: Event,
        *,
        folder_count: int = 0,
        guest_count: int = 0,
    ) -> EventDetail:
        """Build a detail payload with computed share URLs."""
        frontend_url = get_settings().frontend_url.rstrip("/")
        return cls(
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
            master_link_url=f"{frontend_url}/event/{event.slug}/master",
            guest_link_url=f"{frontend_url}/event/{event.slug}/guest",
            total_photos=event.total_photos,
            total_faces=event.total_faces,
            processed_photos=event.processed_photos,
            folder_count=folder_count,
            guest_count=guest_count,
            archive_at=event.archive_at,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )


class EventPublicInfo(BaseModel):
    """Public details of an event for unauthenticated landing pages."""

    name: str
    date_start: date | None
    date_end: date | None
    studio_name: str
    studio_logo_url: str | None
    guest_link_active: bool
    master_link_active: bool
