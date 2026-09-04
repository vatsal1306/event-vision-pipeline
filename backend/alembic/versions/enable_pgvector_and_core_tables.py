"""Enable pgvector extension and create core application tables."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "enable_pgvector_and_core_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENT_STATUS = postgresql.ENUM(
    "draft",
    "uploading",
    "processing",
    "ready",
    "archived",
    name="event_status",
    create_type=False,
)
EVENT_TYPE = postgresql.ENUM(
    "wedding",
    "corporate",
    "birthday",
    "other",
    name="event_type",
    create_type=False,
)
PROCESSING_STATUS = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="processing_status",
    create_type=False,
)
ANALYTICS_ACTION = postgresql.ENUM(
    "view",
    "download",
    name="analytics_action",
    create_type=False,
)


def upgrade() -> None:
    """Create pgvector extension, enums, tables, and indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        "CREATE TYPE event_status AS ENUM "
        "('draft', 'uploading', 'processing', 'ready', 'archived')"
    )
    op.execute(
        "CREATE TYPE event_type AS ENUM ('wedding', 'corporate', 'birthday', 'other')"
    )
    op.execute(
        "CREATE TYPE processing_status AS ENUM "
        "('pending', 'processing', 'completed', 'failed')"
    )
    op.execute("CREATE TYPE analytics_action AS ENUM ('view', 'download')")

    op.create_table(
        "photographers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("studio_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("watermark_url", sa.String(length=500), nullable=True),
        sa.Column("storage_used_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "storage_limit_bytes",
            sa.BigInteger(),
            server_default=sa.text("214748364800"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_photographers_email"),
    )
    op.create_index("idx_photographers_email", "photographers", ["email"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("photographer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=True),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column(
            "event_type",
            EVENT_TYPE,
            server_default=sa.text("'wedding'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            EVENT_STATUS,
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_photo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("download_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("master_link_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("guest_link_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("total_photos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_faces", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_photos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("archive_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["photographer_id"], ["photographers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_events_slug"),
    )
    op.create_index("idx_events_photographer", "events", ["photographer_id"])
    op.create_index("idx_events_slug", "events", ["slug"])
    op.create_index("idx_events_status", "events", ["status"])
    op.create_index(
        "idx_events_archive_at",
        "events",
        ["archive_at"],
        postgresql_where=sa.text("status != 'archived'"),
    )

    op.create_table(
        "folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["folders.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_folders_event", "folders", ["event_id"])
    op.create_index("idx_folders_parent", "folders", ["parent_id"])
    op.create_index(
        "uq_folders_event_root_name",
        "folders",
        ["event_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(
        "uq_folders_event_parent_name",
        "folders",
        ["event_id", "parent_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )

    op.create_table(
        "photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("original_s3_key", sa.String(length=500), nullable=False),
        sa.Column("proxy_s3_key", sa.String(length=500), nullable=True),
        sa.Column("blurhash", sa.String(length=50), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("face_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "processing_status",
            PROCESSING_STATUS,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_photos_event", "photos", ["event_id"])
    op.create_index("idx_photos_folder", "photos", ["folder_id"])
    op.create_index("idx_photos_event_folder", "photos", ["event_id", "folder_id"])
    op.create_index(
        "idx_photos_processing",
        "photos",
        ["processing_status"],
        postgresql_where=sa.text("processing_status != 'completed'"),
    )

    op.create_table(
        "face_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("centroid", Vector(512), nullable=False),
        sa.Column("cluster_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_face_clusters_event", "face_clusters", ["event_id"])

    op.create_table(
        "face_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_w", sa.Float(), nullable=False),
        sa.Column("bbox_h", sa.Float(), nullable=False),
        sa.Column("detection_score", sa.Float(), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["face_clusters.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_face_embeddings_photo", "face_embeddings", ["photo_id"])
    op.create_index("idx_face_embeddings_event", "face_embeddings", ["event_id"])
    op.create_index("idx_face_embeddings_cluster", "face_embeddings", ["cluster_id"])
    op.execute(
        "CREATE INDEX idx_face_embeddings_vector ON face_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("selfie_s3_key", sa.String(length=500), nullable=True),
        sa.Column("selfie_embedding", Vector(512), nullable=True),
        sa.Column(
            "matched_cluster_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'::uuid[]"),
            nullable=False,
        ),
        sa.Column("matched_photo_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", "phone", name="uq_guest_sessions_event_phone"),
    )
    op.create_index("idx_guest_sessions_event", "guest_sessions", ["event_id"])
    op.create_index("idx_guest_sessions_phone", "guest_sessions", ["event_id", "phone"])

    op.create_table(
        "couple_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id", "phone", name="uq_couple_sessions_event_phone"),
    )
    op.create_index("idx_couple_sessions_event", "couple_sessions", ["event_id"])

    op.create_table(
        "favorites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("couple_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["couple_session_id"], ["couple_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "couple_session_id",
            "photo_id",
            name="uq_favorites_couple_session_photo",
        ),
    )
    op.create_index("idx_favorites_couple", "favorites", ["couple_session_id"])

    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("guest_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("couple_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", ANALYTICS_ACTION, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guest_session_id"], ["guest_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["couple_session_id"], ["couple_sessions.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_analytics_event", "analytics_events", ["event_id"])
    op.create_index("idx_analytics_photo", "analytics_events", ["photo_id"])
    op.create_index("idx_analytics_action", "analytics_events", ["event_id", "action"])
    op.create_index(
        "idx_analytics_downloads",
        "analytics_events",
        ["event_id", "photo_id"],
        postgresql_where=sa.text("action = 'download'"),
    )


def downgrade() -> None:
    """Drop core tables, enums, and pgvector extension."""
    op.drop_index("idx_analytics_downloads", table_name="analytics_events")
    op.drop_index("idx_analytics_action", table_name="analytics_events")
    op.drop_index("idx_analytics_photo", table_name="analytics_events")
    op.drop_index("idx_analytics_event", table_name="analytics_events")
    op.drop_table("analytics_events")

    op.drop_index("idx_favorites_couple", table_name="favorites")
    op.drop_table("favorites")

    op.drop_index("idx_couple_sessions_event", table_name="couple_sessions")
    op.drop_table("couple_sessions")

    op.drop_index("idx_guest_sessions_phone", table_name="guest_sessions")
    op.drop_index("idx_guest_sessions_event", table_name="guest_sessions")
    op.drop_table("guest_sessions")

    op.execute("DROP INDEX IF EXISTS idx_face_embeddings_vector")
    op.drop_index("idx_face_embeddings_cluster", table_name="face_embeddings")
    op.drop_index("idx_face_embeddings_event", table_name="face_embeddings")
    op.drop_index("idx_face_embeddings_photo", table_name="face_embeddings")
    op.drop_table("face_embeddings")

    op.drop_index("idx_face_clusters_event", table_name="face_clusters")
    op.drop_table("face_clusters")

    op.drop_index("idx_photos_processing", table_name="photos")
    op.drop_index("idx_photos_event_folder", table_name="photos")
    op.drop_index("idx_photos_folder", table_name="photos")
    op.drop_index("idx_photos_event", table_name="photos")
    op.drop_table("photos")

    op.drop_index("uq_folders_event_parent_name", table_name="folders")
    op.drop_index("uq_folders_event_root_name", table_name="folders")
    op.drop_index("idx_folders_parent", table_name="folders")
    op.drop_index("idx_folders_event", table_name="folders")
    op.drop_table("folders")

    op.drop_index("idx_events_archive_at", table_name="events")
    op.drop_index("idx_events_status", table_name="events")
    op.drop_index("idx_events_slug", table_name="events")
    op.drop_index("idx_events_photographer", table_name="events")
    op.drop_table("events")

    op.drop_index("idx_photographers_email", table_name="photographers")
    op.drop_table("photographers")

    op.execute("DROP TYPE IF EXISTS analytics_action")
    op.execute("DROP TYPE IF EXISTS processing_status")
    op.execute("DROP TYPE IF EXISTS event_type")
    op.execute("DROP TYPE IF EXISTS event_status")

    op.execute("DROP EXTENSION IF EXISTS vector")
