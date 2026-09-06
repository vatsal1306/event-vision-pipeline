"""Favorite photo model for couple sessions."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.couple_session import CoupleSession
    from app.models.photo import Photo


class Favorite(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Couple favorite on a photo."""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint(
            "couple_session_id",
            "photo_id",
            name="uq_favorites_couple_session_photo",
        ),
        Index("idx_favorites_couple", "couple_session_id"),
    )

    couple_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couple_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
    )

    couple_session: Mapped[CoupleSession] = relationship(
        "CoupleSession",
        back_populates="favorites",
        lazy="selectin",
    )
    photo: Mapped[Photo] = relationship("Photo", back_populates="favorites", lazy="selectin")
