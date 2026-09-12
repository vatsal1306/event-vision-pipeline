"""Unit tests for FaceEmbedding row construction (no model weights)."""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.face_rows import (
    FAILED_FACE_PLACEHOLDER_EMBEDDING,
    build_face_embedding_row,
    embedding_vector_to_list,
)
from app.ml.quality.types import QualityResult


def _crop() -> FaceCrop:
    detection = DetectedFace(
        bbox=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        bbox_pixel=np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.88,
    )
    return FaceCrop(
        aligned_face=np.zeros((112, 112, 3), dtype=np.uint8),
        source_detection=detection,
        alignment_matrix=None,
    )


def test_embedding_vector_to_list_flattens_float32() -> None:
    """pgvector storage uses a Python list of floats."""
    vector = np.array([0.5, -0.25, 0.0], dtype=np.float32)
    converted = embedding_vector_to_list(vector)
    assert converted == [0.5, -0.25, 0.0]


def test_build_face_embedding_row_quality_reject_placeholder() -> None:
    """Rejected faces still persist a 512-d placeholder vector."""
    quality = QualityResult(
        passed=False,
        reject_reason="blur",
        blur_score=0.9,
        ypr=(11.0, 4.0, 1.0),
        age=None,
        has_sunglasses=False,
    )
    photo_id = uuid.uuid4()
    event_id = uuid.uuid4()
    row = build_face_embedding_row(
        photo_id=photo_id,
        event_id=event_id,
        crop=_crop(),
        quality=quality,
        primary=list(FAILED_FACE_PLACEHOLDER_EMBEDDING),
        secondary=None,
        quality_passed=False,
    )
    assert row.photo_id == photo_id
    assert row.event_id == event_id
    assert row.quality_passed is False
    assert row.embedding == FAILED_FACE_PLACEHOLDER_EMBEDDING
    assert row.yaw == 11.0
    assert row.pitch == 4.0
    assert row.roll == 1.0
    assert row.detection_score == 0.88
    assert row.bbox_x == pytest.approx(0.1, abs=1e-5)
    assert row.bbox_w == pytest.approx(0.3, abs=1e-5)


def test_build_face_embedding_row_without_ypr() -> None:
    """Missing YPR leaves pose columns unset."""
    quality = QualityResult(
        passed=True,
        reject_reason=None,
        blur_score=0.1,
        ypr=None,
        age=None,
        has_sunglasses=False,
    )
    row = build_face_embedding_row(
        photo_id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        crop=_crop(),
        quality=quality,
        primary=[0.0] * 512,
        secondary=[0.1] * 512,
        quality_passed=True,
    )
    assert row.yaw is None
    assert row.pitch is None
    assert row.roll is None
    assert row.secondary_embedding == [0.1] * 512
    assert row.quality_passed is True
