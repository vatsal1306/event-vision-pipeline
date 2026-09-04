"""Analytics event model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import AnalyticsAction, pg_enum

if TYPE_CHECKING:
    from app.models.couple_session import CoupleSession
    from app.models.event import Event
    from app.models.guest_session import GuestSession
    from app.models.photo import Photo


class AnalyticsEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Append-only analytics log entry."""

    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("idx_analytics_event", "event_id"),
        Index("idx_analytics_photo", "photo_id"),
        Index("idx_analytics_action", "event_id", "action"),
        Index(
            "idx_analytics_downloads",
            "event_id",
            "photo_id",
            postgresql_where=text("action = 'download'"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
    )
    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guest_sessions.id", ondelete="SET NULL"),
    )
    couple_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couple_sessions.id", ondelete="SET NULL"),
    )
    action: Mapped[AnalyticsAction] = mapped_column(
        pg_enum(AnalyticsAction, "analytics_action"),
        nullable=False,
    )

    event: Mapped[Event] = relationship(
        "Event",
        back_populates="analytics_events",
        lazy="selectin",
    )
    photo: Mapped[Photo | None] = relationship(
        "Photo",
        back_populates="analytics_events",
        lazy="selectin",
    )
    guest_session: Mapped[GuestSession | None] = relationship(
        "GuestSession",
        back_populates="analytics_events",
        lazy="selectin",
    )
    couple_session: Mapped[CoupleSession | None] = relationship(
        "CoupleSession",
        back_populates="analytics_events",
        lazy="selectin",
    )
