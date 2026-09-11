"""Pure numpy cosine helpers for clustering recovery."""

from __future__ import annotations

import numpy as np

from app.ml.clustering.types import ExistingCluster

MATCH_CENTROID = "centroid"
MATCH_CENTROID_VS_PYR = "centroid_vs_pyr"
MATCH_PYR = "pyr_centroid"

_MATCH_CODE_TO_NAME = (
    MATCH_CENTROID,
    MATCH_CENTROID_VS_PYR,
    MATCH_PYR,
)


def l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """L2-normalise each row, leaving zero rows unchanged.

    Args:
        matrix: Shape ``(n, dim)`` float array.

    Returns:
        Same shape, float32, unit-length rows where the norm is non-zero.
    """
    stacked = np.asarray(matrix, dtype=np.float32)
    if stacked.ndim != 2:
        raise ValueError(f"Expected a 2-D matrix, got shape {stacked.shape}.")
    norms = np.linalg.norm(stacked, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0.0, 1.0, norms)
    return np.asarray(stacked / safe_norms, dtype=np.float32)


def pairwise_cosine_similarity(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return cosine similarities between two sets of vectors.

    Args:
        left: Shape ``(n, dim)``.
        right: Shape ``(m, dim)``.

    Returns:
        Shape ``(n, m)`` float32 similarities in ``[-1, 1]``.
    """
    if left.size == 0 or right.size == 0:
        n = 0 if left.size == 0 else int(left.shape[0])
        m = 0 if right.size == 0 else int(right.shape[0])
        return np.asarray(np.zeros((n, m)), dtype=np.float32)
    product = l2_normalize_rows(left) @ l2_normalize_rows(right).T
    return np.asarray(product, dtype=np.float32)


def weighted_l2_centroid(vectors: list[np.ndarray], weights: list[int]) -> np.ndarray:
    """Return the L2-normalised weighted mean of vectors.

    Args:
        vectors: Non-empty list of 1-D embeddings.
        weights: Positive weights aligned with ``vectors``.

    Returns:
        Shape ``(dim,)`` float32 unit vector.

    Raises:
        ValueError: If inputs are empty or weights are not positive.
    """
    if not vectors or not weights or len(vectors) != len(weights):
        raise ValueError("vectors and weights must be non-empty and the same length.")
    total = sum(weights)
    if total <= 0:
        raise ValueError("Total weight must be positive.")
    stacked = np.stack([np.asarray(vector, dtype=np.float64).reshape(-1) for vector in vectors])
    weighted = np.average(stacked, axis=0, weights=np.asarray(weights, dtype=np.float64))
    norm = float(np.linalg.norm(weighted))
    if norm == 0.0:
        return np.asarray(weighted, dtype=np.float32)
    return np.asarray(weighted / norm, dtype=np.float32)


def update_pyr_centroid(
    existing: ExistingCluster,
    new_vectors: list[np.ndarray],
) -> tuple[np.ndarray, int]:
    """Fold new high-angle embeddings into an existing PYR centroid.

    Args:
        existing: Cluster that already has a PYR centroid.
        new_vectors: Newly assigned high-angle embeddings.

    Returns:
        Updated PYR centroid and PYR member count.

    Raises:
        ValueError: If there are no new vectors or the cluster has no PYR centroid.
    """
    if not new_vectors:
        raise ValueError("Cannot update a PYR centroid without new embeddings.")
    if existing.pyr_centroid is None:
        raise ValueError("Cannot update PYR centroid because the cluster has none.")
    old_size = existing.pyr_size if existing.pyr_size > 0 else 1
    centroid = weighted_l2_centroid(
        [existing.pyr_centroid, *new_vectors],
        [old_size, *[1] * len(new_vectors)],
    )
    return centroid, old_size + len(new_vectors)


def dual_centroid_similarity_matrix(
    orphan_centroids: np.ndarray,
    orphan_pyr_centroids: np.ndarray | None,
    orphan_pyr_mask: np.ndarray,
    established_centroids: np.ndarray,
    established_pyr_centroids: np.ndarray | None,
    established_pyr_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Compare orphans to established clusters with three cosine channels.

    Channels (take the per-pair maximum):

    1. orphan centroid vs established centroid
    2. orphan centroid vs established PYR (when the target has PYR)
    3. orphan PYR vs established PYR (when both have PYR)

    Orphan PYR vs established main centroid is intentionally omitted.

    Args:
        orphan_centroids: Shape ``(n, dim)``.
        orphan_pyr_centroids: Shape ``(n, dim)`` or ``None``.
        orphan_pyr_mask: Shape ``(n,)`` bool — True where orphan PYR exists.
        established_centroids: Shape ``(m, dim)``.
        established_pyr_centroids: Shape ``(m, dim)`` or ``None``.
        established_pyr_mask: Shape ``(m,)`` bool — True where target PYR exists.

    Returns:
        ``similarities`` of shape ``(n, m)`` and integer match-type codes of
        the same shape (0 = centroid, 1 = centroid_vs_pyr, 2 = pyr_centroid).
    """
    sim_centroid = pairwise_cosine_similarity(orphan_centroids, established_centroids)
    combined = sim_centroid.copy()
    match_codes = np.zeros(sim_centroid.shape, dtype=np.int8)

    if established_pyr_centroids is not None and bool(np.any(established_pyr_mask)):
        sim_centroid_vs_pyr = pairwise_cosine_similarity(
            orphan_centroids,
            established_pyr_centroids,
        )
        est_mask = established_pyr_mask.reshape(1, -1)
        better = est_mask & (sim_centroid_vs_pyr > combined)
        combined = np.where(better, sim_centroid_vs_pyr, combined)
        match_codes = np.where(better, 1, match_codes).astype(np.int8)

        if orphan_pyr_centroids is not None and bool(np.any(orphan_pyr_mask)):
            sim_pyr = pairwise_cosine_similarity(orphan_pyr_centroids, established_pyr_centroids)
            both_mask = orphan_pyr_mask.reshape(-1, 1) & est_mask
            better_pyr = both_mask & (sim_pyr > combined)
            combined = np.where(better_pyr, sim_pyr, combined)
            match_codes = np.where(better_pyr, 2, match_codes).astype(np.int8)

    return combined.astype(np.float32), match_codes


def match_type_name(code: int) -> str:
    """Map a dual-centroid channel code to a stable string name.

    Args:
        code: 0, 1, or 2.

    Returns:
        One of ``centroid``, ``centroid_vs_pyr``, ``pyr_centroid``.
    """
    if 0 <= code < len(_MATCH_CODE_TO_NAME):
        return _MATCH_CODE_TO_NAME[code]
    return MATCH_CENTROID
