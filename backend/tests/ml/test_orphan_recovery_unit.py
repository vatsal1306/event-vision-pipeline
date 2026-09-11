"""Unit tests for orphan recovery cosine matching (ML-007)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.clustering.recovery.orphan_clusters import (
    match_orphan_clusters,
    merges_to_clustering_result,
    partition_orphan_clusters,
)
from app.ml.clustering.recovery.orphan_crops import match_orphan_crops
from app.ml.clustering.recovery.similarity import (
    MATCH_CENTROID,
    MATCH_CENTROID_VS_PYR,
    MATCH_PYR,
    dual_centroid_similarity_matrix,
    match_type_name,
    pairwise_cosine_similarity,
)
from app.ml.clustering.types import ExistingCluster

EMBEDDING_DIM = 512


def _axis(index: int) -> np.ndarray:
    """Return a standard-basis unit vector."""
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vector[index] = 1.0
    return vector


def _blend(left: np.ndarray, right: np.ndarray, right_weight: float) -> np.ndarray:
    """Mix two unit vectors and re-normalise."""
    mixed = left * (1.0 - right_weight) + right * right_weight
    return mixed / np.linalg.norm(mixed)


def _cluster(
    centroid: np.ndarray,
    size: int,
    pyr_centroid: np.ndarray | None = None,
    pyr_size: int = 0,
) -> ExistingCluster:
    """Build a cluster snapshot."""
    return ExistingCluster(
        centroid=centroid,
        size=size,
        crop_ids=[],
        pyr_centroid=pyr_centroid,
        pyr_size=pyr_size,
    )


def test_pairwise_cosine_identical_vectors_are_one() -> None:
    """Identical L2-normalised vectors have cosine similarity 1."""
    vector = _axis(0)
    similarities = pairwise_cosine_similarity(vector.reshape(1, -1), vector.reshape(1, -1))
    assert similarities.shape == (1, 1)
    assert similarities[0, 0] == pytest.approx(1.0, abs=1e-5)


def test_orphan_crop_assigns_above_threshold() -> None:
    """A leftover crop near a PYR centroid is assigned to that cluster."""
    pyr = _axis(0)
    assignments = match_orphan_crops(
        {"crop-a": _blend(pyr, _axis(1), 0.01)},
        {"cluster-a": _cluster(_axis(2), size=10, pyr_centroid=pyr, pyr_size=4)},
        threshold=0.55,
    )
    assert len(assignments) == 1
    assert assignments[0].crop_id == "crop-a"
    assert assignments[0].cluster_id == "cluster-a"
    assert assignments[0].similarity >= 0.55


def test_orphan_crop_stays_unassigned_below_threshold() -> None:
    """A leftover crop far from every PYR centroid stays unmatched."""
    assignments = match_orphan_crops(
        {"crop-a": _axis(0)},
        {"cluster-a": _cluster(_axis(0), size=10, pyr_centroid=_axis(1), pyr_size=4)},
        threshold=0.55,
    )
    assert assignments == []


def test_orphan_crop_ignores_clusters_without_pyr() -> None:
    """Clusters that only have a main centroid are not recovery targets."""
    assignments = match_orphan_crops(
        {"crop-a": _axis(0)},
        {"cluster-a": _cluster(_axis(0), size=10, pyr_centroid=None)},
        threshold=0.55,
    )
    assert assignments == []


def test_dual_centroid_takes_max_of_three_channels() -> None:
    """PYR-vs-PYR can win even when main centroids are dissimilar."""
    orphan_centroid = _axis(0)
    orphan_pyr = _axis(1)
    established_centroid = _axis(2)
    established_pyr = _axis(1)
    similarities, codes = dual_centroid_similarity_matrix(
        orphan_centroid.reshape(1, -1),
        orphan_pyr.reshape(1, -1),
        np.array([True]),
        established_centroid.reshape(1, -1),
        established_pyr.reshape(1, -1),
        np.array([True]),
    )
    assert similarities[0, 0] == pytest.approx(1.0, abs=1e-5)
    assert int(codes[0, 0]) == 2
    assert match_type_name(int(codes[0, 0])) == MATCH_PYR


def test_dual_centroid_centroid_vs_pyr_channel() -> None:
    """Orphan main centroid vs established PYR is used when it is the best score."""
    orphan_centroid = _axis(1)
    established_centroid = _axis(0)
    established_pyr = _axis(1)
    similarities, codes = dual_centroid_similarity_matrix(
        orphan_centroid.reshape(1, -1),
        None,
        np.array([False]),
        established_centroid.reshape(1, -1),
        established_pyr.reshape(1, -1),
        np.array([True]),
    )
    assert similarities[0, 0] == pytest.approx(1.0, abs=1e-5)
    assert int(codes[0, 0]) == 1
    assert match_type_name(int(codes[0, 0])) == MATCH_CENTROID_VS_PYR


def test_dual_centroid_does_not_use_orphan_pyr_vs_established_centroid() -> None:
    """High-angle orphan PYR vs frontal established centroid is not a channel."""
    orphan_centroid = _axis(0)
    orphan_pyr = _axis(1)
    established_centroid = _axis(1)
    similarities, codes = dual_centroid_similarity_matrix(
        orphan_centroid.reshape(1, -1),
        orphan_pyr.reshape(1, -1),
        np.array([True]),
        established_centroid.reshape(1, -1),
        None,
        np.array([False]),
    )
    assert similarities[0, 0] == pytest.approx(0.0, abs=1e-5)
    assert int(codes[0, 0]) == 0
    assert match_type_name(int(codes[0, 0])) == MATCH_CENTROID


def test_partition_uses_inclusive_max_orphan_size() -> None:
    """Size 3 is an orphan; size 4 is established."""
    clusters = {
        "small": _cluster(_axis(0), size=3),
        "large": _cluster(_axis(1), size=4),
    }
    orphans, established = partition_orphan_clusters(clusters, max_orphan_size=3)
    assert set(orphans) == {"small"}
    assert set(established) == {"large"}


def test_orphan_cluster_merge_above_threshold() -> None:
    """A size-2 cluster near a large centroid is selected for merge."""
    base = _axis(0)
    assignments = match_orphan_clusters(
        {"orphan": _cluster(_blend(base, _axis(1), 0.01), size=2)},
        {"big": _cluster(base, size=50)},
        threshold=0.55,
    )
    assert len(assignments) == 1
    assert assignments[0].orphan_id == "orphan"
    assert assignments[0].target_id == "big"
    assert assignments[0].match_type == MATCH_CENTROID


def test_orphan_cluster_not_merged_when_dissimilar() -> None:
    """A small cluster orthogonal to every established cluster stays independent."""
    assignments = match_orphan_clusters(
        {"orphan": _cluster(_axis(0), size=2)},
        {"big": _cluster(_axis(1), size=50)},
        threshold=0.55,
    )
    assert assignments == []


def test_grouped_merges_share_one_survivor() -> None:
    """Two orphans matching the same target become one persistable merge."""
    base = _axis(0)
    orphans = {
        "o1": _cluster(_blend(base, _axis(1), 0.01), size=1),
        "o2": _cluster(_blend(base, _axis(2), 0.01), size=2),
    }
    established = {"big": _cluster(base, size=50)}
    assignments = match_orphan_clusters(orphans, established, threshold=0.55)
    result = merges_to_clustering_result(orphans, established, assignments)
    assert len(result.merged_clusters) == 1
    merged = result.merged_clusters[0]
    assert merged.surviving_cluster_id == "big"
    assert set(merged.absorbed_cluster_ids) == {"o1", "o2"}
    assert merged.new_size == 53
