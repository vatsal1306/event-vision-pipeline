"""Guest session model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.face_cluster import EMBEDDING_DIMENSIONS

if TYPE_CHECKING:
    from app.models.analytics_event import AnalyticsEvent
    from app.models.event import Event


class GuestSession(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Guest OTP session scoped to a single event."""

    __tablename__ = "guest_sessions"
    __table_args__ = (
        UniqueConstraint("event_id", "phone", name="uq_guest_sessions_event_phone"),
        Index("idx_guest_sessions_event", "event_id"),
        Index("idx_guest_sessions_phone", "event_id", "phone"),
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
    selfie_s3_key: Mapped[str | None] = mapped_column(String(500))
    selfie_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    matched_cluster_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        server_default=text("'{}'::uuid[]"),
        nullable=False,
    )
    matched_photo_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )

    event: Mapped[Event] = relationship("Event", back_populates="guest_sessions", lazy="selectin")
    analytics_events: Mapped[list[AnalyticsEvent]] = relationship(
        "AnalyticsEvent",
        back_populates="guest_session",
        lazy="selectin",
    )
