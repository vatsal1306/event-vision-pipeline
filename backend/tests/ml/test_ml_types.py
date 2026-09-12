"""Serialization and shape contracts for ML dataclasses (no model weights)."""

from __future__ import annotations

import uuid
from dataclasses import asdict

import numpy as np

from app.ml.detection.types import DetectedFace, FaceCrop
from app.ml.embedding.types import EmbeddingResult
from app.ml.matching.types import LivenessResult, MatchResult, MatchStatus
from app.ml.quality.types import QualityResult


def test_detected_face_asdict_round_trip_fields() -> None:
    """DetectedFace should expose bbox fields through dataclass asdict."""
    face = DetectedFace(
        bbox=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        bbox_pixel=np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.91,
    )
    payload = asdict(face)
    assert payload["score"] == 0.91
    np.testing.assert_allclose(payload["bbox"], [0.1, 0.2, 0.3, 0.4])


def test_quality_result_asdict_includes_metadata() -> None:
    """QualityResult metadata must survive asdict for analytics logging."""
    result = QualityResult(
        passed=False,
        reject_reason="blur",
        blur_score=0.8,
        ypr=(10.0, 1.0, 2.0),
        age=None,
        has_sunglasses=False,
        metadata={"blur_threshold": 0.5},
    )
    payload = asdict(result)
    assert payload["reject_reason"] == "blur"
    assert payload["metadata"]["blur_threshold"] == 0.5


def test_embedding_result_primary_is_512d() -> None:
    """EmbeddingResult.primary is always a 512-d vector."""
    vector = np.ones(512, dtype=np.float32) / np.sqrt(512.0)
    result = EmbeddingResult(primary=vector, secondary=None, model_secondary=None)
    assert result.primary.shape == (512,)
    assert result.secondary is None


def test_match_result_clusters_alias() -> None:
    """Guest API reads ``clusters`` as an alias of matched_cluster_ids."""
    cluster_id = uuid.uuid4()
    result = MatchResult(status=MatchStatus.MATCHED, matched_cluster_ids=[cluster_id])
    assert result.clusters == [cluster_id]


def test_liveness_result_failed_checks_empty_when_passed() -> None:
    """A passing liveness result has no failed check names."""
    result = LivenessResult(
        passed=True,
        checks={"face_size": True},
        failed_checks=[],
        face_size_ratio=0.3,
        sharpness=80.0,
        saturation=40.0,
    )
    assert result.passed is True
    assert result.failed_checks == []


def test_face_crop_optional_photo_id_defaults_none() -> None:
    """FaceCrop.source_photo_id is optional for in-memory crops."""
    face = DetectedFace(
        bbox=np.array([0.1, 0.1, 0.2, 0.2], dtype=np.float32),
        bbox_pixel=np.array([1.0, 1.0, 10.0, 10.0], dtype=np.float32),
        landmarks=np.zeros((5, 2), dtype=np.float32),
        score=0.5,
    )
    crop = FaceCrop(
        aligned_face=np.zeros((112, 112, 3), dtype=np.uint8),
        source_detection=face,
        alignment_matrix=None,
    )
    assert crop.source_photo_id is None
    assert crop.aligned_face.shape == (112, 112, 3)
