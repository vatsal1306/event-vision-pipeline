# ML Pipeline — Agent Reference (ML-001+)

This document tracks ML infrastructure decisions for AI agents working on later stories.

## Package Layout

```
backend/app/ml/
├── config.py           # MLConfig (pydantic-settings, ML_ env prefix)
├── device.py           # resolve_device() — cuda / mps / cpu
├── exceptions.py       # ModelNotRegisteredError, ModelLoadError
├── model_registry.py   # Thread-safe lazy singleton + register_model_loader()
├── detection/          # ML-002 — SCRFD + FaceCropper (done)
│   ├── scrfd.py
│   ├── face_cropper.py
│   ├── types.py
│   ├── onnx_providers.py
│   └── registry.py
├── face_preprocess.py  # ML-002 — ArcFace alignment utils
├── tflite_interpreter.py  # LiteRT factory for all .tflite models
├── quality/            # ML-003 — blur, YPR, age, sunglasses (done)
│   ├── blur_detector.py
│   ├── ypr_3ddfa.py
│   ├── ypr_tflite.py
│   ├── age_detector.py
│   ├── sunglasses.py
│   ├── quality_filter.py
│   ├── types.py
│   └── registry.py
├── embedding/          # ML-004 — dual embeddings (done)
│   ├── base.py
│   ├── arcface_r100.py
│   ├── adaface_vit_kprpe.py
│   ├── mobilefacenet.py
│   ├── dual_embedder.py
│   ├── batch_utils.py
│   ├── mode.py
│   ├── types.py
│   └── registry.py
├── clustering/         # ML-005, ML-006, ML-007
│   ├── incremental_clusterer.py  # DBSCAN + Agglomerative (done)
│   ├── clustering_config.py      # Cluster vs Sweeper configs (done)
│   ├── types.py                  # Input/output dataclasses (done)
│   ├── cluster_manager.py        # Load + lock + batched pass (ML-006)
│   ├── cluster_persistence.py    # Transactional DB writes (ML-006)
│   ├── vector_utils.py           # pgvector numpy helpers (ML-006)
│   ├── locks.py                  # Redis event clustering lock (ML-006)
│   └── recovery/                 # ML-007 (done)
│       ├── orphan_crops.py
│       ├── orphan_clusters.py
│       ├── similarity.py
│       └── types.py
├── matching/           # ML-008
└── vendor/             # PicSee / pix-workers code copies
    └── ypr_3ddfa_v2/   # 3DDFA FaceBoxes + TDDFA ONNX (ML-003)
```

Model weight files live in `backend/models/` (git-ignored).

## Configuration

- **Class:** `app.ml.config.MLConfig`
- **Accessor:** `get_ml_config()` (cached singleton)
- **Env prefix:** `ML_` (e.g. `ML_DEVICE=cpu`, `ML_BLUR_THRESHOLD=0.6`)
- **Path resolution:** Relative paths resolve against `backend/` via `models_path` and `resolve_model_path()`

### Device Selection

`ML_DEVICE` accepts `auto`, `cuda`, `mps`, or `cpu`.

| Value | Behaviour |
|-------|-----------|
| `auto` | CUDA if available, else CPU for ONNX; PyTorch still uses MPS on Apple Silicon |
| `cuda` | CUDA if available, else CPU |
| `mps` | PyTorch on Apple MPS; **ONNX SCRFD uses CPU** (CoreML EP breaks 128×128 pass) |
| `cpu` | Always CPU |

Use `ModelRegistry.resolved_device` or `resolve_device(config.device)` — both lazy-import torch.

## Model Registry

- **Accessor:** `get_model_registry()`
- **Pattern:** Later stories call `register_model_loader("scrfd", loader_fn)` at module import time
- **Loading:** `registry.get_model("scrfd")` lazy-loads once per process, thread-safe
- **Teardown:** `registry.unload_all()` for tests and worker shutdown

### Worker Context Policy (ML-001 decision)

- **Default:** Warn but allow model loading outside Celery workers (local dev + pytest)
- **Strict mode:** Set `ML_STRICT_WORKER_ONLY=true` to block non-worker loads (production ML host)
- FastAPI startup never calls `get_model()` — models load only when explicitly requested

