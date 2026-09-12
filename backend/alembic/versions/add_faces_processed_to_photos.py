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


def _column_names(table_name: str) -> set[str]:
    """Return existing column names for ``table_name``."""
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    """Return existing index names for ``table_name``."""
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    """Track whether ML face extraction has already run for a photo."""
    existing = _column_names("photos")
    if "faces_processed" not in existing:
        op.add_column(
            "photos",
            sa.Column(
                "faces_processed",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )
    indexes = _index_names("photos")
    if "idx_photos_event_faces_pending" not in indexes:
        op.create_index(
            "idx_photos_event_faces_pending",
            "photos",
            ["event_id"],
            unique=False,
            postgresql_where=sa.text("faces_processed IS FALSE"),
        )


def downgrade() -> None:
    """Remove the faces_processed column and pending index when present."""
    indexes = _index_names("photos")
    if "idx_photos_event_faces_pending" in indexes:
        op.drop_index("idx_photos_event_faces_pending", table_name="photos")
    existing = _column_names("photos")
    if "faces_processed" in existing:
        op.drop_column("photos", "faces_processed")
