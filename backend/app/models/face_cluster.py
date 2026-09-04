"""Face cluster model for grouped face identities."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.face_embedding import FaceEmbedding

EMBEDDING_DIMENSIONS = 512


class FaceCluster(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Cluster of similar face embeddings within an event."""

    __tablename__ = "face_clusters"
    __table_args__ = (Index("idx_face_clusters_event", "event_id"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    centroid: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    cluster_size: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    event: Mapped[Event] = relationship(
        "Event",
        back_populates="face_clusters",
        lazy="selectin",
    )
    face_embeddings: Mapped[list[FaceEmbedding]] = relationship(
        "FaceEmbedding",
        back_populates="cluster",
        lazy="selectin",
    )
