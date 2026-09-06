"""Folder model for nested event photo organization."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.photo import Photo


class Folder(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Nested folder within an event."""

    __tablename__ = "folders"
    __table_args__ = (
        Index("idx_folders_event", "event_id"),
        Index("idx_folders_parent", "parent_id"),
        Index(
            "uq_folders_event_root_name",
            "event_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_folders_event_parent_name",
            "event_id",
            "parent_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    event: Mapped[Event] = relationship("Event", back_populates="folders", lazy="selectin")
    parent: Mapped[Folder | None] = relationship(
        "Folder",
        remote_side="Folder.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list[Folder]] = relationship(
        "Folder",
        back_populates="parent",
        lazy="selectin",
    )
    photos: Mapped[list[Photo]] = relationship("Photo", back_populates="folder", lazy="selectin")
