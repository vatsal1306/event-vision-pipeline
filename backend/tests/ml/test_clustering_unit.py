"""Unit tests for incremental clustering (ML-005)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ml.clustering import (
    CLUSTER_TYPE,
    SWEEPER_TYPE,
    ClusteringInput,
    ExistingCluster,
    IncrementalClusterer,
)
from app.ml.config import MLConfig

EMBEDDING_DIM = 512


def _unit_vector(seed: int, perturbation: float = 0.0) -> np.ndarray:
    """Build a deterministic L2-normalised 512-d vector."""
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    if perturbation > 0:
        vector += perturbation * rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    norm = np.linalg.norm(vector)
    return vector / norm


def _near_vector(base: np.ndarray, seed: int, scale: float = 1e-3) -> np.ndarray:
    """Return a vector very close to ``base`` (cosine distance well below 0.45)."""
    rng = np.random.default_rng(seed)
    perturbation = rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * scale
    vector = base + perturbation
    norm = np.linalg.norm(vector)
    return vector / norm


@pytest.fixture
def clusterer() -> IncrementalClusterer:
    """Clusterer with default PicSee production thresholds."""
    return IncrementalClusterer(MLConfig(dbscan_eps=0.45, agglo_threshold=0.45))


def test_two_identical_embeddings_create_one_new_cluster(clusterer: IncrementalClusterer) -> None:
    """Two identical embeddings with no existing clusters form one group of size 2."""
    base = _unit_vector(1)
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"crop-a": base, "crop-b": base.copy()},
            existing_clusters={},
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert len(result.new_clusters) == 1
    assert result.new_clusters[0].size == 2
    assert set(result.new_clusters[0].crop_ids) == {"crop-a", "crop-b"}
    assert result.expanded_clusters == []
    assert result.merged_clusters == []
    assert result.unassigned_crop_ids == []


def test_near_existing_centroid_expands_cluster(clusterer: IncrementalClusterer) -> None:
    """A new embedding close to an existing centroid expands that cluster."""
    centroid = _unit_vector(10)
    existing = ExistingCluster(
        centroid=centroid,
        size=4,
        crop_ids=["existing-crop"],
    )
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"new-crop": _near_vector(centroid, seed=11)},
            existing_clusters={"cluster-1": existing},
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert result.new_clusters == []
    assert len(result.expanded_clusters) == 1
    expanded = result.expanded_clusters[0]
    assert expanded.cluster_id == "cluster-1"
    assert expanded.new_crop_ids == ["new-crop"]
    assert expanded.new_size == 5
    assert expanded.new_centroid is not None
    assert abs(np.linalg.norm(expanded.new_centroid) - 1.0) < 1e-5


def test_similar_centroids_merge_with_largest_survivor(clusterer: IncrementalClusterer) -> None:
    """Two close centroids merge; the larger cluster survives."""
    shared = _unit_vector(20)
    existing = {
        "cluster-large": ExistingCluster(
            centroid=shared.copy(),
            size=10,
            crop_ids=["large-crop"],
        ),
        "cluster-small": ExistingCluster(
            centroid=_near_vector(shared, seed=21),
            size=3,
            crop_ids=["small-crop"],
        ),
    }
    bridge = _near_vector(shared, seed=22)
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"bridge-crop": bridge},
            existing_clusters=existing,
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert result.new_clusters == []
    assert len(result.merged_clusters) == 1
    merged = result.merged_clusters[0]
    assert merged.surviving_cluster_id == "cluster-large"
    assert merged.absorbed_cluster_ids == ["cluster-small"]
    assert "bridge-crop" in merged.all_crop_ids
    assert merged.new_size == 14
    assert abs(np.linalg.norm(merged.new_centroid) - 1.0) < 1e-5


def test_merge_tie_breaks_on_smaller_cluster_id(clusterer: IncrementalClusterer) -> None:
    """Equal-size merges keep the lexicographically smaller cluster id."""
    shared = _unit_vector(30)
    existing = {
        "cluster-b": ExistingCluster(
            centroid=shared.copy(),
            size=5,
            crop_ids=["b-crop"],
        ),
        "cluster-a": ExistingCluster(
            centroid=_near_vector(shared, seed=31),
            size=5,
            crop_ids=["a-crop"],
        ),
    }
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"bridge": _near_vector(shared, seed=32)},
            existing_clusters=existing,
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert len(result.merged_clusters) == 1
    assert result.merged_clusters[0].surviving_cluster_id == "cluster-a"


def test_sweeper_never_creates_new_clusters(clusterer: IncrementalClusterer) -> None:
    """Sweeper pass sends would-be new groups to unassigned instead."""
    base = _unit_vector(40)
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"crop-1": base, "crop-2": base.copy()},
            existing_clusters={},
            clustering_type=SWEEPER_TYPE,
        )
    )

    assert result.new_clusters == []
    assert set(result.unassigned_crop_ids) == {"crop-1", "crop-2"}


def test_sweeper_expands_without_updating_main_centroid(clusterer: IncrementalClusterer) -> None:
    """Sweeper expansion updates pyr centroid only."""
    centroid = _unit_vector(50)
    existing = ExistingCluster(
        centroid=centroid,
        size=6,
        crop_ids=["old"],
        pyr_centroid=None,
        pyr_size=0,
    )
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"angled": _near_vector(centroid, seed=51)},
            existing_clusters={"person-1": existing},
            clustering_type=SWEEPER_TYPE,
        )
    )

    assert result.new_clusters == []
    assert len(result.expanded_clusters) == 1
    expanded = result.expanded_clusters[0]
    assert expanded.new_crop_ids == ["angled"]
    assert expanded.new_centroid is None
    assert expanded.new_size is None
    assert expanded.new_pyr_centroid is not None
    assert expanded.new_pyr_size == 1
    assert abs(np.linalg.norm(expanded.new_pyr_centroid) - 1.0) < 1e-5


def test_sweeper_blocks_merge_and_unassigns_new_crops(clusterer: IncrementalClusterer) -> None:
    """Sweeper does not merge existing clusters; new crops become unassigned."""
    shared = _unit_vector(60)
    existing = {
        "cluster-large": ExistingCluster(
            centroid=shared.copy(),
            size=8,
            crop_ids=["large"],
        ),
        "cluster-small": ExistingCluster(
            centroid=_near_vector(shared, seed=61),
            size=2,
            crop_ids=["small"],
        ),
    }
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={"bridge": _near_vector(shared, seed=62)},
            existing_clusters=existing,
            clustering_type=SWEEPER_TYPE,
        )
    )

    assert result.merged_clusters == []
    assert result.new_clusters == []
    assert result.unassigned_crop_ids == ["bridge"]


def test_weighted_centroid_is_l2_normalized(clusterer: IncrementalClusterer) -> None:
    """Expanded cluster centroids must remain unit vectors."""
    centroid = _unit_vector(70)
    existing = ExistingCluster(centroid=centroid, size=20, crop_ids=[])
    vectors = [_near_vector(centroid, seed=71 + idx) for idx in range(3)]

    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={f"crop-{idx}": vector for idx, vector in enumerate(vectors)},
            existing_clusters={"cluster": existing},
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert len(result.expanded_clusters) == 1
    norm = np.linalg.norm(result.expanded_clusters[0].new_centroid)
    assert norm == pytest.approx(1.0, abs=1e-5)


def test_large_batch_processes_without_error(clusterer: IncrementalClusterer) -> None:
    """A batch larger than 5000 embeddings should complete without memory failures."""
    embeddings = {f"crop-{index}": _unit_vector(index) for index in range(5100)}
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings=embeddings,
            existing_clusters={},
            clustering_type=CLUSTER_TYPE,
        )
    )

    assigned = sum(len(cluster.crop_ids) for cluster in result.new_clusters)
    assigned += sum(len(cluster.new_crop_ids) for cluster in result.expanded_clusters)
    assigned += len(result.unassigned_crop_ids)
    assert assigned == 5100


def test_empty_new_embeddings_returns_empty_result(clusterer: IncrementalClusterer) -> None:
    """No new embeddings should short-circuit to an empty result."""
    result = clusterer.cluster(
        ClusteringInput(
            new_embeddings={},
            existing_clusters={
                "cluster": ExistingCluster(
                    centroid=_unit_vector(80),
                    size=1,
                    crop_ids=["x"],
                )
            },
            clustering_type=CLUSTER_TYPE,
        )
    )

    assert result.new_clusters == []
    assert result.expanded_clusters == []
    assert result.merged_clusters == []
    assert result.unassigned_crop_ids == []


def test_clustering_module_has_no_database_imports() -> None:
    """ML-005 clustering code must remain free of database dependencies."""

    clustering_dir = Path(__file__).resolve().parents[2] / "app" / "ml" / "clustering"
    forbidden = ("sqlalchemy", "asyncpg", "alembic", "app.models")
    for py_file in clustering_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text, f"Forbidden import reference '{term}' in {py_file.name}"
