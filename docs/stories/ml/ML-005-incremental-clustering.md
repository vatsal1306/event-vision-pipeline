# ML-005 — Incremental Clustering with Sweeper Config

**Type:** Feature
**Depends on:** ML-001
**Area:** `backend/app/ml/clustering/`

## Goal

Port the PicSee/pix-workers two-stage incremental clustering algorithm:
DBSCAN → centroid computation → Agglomerative merge. Include the **Sweeper** config
from pix-workers that handles high-angle (47°–120°) faces in a second pass.

The algorithm is **pure numpy/sklearn with no database dependencies** — it takes an
input dictionary of embeddings + existing cluster centroids and returns a result
dictionary of new/expanded/merged clusters.

## PicSee / pix-workers Source Files

| Source File | SpotMe Target | LOC | Notes |
|-------------|---------------|-----|-------|
| PicSee notebook → `Clustering` class (Cells 22–26) | `clustering/incremental_clusterer.py` | ~250 | Core algorithm |
| PicSee notebook → `EmbeddingDatabase` (Cell 22) | Not needed — SpotMe uses pgvector | ~100 | In-memory pandas tables — replaced by ML-006 |
| pix-workers `clustering_service/clustering.py` | `clustering/incremental_clusterer.py` | 692 | Production version (same algorithm, cleaner) |
| pix-workers `clustering_service/clustering_config.py` | `clustering/clustering_config.py` | 42 | Cluster vs Sweeper type configs |
| PicSee `update_crops_reject_situation.md` | Reference doc | — | I/O contract documentation |

## Algorithm: Two-Stage Incremental Clustering

```
┌─────────────────────────────────────────────────────────────┐
│  Input:                                                      │
│    - new_embeddings: dict[crop_id → 512-d vector]           │
│    - existing_clusters: dict[cluster_id → {centroid, size}] │
│    - clustering_type: "cluster" | "sweeper"                 │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  1. MERGE: Combine existing centroids as pseudo-embeddings  │
│     with new embeddings into a single matrix                │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. DBSCAN (cosine, eps=0.45, min_samples=1)               │
│     → Micro-clusters (tight groupings)                     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CENTROIDS: Compute mean of each DBSCAN cluster         │
│     → L2-normalize each centroid                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. AGGLOMERATIVE (cosine, average linkage, threshold=0.45)│
│     Merge micro-clusters into macro-clusters               │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  5. CLASSIFY: For each resulting cluster, determine:       │
│     - new_cluster: all members are new embeddings          │
│     - expanded_cluster: mix of existing centroid + new     │
│     - merged_cluster: two+ existing clusters combined      │
│  6. CENTROID UPDATE: Weighted mean of old + new members    │
└─────────────────────────────────────────────────────────────┘
```

## Clustering Types (from pix-workers)

```python
@dataclass
class ClusteringTypeConfig:
    name: str
    creates_new_clusters: bool
    expands_existing: bool
    centroid_field: str           # Which centroid to use for matching
    pyr_range: tuple[float, float]  # (min_degrees, max_degrees) for YPR filter

CLUSTER_TYPE = ClusteringTypeConfig(
    name="cluster",
    creates_new_clusters=True,
    expands_existing=True,
    centroid_field="centroid",
    pyr_range=(0.0, 47.0),
)

SWEEPER_TYPE = ClusteringTypeConfig(
    name="sweeper",
    creates_new_clusters=False,    # Sweeper only expands, never creates
    expands_existing=True,
    centroid_field="centroid",     # Matches against regular centroid
    pyr_range=(47.0, 120.0),      # Only processes high-angle faces
)
```

### Sweeper Workflow
1. Regular clustering pass runs first (PYR 0°–47°)
2. Sweeper pass runs on faces that failed the regular PYR filter (47°–120°)
3. Sweeper can **expand** existing clusters but NOT create new ones
4. After sweeper, update `pyr_centroid` (separate centroid for angled faces)

## Data Structures

### Input

```python
@dataclass
class ClusteringInput:
    new_embeddings: dict[str, np.ndarray]
    # crop_id → 512-d embedding vector

    existing_clusters: dict[str, ExistingCluster]
    # cluster_id → {centroid, pyr_centroid, size, crop_ids}

    clustering_type: ClusteringTypeConfig

@dataclass
class ExistingCluster:
    centroid: np.ndarray          # 512-d, L2-normalized
    pyr_centroid: np.ndarray | None  # Separate centroid for high-angle faces
    size: int                     # Number of crops in cluster
    crop_ids: list[str]           # IDs of crops in this cluster
```

### Output

```python
@dataclass
class ClusteringResult:
    new_clusters: list[NewCluster]
    expanded_clusters: list[ExpandedCluster]
    merged_clusters: list[MergedCluster]
    unassigned_crop_ids: list[str]  # Crops that couldn't be clustered

@dataclass
class NewCluster:
    cluster_id: str               # UUID
    centroid: np.ndarray          # 512-d
    crop_ids: list[str]
    size: int

@dataclass
class ExpandedCluster:
    cluster_id: str               # Existing cluster ID
    new_centroid: np.ndarray      # Weighted updated centroid
    new_crop_ids: list[str]       # Only the new additions
    new_size: int                 # Updated total size

@dataclass
class MergedCluster:
    surviving_cluster_id: str     # Kept cluster (largest)
    absorbed_cluster_ids: list[str]  # Clusters merged into survivor
    new_centroid: np.ndarray
    all_crop_ids: list[str]
    new_size: int
```

## Weighted Centroid Update

When expanding a cluster (adding new embeddings to existing):
```python
def update_centroid(old_centroid, old_size, new_embeddings):
    total = old_size + len(new_embeddings)
    weighted = (old_centroid * old_size + np.sum(new_embeddings, axis=0)) / total
    return weighted / np.linalg.norm(weighted)  # L2-normalize
```

## Parameters

| Parameter | Default | Config Key | Notes |
|-----------|---------|------------|-------|
| DBSCAN metric | cosine | Hardcoded | Must be cosine for face embeddings |
| DBSCAN eps | 0.45 | `ML_DBSCAN_EPS` | Cosine distance threshold |
| DBSCAN min_samples | 1 | `ML_DBSCAN_MIN_SAMPLES` | Every face is meaningful |
| Agglo metric | cosine | Hardcoded | Must match DBSCAN |
| Agglo linkage | average | Hardcoded | Average linkage (not complete/single) |
| Agglo threshold | 0.45 | `ML_AGGLO_THRESHOLD` | Distance threshold for merge |
| Batch size | 5000 | `ML_CLUSTERING_BATCH_SIZE` | Max embeddings per clustering run |

**Cosine distance 0.45 ≈ cosine similarity ≥ 0.55** — empirically tuned on Indian wedding data (PicSee production).

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/clustering/__init__.py` | Create |
| `backend/app/ml/clustering/incremental_clusterer.py` | Create — port from pix-workers `clustering.py` |
| `backend/app/ml/clustering/clustering_config.py` | Create — port from pix-workers |
| Unit tests with synthetic embeddings | Create |

## Acceptance

- [ ] Two identical embeddings + empty existing → one `new_cluster` with size 2
- [ ] New embedding near existing centroid → `expanded_clusters` with updated centroid
- [ ] Two centroids that should merge → `merged_clusters` with largest as survivor
- [ ] Sweeper type: never produces `new_clusters`, only `expanded_clusters`
- [ ] Weighted centroid update is L2-normalized
- [ ] Batch of 5000+ embeddings processes without memory issues
- [ ] Pure numpy/sklearn — no database imports in this module
- [ ] All parameters configurable via `MLConfig`
