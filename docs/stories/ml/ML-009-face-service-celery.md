# ML-009 — FaceService Orchestration and Celery Face Tasks

**Type:** Feature
**Depends on:** ML-002, ML-003, ML-004, ML-005, ML-006, ML-007, ML-008
**Area:** `backend/app/ml/pipeline.py`, `backend/app/tasks/`

## Goal

Wire all ML components into a single `FaceService` facade that orchestrates the full
pipeline. Create Celery tasks for async face processing. Enforce the critical constraint:
**face processing tasks run ONLY on the ML host, never on the CPU-only app EC2**.

## FaceService API

```python
class FaceService:
    """
    Facade that orchestrates the full face processing pipeline.
    Used by both Celery tasks (upload processing) and sync API (selfie matching).
    """

    def __init__(self, config: MLConfig, registry: ModelRegistry):
        self.detector = registry.get_model("scrfd")
        self.cropper = registry.get_model("face_cropper")
        self.quality_filter = registry.get_model("quality_filter")
        self.embedder = registry.get_model("dual_embedder")
        self.cluster_manager = ClusterManager(config)
        self.orphan_recovery = OrphanCropRecovery(self.cluster_manager)
        self.orphan_merge = OrphanClusterMerge(self.cluster_manager)
        self.selfie_matcher = SelfieMatcher(config)

    # ─── Upload Pipeline (async, Celery) ───────────────────────

    async def process_photo(self, photo_id: UUID, image_bytes: bytes) -> ProcessingResult:
        """
        Process a single photo through the full pipeline:
        1. Decode image (HEIC → PNG if needed)
        2. Detect all faces (SCRFD multi-scale)
        3. Crop and align each face (112×112 ArcFace)
        4. Quality filter each crop (blur, YPR, age, sunglasses)
        5. Generate embeddings for passed crops (dual R100 + AdaFace)
        6. Store embeddings in face_embeddings table
        7. Update photo.face_count

        Does NOT trigger clustering — that's a separate task.
        """

    async def run_clustering(self, event_id: UUID) -> ClusteringPipelineResult:
        """
        Run the full clustering pipeline for an event:
        1. Regular clustering pass (PYR 0–47°)
        2. Sweeper pass (PYR 47–120°)
        3. Orphan crop recovery
        4. Orphan cluster merge
        5. Update event.processing_status

        Called after batch processing completes.
        """

    # ─── Selfie Pipeline (sync, API) ──────────────────────────

    async def match_selfie(self, image_bgr: np.ndarray, event_id: UUID) -> MatchResult:
        """
        Match a guest selfie against event clusters:
        1. Liveness check
        2. Detect single face
        3. Quality filter (stricter: PYR 0–30°)
        4. Generate embedding
        5. Cosine match against centroids
        6. Return matched cluster IDs

        Must complete in < 2s. Runs synchronously in API request.
        """
```

## Celery Task Definitions

### Task Queue Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  App EC2 (CPU-only, m6i.xlarge)                             │
│                                                              │
│  FastAPI ─── Celery Producer ──→ Redis Broker               │
│  (enqueues tasks)                                            │
│                                                              │
│  Celery Workers: proxy, watermark, blurhash (CPU tasks)      │
│  ❌ NO face_processing queue registered here                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ML Host (GPU instance)                                      │
│                                                              │
│  Celery Workers: face_processing queue ONLY                  │
│  ✅ Models loaded here                                      │
│  Redis Broker (same as App EC2)                              │
└─────────────────────────────────────────────────────────────┘
```

### Task Definitions

```python
# backend/app/tasks/face_tasks.py

