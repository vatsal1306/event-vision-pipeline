"""Add unique constraint on photographers.phone."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "add_unique_photographers_phone"
down_revision: str | None = "enable_pgvector_and_core_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Ensure each phone number maps to at most one photographer account."""
    op.create_unique_constraint("uq_photographers_phone", "photographers", ["phone"])


def downgrade() -> None:
    """Drop the unique phone constraint."""
    op.drop_constraint("uq_photographers_phone", "photographers", type_="unique")
