"""Photographer start-face-processing API tests (ML-009)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis_dep
from app.core.database import get_db as core_get_db
from app.main import app
from app.ml.config import get_ml_config
from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

VALID_PASSWORD = "Password1!"
REGISTER = {
    "email": "face-start@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Face Start Studio",
    "phone": "+919876543240",
}


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    from app.core.redis_client import create_redis_client

    client = create_redis_client()
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        await client.aclose()
        pytest.skip(f"Redis unavailable: {exc}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def _verify_registration(client: AsyncClient, redis_client: object, payload: dict) -> dict:
    register = await client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    otp_service = OTPService(redis_client, SMSService())  # type: ignore[arg-type]
    otp = await otp_service.peek_otp(payload["phone"], "registration")
    assert otp is not None
    verify = await client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": payload["phone"], "otp": otp, "purpose": "registration"},
    )
    assert verify.status_code == 200, verify.text
    return verify.json()


@pytest_asyncio.fixture
async def authed_client(
    db_session: AsyncSession, redis_client: object
) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[core_get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        tokens = await _verify_registration(http_client, redis_client, REGISTER)
        http_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        yield http_client
    app.dependency_overrides.clear()


async def _event_with_photo(db_session: AsyncSession, authed_client: AsyncClient) -> Event:
    created = await authed_client.post(
        "/api/v1/events",
        json={"name": "Face Event", "event_type": "wedding"},
    )
    assert created.status_code == 201, created.text
    event = await db_session.get(Event, created.json()["id"])
    assert event is not None
    photo = Photo(
        event_id=event.id,
        filename="a.jpg",
        original_s3_key=f"originals/{event.id}/a.jpg",
        file_size_bytes=100,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
        faces_processed=False,
    )
    db_session.add(photo)
    event.status = EventStatus.UPLOADING
    event.total_photos = 1
    event.processed_photos = 1
    await db_session.commit()
    await db_session.refresh(event)
    return event


@pytest.mark.asyncio
async def test_start_face_processing_disabled(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag off → 503 and event stays Uploading."""
    monkeypatch.setenv("ML_FACE_PROCESSING_ENABLED", "false")
    get_ml_config.cache_clear()
    try:
        event = await _event_with_photo(db_session, authed_client)
        response = await authed_client.post(f"/api/v1/events/{event.id}/start-face-processing")
        assert response.status_code == 503
        assert response.json()["code"] == "FACE_PROCESSING_DISABLED"
        await db_session.refresh(event)
        assert event.status == EventStatus.UPLOADING
    finally:
        get_ml_config.cache_clear()


@pytest.mark.asyncio
async def test_start_face_processing_enqueues(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on → 202, status Processing, Celery delay called."""
    monkeypatch.setenv("ML_FACE_PROCESSING_ENABLED", "true")
    get_ml_config.cache_clear()
    try:
        event = await _event_with_photo(db_session, authed_client)
        with patch("app.tasks.face_tasks.process_event_photos.delay") as mock_delay:
            response = await authed_client.post(f"/api/v1/events/{event.id}/start-face-processing")
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["already_running"] is False
        assert body["photos_queued"] == 1
        assert body["status"] == "processing"
        mock_delay.assert_called_once_with(str(event.id))
        await db_session.refresh(event)
        assert event.status == EventStatus.PROCESSING
    finally:
        get_ml_config.cache_clear()


@pytest.mark.asyncio
async def test_start_face_processing_already_running(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second click while lock is held does not enqueue again."""
    monkeypatch.setenv("ML_FACE_PROCESSING_ENABLED", "true")
    get_ml_config.cache_clear()
    try:
        event = await _event_with_photo(db_session, authed_client)
        from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE, EventClusteringLock

        lock = EventClusteringLock(
            redis_client,  # type: ignore[arg-type]
            event.id,
            ttl_seconds=60,
            key_template=FACE_PIPELINE_LOCK_KEY_TEMPLATE,
        )
        assert await lock.acquire()
        with patch("app.tasks.face_tasks.process_event_photos.delay") as mock_delay:
            response = await authed_client.post(f"/api/v1/events/{event.id}/start-face-processing")
        assert response.status_code == 202
        assert response.json()["already_running"] is True
        mock_delay.assert_not_called()
        await lock.release()
    finally:
        get_ml_config.cache_clear()


@pytest.mark.asyncio
async def test_face_processing_progress_idle_then_hash(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progress endpoint returns idle without a hash, then Redis values after start."""
    monkeypatch.setenv("ML_FACE_PROCESSING_ENABLED", "true")
    get_ml_config.cache_clear()
    try:
        event = await _event_with_photo(db_session, authed_client)
        idle = await authed_client.get(f"/api/v1/events/{event.id}/face-processing-progress")
        assert idle.status_code == 200, idle.text
        assert idle.json()["pipeline_status"] == "idle"

        with patch("app.tasks.face_tasks.process_event_photos.delay"):
            start = await authed_client.post(f"/api/v1/events/{event.id}/start-face-processing")
        assert start.status_code == 202

        live = await authed_client.get(f"/api/v1/events/{event.id}/face-processing-progress")
        assert live.status_code == 200
        body = live.json()
        assert body["pipeline_status"] == "processing"
        assert body["total_photos"] == 1
        assert body["processed_photos"] == 0
        assert body["event_status"] == "processing"
    finally:
        get_ml_config.cache_clear()