@celery_app.task(
    queue="face_processing",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_event_photos(self, event_id: str):
    """
    Bulk process all unprocessed photos for an event.
    Triggered after upload completion (bulk mode).

    Steps:
    1. Load all photos with processing_status='uploaded'
    2. For each photo: detect → crop → filter → embed → store
    3. Run clustering pipeline
    4. Update event.processing_status → 'ready'
    5. Trigger notification (email/SMS to photographer)
    """

@celery_app.task(
    queue="face_processing",
    bind=True,
)
def run_event_clustering(self, event_id: str):
    """
    Standalone clustering task. Can be triggered after
    new photos are added to an existing event.
    """
```

### Redis Clustering Lock

```python
CLUSTERING_LOCK_KEY = "spotme:clustering_lock:{event_id}"
CLUSTERING_LOCK_TIMEOUT = 300  # 5 minutes

async def acquire_clustering_lock(event_id: UUID) -> bool:
    """
    Acquire distributed lock before running clustering.
    Prevents concurrent clustering for the same event.
    If lock is held, task retries with exponential backoff.
    """
    return await redis.set(
        CLUSTERING_LOCK_KEY.format(event_id=event_id),
        "locked",
        nx=True,
        ex=CLUSTERING_LOCK_TIMEOUT,
    )
```

## Critical Deployment Constraints

### DO NOT run face tasks on App EC2

```python
# backend/app/tasks/celery_app.py

celery_app = Celery("spotme")

# App EC2 workers — CPU-only tasks
APP_QUEUES = ["default", "proxy", "watermark"]

# ML Host workers — GPU tasks
ML_QUEUES = ["face_processing"]

# Worker startup command on App EC2:
# celery -A app.tasks.celery_app worker -Q default,proxy,watermark

# Worker startup command on ML Host:
# celery -A app.tasks.celery_app worker -Q face_processing -c 2
```

### Feature Flag

```python
# backend/app/config.py
FACE_PROCESSING_ENABLED = env.bool("FACE_PROCESSING_ENABLED", default=False)

# In upload webhook / task enqueue:
if settings.FACE_PROCESSING_ENABLED:
    process_event_photos.delay(str(event_id))
else:
    # Stub: mark event as ready without face processing
    await mark_event_ready(event_id)
```

### Selfie Matching on App EC2

Selfie matching is a sync API call. Two deployment options:

**Option A (Phase 1)**: Forward selfie to ML Host via internal HTTP/gRPC
**Option B (Phase 2)**: Load R100 on App EC2 CPU (slow but works, ~2s per selfie)

Recommendation: **Option A** — keep all ML inference on the GPU host.

## Event Processing Status Flow

```
draft → uploading → uploaded → processing → ready → archived
                                   ↓
                            (face processing)
                                   ↓
                              clustering
                                   ↓
                              recovery
                                   ↓
                               ready ✓
```

Update `events.processing_status` at each stage.
Increment `events.total_faces` as faces are detected.

## Error Handling

| Error | Action |
|-------|--------|
| Single photo fails detection | Log warning, continue with next photo |
| GPU OOM during embedding | Retry with smaller batch, fall back to MBF |
| Clustering lock timeout | Retry task with backoff (max 3 retries) |
| All photos fail | Mark event status `processing_failed` |
| Selfie match timeout (> 5s) | Return `status="error"`, log alert |

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/pipeline.py` | Create — `FaceService` facade |
| `backend/app/tasks/face_tasks.py` | Create — Celery task definitions |
| `backend/app/tasks/celery_app.py` | Edit — add `face_processing` queue config |
| `backend/app/config.py` | Edit — add `FACE_PROCESSING_ENABLED` flag |
| Integration tests with eager Celery | Create |

## Acceptance

- [ ] `FaceService.process_photo()` returns `ProcessingResult` with face count and embedding IDs
- [ ] `FaceService.run_clustering()` produces clusters from stored embeddings
- [ ] `FaceService.match_selfie()` returns `MatchResult` within 2 seconds
- [ ] Celery task `process_event_photos` runs on `face_processing` queue only
- [ ] App EC2 workers do NOT register `face_processing` queue
- [ ] `FACE_PROCESSING_ENABLED=false` → tasks are not enqueued, event marked ready
- [ ] Concurrent clustering tasks → second task waits/retries on lock
- [ ] Single photo failure → other photos still processed successfully
- [ ] Event status transitions: uploaded → processing → ready

## Implementation notes (what we actually built)

- Photographer **starts** face processing via
  `POST /api/v1/events/{id}/start-face-processing`. It is not enqueued from
  tus completion. GPU EC2 start/stop is **INF-009**. Dashboard button is
  **FE-023**.
- Photographer statuses: `draft` → `uploading` → `processing` → `ready` →
  `archived`. No `uploaded` / `processing_failed` public states.
- Ready only when every photo has `faces_processed=true` **and** proxy jobs
  are completed or failed. Previews still run automatically on CPU.
- Face work uses **original** JPG/HEIC bytes, not WebP proxies.
- `ML_FACE_PROCESSING_ENABLED` (default false) — not a second flag in
  `app/config.py`. App workers stay on `photo_processing`; ML worker uses
  `face_processing`.
- Selfie matching stays sync on the app CPU host.
- Per-photo GPU batching stays **ML-010**; this story loops `process_photo`.
