"""Tests for notification services and tasks."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
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

    settings = get_settings()
    settings.debug = True

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
    await db_session.commit()
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
    photographer = Photographer(
        email="trigger@test.com",
        password_hash="hash",
        studio_name="Trigger Studio",
        phone="+919999999997",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="Trigger Event",
        slug="trigger-event",
        total_photos=1,
        processed_photos=0,
        status=EventStatus.PROCESSING,
    )
    db_session.add(event)
    await db_session.flush()

    photo = Photo(
        event_id=event.id,
        original_s3_key="orig.jpg",
        proxy_s3_key="proxy.jpg",
        filename="test.jpg",
        file_size_bytes=100,
        processing_status=ProcessingStatus.COMPLETED,
    )
    db_session.add(photo)
    await db_session.commit()
    await db_session.refresh(event)

    event_service = EventService(db_session)

    with patch("app.services.event_service.notify_processing_complete_task.delay") as mock_delay:
        await event_service._recalculate_status(event.id)

        await db_session.refresh(event)
        assert event.status == EventStatus.READY
        mock_delay.assert_called_once_with(str(event.id))
