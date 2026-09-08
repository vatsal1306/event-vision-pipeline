"""Unit tests for detection helpers (no model required)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.detection.types import DetectedFace
from app.ml.face_preprocess import estimate_norm, norm_crop


def test_estimate_norm_returns_2x3_matrix() -> None:
    """Alignment matrix should be a valid affine transform."""
    landmarks = np.array(
        [
            [50.0, 60.0],
            [90.0, 58.0],
            [70.0, 80.0],
            [55.0, 100.0],
            [85.0, 102.0],
        ],
        dtype=np.float32,
    )
    matrix = estimate_norm(landmarks, image_size=112)
    assert matrix.shape == (2, 3)


def test_norm_crop_output_shape() -> None:
    """norm_crop should return a square BGR crop."""
    image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    landmarks = np.array(
        [
            [80.0, 90.0],
            [150.0, 92.0],
            [115.0, 130.0],
            [85.0, 170.0],
            [145.0, 168.0],
        ],
        dtype=np.float32,
    )
    crop = norm_crop(image, landmarks, image_size=112)
    assert crop.shape == (112, 112, 3)
    assert crop.dtype == np.uint8


def test_detected_face_bbox_fields() -> None:
    """DetectedFace stores normalized and pixel bbox separately."""
    face = DetectedFace(
        bbox=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        bbox_pixel=np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.9,
    )
    assert face.bbox.tolist() == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert face.bbox_pixel.tolist() == [10.0, 20.0, 30.0, 40.0]
