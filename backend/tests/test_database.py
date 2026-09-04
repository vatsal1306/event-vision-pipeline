"""Database integration tests for BE-003."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Photographer
from app.models.enums import EventStatus, EventType
from app.models.event import Event
from app.models.folder import Folder


@pytest.mark.asyncio
async def test_get_db_session_executes_query(db_session: AsyncSession) -> None:
    """An injected session should execute SQL against migrated schema."""
    result = await db_session.scalar(text("SELECT 1"))
    assert result == 1


@pytest.mark.asyncio
async def test_vector_extension_installed(db_session: AsyncSession) -> None:
    """The pgvector extension should be enabled by the initial migration."""
    result = await db_session.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
    assert result == 1


@pytest.mark.asyncio
async def test_core_tables_exist(db_session: AsyncSession) -> None:
    """All core application tables should exist after migration."""
    expected_tables = {
        "photographers",
        "events",
        "folders",
        "photos",
        "face_clusters",
        "face_embeddings",
        "guest_sessions",
        "couple_sessions",
        "favorites",
        "analytics_events",
    }
    rows = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
    )
    actual_tables = {row[0] for row in rows}
    assert expected_tables.issubset(actual_tables)


@pytest.mark.asyncio
async def test_hnsw_index_exists(db_session: AsyncSession) -> None:
    """Face embedding vectors should have the HNSW index from the spec."""
    result = await db_session.scalar(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname = 'idx_face_embeddings_vector'"
        )
    )
    assert result == 1


@pytest.mark.asyncio
async def test_photographer_insert_and_read(db_session: AsyncSession) -> None:
    """ORM models should persist rows through the async session."""
    photographer = Photographer(
        email="studio@example.com",
        password_hash="hashed",
        studio_name="Studio One",
        phone="+919999999999",
    )
    db_session.add(photographer)
    await db_session.flush()

    loaded = await db_session.get(Photographer, photographer.id)
    assert loaded is not None
    assert loaded.email == "studio@example.com"
    assert loaded.storage_limit_bytes == 214_748_364_800


@pytest.mark.asyncio
async def test_folder_root_name_partial_unique_index(db_session: AsyncSession) -> None:
    """Root folders should enforce unique names per event despite NULL parent_id."""
    photographer = Photographer(
        email=f"folder-{uuid.uuid4()}@example.com",
        password_hash="hashed",
        studio_name="Folder Studio",
        phone="+919999999998",
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="Wedding",
        slug=f"wedding-{uuid.uuid4()}",
        event_type=EventType.WEDDING,
        status=EventStatus.DRAFT,
    )
    db_session.add(event)
    await db_session.flush()

    db_session.add_all(
        [
            Folder(event_id=event.id, parent_id=None, name="Highlights"),
            Folder(event_id=event.id, parent_id=None, name="Ceremony"),
        ]
    )
    await db_session.flush()

    duplicate = Folder(event_id=event.id, parent_id=None, name="Highlights")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.flush()
