"""Add secondary_embedding column to face_embeddings

Revision ID: add_secondary_embedding
Revises: 348cce618932
Create Date: 2026-09-09 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_secondary_embedding"
down_revision: str | None = "348cce618932"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "face_embeddings",
        sa.Column("secondary_embedding", Vector(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("face_embeddings", "secondary_embedding")