## Dependencies

ML packages are optional. Install with:

```bash
cd backend
uv sync --extra dev --extra ml
```

### Pinned Versions (PicSee compatibility, Python 3.10)

| Package | Version | Source |
|---------|---------|--------|
| torch | 2.6.0 | pix-workers production |
| torchvision | 0.21.0 | pix-workers production |
| onnxruntime | >=1.20.1 | pix-workers + clustering_pipeline |
| ai-edge-litert | >=2.1 | TFLite inference (blur, YPR, MBF) — replaces deprecated `tf.lite.Interpreter` |
| timm | >=1.0.29 | AdaFace VIT-KPRPE backbone |
| easydict | >=1.13 | AdaFace VIT-KPRPE RPE config |
| safetensors | >=0.8.0 | AdaFace/DFA weight loading |

> Note: `clustering_pipeline` pins torch 2.7.1 but requires Python 3.12. We use pix-workers'
> torch 2.6.0 for Python 3.10 compatibility.

## What ML-001 Delivered vs Deferred

| Delivered (ML-001) | Deferred to |
|--------------------|-------------|
| `MLConfig` with all thresholds/paths | — |
| `ModelRegistry` singleton + loader registration API | — |
| Empty subpackage tree | — |
| `resolve_device()` with cuda/mps/cpu | — |
| Import safety (no torch/onnx/tf at import) | — |
| SCRFD detector + FaceCropper | ML-002 (done) |
| Vendor code copies | ML-003 (ypr_3ddfa_v2), ML-004 |
| Model weight files on disk | Manual copy by developer |
| Quality filters | ML-003 (done) |
| Embeddings (R100, AdaFace, MBF) | ML-004 (done) |
| Clustering algorithm | ML-005 (done) |
| Cluster persistence (pgvector) | ML-006 (done) |
| Orphan crop/cluster recovery | ML-007 (done) |
| FaceService + Celery tasks | ML-009 |

## ML-003 — Quality Filters

| Module | Purpose |
|--------|---------|
| `quality/blur_detector.py` | TFLite blur score — reject when score **>** `ML_BLUR_THRESHOLD` |
| `quality/ypr_3ddfa.py` | 3DDFA_V2 ONNX YPR (primary) + unified `YPRPredictor` |
| `quality/ypr_tflite.py` | TFLite YPR fallback |
| `quality/age_detector.py` | Local ViT snapshot (`ML_AGE_MODEL_DIR`, default `vit-age-classifier`) |
| `quality/sunglasses.py` | Optional `glasses-detector` (Python 3.12+ only; inactive on 3.10) |
| `quality/quality_filter.py` | Orchestrator with early exit + pass-on-error |
| `quality/registry.py` | Registers `blur_detector`, `ypr_predictor`, `age_detector`, `sunglasses_detector`, `quality_filter` |

### Model Files

| File | Location |
|------|----------|
| Blur TFLite | `models/blur_model_tflite_may6_ckpt49.tflite` |
| YPR TFLite fallback | `models/ypr_model_float32.tflite` |
| 3DDFA ResNet22 | `models/resnet22.onnx` |
| FaceBoxes | `models/FaceBoxesProd.onnx` |
| 3DDFA config + stats | `models/ypr_3ddfa_v2/resnet_config.yml`, `param_mean_std_62d_120x120.pkl` |
| Age ViT snapshot | `models/vit-age-classifier/` (local HuggingFace export) |

Download age model once:

```bash
cd backend
huggingface-cli download nateraw/vit-age-classifier \
  --local-dir models/vit-age-classifier \
  --local-dir-use-symlinks False
```

Keep `config.json`, `preprocessor_config.json`, and `model.safetensors` (drop duplicate `pytorch_model.bin` to save space).

### Filter Behaviour

| Gate | Hard reject? | Embedding |
|------|--------------|-----------|
| Blur (score > threshold) | Yes (`reject_reason="blur"`) | Skip |
| YPR (angle exceeds thresholds) | Yes (`reject_reason="ypr"`) | Skip |
| Age (< `ML_AGE_MIN_THRESHOLD`) | Yes (`reject_reason="age"`) | Skip |
| Sunglasses | No — soft flag only | Still embed |
| Model inference error | No — pass-on-error | Still embed |

**Early exit:** blur → YPR → age → sunglasses. Later gates are skipped after a hard reject.

**Blur semantics (PicSee production):** higher score = blurrier. Reject when `blur_score > ML_BLUR_THRESHOLD` (default `0.5`). Story wording was imprecise; implementation follows PicSee.

**YPR fallback:** TFLite is used only when 3DDFA **fails to initialize** or throws at runtime. When 3DDFA finds no face in the crop, we **pass-on-error** (do not fall back to TFLite).

**3DDFA NMS on macOS:** vendored FaceBoxes uses pure-Python NMS (`py_cpu_nms`) when the Cython extension is unavailable.

**TFLite runtime (ML-003):** blur and YPR TFLite models use the standalone `ai-edge-litert` package via `app/ml/tflite_interpreter.py`. This replaces the deprecated `tf.lite.Interpreter` removed in TensorFlow 2.20+ and drops the full TensorFlow dependency (~220 MB saved).

**Registry fix (ML-003):** `ModelRegistry` uses `threading.RLock` so composite loaders (e.g. `quality_filter`) can call `get_model()` recursively.

### Usage

```python
import app.ml.detection   # scrfd loader
import app.ml.quality.registry  # quality loaders
from app.ml.model_registry import get_model_registry

registry = get_model_registry()
quality = registry.get_model("quality_filter")

result = quality.filter(face_crop)
if result.passed:
    ...  # proceed to embedding in ML-004
```

Config flags: `ML_AGE_DETECTION_ENABLED`, `ML_SUNGLASSES_DETECTION_ENABLED`, `ML_YPR_MODEL_TYPE` (`3ddfa` | `tflite`).

### Testing

```bash
cd backend
uv run pytest tests/ml/test_quality_filter_unit.py tests/ml/test_quality_integration.py -v
uv run pytest tests/ml/test_age_detector_integration.py -v  # loads ViT; run separately if TF/torch conflict
```

Run age integration test separately from SCRFD tests if you see a Torch/Triton registration error (known TF+torch coexistence issue in one pytest process).

## ML-004 — Dual-Model Embeddings

| Module | Purpose |
|--------|---------|
| `embedding/arcface_r100.py` | Primary ArcFace R100 (PicSee normalization) |
| `embedding/adaface_vit_kprpe.py` | Secondary AdaFace VIT-KPRPE + DFA aligner |
| `embedding/mobilefacenet.py` | TFLite CPU fallback when GPU OOM persists |
| `embedding/dual_embedder.py` | Orchestrator — primary + optional secondary |
| `embedding/registry.py` | Registers `arcface_r100`, `adaface_vit_kprpe`, `mobilefacenet`, `dual_embedder` |
| `vendor/adaface_insightface/backbones.py` | R100 IResNet-100 architecture (vendor copy) |

### Model Files

| File | Location |
|------|----------|
| ArcFace R100 | `models/model_v1_scratch_training_epoch_20_r100.pt` |
| AdaFace VIT-KPRPE | `models/cvlface_adaface_vit_base_kprpe_webface12m/` |
| DFA Mobilenet aligner | `models/cvlface_DFA_mobilenet/` |
| MobileFaceNet TFLite | `models/preprocessed_transformation_mbf_model_w12m_RE10.tflite` |

Weights stay in `backend/models/` (git-ignored). HuggingFace model **code** for AdaFace/DFA lives alongside weights in those directories (not duplicated under `vendor/`).

**Weight loading (ML-004 decision):** `cvlface_loader.py` tries `pretrained_model/model.pt` then root `model.safetensors`, strips `model.` key prefixes from HuggingFace exports, and skips corrupt checkpoints. Some local copies ship truncated `.pt` files — safetensors is the reliable source for AdaFace VIT.

### Embedding Modes

| `ML_EMBEDDING_MODEL` | `ML_DUAL_MODEL_ENABLED` | Behaviour |
|----------------------|-------------------------|-----------|
| `dual` (default) | `true` (default) | R100 primary + AdaFace secondary |
| `r100` | any | R100 primary only |
| any | `false` | R100 primary only |

