"""Photographer account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Float, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.event import Event

STORAGE_LIMIT_BYTES_DEFAULT = 214_748_364_800  # 200 GB


class Photographer(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Professional photographer or studio account."""

    __tablename__ = "photographers"
    __table_args__ = (Index("idx_photographers_email", "email"),)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    studio_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    logo_url: Mapped[str | None] = mapped_column(String(500))
    watermark_url: Mapped[str | None] = mapped_column(String(500))

    # Watermark UI settings
    watermark_scale: Mapped[float] = mapped_column(Float, default=0.20, server_default="0.20")
    watermark_x: Mapped[float] = mapped_column(Float, default=0.98, server_default="0.98")
    watermark_y: Mapped[float] = mapped_column(Float, default=0.98, server_default="0.98")
    watermark_opacity: Mapped[float] = mapped_column(Float, default=0.70, server_default="0.70")

    storage_used_bytes: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("0"),
        nullable=False,
    )
    storage_limit_bytes: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text(str(STORAGE_LIMIT_BYTES_DEFAULT)),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )

    events: Mapped[list[Event]] = relationship(
        "Event",
        back_populates="photographer",
        lazy="selectin",
    )
