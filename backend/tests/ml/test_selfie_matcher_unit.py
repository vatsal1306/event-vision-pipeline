"""Unit tests for centroid cosine matching and dual-model confidence tags."""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from app.ml.matching.selfie_matcher import cross_validate, rank_centroid_matches
from app.ml.matching.types import ClusterCentroid, ClusterMatch

pytestmark = pytest.mark.ml

DIM = 512


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(DIM).astype(np.float32)
    return vector / np.linalg.norm(vector)


def _cluster(centroid: np.ndarray, secondary: np.ndarray | None = None) -> ClusterCentroid:
    return ClusterCentroid(
        cluster_id=uuid.uuid4(),
        centroid=centroid,
        secondary_centroid=secondary,
    )


def test_identical_centroid_matches_with_similarity_one() -> None:
    """A query identical to a centroid should match with cosine ~1.0."""
    query = _unit(1)
    other = _unit(99)
    target = _cluster(query)
    decoy = _cluster(other)

    matches = rank_centroid_matches(
        query,
        [decoy, target],
        threshold=0.55,
        max_matches=5,
    )
    assert len(matches) == 1
    assert matches[0].cluster_id == target.cluster_id
    assert matches[0].similarity == pytest.approx(1.0, abs=1e-5)
    assert matches[0].confidence == "high"


def test_far_vector_returns_no_matches() -> None:
    """Orthogonal-ish vectors should fall below the 0.55 threshold."""
    query = _unit(1)
    far = _cluster(_unit(2))
    matches = rank_centroid_matches(query, [far], threshold=0.55, max_matches=5)
    assert matches == []


def test_max_cluster_matches_caps_results() -> None:
    """Never return more than max_cluster_matches even when many pass."""
    query = _unit(3)
    clusters = [_cluster(query) for _ in range(8)]
    matches = rank_centroid_matches(query, clusters, threshold=0.55, max_matches=5)
    assert len(matches) == 5


def test_dual_model_both_agree_high_confidence() -> None:
    """When both embedding spaces hit the same cluster, confidence is high."""
    primary = _unit(4)
    secondary = _unit(5)
    cluster = _cluster(primary, secondary=secondary)
    matches = rank_centroid_matches(
        primary,
        [cluster],
        threshold=0.55,
        max_matches=5,
        secondary_embedding=secondary,
        dual_model_enabled=True,
    )
    assert len(matches) == 1
    assert matches[0].confidence == "high"


def test_dual_model_primary_only_low_confidence() -> None:
    """Primary hit without AdaFace agreement is still returned as low confidence."""
    primary = _unit(6)
    secondary_query = _unit(7)
    unrelated_secondary = _unit(8)
    cluster = _cluster(primary, secondary=unrelated_secondary)
    matches = rank_centroid_matches(
        primary,
        [cluster],
        threshold=0.55,
        max_matches=5,
        secondary_embedding=secondary_query,
        dual_model_enabled=True,
    )
    assert len(matches) == 1
    assert matches[0].confidence == "low"


def test_dual_model_drops_secondary_only_cluster() -> None:
    """AdaFace-only hits must not appear in the guest gallery."""
    primary_query = _unit(9)
    secondary_query = _unit(10)
    primary_only = _cluster(primary_query, secondary=_unit(11))
    secondary_only = _cluster(_unit(12), secondary=secondary_query)
    matches = rank_centroid_matches(
        primary_query,
        [primary_only, secondary_only],
        threshold=0.55,
        max_matches=5,
        secondary_embedding=secondary_query,
        dual_model_enabled=True,
    )
    assert [item.cluster_id for item in matches] == [primary_only.cluster_id]
    assert matches[0].confidence == "low"


def test_cross_validate_helper_matches_story_sets() -> None:
    """Intersection is high; primary-only is low; secondary-only is dropped."""
    shared = uuid.uuid4()
    primary_only = uuid.uuid4()
    secondary_only = uuid.uuid4()
    result = cross_validate(
        [
            ClusterMatch(cluster_id=shared, similarity=0.9, confidence="low"),
            ClusterMatch(cluster_id=primary_only, similarity=0.8, confidence="low"),
        ],
        [
            ClusterMatch(cluster_id=shared, similarity=0.7, confidence="low"),
            ClusterMatch(cluster_id=secondary_only, similarity=0.95, confidence="low"),
        ],
    )
    by_id = {item.cluster_id: item.confidence for item in result}
    assert by_id[shared] == "high"
    assert by_id[primary_only] == "low"
    assert secondary_only not in by_id
