"""Tests for event archival and retention."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.archival_service import ArchivalService


async def create_photographer(db_session: AsyncSession, storage_used=0) -> Photographer:
    p = Photographer(
        email=f"test_{uuid.uuid4().hex}@example.com",
        password_hash="hash",
        studio_name="Test Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
        storage_used_bytes=storage_used,
    )
    db_session.add(p)
    await db_session.flush()
    return p


async def create_event(
    db_session: AsyncSession, p_id: uuid.UUID, status=EventStatus.READY, slug=None, archive_at=None
) -> Event:
    e = Event(
        photographer_id=p_id,
        name="Test Event",
        slug=slug or f"test-event-{uuid.uuid4().hex[:8]}",
        date_start=datetime.now(timezone.utc).date(),
        status=status,
        archive_at=archive_at,
    )
    db_session.add(e)
    await db_session.flush()
    return e


@pytest.mark.asyncio
async def test_archive_event(db_session: AsyncSession):
    p = await create_photographer(db_session)
    e = await create_event(db_session, p.id, status=EventStatus.READY)

    photo1 = Photo(
        event_id=e.id,
        filename="test.jpg",
        mime_type="image/jpeg",
        original_s3_key=f"orig_{uuid.uuid4().hex}.jpg",
        proxy_s3_key=f"proxy_{uuid.uuid4().hex}.webp",
        blurhash="blur1",
        processing_status=ProcessingStatus.COMPLETED,
        file_size_bytes=100,
    )
    db_session.add(photo1)
    await db_session.flush()

    cluster = FaceCluster(event_id=e.id, centroid=[0.1] * 512, cluster_size=1)
    db_session.add(cluster)
    await db_session.flush()

    embedding = FaceEmbedding(
        event_id=e.id,
        photo_id=photo1.id,
        cluster_id=cluster.id,
        embedding=[0.1] * 512,
        bbox_x=10.0,
        bbox_y=10.0,
        bbox_w=50.0,
        bbox_h=50.0,
    )
    db_session.add(embedding)

    await db_session.commit()

    with (
        patch("app.services.archival_service.get_storage_service") as mock_storage_getter,
        patch("app.tasks.notification_tasks.notify_archival_complete_task.delay") as mock_notify,
    ):
        mock_storage = AsyncMock()
        mock_storage_getter.return_value = mock_storage

        service = ArchivalService(db_session)
        await service.archive_event(e.id)

        await db_session.refresh(e)
        assert e.status == EventStatus.ARCHIVED

        await db_session.refresh(photo1)
        assert photo1.proxy_s3_key is None
        assert photo1.blurhash is None
        assert photo1.processing_status == ProcessingStatus.PENDING

        embeddings = (
            (await db_session.execute(select(FaceEmbedding).where(FaceEmbedding.event_id == e.id)))
            .scalars()
            .all()
        )
        assert len(embeddings) == 0

        clusters = (
            (await db_session.execute(select(FaceCluster).where(FaceCluster.event_id == e.id)))
            .scalars()
            .all()
        )
        assert len(clusters) == 0

        mock_storage.change_storage_class.assert_awaited_with(
            bucket=service.settings.s3_bucket_originals,
            key=photo1.original_s3_key,
            storage_class="GLACIER_IR",
        )
        assert mock_storage.delete_objects.call_count == 1
        mock_notify.assert_called_once_with(str(e.id))


@pytest.mark.asyncio
async def test_restore_event(db_session: AsyncSession):
    p = await create_photographer(db_session)
    e = await create_event(db_session, p.id, status=EventStatus.ARCHIVED)
    photo1 = Photo(
        event_id=e.id,
        filename="test.jpg",
        mime_type="image/jpeg",
        original_s3_key=f"orig_{uuid.uuid4().hex}.jpg",
        processing_status=ProcessingStatus.PENDING,
        file_size_bytes=100,
    )
    db_session.add(photo1)
    await db_session.commit()

    with (
        patch("app.services.archival_service.get_storage_service") as mock_storage_getter,
        patch("app.tasks.photo_tasks.process_uploaded_photo.delay") as mock_process,
    ):
        mock_storage = AsyncMock()
        mock_storage_getter.return_value = mock_storage

        service = ArchivalService(db_session)
        await service.restore_event(e.id)

        await db_session.refresh(e)
        assert e.status == EventStatus.PROCESSING

        mock_storage.change_storage_class.assert_awaited_with(
            bucket=service.settings.s3_bucket_originals,
            key=photo1.original_s3_key,
            storage_class="STANDARD",
        )
        mock_process.assert_called_once_with(str(photo1.id), photo1.original_s3_key, str(e.id))


@pytest.mark.asyncio
async def test_delete_event_permanently(db_session: AsyncSession):
    p = await create_photographer(db_session, storage_used=1000)
    e = await create_event(db_session, p.id, status=EventStatus.ARCHIVED)
    photo1 = Photo(
        event_id=e.id,
        filename="test.jpg",
        mime_type="image/jpeg",
        original_s3_key=f"orig_{uuid.uuid4().hex}.jpg",
        proxy_s3_key=f"proxy_{uuid.uuid4().hex}.webp",
        file_size_bytes=500,
    )
    db_session.add(photo1)
    await db_session.commit()

    with patch("app.services.archival_service.get_storage_service") as mock_storage_getter:
        mock_storage = AsyncMock()
        mock_storage_getter.return_value = mock_storage

        service = ArchivalService(db_session)
        await service.delete_event_permanently(e.id)

        deleted_event = await db_session.get(Event, e.id)
        assert deleted_event is None

        await db_session.refresh(p)
        assert p.storage_used_bytes == 0

        assert mock_storage.delete_objects.call_count == 2


@pytest.mark.asyncio
async def test_guest_auth_fails_on_archived_event(db_client: AsyncClient, db_session: AsyncSession):
    p = await create_photographer(db_session)
    e = await create_event(db_session, p.id, status=EventStatus.ARCHIVED)
    await db_session.commit()

    response = await db_client.post(
        f"/api/v1/event/{e.slug}/auth",
        json={"name": "Test Guest", "phone": "+919876543210", "link_type": "guest"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "EVENT_ARCHIVED"


@pytest.mark.asyncio
async def test_master_auth_fails_on_archived_event(
    db_client: AsyncClient, db_session: AsyncSession
):
    p = await create_photographer(db_session)
    e = await create_event(db_session, p.id, status=EventStatus.ARCHIVED)
    await db_session.commit()

    response = await db_client.post(
        f"/api/v1/event/{e.slug}/auth",
        json={"name": "Test Master", "phone": "+919876543210", "link_type": "master"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "EVENT_ARCHIVED"


@pytest.mark.asyncio
async def test_restore_event_http(db_client: AsyncClient, db_session: AsyncSession):
    p = await create_photographer(db_session)
    e = await create_event(db_session, p.id, status=EventStatus.ARCHIVED)
    await db_session.commit()

    from app.api.deps import get_photographer_event
    from app.main import app

    async def override_get_event() -> Event:
        return e

    app.dependency_overrides[get_photographer_event] = override_get_event

    with patch("app.tasks.archival_tasks.restore_event_task.delay") as mock_delay:
        response = await db_client.post(f"/api/v1/events/{e.id}/restore")
        assert response.status_code == 202
        mock_delay.assert_called_once_with(str(e.id))

    # Also test that it returns 409 if not archived
    e.status = EventStatus.READY
    await db_session.commit()

    response2 = await db_client.post(f"/api/v1/events/{e.id}/restore")
    assert response2.status_code == 409

    app.dependency_overrides.pop(get_photographer_event, None)


@pytest.mark.asyncio
async def test_check_events_for_archival_db(db_session: AsyncSession):
    from datetime import timedelta

    p = await create_photographer(db_session)
    past_date = datetime.now(timezone.utc) - timedelta(days=1)
    e1 = await create_event(
        db_session, p.id, status=EventStatus.READY, archive_at=past_date, slug="e1"
    )
    await create_event(
        db_session, p.id, status=EventStatus.PROCESSING, archive_at=past_date, slug="e2"
    )
    future_date = datetime.now(timezone.utc) + timedelta(days=1)
    await create_event(
        db_session, p.id, status=EventStatus.READY, archive_at=future_date, slug="e3"
    )
    await db_session.commit()

    import asyncio

    from app.tasks.archival_tasks import check_events_for_archival

    with patch("app.tasks.archival_tasks.archive_event_task.delay") as mock_delay:
        await asyncio.to_thread(check_events_for_archival)

        # Only e1 should be archived because it is READY and past archive_at
        mock_delay.assert_called_once_with(str(e1.id))
