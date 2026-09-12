"""Unit tests for QualityFilter orchestration."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np

from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.quality.quality_filter import QualityFilter


def _make_crop() -> FaceCrop:
    detection = DetectedFace(
        bbox=np.array([0.1, 0.1, 0.3, 0.3]),
        bbox_pixel=np.array([10, 10, 30, 30]),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.99,
    )
    aligned = np.zeros((112, 112, 3), dtype=np.uint8)
    return FaceCrop(aligned_face=aligned, source_detection=detection, alignment_matrix=None)


def test_blur_reject_stops_early_without_running_age() -> None:
    """Blur failure should short-circuit before age or sunglasses checks."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (True, 0.91)

    ypr_predictor = Mock()
    age_detector = Mock()
    sunglasses_detector = Mock()

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=sunglasses_detector,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is False
    assert result.reject_reason == "blur"
    assert result.blur_score == 0.91
    assert result.ypr is None
    assert result.age is None
    assert result.has_sunglasses is False
    ypr_predictor.estimate.assert_not_called()
    age_detector.estimate.assert_not_called()
    sunglasses_detector.detect.assert_not_called()


def test_ypr_reject_stops_before_age() -> None:
    """Extreme pose should reject before age detection runs."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((50.0, 10.0, 5.0), True, False)

    age_detector = Mock()
    sunglasses_detector = Mock()

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=sunglasses_detector,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is False
    assert result.reject_reason == "ypr"
    assert result.ypr == (50.0, 10.0, 5.0)
    age_detector.estimate.assert_not_called()


def test_age_reject_for_young_child() -> None:
    """Children below the configured threshold should not be embedded."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((5.0, 5.0, 2.0), False, False)

    age_detector = Mock()
    age_detector.estimate.return_value = (3, 0.92)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=None,
        age_min_threshold=5,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is False
    assert result.reject_reason == "age"
    assert result.age == 3


def test_sunglasses_is_soft_flag() -> None:
    """Sunglasses should not block embedding or set reject_reason."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((5.0, 5.0, 2.0), False, False)

    sunglasses_detector = Mock()
    sunglasses_detector.available = True
    sunglasses_detector.detect.return_value = (True, 0.88)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=None,
        sunglasses_detector=sunglasses_detector,
        age_detection_enabled=False,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is True
    assert result.reject_reason is None
    assert result.has_sunglasses is True
    assert result.metadata["sunglasses_probability"] == 0.88


def test_ypr_error_passes_on_error() -> None:
    """YPR inference failure should allow embedding."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = (None, False, True)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=None,
        sunglasses_detector=None,
        age_detection_enabled=False,
        sunglasses_detection_enabled=False,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is True
    assert result.reject_reason is None
    assert result.metadata["ypr_pass_on_error"] is True


def test_blur_error_passes_on_error() -> None:
    """Blur inference failure should allow embedding."""
    blur_detector = Mock()
    blur_detector.is_blurry.side_effect = RuntimeError("tflite failed")

    ypr_predictor = Mock()
    ypr_predictor.backend = "tflite"
    ypr_predictor.estimate.return_value = ((1.0, 2.0, 3.0), False, False)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=None,
        sunglasses_detector=None,
        age_detection_enabled=False,
        sunglasses_detection_enabled=False,
    )

    result = quality_filter.filter(_make_crop())

    assert result.passed is True
    assert result.metadata["blur_error"] == "tflite failed"


def test_selfie_skips_age_and_uses_stricter_ypr() -> None:
    """Guest selfies skip age reject and apply 30° pose limits."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((32.0, 5.0, 2.0), False, False)

    age_detector = Mock()
    age_detector.estimate.return_value = (3, 0.99)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=None,
        age_min_threshold=5,
    )

    skipped_age = quality_filter.filter(_make_crop(), skip_age=True)
    assert skipped_age.passed is True
    age_detector.estimate.assert_not_called()

    selfie_result = quality_filter.filter(
        _make_crop(),
        skip_age=True,
        skip_sunglasses=True,
        yaw_threshold=30.0,
        pitch_threshold=30.0,
        roll_threshold=30.0,
    )
    assert selfie_result.passed is False
    assert selfie_result.reject_reason == "ypr"
    assert selfie_result.metadata["ypr_threshold_override"] is True


def test_quality_filter_all_gates_pass() -> None:
    """A sharp, frontal, adult crop should pass with sunglasses as a soft flag only."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.12)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((4.0, 3.0, 1.0), False, False)

    age_detector = Mock()
    age_detector.estimate.return_value = (28, 0.9)

    sunglasses_detector = Mock()
    sunglasses_detector.available = True
    sunglasses_detector.detect.return_value = (False, 0.05)

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=sunglasses_detector,
    )
    result = quality_filter.filter(_make_crop())
    assert result.passed is True
    assert result.reject_reason is None
    assert result.age == 28


def test_age_error_passes_on_error() -> None:
    """Age-model crashes must not drop a usable face."""
    blur_detector = Mock()
    blur_detector.is_blurry.return_value = (False, 0.1)

    ypr_predictor = Mock()
    ypr_predictor.backend = "3ddfa"
    ypr_predictor.estimate.return_value = ((1.0, 2.0, 3.0), False, False)

    age_detector = Mock()
    age_detector.estimate.side_effect = RuntimeError("vit missing")

    quality_filter = QualityFilter(
        blur_detector=blur_detector,
        ypr_predictor=ypr_predictor,
        age_detector=age_detector,
        sunglasses_detector=None,
        sunglasses_detection_enabled=False,
    )
    result = quality_filter.filter(_make_crop())
    assert result.passed is True
    assert result.metadata["age_pass_on_error"] is True
