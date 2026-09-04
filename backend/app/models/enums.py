"""PostgreSQL enum types used by ORM models."""

from __future__ import annotations

import enum

from sqlalchemy import Enum


class EventStatus(str, enum.Enum):
    """Lifecycle status of an event."""

    DRAFT = "draft"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ARCHIVED = "archived"


class EventType(str, enum.Enum):
    """Category of event."""

    WEDDING = "wedding"
    CORPORATE = "corporate"
    BIRTHDAY = "birthday"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    """Photo processing pipeline status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyticsAction(str, enum.Enum):
    """Analytics event action type."""

    VIEW = "view"
    DOWNLOAD = "download"


def pg_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    """Build a native PostgreSQL enum that persists enum values, not names."""
    return Enum(
        enum_class,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )
