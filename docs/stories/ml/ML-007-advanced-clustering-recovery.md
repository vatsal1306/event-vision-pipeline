# ML-007 — Advanced Clustering Recovery: Orphan Crops and Orphan Clusters

**Type:** Feature
**Depends on:** ML-005, ML-006
**Area:** `backend/app/ml/clustering/recovery/`

## Goal

Port two recovery algorithms from pix-workers production that significantly improve
clustering **recall** — catching faces that the primary DBSCAN + Agglomerative pass
misses. These are critical for Indian wedding photography where extreme poses, varying
lighting, and makeup changes cause faces to scatter across clusters.

### What This Solves

After the main clustering pass (ML-005) + sweeper (ML-005), there are still two
categories of "lost" faces:

1. **Orphan Crops** — face crops whose YPR angles fell in the sweeper range (47°–120°)
   but the sweeper couldn't match them to any existing cluster. These are high-angle
   faces that are too far from any centroid.

2. **Orphan Clusters** — small clusters (often singletons) that are actually the same
   person as a larger cluster but didn't merge during agglomerative clustering because
   the sample was insufficient.

## PicSee / pix-workers Source Files

| Source File | SpotMe Target | LOC | Notes |
|-------------|---------------|-----|-------|
| pix-workers `clustering_service/orphan_crops.py` | `clustering/recovery/orphan_crops.py` | 223 | Bulk cosine distance matching |
| pix-workers `clustering_service/orphan_clusters.py` | `clustering/recovery/orphan_clusters.py` | 392 | Dual-centroid cluster merging |

**Note**: Both source files are tightly coupled to pix-workers' PostgreSQL queries.
The SpotMe port must **extract the pure algorithm** and adapt it to use `ClusterManager`
(ML-006) for data access.

## Algorithm 1: Orphan Crop Recovery

### Problem
After sweeper pass, some high-angle crops have `cluster_id = NULL` and `quality_passed = True`.
These are valid faces that just don't match well with any existing centroid.

### Solution
1. Load all orphan crops (unclustered, YPR > 47°)
2. Load all cluster `pyr_centroid`s (not regular centroids — use the high-angle centroid)
3. Compute cosine similarity between each orphan and each `pyr_centroid`
4. Assign orphan to the closest cluster IF similarity ≥ threshold (0.55)
5. Update `pyr_centroid` with the newly assigned crop

```python
class OrphanCropRecovery:
    """Recovers unassigned high-angle face crops by matching against PYR centroids."""

    SIMILARITY_THRESHOLD = 0.55  # More lenient than clustering (0.55 vs 0.45 distance)

    async def recover(self, event_id: UUID) -> RecoveryResult:
        """
        1. Load orphan crops (no cluster_id, YPR in sweeper range)
        2. Load all cluster pyr_centroids
        3. Bulk cosine similarity matrix
        4. Assign best match above threshold
        5. Update pyr_centroids
        """
        orphans = await self.cluster_manager.load_orphan_crops(event_id)
        clusters = await self.cluster_manager.load_event_clusters(event_id)

        if not orphans or not clusters:
            return RecoveryResult(recovered=0, still_orphaned=len(orphans))

        # Build matrices
        orphan_matrix = np.stack([o.embedding for o in orphans])
        centroid_matrix = np.stack([
            c.pyr_centroid if c.pyr_centroid is not None else c.centroid
            for c in clusters.values()
        ])

        # Cosine similarity matrix: (n_orphans, n_clusters)
        similarities = orphan_matrix @ centroid_matrix.T

        # Assign each orphan to best match above threshold
        for i, orphan in enumerate(orphans):
            best_idx = np.argmax(similarities[i])
            if similarities[i, best_idx] >= self.SIMILARITY_THRESHOLD:
                await self.cluster_manager.assign_crop_to_cluster(
                    orphan.crop_id, cluster_ids[best_idx]
                )
                recovered += 1
```

