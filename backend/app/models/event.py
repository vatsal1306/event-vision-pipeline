"""Event model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import EventStatus, EventType, pg_enum

if TYPE_CHECKING:
    from app.models.analytics_event import AnalyticsEvent
    from app.models.couple_session import CoupleSession
    from app.models.face_cluster import FaceCluster
    from app.models.face_embedding import FaceEmbedding
    from app.models.folder import Folder
    from app.models.guest_session import GuestSession
    from app.models.photo import Photo
    from app.models.photographer import Photographer


class Event(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Wedding or other photo event owned by a photographer."""

    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_photographer", "photographer_id"),
        Index("idx_events_slug", "slug"),
        Index("idx_events_status", "status"),
        Index(
            "idx_events_archive_at",
            "archive_at",
            postgresql_where=text("status != 'archived'"),
        ),
    )

    photographer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photographers.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    event_type: Mapped[EventType] = mapped_column(
        pg_enum(EventType, "event_type"),
        server_default=EventType.WEDDING.value,
        nullable=False,
    )
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"),
        server_default=EventStatus.DRAFT.value,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    cover_photo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    download_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    master_link_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    guest_link_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    total_photos: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    total_faces: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    processed_photos: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    archive_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    photographer: Mapped[Photographer] = relationship(
        "Photographer",
        back_populates="events",
        lazy="selectin",
    )
    folders: Mapped[list[Folder]] = relationship("Folder", back_populates="event", lazy="selectin")
    photos: Mapped[list[Photo]] = relationship("Photo", back_populates="event", lazy="selectin")
    face_clusters: Mapped[list[FaceCluster]] = relationship(
        "FaceCluster",
        back_populates="event",
        lazy="selectin",
    )
    face_embeddings: Mapped[list[FaceEmbedding]] = relationship(
        "FaceEmbedding",
        back_populates="event",
        lazy="selectin",
    )
    guest_sessions: Mapped[list[GuestSession]] = relationship(
        "GuestSession",
        back_populates="event",
        lazy="selectin",
    )
    couple_sessions: Mapped[list[CoupleSession]] = relationship(
        "CoupleSession",
        back_populates="event",
        lazy="selectin",
    )
    analytics_events: Mapped[list[AnalyticsEvent]] = relationship(
        "AnalyticsEvent",
        back_populates="event",
        lazy="selectin",
    )
