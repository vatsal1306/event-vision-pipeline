"""Data structures for incremental face clustering."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

EMBEDDING_DIM = 512


@dataclass(frozen=True)
class ClusteringTypeConfig:
    """Behaviour flags for a clustering pass (regular cluster vs sweeper)."""

    name: str
    creates_new_clusters: bool
    expands_existing: bool
    allows_merge_clusters: bool
    centroid_field: str
    pyr_range: tuple[float, float]


@dataclass
class ExistingCluster:
    """Snapshot of a persisted face cluster used as clustering input."""

    centroid: np.ndarray
    size: int
    crop_ids: list[str] = field(default_factory=list)
    pyr_centroid: np.ndarray | None = None
    pyr_size: int = 0


@dataclass
class ClusteringInput:
    """Input payload for a single incremental clustering run."""

    new_embeddings: dict[str, np.ndarray]
    existing_clusters: dict[str, ExistingCluster]
    clustering_type: ClusteringTypeConfig


@dataclass
class NewCluster:
    """A newly discovered person-group."""

    cluster_id: str
    centroid: np.ndarray
    crop_ids: list[str]
    size: int


@dataclass
class ExpandedCluster:
    """An existing cluster that gained new face crops."""

    cluster_id: str
    new_crop_ids: list[str]
    new_centroid: np.ndarray | None = None
    new_size: int | None = None
    new_pyr_centroid: np.ndarray | None = None
    new_pyr_size: int | None = None


@dataclass
class MergedCluster:
    """Two or more existing clusters combined into one survivor."""

    surviving_cluster_id: str
    absorbed_cluster_ids: list[str]
    new_centroid: np.ndarray
    all_crop_ids: list[str]
    new_size: int


@dataclass
class ClusteringResult:
    """Output of one incremental clustering invocation."""

    new_clusters: list[NewCluster] = field(default_factory=list)
    expanded_clusters: list[ExpandedCluster] = field(default_factory=list)
    merged_clusters: list[MergedCluster] = field(default_factory=list)
    unassigned_crop_ids: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> ClusteringResult:
        """Return an empty clustering result."""
        return cls()


def new_cluster_id() -> str:
    """Generate a new cluster identifier."""
    return str(uuid4())
