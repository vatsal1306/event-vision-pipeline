"""Photo model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import ProcessingStatus, pg_enum

if TYPE_CHECKING:
    from app.models.analytics_event import AnalyticsEvent
    from app.models.event import Event
    from app.models.face_embedding import FaceEmbedding
    from app.models.favorite import Favorite
    from app.models.folder import Folder


class Photo(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Uploaded photo belonging to an event."""

    __tablename__ = "photos"
    __table_args__ = (
        Index("idx_photos_event", "event_id"),
        Index("idx_photos_folder", "folder_id"),
        Index("idx_photos_event_folder", "event_id", "folder_id"),
        Index(
            "idx_photos_processing",
            "processing_status",
            postgresql_where=text("processing_status != 'completed'"),
        ),
        Index(
            "idx_photos_event_faces_pending",
            "event_id",
            postgresql_where=text("faces_processed IS FALSE"),
        ),
        Index(
            "idx_photos_event_thumb_pending",
            "event_id",
            postgresql_where=text("thumb_s3_key IS NULL"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
    )
    tus_upload_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    proxy_s3_key: Mapped[str | None] = mapped_column(String(500))
    # Gallery grid rendition (~480px). Null until the derivative ladder runs,
    # in which case callers fall back to the larger renditions.
    thumb_s3_key: Mapped[str | None] = mapped_column(String(500))
    # Smaller grid rendition (~240px) for narrow/mobile tiles, picked via srcset.
    micro_thumb_s3_key: Mapped[str | None] = mapped_column(String(500))
    # Legacy lightbox rendition (~1280px). No longer generated for new photos —
    # the viewer now uses `proxy_s3_key` directly — but kept so photos processed
    # before the merge keep resolving through the fallback chain.
    preview_s3_key: Mapped[str | None] = mapped_column(String(500))
    blurhash: Mapped[str | None] = mapped_column(String(50))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proxy_file_size_bytes: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    derivative_file_size_bytes: Mapped[int] = mapped_column(
        BigInteger, server_default=text("0"), nullable=False
    )
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    face_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    faces_processed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus, "processing_status"),
        server_default=ProcessingStatus.PENDING.value,
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    shared_with_guests: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    @property
    def proxy_bucket_keys(self) -> list[str]:
        """Return every object this photo owns in the proxies bucket.

        Used when archiving or deleting so no rendition is orphaned in S3.
        """
        keys = (
            self.proxy_s3_key,
            self.thumb_s3_key,
            self.micro_thumb_s3_key,
            self.preview_s3_key,
        )
        return [key for key in keys if key]

    @classmethod
    def stored_bytes_expression(cls) -> ColumnElement[int]:
        """Return the SQL sum of every object stored on behalf of a photo.

        Photographer quota accounting must cover the original, the 2048px
        proxy, and the smaller gallery renditions. Centralised here so the
        several call sites cannot drift apart as renditions are added.
        """
        return cls.file_size_bytes + cls.proxy_file_size_bytes + cls.derivative_file_size_bytes

    event: Mapped[Event] = relationship("Event", back_populates="photos", lazy="selectin")
    folder: Mapped[Folder | None] = relationship("Folder", back_populates="photos", lazy="selectin")
    face_embeddings: Mapped[list[FaceEmbedding]] = relationship(
        "FaceEmbedding",
        back_populates="photo",
        lazy="selectin",
    )
    favorites: Mapped[list[Favorite]] = relationship(
        "Favorite",
        back_populates="photo",
        lazy="selectin",
    )
    analytics_events: Mapped[list[AnalyticsEvent]] = relationship(
        "AnalyticsEvent",
        back_populates="photo",
        lazy="selectin",
    )
