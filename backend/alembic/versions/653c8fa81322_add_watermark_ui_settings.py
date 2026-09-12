"""Add watermark ui settings

Revision ID: 653c8fa81322
Revises: add_clustering_persistence
Create Date: 2026-09-11 08:05:35.605212

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "653c8fa81322"
down_revision: str | None = "add_clustering_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table_name: str) -> set[str]:
    """Return existing column names for ``table_name``."""
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Add photographer watermark placement columns if they are missing.

    Local databases may already have these columns from an earlier untracked
    schema change. Skip existing names so ``alembic upgrade head`` can stamp
    this revision and continue to later migrations.
    """
    existing = _column_names("photographers")
    columns = (
        (
            "watermark_scale",
            sa.Column("watermark_scale", sa.Float(), nullable=True, server_default="0.2"),
        ),
        (
            "watermark_x",
            sa.Column("watermark_x", sa.Float(), nullable=True, server_default="0.98"),
        ),
        (
            "watermark_y",
            sa.Column("watermark_y", sa.Float(), nullable=True, server_default="0.98"),
        ),
        (
            "watermark_opacity",
            sa.Column("watermark_opacity", sa.Float(), nullable=True, server_default="0.7"),
        ),
    )
    for name, column in columns:
        if name not in existing:
            op.add_column("photographers", column)


def downgrade() -> None:
    """Remove photographer watermark placement columns when present."""
    existing = _column_names("photographers")
    for name in ("watermark_opacity", "watermark_y", "watermark_x", "watermark_scale"):
        if name in existing:
            op.drop_column("photographers", name)
