"""Add shared_with_guests column to photos.

Revision ID: add_shared_with_guests
Revises: add_photographers_email_verified
Create Date: 2026-09-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_shared_with_guests"
down_revision: str | None = "add_photographers_email_verified"
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
    """Add shared_with_guests boolean and a partial index for efficient lookups."""
    columns = _column_names("photos")
    if "shared_with_guests" not in columns:
        op.add_column(
            "photos",
            sa.Column(
                "shared_with_guests",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )

    if "idx_photos_event_shared" not in _index_names("photos"):
        op.create_index(
            "idx_photos_event_shared",
            "photos",
            ["event_id"],
            postgresql_where=sa.text("shared_with_guests IS TRUE"),
        )


def downgrade() -> None:
    """Remove shared_with_guests column and index."""
    if "idx_photos_event_shared" in _index_names("photos"):
        op.drop_index("idx_photos_event_shared", table_name="photos")

    columns = _column_names("photos")
    if "shared_with_guests" in columns:
        op.drop_column("photos", "shared_with_guests")
