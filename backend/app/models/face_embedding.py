"""Face embedding model with pgvector storage."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.face_cluster import EMBEDDING_DIMENSIONS

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.face_cluster import FaceCluster
    from app.models.photo import Photo


class FaceEmbedding(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Detected face embedding extracted from a photo."""

    __tablename__ = "face_embeddings"
    __table_args__ = (
        Index("idx_face_embeddings_photo", "photo_id"),
        Index("idx_face_embeddings_event", "event_id"),
        Index("idx_face_embeddings_cluster", "cluster_id"),
        Index(
            "idx_face_embeddings_event_unclustered",
            "event_id",
            postgresql_where=text("cluster_id IS NULL AND quality_passed IS TRUE"),
        ),
    )

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("face_clusters.id", ondelete="SET NULL"),
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    secondary_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS),
        nullable=True,
    )
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_w: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_h: Mapped[float] = mapped_column(Float, nullable=False)
    detection_score: Mapped[float | None] = mapped_column(Float)
    blur_score: Mapped[float | None] = mapped_column(Float)
    yaw: Mapped[float | None] = mapped_column(Float)
    pitch: Mapped[float | None] = mapped_column(Float)
    roll: Mapped[float | None] = mapped_column(Float)
    quality_passed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    photo: Mapped[Photo] = relationship("Photo", back_populates="face_embeddings", lazy="selectin")
    event: Mapped[Event] = relationship(
        "Event",
        back_populates="face_embeddings",
        lazy="selectin",
    )
    cluster: Mapped[FaceCluster | None] = relationship(
        "FaceCluster",
        back_populates="face_embeddings",
        lazy="selectin",
    )
