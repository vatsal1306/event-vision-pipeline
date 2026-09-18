"""Add micro_thumb derivative key to photos

A smaller grid tier (~240px) alongside the existing ~480px thumb, so narrow
mobile grid tiles can be served a smaller image via srcset instead of always
downloading the 480px thumb. Nullable: photos processed before this migration
fall back to `thumb_s3_key` (see `GalleryUrlBuilder.resolve_storage_key`).

Revision ID: add_photo_micro_thumb_key
Revises: add_photo_derivative_keys
Create Date: 2026-09-18 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_photo_micro_thumb_key"
down_revision: str | None = "add_photo_derivative_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable micro-thumb key column."""
    op.add_column("photos", sa.Column("micro_thumb_s3_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Drop the micro-thumb key column."""
    op.drop_column("photos", "micro_thumb_s3_key")
