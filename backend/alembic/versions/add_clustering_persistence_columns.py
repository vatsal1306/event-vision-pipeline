"""Add cluster persistence columns for PYR, dual-model, and quality.

Revision ID: add_clustering_persistence
Revises: add_secondary_embedding
Create Date: 2026-09-11 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "add_clustering_persistence"
down_revision: str | None = "add_secondary_embedding"
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
    """Add clustering persistence columns and an unclustered-face lookup index.

    Column adds are skipped when they already exist so a local database that
    received these columns from a deleted Alembic revision can still reach head.
    """
    cluster_columns = _column_names("face_clusters")
    if "pyr_centroid" not in cluster_columns:
        op.add_column(
            "face_clusters",
            sa.Column("pyr_centroid", Vector(512), nullable=True),
        )
    if "secondary_centroid" not in cluster_columns:
        op.add_column(
            "face_clusters",
            sa.Column("secondary_centroid", Vector(512), nullable=True),
        )
    if "pyr_size" not in cluster_columns:
        op.add_column(
            "face_clusters",
            sa.Column(
                "pyr_size",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )

    embedding_columns = _column_names("face_embeddings")
    if "yaw" not in embedding_columns:
        op.add_column("face_embeddings", sa.Column("yaw", sa.Float(), nullable=True))
    if "pitch" not in embedding_columns:
        op.add_column("face_embeddings", sa.Column("pitch", sa.Float(), nullable=True))
    if "roll" not in embedding_columns:
        op.add_column("face_embeddings", sa.Column("roll", sa.Float(), nullable=True))
    if "quality_passed" not in embedding_columns:
        op.add_column(
            "face_embeddings",
            sa.Column(
                "quality_passed",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )

    if "idx_face_embeddings_event_unclustered" not in _index_names("face_embeddings"):
        op.create_index(
            "idx_face_embeddings_event_unclustered",
            "face_embeddings",
            ["event_id"],
            postgresql_where=sa.text("cluster_id IS NULL AND quality_passed IS TRUE"),
        )


def downgrade() -> None:
    """Drop clustering persistence columns and the unclustered-face index."""
    if "idx_face_embeddings_event_unclustered" in _index_names("face_embeddings"):
        op.drop_index("idx_face_embeddings_event_unclustered", table_name="face_embeddings")

    embedding_columns = _column_names("face_embeddings")
    for column_name in ("quality_passed", "roll", "pitch", "yaw"):
        if column_name in embedding_columns:
            op.drop_column("face_embeddings", column_name)

    cluster_columns = _column_names("face_clusters")
    for column_name in ("pyr_size", "secondary_centroid", "pyr_centroid"):
        if column_name in cluster_columns:
            op.drop_column("face_clusters", column_name)