`adaface` and `mbf` are **not** standalone modes. MobileFaceNet is used only when R100 OOM persists at batch size 1.

### OOM Fallback Policy

1. Halve batch size on CUDA OOM (down to 1) for R100 and AdaFace.
2. If R100 still fails at batch size 1 → MobileFaceNet replaces primary for that batch.
3. If AdaFace fails → omit `secondary_embedding` (primary still stored).

### Database

Migration `add_secondary_embedding` adds nullable `face_embeddings.secondary_embedding vector(512)`. No HNSW index on secondary (matching uses cluster centroids in ML-006/ML-008).

### Usage

```python
import app.ml.embedding.registry  # registers loaders
from app.ml.model_registry import get_model_registry

embedder = get_model_registry().get_model("dual_embedder")
results = embedder.embed_batch([crop.aligned_face for crop in face_crops])

for result in results:
    primary = result.primary          # (512,) L2-normalized R100
    secondary = result.secondary      # (512,) or None
```

### Testing

```bash
cd backend
uv sync --extra dev --extra ml
uv run pytest tests/ml/test_embedding_unit.py -v
uv run pytest tests/ml/test_embedding_integration.py -v  # loads ~700MB of weights
```

## ML-002 — Detection and Cropping

| Module | Purpose |
|--------|---------|
| `detection/scrfd.py` | `SCRFDDetector` — multi-scale ONNX SCRFD (640+128) |
| `detection/face_cropper.py` | `crop_all()`, `crop_primary()`, detect+crop helpers |
| `detection/types.py` | `DetectedFace`, `FaceCrop` |
| `detection/onnx_providers.py` | CUDA / CoreML / CPU provider selection |
| `detection/registry.py` | Auto-registers `scrfd` loader |
| `face_preprocess.py` | `norm_crop` (pix-workers) + legacy `preprocess()` (PicSee fallback) |

**PicSee parity:** Ported from pix-workers `SCRFD` + `norm_crop`. Parity test in
`tests/ml/test_scrfd_crop.py` compares bbox/landmarks/score against pix-workers on the same image.

**Bbox clipping:** Raw SCRFD boxes are clipped to image bounds before normalizing to `[0, 1]` for DB.

### Usage

```python
import cv2
import app.ml.detection  # registers scrfd loader
from app.ml.detection import FaceCropper
from app.ml.model_registry import get_model_registry

detector = get_model_registry().get_model("scrfd")
image = cv2.imread("photo.jpg")
faces = detector.detect(image)

cropper = FaceCropper(detector=detector)
all_crops = cropper.crop_all(image, faces)       # upload: every face
selfie = cropper.crop_primary(image, faces)      # selfie: nose-closest-to-center
```

## ML-005 — Incremental Clustering

| Module | Purpose |
|--------|---------|
| `clustering/types.py` | Input/output dataclasses (`ClusteringInput`, `ClusteringResult`, …) |
| `clustering/clustering_config.py` | `CLUSTER_TYPE` (0–47°) and `SWEEPER_TYPE` (47–120°) |
| `clustering/incremental_clusterer.py` | DBSCAN → centroid → agglomerative merge (PicSee port) |

Pure numpy/sklearn — **no database imports**. Batching (5000 crops) is handled by ML-006; one `cluster()` call processes the full input list it receives.

### Algorithm

1. Inject existing cluster **main centroids** as pseudo-embeddings (`centroid_{id}`).
2. DBSCAN (cosine, `ML_DBSCAN_EPS`, `ML_DBSCAN_MIN_SAMPLES`, `algorithm=brute`).
3. L2-normalise per-group centroids.
4. Agglomerative merge (cosine, average linkage, `ML_AGGLO_THRESHOLD`).
5. Classify groups as **new**, **expanded**, or **merged**; DBSCAN noise → `unassigned_crop_ids`.

### Cluster vs Sweeper

| Pass | Creates new clusters | Merges existing | Updates main centroid | Updates pyr centroid |
|------|---------------------|-----------------|----------------------|----------------------|
| `CLUSTER_TYPE` | Yes | Yes (largest survives; tie → smaller id) | Yes | No |
| `SWEEPER_TYPE` | No → unassigned | No → unassigned crops | No | Yes (`new_pyr_centroid`, `new_pyr_size`) |

