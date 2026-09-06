"""Couple session model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analytics_event import AnalyticsEvent
    from app.models.event import Event
    from app.models.favorite import Favorite


class CoupleSession(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Couple OTP session scoped to a single event."""

    __tablename__ = "couple_sessions"
    __table_args__ = (
        UniqueConstraint("event_id", "phone", name="uq_couple_sessions_event_phone"),
        Index("idx_couple_sessions_event", "event_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    event: Mapped[Event] = relationship(
        "Event",
        back_populates="couple_sessions",
        lazy="selectin",
    )
    favorites: Mapped[list[Favorite]] = relationship(
        "Favorite",
        back_populates="couple_session",
        lazy="selectin",
    )
    analytics_events: Mapped[list[AnalyticsEvent]] = relationship(
        "AnalyticsEvent",
        back_populates="couple_session",
        lazy="selectin",
    )
