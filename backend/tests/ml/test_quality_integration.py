"""Integration tests for quality filters with real model weights."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

pytest.importorskip("onnxruntime")
pytest.importorskip("ai_edge_litert")

from app.ml.config import get_ml_config
from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.quality.blur_detector import BlurDetector
from app.ml.quality.ypr_3ddfa import YPRPredictor
from tests.ml.conftest import quality_models_available, run_ml_integration_tests

pytestmark = pytest.mark.ml


@pytest.fixture(autouse=True)
def _require_quality_integration_models() -> None:
    """Skip integration tests when ML weights are unavailable (e.g. CI)."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not quality_models_available():
        pytest.skip("Quality model files missing")


def test_blur_detector_scores_sharp_crop_low(
    quality_filter,
) -> None:
    """A sharp aligned crop should score well below the blur threshold."""
    _, crop = quality_filter
    config = get_ml_config()
    detector = BlurDetector(config.blur_model_path, threshold=config.blur_threshold)
    try:
        score = detector.score(crop.aligned_face)
    finally:
        detector.close()

    assert score < config.blur_threshold


def test_blur_detector_rejects_heavily_blurred_crop(
    scrfd_detector,
    face_cropper,
    load_bgr_image,
) -> None:
    """Heavily blurred face crop should exceed the blur threshold."""
    config = get_ml_config()
    if not config.blur_model_path.exists():
        pytest.skip("Blur model missing")

    image = load_bgr_image("single_face.jpg")
    faces = scrfd_detector.detect(image)
    crops = face_cropper.crop_all(image, faces)
    assert crops

    blurred_face = cv2.GaussianBlur(crops[0].aligned_face, (15, 15), 12)

    detector = BlurDetector(config.blur_model_path, threshold=config.blur_threshold)
    try:
        is_blurry, score = detector.is_blurry(blurred_face)
    finally:
        detector.close()

    assert score > config.blur_threshold
    assert is_blurry is True


def test_quality_filter_passes_sharp_frontal_crop(quality_filter) -> None:
    """Known good fixture crop should pass all hard gates."""
    filter_model, crop = quality_filter
    result = filter_model.filter(crop)

    assert result.passed is True
    assert result.reject_reason is None
    assert result.blur_score is not None
    assert result.ypr is not None
    assert len(result.ypr) == 3


def test_quality_filter_rejects_blurred_crop(quality_filter) -> None:
    """Synthetic blur applied to a crop should trigger blur rejection."""
    filter_model, crop = quality_filter
    blurred_face = cv2.GaussianBlur(crop.aligned_face, (15, 15), 12)
    blurred_crop = FaceCrop(
        aligned_face=blurred_face,
        source_detection=crop.source_detection,
        alignment_matrix=crop.alignment_matrix,
        source_photo_id=crop.source_photo_id,
    )

    result = filter_model.filter(blurred_crop)

    assert result.passed is False
    assert result.reject_reason == "blur"
    assert result.ypr is None


def test_ypr_predictor_returns_angles_for_aligned_crop(quality_filter) -> None:
    """3DDFA (or fallback) should return yaw/pitch/roll for a valid crop."""
    _, crop = quality_filter
    config = get_ml_config()
    predictor = YPRPredictor(
        model_type=config.ypr_model_type,
        config_path=config.ypr_3ddfa_config_path,
        tflite_model_path=config.ypr_tflite_model_path,
        yaw_threshold=config.yaw_threshold,
        pitch_threshold=config.pitch_threshold,
        roll_threshold=config.roll_threshold,
    )
    try:
        ypr, is_extreme, had_error = predictor.estimate(crop.aligned_face)
    finally:
        predictor.close()

    assert had_error is False
    assert ypr is not None
    assert len(ypr) == 3
    assert isinstance(is_extreme, bool)


def test_quality_filter_ypr_pass_on_error_when_no_face_in_crop(
    quality_registry,
) -> None:
    """Blank crop should trigger YPR pass-on-error semantics."""
    blank = np.zeros((112, 112, 3), dtype=np.uint8)
    detection = DetectedFace(
        bbox=np.zeros(4),
        bbox_pixel=np.zeros(4),
        landmarks=np.zeros((5, 2)),
        score=0.5,
    )
    crop = FaceCrop(aligned_face=blank, source_detection=detection, alignment_matrix=None)

    quality = quality_registry.get_model("quality_filter")
    result = quality.filter(crop)

    assert result.passed is True
    assert result.metadata.get("ypr_pass_on_error") is True