Sweeper matches against the **main** centroid (PicSee behaviour) but only writes the high-angle average. PicSee `face_rec_id` conflict resolution is **not** ported (no equivalent IDs yet).

### Config Keys

| Setting | Env var | Default |
|---------|---------|---------|
| DBSCAN eps | `ML_DBSCAN_EPS` | 0.45 |
| DBSCAN min samples | `ML_DBSCAN_MIN_SAMPLES` | 1 |
| Agglo threshold | `ML_AGGLO_THRESHOLD` | 0.45 |
| Batch size (ML-006) | `ML_CLUSTERING_BATCH_SIZE` | 5000 |
| Sweeper PYR min/max | `ML_SWEEPER_PYR_MIN` / `ML_SWEEPER_PYR_MAX` | 47 / 120 |

### Usage

```python
from app.ml.clustering import (
    CLUSTER_TYPE,
    SWEEPER_TYPE,
    ClusteringInput,
    ExistingCluster,
    IncrementalClusterer,
)

clusterer = IncrementalClusterer()
result = clusterer.cluster(
    ClusteringInput(
        new_embeddings={"crop-uuid": embedding_vector},  # (512,) float32, L2-normalised
        existing_clusters={
            "cluster-uuid": ExistingCluster(
                centroid=centroid_vector,
                size=12,
                crop_ids=["existing-crop"],
                pyr_centroid=None,
                pyr_size=0,
            )
        },
        clustering_type=CLUSTER_TYPE,
    )
)
```

### Testing

```bash
cd backend
uv sync --extra dev --extra ml
uv run pytest tests/ml/test_clustering_unit.py -v --no-cov
```

Synthetic embeddings only — no model weights or GPU required.

## ML-006 — Cluster Persistence (pgvector)

`ClusterManager` loads event clusters and unclustered embeddings from Postgres,
runs `IncrementalClusterer` in batches of `ML_CLUSTERING_BATCH_SIZE` (default 5000),
and writes results in **one DB transaction per batch**.

| Module | Purpose |
|--------|---------|
| `clustering/cluster_manager.py` | Load + PYR filter + Redis lock + batch loop |
| `clustering/cluster_persistence.py` | New / expand / merge writes + AdaFace centroid refresh |
| `clustering/locks.py` | Per-event Redis lock (`clustering_lock:{event_id}`) |

### Schema (migration `add_clustering_persistence`)

`face_embeddings`: `yaw`, `pitch`, `roll`, `quality_passed` (default false).
`face_clusters`: `pyr_centroid`, `secondary_centroid`, **`pyr_size`** (not in the original story; required for weighted sweeper centroid updates, matching PicSee `pyr_centroid_crop_count`).

Partial index `idx_face_embeddings_event_unclustered` on `event_id` where `cluster_id IS NULL AND quality_passed IS TRUE`.

`secondary_embedding` was already added by ML-004.

### Behaviour vs original story / component doc

| Topic | What we shipped |
|-------|-----------------|
| Merge | Keep the **largest surviving cluster** (ML-005). Do **not** insert a new cluster and delete all sources (old `component_ai_ml.md` sketch). Reassign members **before** deleting absorbed rows (`ON DELETE SET NULL`). |
| PYR cluster pass | All of `abs(yaw/pitch/roll)` in `[0, 47)` — 47° is sweeper, not cluster. |
| PYR sweeper pass | All angles `<= 120` and **at least one** `>= 47`. Angles `> 120` or missing YPR are skipped. |
| Quality | Only `quality_passed = true`. |
| Sweeper leftovers | Each face is tried **once per pass** (`exclude_ids`). Unassigned rows stay `cluster_id NULL` for ML-007. |
| Secondary centroid | Recomputed after each batch from members that have AdaFace vectors (L2-normalised mean). Clustering still uses R100 only. |
| Lock | Token-based SET NX (works with `decode_responses=True`). TTL **900s**, extended after every batch (10–20k wedding photos). Story's 300s is too short. Retry with exponential backoff then `ClusteringLockBusyError`. |
| Celery | Not in this story (ML-009). Call `run_clustering_pass` from a worker later. |

### Usage

