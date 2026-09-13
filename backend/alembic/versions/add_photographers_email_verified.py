"""Add email_verified flag on photographers.

Revision ID: add_photographers_email_verified
Revises: add_faces_processed
Create Date: 2026-09-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_photographers_email_verified"
down_revision: str | None = "add_faces_processed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email_verified with a false default for existing accounts."""
    op.add_column(
        "photographers",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop email_verified."""
    op.drop_column("photographers", "email_verified")
