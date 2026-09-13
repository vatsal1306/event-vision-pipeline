"""Fast tests for notification-related code (no DB required)."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.config import get_settings
from app.services.email_service import EmailService
from app.tasks.notification_tasks import (
    notify_archival_warning_task,
    notify_processing_complete_task,
)


@pytest.mark.asyncio
async def test_email_service_log_adapter() -> None:
    """Test that EmailService falls back to LogEmailAdapter and returns True."""
    settings = get_settings()
    settings.email_provider = "log"
    service = EmailService(settings)
    result = await service.send("test@example.com", "Subject", "Body")
    assert result is True


@pytest.mark.asyncio
async def test_email_service_unknown_provider() -> None:
    """Test that EmailService handles unknown provider gracefully."""
    settings = get_settings()
    settings.email_provider = "invalid"
    service = EmailService(settings)
    result = await service.send("test@example.com", "Subject", "Body")
    assert result is True


def test_notification_tasks_can_be_imported() -> None:
    """Test that we can import and inspect tasks without DB."""
    assert notify_processing_complete_task.name is not None
    assert notify_archival_warning_task.name is not None


@pytest.mark.asyncio
async def test_notification_service_send_processing_complete_fast() -> None:
    """Test NotificationService without DB."""
    from app.services.notification_service import NotificationService

    mock_db = AsyncMock()
    mock_email = AsyncMock()

    mock_event = AsyncMock()
    mock_event.name = "Test Event"
    mock_event.total_photos = 10
    mock_event.photographer.studio_name = "Test Studio"
    mock_event.photographer.email = "test@example.com"
    mock_db.get.return_value = mock_event

    service = NotificationService(mock_db, mock_email)
    await service.send_processing_complete("00000000-0000-0000-0000-000000000000")

    mock_email.send.assert_called_once()
    assert mock_email.send.call_args[1]["to"] == "test@example.com"


@pytest.mark.asyncio
async def test_notification_service_send_archival_warning_fast() -> None:
    """Test NotificationService without DB."""
    import datetime

    from app.services.notification_service import NotificationService

    mock_db = AsyncMock()
    mock_email = AsyncMock()

    mock_event = AsyncMock()
    mock_event.name = "Test Event"
    mock_event.archive_at = datetime.datetime.now()
    mock_event.photographer.studio_name = "Test Studio"
    mock_event.photographer.email = "test@example.com"
    mock_db.get.return_value = mock_event

    service = NotificationService(mock_db, mock_email)
    await service.send_archival_warning("00000000-0000-0000-0000-000000000000")

    mock_email.send.assert_not_called()


@pytest.mark.asyncio
async def test_notification_service_sends_stalled_ops_to_each_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPS_ALERT_EMAIL comma list should get one send per address."""
    monkeypatch.setenv("OPS_ALERT_EMAIL", "ops1@hpk.ai, ops2@hpk.ai")
    get_settings.cache_clear()
    from app.services.notification_service import NotificationService

    mock_email = AsyncMock()
    service = NotificationService(AsyncMock(), mock_email)
    await service.send_face_processing_stalled_ops(
        event_id=UUID("00000000-0000-0000-0000-000000000000"),
        event_name="Sharma Wedding",
        reason="no_worker_heartbeat",
    )
    assert mock_email.send.await_count == 2
    sent_to = [call.kwargs["to"] for call in mock_email.send.await_args_list]
    assert sent_to == ["ops1@hpk.ai", "ops2@hpk.ai"]
    get_settings.cache_clear()
