"""Pipeline status mapping tests using injected fakes (no model weights)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from app.ml.config import MLConfig
from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.embedding.types import EmbeddingResult
from app.ml.matching.pipeline import SelfieMatchPipeline, decode_selfie_bytes
from app.ml.matching.types import LivenessResult, MatchResult, MatchStatus
from app.ml.quality.types import QualityResult

pytestmark = pytest.mark.ml


def _bgr(value: int = 80) -> np.ndarray:
    return np.full((64, 64, 3), value, dtype=np.uint8)


def _face() -> DetectedFace:
    return DetectedFace(
        bbox=np.array([0.2, 0.2, 0.5, 0.5], dtype=np.float32),
        bbox_pixel=np.array([10.0, 10.0, 40.0, 40.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.99,
    )


def _crop(face: DetectedFace) -> FaceCrop:
    return FaceCrop(
        aligned_face=np.zeros((112, 112, 3), dtype=np.uint8),
        source_detection=face,
        alignment_matrix=None,
    )


def _liveness(*, passed: bool) -> LivenessResult:
    return LivenessResult(
        passed=passed,
        checks={"face_size": passed},
        failed_checks=[] if passed else ["face_size"],
        face_size_ratio=0.25,
        sharpness=80.0,
        saturation=40.0,
    )


def _quality(*, passed: bool, reason: str | None = None) -> QualityResult:
    return QualityResult(
        passed=passed,
        reject_reason=reason,
        blur_score=0.1,
        ypr=(1.0, 2.0, 3.0),
        age=None,
        has_sunglasses=False,
    )


@pytest.mark.asyncio
async def test_pipeline_blank_image_is_no_face() -> None:
    """No SCRFD detections map to no_face_detected."""
    detector = Mock()
    detector.detect.return_value = []
    cropper = Mock()
    pipeline = SelfieMatchPipeline(
        db=Mock(),
        config=MLConfig(),
        detector=detector,
        cropper=cropper,
        liveness=Mock(),
        quality_filter=Mock(),
        embedder=Mock(),
        matcher=Mock(),
    )
    result = await pipeline.run(_bgr(), uuid.uuid4())
    assert result.status == MatchStatus.NO_FACE_DETECTED
    cropper.select_primary.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_liveness_failed() -> None:
    """Failed heuristic liveness stops before quality or embedding."""
    face = _face()
    detector = Mock()
    detector.detect.return_value = [face]
    cropper = Mock()
    cropper.select_primary.return_value = face
    liveness = Mock()
    liveness.check.return_value = _liveness(passed=False)
    quality = Mock()
    pipeline = SelfieMatchPipeline(
        db=Mock(),
        config=MLConfig(),
        detector=detector,
        cropper=cropper,
        liveness=liveness,
        quality_filter=quality,
        embedder=Mock(),
        matcher=Mock(),
    )
    result = await pipeline.run(_bgr(), uuid.uuid4())
    assert result.status == MatchStatus.LIVENESS_FAILED
    quality.filter.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_blurry_selfie_is_low_quality() -> None:
    """TFLite blur / 30° YPR reject maps to low_quality after liveness passes."""
    face = _face()
    detector = Mock()
    detector.detect.return_value = [face]
    cropper = Mock()
    cropper.select_primary.return_value = face
    cropper.crop_primary.return_value = _crop(face)
    liveness = Mock()
    liveness.check.return_value = _liveness(passed=True)
    quality = Mock()
    quality.filter.return_value = _quality(passed=False, reason="blur")
    pipeline = SelfieMatchPipeline(
        db=Mock(),
        config=MLConfig(),
        detector=detector,
        cropper=cropper,
        liveness=liveness,
        quality_filter=quality,
        embedder=Mock(),
        matcher=Mock(),
    )
    result = await pipeline.run(_bgr(), uuid.uuid4())
    assert result.status == MatchStatus.LOW_QUALITY
    assert result.quality_issue == "blur"
    quality.filter.assert_called_once()
    kwargs = quality.filter.call_args.kwargs
    assert kwargs["skip_age"] is True
    assert kwargs["skip_sunglasses"] is True
    assert kwargs["yaw_threshold"] == 30.0


@pytest.mark.asyncio
async def test_pipeline_matched_attaches_photo_ids() -> None:
    """A matcher hit should load distinct photo IDs for the guest API."""
    face = _face()
    cluster_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    embedding = np.zeros(512, dtype=np.float32)
    embedding[0] = 1.0

    detector = Mock()
    detector.detect.return_value = [face]
    cropper = Mock()
    cropper.select_primary.return_value = face
    cropper.crop_primary.return_value = _crop(face)
    liveness = Mock()
    liveness.check.return_value = _liveness(passed=True)
    quality = Mock()
    quality.filter.return_value = _quality(passed=True)
    embedder = Mock()
    embedder.embed_single.return_value = EmbeddingResult(
        primary=embedding,
        secondary=None,
        model_secondary=None,
    )
    matcher = Mock()
    matcher.match = AsyncMock(
        return_value=MatchResult(
            status=MatchStatus.MATCHED,
            matched_cluster_ids=[cluster_id],
            selfie_embedding=embedding,
        )
    )
    pipeline = SelfieMatchPipeline(
        db=Mock(),
        config=MLConfig(),
        detector=detector,
        cropper=cropper,
        liveness=liveness,
        quality_filter=quality,
        embedder=embedder,
        matcher=matcher,
    )
    pipeline._load_photo_ids = AsyncMock(return_value=[photo_id])  # type: ignore[method-assign]

    result = await pipeline.run(_bgr(), uuid.uuid4())
    assert result.status == MatchStatus.MATCHED
    assert result.photo_ids == [photo_id]
    matcher.match.assert_awaited_once()


def test_decode_selfie_bytes_rejects_garbage() -> None:
    """Undecodable bytes should return None (invalid_image upstream)."""
    assert decode_selfie_bytes(b"not-an-image") is None
    assert decode_selfie_bytes(b"") is None
