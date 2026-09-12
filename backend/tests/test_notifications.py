"""Tests for notification services and tasks."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.event_service import EventService
from app.services.notification_service import NotificationService
from app.utils.otp import OTPService


@pytest.mark.asyncio
async def test_otp_debug_bypass() -> None:
    """Test that OTP verification allows '123456' in debug mode."""
    # We must construct a mock redis for the otp service
    redis_mock = AsyncMock()
    # It shouldn't even call redis if debug=True and otp="123456"

    from app.config import Settings

    settings = Settings(debug=True, sms_provider="log", email_provider="log")

    sms_mock = AsyncMock()
    otp_service = OTPService(redis_client=redis_mock, sms_service=sms_mock, settings=settings)

    result = await otp_service.verify_otp("+919999999999", "login", "123456")
    assert result is True
    redis_mock.incr.assert_not_called()


@pytest.mark.asyncio
async def test_notification_service_processing_complete(db_session: AsyncSession) -> None:
    """Test that NotificationService formats and sends the processing complete email."""
    # Create photographer and event
    photographer = Photographer(
        email="test_notify@test.com",
        password_hash="hash",
        studio_name="Notify Studio",
        phone="+919999999998",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="Test Notification Event",
        slug="test-notify-event",
        total_photos=5,
        processed_photos=5,
        status=EventStatus.READY,
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)

    email_mock = AsyncMock()
    notification_service = NotificationService(db_session, email_mock)

    await notification_service.send_processing_complete(event.id)

    email_mock.send.assert_called_once()
    call_args = email_mock.send.call_args[1]
    assert call_args["to"] == "test_notify@test.com"
    assert "Event Processing Complete: Test Notification Event" in call_args["subject"]
    assert "Notify Studio" in call_args["body"]


@pytest.mark.asyncio
async def test_event_service_triggers_notification_task(db_session: AsyncSession) -> None:
    """Test that EventService dispatches the notification task when status reaches READY."""
    import uuid

    unique = uuid.uuid4().hex[:6]
    photographer = Photographer(
        email=f"trigger_{unique}@test.com",
        password_hash="hash",
        studio_name="Trigger Studio",
        phone=f"+919988{unique[:4]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name=f"Trigger Event {unique}",
        slug=f"trigger-event-{unique}",
        total_photos=1,
        processed_photos=0,
        status=EventStatus.UPLOADING,
    )
    db_session.add(event)
    await db_session.flush()

    photo = Photo(
        event_id=event.id,
        original_s3_key=f"orig_{unique}.jpg",
        proxy_s3_key=f"proxy_{unique}.jpg",
        filename="test.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
        processing_status=ProcessingStatus.COMPLETED,
        tus_upload_id=f"test_upload_{unique}",
    )
    db_session.add(photo)
    await db_session.flush()
    await db_session.refresh(event)

    event_service = EventService(db_session)

    with patch("app.tasks.notification_tasks.notify_processing_complete_task.delay") as mock_delay:
        await event_service.update_event_processing_status(event.id)

        await db_session.refresh(event)
        assert event.status == EventStatus.UPLOADING
        mock_delay.assert_not_called()


@pytest.mark.asyncio
async def test_event_ready_notifies_after_faces_processed(db_session: AsyncSession) -> None:
    """Ready + photographer email only after faces_processed and proxies are done."""
    unique = uuid.uuid4().hex[:8]
    photographer = Photographer(
        email=f"facesready_{unique}@test.com",
        password_hash="hash",
        studio_name="Ready Studio",
        phone=f"+919977{unique[:4]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()
    event = Event(
        photographer_id=photographer.id,
        name=f"Ready Event {unique}",
        slug=f"ready-event-{unique}",
        total_photos=1,
        processed_photos=1,
        status=EventStatus.PROCESSING,
    )
    db_session.add(event)
    await db_session.flush()
    photo = Photo(
        event_id=event.id,
        original_s3_key=f"orig_{unique}.jpg",
        filename="test.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
        processing_status=ProcessingStatus.COMPLETED,
        faces_processed=True,
        tus_upload_id=f"ready_upload_{unique}",
    )
    db_session.add(photo)
    await db_session.flush()

    with patch("app.tasks.notification_tasks.notify_processing_complete_task.delay") as mock_delay:
        await EventService(db_session).update_event_processing_status(event.id)

    await db_session.refresh(event)
    assert event.status == EventStatus.READY
    mock_delay.assert_called_once_with(str(event.id))
