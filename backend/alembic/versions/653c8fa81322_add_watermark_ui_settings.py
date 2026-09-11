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


def upgrade() -> None:
    """Add photographer watermark placement columns."""
    op.add_column(
        "photographers",
        sa.Column("watermark_scale", sa.Float(), nullable=True, server_default="0.2"),
    )
    op.add_column(
        "photographers",
        sa.Column("watermark_x", sa.Float(), nullable=True, server_default="0.98"),
    )
    op.add_column(
        "photographers",
        sa.Column("watermark_y", sa.Float(), nullable=True, server_default="0.98"),
    )
    op.add_column(
        "photographers",
        sa.Column("watermark_opacity", sa.Float(), nullable=True, server_default="0.7"),
    )


def downgrade() -> None:
    """Remove photographer watermark placement columns."""
    op.drop_column("photographers", "watermark_opacity")
    op.drop_column("photographers", "watermark_y")
    op.drop_column("photographers", "watermark_x")
    op.drop_column("photographers", "watermark_scale")
