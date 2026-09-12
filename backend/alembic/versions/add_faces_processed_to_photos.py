"""Add faces_processed flag on photos.

Revision ID: add_faces_processed
Revises: 653c8fa81322
Create Date: 2026-09-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_faces_processed"
down_revision: str | None = "653c8fa81322"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track whether ML face extraction has already run for a photo."""
    op.add_column(
        "photos",
        sa.Column(
            "faces_processed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_photos_event_faces_pending",
        "photos",
        ["event_id"],
        unique=False,
        postgresql_where=sa.text("faces_processed IS FALSE"),
    )


def downgrade() -> None:
    """Remove the faces_processed column and pending index."""
    op.drop_index("idx_photos_event_faces_pending", table_name="photos")
    op.drop_column("photos", "faces_processed")
