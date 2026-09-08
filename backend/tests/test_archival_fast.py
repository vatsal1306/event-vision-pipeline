"""Fast unit tests for archival services and tasks with mocked dependencies (no DB required)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.models.enums import EventStatus, ProcessingStatus
from app.services.archival_service import ArchivalService
from app.services.notification_service import NotificationService
from app.tasks.archival_tasks import (
    archive_event_task,
    check_events_for_archival,
    send_archival_warnings,
)
from app.tasks.notification_tasks import (
    notify_archival_complete_task,
    notify_archival_warning_task,
    notify_processing_complete_task,
)


@pytest.mark.asyncio
async def test_archival_service_archive_event_unit() -> None:
    """Test ArchivalService.archive_event with mocked session."""
    mock_session = AsyncMock()
    mock_storage = AsyncMock()

    event_id = uuid.uuid4()
    mock_event = MagicMock()
    mock_event.id = event_id
    mock_event.status = EventStatus.READY

    mock_photo = MagicMock()
    mock_photo.original_s3_key = "orig.jpg"
    mock_photo.proxy_s3_key = "proxy.webp"
    mock_photo.blurhash = "blur"
    mock_photo.processing_status = ProcessingStatus.COMPLETED

    mock_session.get.return_value = mock_event

    mock_photos_result = MagicMock()
    mock_photos_result.scalars.return_value.all.return_value = [mock_photo]
    mock_session.execute.return_value = mock_photos_result

    with (
        patch("app.services.archival_service.get_storage_service", return_value=mock_storage),
        patch("app.tasks.notification_tasks.notify_archival_complete_task.delay") as mock_notify,
    ):
        service = ArchivalService(mock_session)
        await service.archive_event(event_id)

        assert mock_event.status == EventStatus.ARCHIVED
        assert mock_photo.proxy_s3_key is None
        assert mock_photo.blurhash is None
        assert mock_photo.processing_status == ProcessingStatus.PENDING
        mock_storage.change_storage_class.assert_awaited_once()
        mock_storage.delete_objects.assert_awaited_once()
        mock_notify.assert_called_once_with(str(event_id))


@pytest.mark.asyncio
async def test_archival_service_event_not_found() -> None:
    """Test ArchivalService raises NotFoundError if event does not exist."""
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    service = ArchivalService(mock_session)
    with pytest.raises(NotFoundError):
        await service.archive_event(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.restore_event(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await service.delete_event_permanently(uuid.uuid4())


@pytest.mark.asyncio
async def test_archival_service_restore_event_unit() -> None:
    """Test ArchivalService.restore_event with mocked session."""
    mock_session = AsyncMock()
    mock_storage = AsyncMock()

    event_id = uuid.uuid4()
    mock_event = MagicMock()
    mock_event.id = event_id
    mock_event.status = EventStatus.ARCHIVED

    mock_photo = MagicMock()
    mock_photo.id = uuid.uuid4()
    mock_photo.original_s3_key = "orig.jpg"
    mock_photo.processing_status = ProcessingStatus.PENDING

    mock_session.get.return_value = mock_event

    mock_photos_result = MagicMock()
    mock_photos_result.scalars.return_value.all.return_value = [mock_photo]
    mock_session.execute.return_value = mock_photos_result

    with (
        patch("app.services.archival_service.get_storage_service", return_value=mock_storage),
        patch("app.tasks.photo_tasks.process_uploaded_photo.delay") as mock_process,
    ):
        service = ArchivalService(mock_session)
        await service.restore_event(event_id)

        assert mock_event.status == EventStatus.PROCESSING
        mock_storage.change_storage_class.assert_awaited_once()
        mock_process.assert_called_once_with(
            str(mock_photo.id), mock_photo.original_s3_key, str(event_id)
        )


@pytest.mark.asyncio
async def test_archival_service_delete_permanently_unit() -> None:
    """Test ArchivalService.delete_event_permanently with mocked session."""
    mock_session = AsyncMock()
    mock_storage = AsyncMock()

    event_id = uuid.uuid4()
    photographer_id = uuid.uuid4()
    mock_event = MagicMock()
    mock_event.id = event_id
    mock_event.photographer_id = photographer_id

    mock_photographer = MagicMock()
    mock_photographer.storage_used_bytes = 2000

    def mock_get(model, pk):
        if pk == event_id:
            return mock_event
        if pk == photographer_id:
            return mock_photographer
        return None

    mock_session.get.side_effect = mock_get

    mock_photo = MagicMock()
    mock_photo.original_s3_key = "orig.jpg"
    mock_photo.proxy_s3_key = "proxy.webp"
    mock_photo.file_size_bytes = 500

    mock_photos_result = MagicMock()
    mock_photos_result.scalars.return_value.all.return_value = [mock_photo]
    mock_session.execute.return_value = mock_photos_result

    with patch("app.services.archival_service.get_storage_service", return_value=mock_storage):
        service = ArchivalService(mock_session)
        await service.delete_event_permanently(event_id)

        mock_session.delete.assert_awaited_once_with(mock_event)
        assert mock_storage.delete_objects.call_count == 2


def test_archive_event_task_execution() -> None:
    """Test archive_event_task celery task execution."""
    mock_db = AsyncMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = None

    mock_service = AsyncMock()
    with (
        patch("app.tasks.archival_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.archival_tasks.ArchivalService", return_value=mock_service),
    ):
        eid = str(uuid.uuid4())
        archive_event_task(eid)
        mock_service.archive_event.assert_awaited_once_with(uuid.UUID(eid))


@pytest.mark.asyncio
async def test_notification_service_send_archival_warning_and_complete() -> None:
    """Test NotificationService archival warning and complete emails."""
    mock_db = AsyncMock()
    mock_email = AsyncMock()

    mock_event = MagicMock()
    mock_event.name = "Test Event"
    mock_event.archive_at = datetime.now(timezone.utc) + timedelta(days=7)
    mock_event.photographer.email = "photographer@example.com"
    mock_event.photographer.studio_name = "Studio Alpha"
    mock_db.get.return_value = mock_event

    service = NotificationService(mock_db, mock_email)

    event_id = uuid.uuid4()
    await service.send_archival_warning(event_id)
    assert mock_email.send.call_count == 1

    await service.send_archival_complete(event_id)
    assert mock_email.send.call_count == 2


def test_archival_tasks_execution() -> None:
    """Test Celery archival tasks dispatch and execute with mocked sessions."""
    mock_db = AsyncMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = None

    now = datetime.now(timezone.utc)
    mock_event1 = MagicMock()
    mock_event1.id = uuid.uuid4()
    mock_event1.archive_at = now - timedelta(days=1)
    mock_event1.status = EventStatus.READY

    mock_exec_result = MagicMock()
    mock_exec_result.scalars.return_value.all.return_value = [mock_event1]
    mock_db.execute.return_value = mock_exec_result

    with (
        patch("app.tasks.archival_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.archival_tasks.archive_event_task.delay") as mock_delay,
    ):
        check_events_for_archival()
        mock_delay.assert_called_once_with(str(mock_event1.id))

    mock_event2 = MagicMock()
    mock_event2.id = uuid.uuid4()
    mock_event2.archive_at = now + timedelta(days=7, hours=2)
    mock_event2.status = EventStatus.READY

    mock_exec_result.scalars.return_value.all.return_value = [mock_event2]
    with (
        patch("app.tasks.archival_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.notification_tasks.notify_archival_warning_task.delay") as mock_warn_delay,
    ):
        send_archival_warnings()
        mock_warn_delay.assert_called_once_with(str(mock_event2.id))


def test_celery_notification_tasks_runs() -> None:
    """Test that celery notification tasks run underlying service methods."""
    mock_db = AsyncMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = None

    mock_service = AsyncMock()
    with (
        patch("app.tasks.notification_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.notification_tasks.get_notification_service", return_value=mock_service),
    ):
        uid = str(uuid.uuid4())
        notify_processing_complete_task(uid)
        mock_service.send_processing_complete.assert_awaited_once_with(uuid.UUID(uid))

        notify_archival_warning_task(uid)
        mock_service.send_archival_warning.assert_awaited_once_with(uuid.UUID(uid))

        notify_archival_complete_task(uid)
        mock_service.send_archival_complete.assert_awaited_once_with(uuid.UUID(uid))
