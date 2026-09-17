"""Add thumb and preview derivative keys to photos

Gallery clients fetch WebP renditions straight from S3, so each photo needs a
grid-sized and a lightbox-sized object alongside the existing 2048px proxy.
All columns are nullable or defaulted, so code running before this migration
keeps working and code running after it falls back to ``proxy_s3_key`` for
photos that have not been backfilled yet.

Revision ID: add_photo_derivative_keys
Revises: 7577bc03e82a
Create Date: 2026-09-17 07:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_photo_derivative_keys"
down_revision: str | None = "7577bc03e82a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable derivative key columns and their size accumulator."""
    op.add_column("photos", sa.Column("thumb_s3_key", sa.String(length=500), nullable=True))
    op.add_column("photos", sa.Column("preview_s3_key", sa.String(length=500), nullable=True))
    op.add_column(
        "photos",
        sa.Column(
            "derivative_file_size_bytes",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    # Lets the backfill task page through unprocessed photos without a seq scan.
    op.create_index(
        "idx_photos_event_thumb_pending",
        "photos",
        ["event_id"],
        unique=False,
        postgresql_where=sa.text("thumb_s3_key IS NULL"),
    )


def downgrade() -> None:
    """Drop the derivative columns and index."""
    op.drop_index(
        "idx_photos_event_thumb_pending",
        table_name="photos",
        postgresql_where=sa.text("thumb_s3_key IS NULL"),
    )
    op.drop_column("photos", "derivative_file_size_bytes")
    op.drop_column("photos", "preview_s3_key")
    op.drop_column("photos", "thumb_s3_key")
