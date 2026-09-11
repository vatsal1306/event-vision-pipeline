"""Optional live-model tests for the selfie pipeline."""

from __future__ import annotations

import time
import uuid

import cv2
import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.config import MLConfig
from app.ml.matching.liveness import BasicLivenessDetector
from app.ml.matching.pipeline import SelfieMatchPipeline
from app.ml.matching.types import MatchStatus
from app.ml.model_registry import get_model_registry
from app.ml.registry_bootstrap import register_default_model_loaders
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer
from tests.ml.conftest import (
    embedding_models_available,
    quality_models_available,
    run_ml_integration_tests,
    scrfd_model_available,
)

pytestmark = pytest.mark.ml


def _selfie_models_ready() -> bool:
    return (
        run_ml_integration_tests()
        and scrfd_model_available()
        and quality_models_available()
        and embedding_models_available()
    )


@pytest.mark.asyncio
async def test_pipeline_no_face_fixture(
    db_session: AsyncSession,
    scrfd_detector,
    face_cropper,
    load_bgr_image,
) -> None:
    """A no-face fixture must stop at detection."""
    pipeline = SelfieMatchPipeline(
        db_session,
        config=MLConfig(),
        detector=scrfd_detector,
        cropper=face_cropper,
        liveness=BasicLivenessDetector(),
    )
    result = await pipeline.run(load_bgr_image("no_face.jpg"), uuid.uuid4())
    assert result.status == MatchStatus.NO_FACE_DETECTED


@pytest.mark.asyncio
async def test_liveness_grayscale_selfie_fails(
    scrfd_detector,
    load_bgr_image,
) -> None:
    """A greyscale conversion of a real face should fail saturation liveness."""
    color = load_bgr_image("single_face.jpg")
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    faces = scrfd_detector.detect(image)
    if not faces:
        pytest.skip("SCRFD did not detect the greyscale fixture face")
    result = BasicLivenessDetector().check(image, faces[0])
    assert result.passed is False
    assert "color_present" in result.failed_checks


@pytest.mark.asyncio
async def test_full_pipeline_self_match_under_two_seconds(
    db_session: AsyncSession,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embed a real selfie, store that vector as a centroid, then match it back."""
    if not _selfie_models_ready():
        pytest.skip("SCRFD/quality/R100 weights missing or RUN_ML_TESTS!=1")

    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_AGE_DETECTION_ENABLED", "false")
    monkeypatch.setenv("ML_SUNGLASSES_DETECTION_ENABLED", "false")
    register_default_model_loaders()
    registry = get_model_registry()
    config = MLConfig(
        device="cpu",
        age_detection_enabled=False,
        sunglasses_detection_enabled=False,
    )

    photographer = Photographer(
        email=f"ml008-live-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="Live",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()
    event = Event(
        photographer_id=photographer.id,
        name="Live selfie",
        slug=f"ml008-live-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(event)
    await db_session.flush()
    photo = Photo(
        event_id=event.id,
        filename="selfie.jpg",
        original_s3_key=f"originals/{event.id}/selfie.jpg",
        file_size_bytes=1024,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.commit()

    image = load_bgr_image("single_face.jpg")
    pipeline = SelfieMatchPipeline(db_session, config=config, registry=registry)

    first = await pipeline.run(image, event.id)
    if first.status in {MatchStatus.LIVENESS_FAILED, MatchStatus.LOW_QUALITY}:
        pytest.skip(f"single_face.jpg rejected before matching: {first.status}")
    assert first.status == MatchStatus.NO_CLUSTERS
    assert first.selfie_embedding is not None

    cluster = FaceCluster(
        event_id=event.id,
        centroid=first.selfie_embedding.astype(np.float32).tolist(),
        cluster_size=1,
    )
    db_session.add(cluster)
    await db_session.flush()
    db_session.add(
        FaceEmbedding(
            photo_id=photo.id,
            event_id=event.id,
            cluster_id=cluster.id,
            embedding=first.selfie_embedding.astype(np.float32).tolist(),
            bbox_x=0.1,
            bbox_y=0.1,
            bbox_w=0.3,
            bbox_h=0.3,
            quality_passed=True,
        )
    )
    await db_session.commit()

    started = time.perf_counter()
    matched = await pipeline.run(image, event.id)
    elapsed = time.perf_counter() - started

    assert matched.status == MatchStatus.MATCHED
    assert cluster.id in matched.matched_cluster_ids
    assert photo.id in matched.photo_ids
    assert elapsed < 2.0
