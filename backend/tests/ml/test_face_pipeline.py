"""FaceService orchestration tests (ML-009)."""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE, EventClusteringLock
from app.ml.config import MLConfig
from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.embedding.types import EmbeddingResult
from app.ml.exceptions import ClusteringLockBusyError
from app.ml.pipeline import FaceService, ProcessingResult
from app.ml.quality.types import QualityResult
from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.event_service import EventService

pytestmark = pytest.mark.ml


def _jpeg_bytes() -> bytes:
    """Return a tiny valid JPEG."""
    image = Image.new("RGB", (32, 32), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _unit_vector(seed: int) -> np.ndarray:
    """Build a deterministic L2-normalised 512-d vector."""
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(512).astype(np.float32)
    return vector / np.linalg.norm(vector)


class _FakeDetector:
    """Return one synthetic face for every image."""

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        return [
            DetectedFace(
                bbox=np.array([0.1, 0.1, 0.2, 0.2], dtype=np.float32),
                bbox_pixel=np.array([1.0, 1.0, 10.0, 10.0], dtype=np.float32),
                landmarks=np.zeros((5, 2), dtype=np.float32),
                score=0.95,
            )
        ]


class _FailingDetector:
    """Raise on detect so the service can skip the photo."""

    def detect(self, image: np.ndarray) -> list[DetectedFace]:
        raise RuntimeError("detector exploded")


class _FakeCropper:
    """Wrap detections as 112×112 zero crops."""

    def crop_all(
        self,
        image: np.ndarray,
        detected_faces: list[DetectedFace],
        source_photo_id: uuid.UUID | None = None,
    ) -> list[FaceCrop]:
        return [
            FaceCrop(
                aligned_face=np.zeros((112, 112, 3), dtype=np.uint8),
                source_detection=face,
                alignment_matrix=None,
                source_photo_id=source_photo_id,
            )
            for face in detected_faces
        ]


class _FakeQuality:
    """Pass every crop with dummy YPR."""

    def filter(self, face_crop: FaceCrop, **kwargs: object) -> QualityResult:
        return QualityResult(
            passed=True,
            reject_reason=None,
            blur_score=0.1,
            ypr=(1.0, 2.0, 3.0),
            age=None,
            has_sunglasses=False,
        )


class _FakeEmbedder:
    """Return a fixed primary embedding."""

    def embed_batch(self, faces: list[np.ndarray]) -> list[EmbeddingResult]:
        vector = _unit_vector(1)
        return [
            EmbeddingResult(
                primary=vector,
                secondary=None,
                model_primary="r100",
                model_secondary=None,
            )
            for _ in faces
        ]


async def _seed_event(db_session: AsyncSession) -> tuple[Event, Photo]:
    """Insert photographer, event, and one photo."""
    photographer = Photographer(
        email=f"ml009-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="ML009 Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()
    event = Event(
        photographer_id=photographer.id,
        name="ML009 Event",
        slug=f"ml009-{uuid.uuid4().hex[:8]}",
        status=EventStatus.UPLOADING,
    )
    db_session.add(event)
    await db_session.flush()
    photo = Photo(
        event_id=event.id,
        filename="face.jpg",
        original_s3_key=f"originals/{event.id}/face.jpg",
        file_size_bytes=1024,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )
    db_session.add(photo)
    await db_session.commit()
    return event, photo


def _face_service(
    db_session: AsyncSession,
    redis_client: object,
    *,
    detector: object | None = None,
) -> FaceService:
    """Build FaceService with injectable fakes."""
    return FaceService(
        db_session,
        redis_client=redis_client,  # type: ignore[arg-type]
        detector=detector or _FakeDetector(),  # type: ignore[arg-type]
        cropper=_FakeCropper(),  # type: ignore[arg-type]
        quality_filter=_FakeQuality(),  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),  # type: ignore[arg-type]
    )


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Real Redis client flushed for lock tests."""
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


@pytest.mark.asyncio
async def test_process_photo_stores_embeddings(
    db_session: AsyncSession, redis_client: object
) -> None:
    """process_photo returns face count and embedding IDs."""
    event, photo = await _seed_event(db_session)
    service = _face_service(db_session, redis_client)
    result = await service.process_photo(photo.id, _jpeg_bytes())

    assert isinstance(result, ProcessingResult)
    assert result.face_count == 1
    assert result.quality_passed_count == 1
    assert len(result.embedding_ids) == 1
    assert result.error is None

    await db_session.refresh(photo)
    await db_session.refresh(event)
    assert photo.faces_processed is True
    assert photo.face_count == 1
    assert event.total_faces == 1
    stored = (await db_session.execute(select(FaceEmbedding))).scalars().all()
    assert len(stored) == 1
    assert stored[0].quality_passed is True


@pytest.mark.asyncio
async def test_process_photo_decode_failure_marks_processed(
    db_session: AsyncSession, redis_client: object
) -> None:
    """Invalid bytes still mark the photo processed so the event can finish."""
    _event, photo = await _seed_event(db_session)
    service = _face_service(db_session, redis_client)
    result = await service.process_photo(photo.id, b"not-an-image")
    assert result.error is not None
    await db_session.refresh(photo)
    assert photo.faces_processed is True
    assert photo.face_count == 0


@pytest.mark.asyncio
async def test_single_photo_failure_continues(
    db_session: AsyncSession, redis_client: object
) -> None:
    """A detector crash on one photo does not block the next photo."""
    event, photo_ok = await _seed_event(db_session)
    photo_bad = Photo(
        event_id=event.id,
        filename="bad.jpg",
        original_s3_key=f"originals/{event.id}/bad.jpg",
        file_size_bytes=10,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )
    db_session.add(photo_bad)
    await db_session.commit()

    failing = FaceService(
        db_session,
        redis_client=redis_client,  # type: ignore[arg-type]
        detector=_FailingDetector(),  # type: ignore[arg-type]
        cropper=_FakeCropper(),  # type: ignore[arg-type]
        quality_filter=_FakeQuality(),  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),  # type: ignore[arg-type]
    )
    bad_result = await failing.process_photo(photo_bad.id, _jpeg_bytes())
    assert bad_result.error is not None

    ok_service = _face_service(db_session, redis_client)
    ok_result = await ok_service.process_photo(photo_ok.id, _jpeg_bytes())
    assert ok_result.embedding_ids
    await db_session.refresh(photo_bad)
    await db_session.refresh(photo_ok)
    assert photo_bad.faces_processed is True
    assert photo_ok.faces_processed is True


@pytest.mark.asyncio
async def test_run_clustering_from_stored_embeddings(
    db_session: AsyncSession, redis_client: object
) -> None:
    """run_clustering groups stored embeddings into clusters."""
    event, photo = await _seed_event(db_session)
    service = _face_service(db_session, redis_client)
    await service.process_photo(photo.id, _jpeg_bytes())
    result = await service.run_clustering(event.id)
    assert result.event_id == event.id
    assert result.cluster_pass is not None


@pytest.mark.asyncio
async def test_pipeline_lock_busy(db_session: AsyncSession, redis_client: object) -> None:
    """A second pipeline run fails when the lock is held."""
    event, _photo = await _seed_event(db_session)
    config = MLConfig(
        clustering_lock_retry_attempts=1,
        clustering_lock_retry_base_delay_seconds=0.01,
        face_pipeline_lock_ttl_seconds=30,
    )
    holder = EventClusteringLock(
        redis_client,  # type: ignore[arg-type]
        event.id,
        ttl_seconds=30,
        key_template=FACE_PIPELINE_LOCK_KEY_TEMPLATE,
    )
    assert await holder.acquire()
    service = FaceService(
        db_session,
        redis_client=redis_client,  # type: ignore[arg-type]
        config=config,
        detector=_FakeDetector(),  # type: ignore[arg-type]
        cropper=_FakeCropper(),  # type: ignore[arg-type]
        quality_filter=_FakeQuality(),  # type: ignore[arg-type]
        embedder=_FakeEmbedder(),  # type: ignore[arg-type]
    )
    with pytest.raises(ClusteringLockBusyError):
        await service.process_event_photos(event.id)
    await holder.release()


@pytest.mark.asyncio
async def test_event_ready_only_after_faces_and_proxies(db_session: AsyncSession) -> None:
    """Proxy completion alone leaves the event Uploading until faces are done."""
    event, photo = await _seed_event(db_session)
    service = EventService(db_session)
    await service.update_event_processing_status(event.id)
    await db_session.refresh(event)
    assert event.status == EventStatus.UPLOADING

    photo.faces_processed = True
    await db_session.commit()
    with patch("app.tasks.notification_tasks.notify_processing_complete_task.delay"):
        await service.update_event_processing_status(event.id)
    await db_session.refresh(event)
    assert event.status == EventStatus.READY