## Algorithm 2: Orphan Cluster Merge

### Problem
After all clustering passes, some small clusters (size 1–3) represent the same person
as a larger cluster. This happens when a person's face appears very different in one or
two photos (e.g., profile shot, heavy makeup).

### Solution
1. Identify "orphan clusters" — clusters with size ≤ `max_orphan_size` (default: 3)
2. For each orphan cluster, compute cosine similarity of its centroid against all
   larger clusters' centroids
3. Also compare `pyr_centroid` if available (dual-centroid comparison)
4. If best match exceeds threshold (0.55), merge the orphan into the larger cluster

```python
class OrphanClusterMerge:
    """Merges small clusters into larger ones when they likely represent the same person."""

    MAX_ORPHAN_SIZE = 3
    MERGE_THRESHOLD = 0.55
    USE_DUAL_CENTROID = True  # Compare both regular and PYR centroids

    async def merge(self, event_id: UUID) -> MergeResult:
        """
        1. Load all clusters for event
        2. Separate into orphans (size ≤ 3) and established (size > 3)
        3. For each orphan, find closest established cluster
        4. If dual_centroid: also compare pyr_centroids, take max similarity
        5. Merge if above threshold
        """
```

### Dual-Centroid Comparison
```python
def dual_centroid_similarity(orphan_cluster, target_cluster):
    """Compare using both regular and PYR centroids — take maximum."""
    sim_regular = cosine_similarity(orphan_cluster.centroid, target_cluster.centroid)
    sim_pyr = 0.0
    if orphan_cluster.pyr_centroid is not None and target_cluster.pyr_centroid is not None:
        sim_pyr = cosine_similarity(orphan_cluster.pyr_centroid, target_cluster.pyr_centroid)
    return max(sim_regular, sim_pyr)
```

## Recovery Pipeline Order

```
1. Main clustering pass (ML-005, type="cluster", PYR 0–47°)
2. Sweeper pass (ML-005, type="sweeper", PYR 47–120°)
3. Orphan crop recovery (this story)
4. Orphan cluster merge (this story)
```

Each step is sequential — later steps depend on results of earlier ones.

## Data Structures

```python
@dataclass
class RecoveryResult:
    recovered: int           # Crops successfully assigned to clusters
    still_orphaned: int      # Crops still without a cluster
    details: list[dict]      # Per-crop: crop_id, assigned_cluster_id, similarity

@dataclass
class MergeResult:
    merged_count: int        # Orphan clusters absorbed
    remaining_orphans: int   # Small clusters that didn't match
    details: list[dict]      # Per-merge: orphan_id, target_id, similarity
```

## Future Enhancement: Missing Friends (Not in Scope)

pix-workers has a third recovery algorithm — **Missing Friends** — that uses
**photo timestamp proximity** (±12 hours) to associate unclustered faces with nearby
clusters. This requires EXIF timestamp data and is complex to adapt.

**Recommendation**: Defer to Phase 2 after evaluating orphan crop/cluster recovery performance.

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/clustering/recovery/__init__.py` | Create |
| `backend/app/ml/clustering/recovery/orphan_crops.py` | Create — extract algorithm from pix-workers |
| `backend/app/ml/clustering/recovery/orphan_clusters.py` | Create — extract algorithm from pix-workers |
| Integration tests with synthetic clusters | Create |

## Acceptance

- [ ] Orphan crop with high cosine similarity to a PYR centroid → assigned to that cluster
- [ ] Orphan crop with low similarity to all centroids → remains unassigned
- [ ] Small cluster (size 2) matching a large cluster (size 50) → merged into large cluster
- [ ] Orphan cluster NOT matching any established cluster → remains independent
- [ ] Dual-centroid comparison uses max of regular and PYR similarity
- [ ] Recovery runs after sweeper pass without errors
- [ ] No database state corruption — all operations are transactional
- [ ] Feature gated by `ML_ORPHAN_RECOVERY_ENABLED` config flag
