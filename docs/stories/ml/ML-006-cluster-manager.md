# ML-006 — Cluster Persistence with pgvector

**Type:** Feature
**Depends on:** BE-003, ML-005
**Area:** `backend/app/ml/clustering/cluster_manager.py`

## Goal

Bridge the pure-algorithm `IncrementalClusterer` (ML-005) with SpotMe's PostgreSQL +
pgvector database. `ClusterManager` loads existing clusters and unclustered embeddings,
invokes clustering, and applies results (new/expanded/merged clusters) in a single
database transaction.

## SpotMe Database Schema (Existing from BE-003)

### `face_embeddings` table
```sql
id              UUID PRIMARY KEY
photo_id        UUID REFERENCES photos(id)
event_id        UUID REFERENCES events(id)
cluster_id      UUID REFERENCES face_clusters(id)  -- NULL until clustered
embedding       vector(512)                         -- Primary (R100)
secondary_embedding vector(512)                     -- Secondary (AdaFace) [added by ML-004]
bbox_x, bbox_y, bbox_w, bbox_h  REAL               -- Normalized 0–1
detection_score REAL
blur_score      REAL
yaw, pitch, roll REAL                               -- Degrees
quality_passed  BOOLEAN
created_at      TIMESTAMPTZ
```

### `face_clusters` table
```sql
id              UUID PRIMARY KEY
event_id        UUID REFERENCES events(id)
centroid        vector(512)                         -- Primary centroid
pyr_centroid    vector(512)                         -- High-angle face centroid (from sweeper)
secondary_centroid vector(512)                      -- AdaFace centroid
cluster_size    INTEGER
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### New columns needed (migration)
- `face_clusters.pyr_centroid vector(512)` — for sweeper pass centroid tracking
- `face_clusters.secondary_centroid vector(512)` — for dual-model centroid
- `face_embeddings.secondary_embedding vector(512)` — for AdaFace embeddings
- `face_embeddings.yaw, pitch, roll REAL` — for YPR angle storage
- `face_embeddings.quality_passed BOOLEAN` — whether face passed quality filters

## ClusterManager API

```python
class ClusterManager:
    """Manages cluster state between pgvector and IncrementalClusterer."""

    async def load_event_clusters(self, event_id: UUID) -> dict[str, ExistingCluster]:
        """Load all clusters for an event from face_clusters table."""

    async def load_unclustered_embeddings(
        self, event_id: UUID, clustering_type: ClusteringTypeConfig
    ) -> dict[str, np.ndarray]:
        """
        Load embeddings without cluster_id, filtered by PYR range.
        - For "cluster" type: yaw/pitch/roll all within 0–47°
        - For "sweeper" type: at least one angle in 47–120°
        """

    async def apply_clustering_result(
        self, event_id: UUID, result: ClusteringResult
    ) -> None:
        """
        Apply clustering result in a single transaction:
        1. INSERT new face_clusters rows for new_clusters
        2. UPDATE centroid + size for expanded_clusters
        3. Reassign crop cluster_ids + DELETE absorbed clusters for merged_clusters
        """

    async def run_clustering_pass(
        self, event_id: UUID, clustering_type: ClusteringTypeConfig
    ) -> ClusteringResult:
        """
        Full clustering pass:
        1. Load existing clusters
        2. Load unclustered embeddings (filtered by PYR range)
        3. Batch into groups of clustering_batch_size
        4. Run IncrementalClusterer for each batch
        5. Apply results to DB
        """
```

## Batching Strategy

For events with 15,000+ photos (~22,500 faces at 1.5 faces/photo):
1. Load all existing cluster centroids (typically < 500 clusters)
2. Load unclustered embeddings in batches of 5000
3. For each batch: run `IncrementalClusterer.cluster()`, apply results, reload centroids
4. Repeat until no unclustered embeddings remain

```python
async def run_clustering_pass(self, event_id, clustering_type):
    while True:
        existing = await self.load_event_clusters(event_id)
        unclustered = await self.load_unclustered_embeddings(
            event_id, clustering_type, limit=self.config.clustering_batch_size
        )
        if not unclustered:
            break

        result = self.clusterer.cluster(
            ClusteringInput(
                new_embeddings=unclustered,
                existing_clusters=existing,
                clustering_type=clustering_type,
            )
        )
        await self.apply_clustering_result(event_id, result)
```

## Centroid Management

### Weighted Centroid Update on Expand
When new embeddings are added to an existing cluster:
```python
new_centroid = (old_centroid * old_size + sum(new_embeddings)) / new_size
new_centroid = new_centroid / np.linalg.norm(new_centroid)  # L2-normalize
```

### PYR Centroid (for Sweeper)
A separate `pyr_centroid` column tracks the centroid computed from high-angle faces only.
Updated during sweeper pass. Used by orphan crop recovery (ML-007).

### Secondary Centroid (for Dual-Model)
If dual-model is enabled, `secondary_centroid` is computed from AdaFace embeddings.
Used for cross-validation during selfie matching (ML-008).

## Concurrency Control

SpotMe processes photos in bulk after upload completion. Multiple clustering tasks
could theoretically run for the same event. Use a Redis distributed lock:

```python
CLUSTERING_LOCK_KEY = "clustering_lock:{event_id}"
CLUSTERING_LOCK_TIMEOUT = 300  # 5 minutes
```

If lock acquisition fails, the task retries with exponential backoff.

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/clustering/cluster_manager.py` | Create |
| Alembic migration: add `pyr_centroid`, `secondary_centroid`, YPR columns | Create |
| Integration tests with test database | Create |

## Acceptance

- [x] Integration test: insert 10 embeddings, run clustering, verify `cluster_id` set on all
- [x] Second batch of 5 embeddings near existing clusters → `expanded_clusters`, centroid updated
- [x] After merge: absorbed cluster row deleted, crops reassigned, no orphan cluster rows
- [x] PYR filter: cluster pass only loads faces with angles < 47°
- [x] PYR filter: sweeper pass only loads faces with angles 47°–120°
- [x] Concurrent clustering for same event → Redis lock prevents race condition
- [x] Transaction rollback on error → no partial cluster state

## Implementation Notes (ML-006 — completed)

**Shipped:**
- `cluster_manager.py` — load, PYR SQL filters, Redis lock, batched `run_clustering_pass`
- `cluster_persistence.py` — transactional new/expand/merge writes
- `locks.py` — token SET NX lock (compatible with `decode_responses=True`)
- Alembic `add_clustering_persistence` — YPR, `quality_passed`, `pyr_centroid`, `secondary_centroid`, **`pyr_size`**
- Integration tests against local Postgres + Redis (`tests/ml/test_cluster_manager.py`)

**Decisions vs original story:**
- Cluster PYR uses `[0, 47)` so 47° is sweeper-only (no overlap).
- Sweeper leftovers are attempted once per pass (no infinite loop).
- Merge keeps the ML-005 survivor ID (not a newly inserted cluster).
- Lock TTL is 900s with per-batch extend (story's 300s is too short for 10–20k photos).
- `pyr_size` added for weighted PYR centroid updates (PicSee `pyr_centroid_crop_count`).
- Secondary centroids are recomputed from AdaFace member vectors after each batch.
- Celery task deferred to ML-009.