```python
from app.core.redis_client import create_redis_client
from app.ml.clustering import CLUSTER_TYPE, SWEEPER_TYPE, ClusterManager

manager = ClusterManager(db_session, redis_client=create_redis_client())
await manager.run_clustering_pass(event_id, CLUSTER_TYPE)
await manager.run_clustering_pass(event_id, SWEEPER_TYPE)
```

### Testing

Needs local Postgres (pgvector) **and** Redis. Pytest migrates **`photoshare_test` only** — it does not stamp the developer `photoshare` database.

```bash
cd backend
docker compose up -d db redis
uv run pytest tests/ml/test_cluster_manager.py tests/ml/test_clustering_unit.py -v --no-cov
```

To migrate the developer database after this story, the Alembic head is `add_clustering_persistence`. If `alembic_version` points at a revision file that is not in git, stamp to `add_secondary_embedding` then `alembic upgrade head`. The clustering migration skips columns that already exist (an old deleted revision may have added `pyr_centroid` already).

## ML-007 — Orphan Crop Recovery and Orphan Cluster Merge

After cluster + sweeper, leftover high-angle faces and tiny same-person clusters are recovered in two sequential steps. **Missing Friends** (timestamp proximity) is not implemented.

| Module | Purpose |
|--------|---------|
| `clustering/recovery/orphan_crops.py` | Match unclustered sweeper-range faces to `pyr_centroid` |
| `clustering/recovery/orphan_clusters.py` | Merge clusters with size ≤ `ML_ORPHAN_CLUSTER_MAX_SIZE` |
| `clustering/recovery/similarity.py` | Bulk cosine + three-channel dual-centroid max |
| `ClusterManager.run_recovery()` | Redis lock, crop recovery, then cluster merge |

### Behaviour vs original story

| Topic | What we shipped |
|-------|-----------------|
| Orphan crop targets | **Only clusters with `pyr_centroid`** (pix-workers). No main-centroid fallback — sweeper already tried that. |
| Leftover definition | Same sweeper PYR SQL filter as ML-006 (`quality_passed`, `cluster_id` NULL). |
| Dual centroid | Max of (1) centroid vs centroid (2) orphan centroid vs established PYR (3) PYR vs PYR. **Skip** orphan PYR vs established main centroid. |
| Tiny cluster | `cluster_size <= 3` (no `face_rec_id`, no age delay). |
| On crop assign | Grow `cluster_size`, update `pyr_centroid`/`pyr_size`, **do not** move the main centroid. Several matches to one cluster → one PYR update per batch. |
| Thresholds | Inclusive cosine similarity ≥ 0.55 via `ML_ORPHAN_CROP_SIMILARITY_THRESHOLD` / `ML_ORPHAN_CLUSTER_MERGE_THRESHOLD`. |
| Flag | `ML_ORPHAN_RECOVERY_ENABLED` (default true). `run_recovery` no-ops when false. |
| Celery | Not in this story (ML-009). |

### Usage

```python
from app.core.redis_client import create_redis_client
from app.ml.clustering import CLUSTER_TYPE, SWEEPER_TYPE, ClusterManager

manager = ClusterManager(db_session, redis_client=create_redis_client())
await manager.run_clustering_pass(event_id, CLUSTER_TYPE)
await manager.run_clustering_pass(event_id, SWEEPER_TYPE)
recovery = await manager.run_recovery(event_id)
```

### Testing

Needs local Postgres (pgvector) **and** Redis for integration tests. Unit tests are numpy-only.

```bash
cd backend
docker compose up -d db redis
uv run pytest tests/ml/test_orphan_recovery_unit.py tests/ml/test_orphan_recovery.py -v --no-cov
```

## Testing

```bash
cd backend
uv sync --extra dev --extra ml
uv run pytest tests/ml/ -v
```

SCRFD integration tests need `backend/models/det_10g.onnx`. Set `RUN_ML_TESTS=0` to skip without models.
Fixtures: `tests/ml/fixtures/` (see `tests/ml/fixtures/README.md`).

## Registering Models

SCRFD is registered automatically via `import app.ml.detection`. Later stories add their own loaders in
`detection/registry.py` or sibling `registry.py` modules.
