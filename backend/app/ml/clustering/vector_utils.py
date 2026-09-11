"""Vector and identifier helpers for cluster persistence."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import numpy as np

from app.ml.clustering.types import ClusteringResult


def merge_clustering_results(combined: ClusteringResult, batch: ClusteringResult) -> None:
    """Append one batch result into the pass-level aggregate."""
    combined.new_clusters.extend(batch.new_clusters)
    combined.expanded_clusters.extend(batch.expanded_clusters)
    combined.merged_clusters.extend(batch.merged_clusters)
    combined.unassigned_crop_ids.extend(batch.unassigned_crop_ids)


def as_float32_vector(value: object) -> np.ndarray:
    """Convert a pgvector value to a 1-D float32 array."""
    return np.asarray(value, dtype=np.float32).reshape(-1)


def as_vector_list(vector: np.ndarray) -> list[float]:
    """Convert a numpy embedding to a Python list for pgvector writes."""
    return [float(value) for value in np.asarray(vector, dtype=np.float32).reshape(-1)]


def mean_l2_normalized(vectors: Sequence[np.ndarray]) -> list[float] | None:
    """Return the L2-normalised mean of vectors, or None when empty."""
    if not vectors:
        return None
    stacked = np.stack([np.asarray(vector, dtype=np.float32).reshape(-1) for vector in vectors])
    mean = stacked.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm == 0.0:
        return None
    return [float(value) for value in (mean / norm).astype(np.float32)]


def as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    """Parse a cluster or crop identifier."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def as_uuids(values: Sequence[uuid.UUID | str]) -> list[uuid.UUID]:
    """Parse a sequence of identifiers."""
    return [as_uuid(value) for value in values]


def affected_cluster_ids(result: ClusteringResult) -> list[uuid.UUID]:
    """Return cluster IDs that were created, expanded, or kept after a merge."""
    ids: set[uuid.UUID] = set()
    for new_cluster in result.new_clusters:
        ids.add(as_uuid(new_cluster.cluster_id))
    for expanded_cluster in result.expanded_clusters:
        ids.add(as_uuid(expanded_cluster.cluster_id))
    for merged_cluster in result.merged_clusters:
        ids.add(as_uuid(merged_cluster.surviving_cluster_id))
    return list(ids)
