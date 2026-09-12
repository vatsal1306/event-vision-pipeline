"""Unit tests for Phase 1 liveness heuristics (no ML weights)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.ml.config import MLConfig
from app.ml.detection.types import DetectedFace
from app.ml.matching.liveness import BasicLivenessDetector

pytestmark = pytest.mark.ml


def _face(*, ratio: float = 0.25, score: float = 0.95) -> DetectedFace:
    side = float(ratio) ** 0.5
    return DetectedFace(
        bbox=np.array([0.2, 0.2, side, side], dtype=np.float32),
        bbox_pixel=np.array([20.0, 20.0, 80.0, 80.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=score,
    )


def _sharp_color_image(size: int = 320) -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.integers(30, 225, size=(size, size, 3), dtype=np.uint8)


def test_liveness_blank_fails() -> None:
    """A solid-color frame is too flat to pass sharpness or colour checks."""
    detector = BasicLivenessDetector(MLConfig())
    blank = np.full((240, 320, 3), 40, dtype=np.uint8)
    result = detector.check(blank, _face())
    assert result.passed is False
    assert "sharpness" in result.failed_checks or "color_present" in result.failed_checks


def test_liveness_rejects_non_bgr_image() -> None:
    """Liveness only accepts a 3-channel BGR array."""
    detector = BasicLivenessDetector(MLConfig())
    with pytest.raises(ValueError, match="BGR"):
        detector.check(np.zeros((32, 32), dtype=np.uint8), _face())


def test_liveness_passes_sharp_color_face() -> None:
    """A sharp, colourful, reasonably sized face should pass all checks."""
    detector = BasicLivenessDetector(MLConfig())
    result = detector.check(_sharp_color_image(), _face())
    assert result.passed is True
    assert result.failed_checks == []


def test_liveness_rejects_tiny_face() -> None:
    """Face covering less than 15% of the frame should fail."""
    detector = BasicLivenessDetector(MLConfig())
    result = detector.check(_sharp_color_image(), _face(ratio=0.05))
    assert result.passed is False
    assert "face_size" in result.failed_checks


def test_liveness_rejects_low_detection_score() -> None:
    """Selfie detection confidence must be at least 0.7."""
    detector = BasicLivenessDetector(MLConfig())
    result = detector.check(_sharp_color_image(), _face(score=0.4))
    assert result.passed is False
    assert "detection_confidence" in result.failed_checks


def test_liveness_rejects_blurry_image() -> None:
    """Low Laplacian variance should fail sharpness (print/screen look)."""
    detector = BasicLivenessDetector(MLConfig())
    image = np.full((240, 240, 3), 120, dtype=np.uint8)
    result = detector.check(image, _face())
    assert result.passed is False
    assert "sharpness" in result.failed_checks


def test_liveness_rejects_grayscale_printout() -> None:
    """Near-zero HSV saturation should fail the colour check."""
    detector = BasicLivenessDetector(MLConfig())
    color = _sharp_color_image()
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    result = detector.check(image, _face())
    assert result.passed is False
    assert "color_present" in result.failed_checks
