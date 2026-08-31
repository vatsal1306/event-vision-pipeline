# AGENTS.md — Backend (Python / FastAPI / AI-ML)

> Scoped rules for AI agents working on `backend/` code.  
> For project-wide context and universal standards, see the root `AGENTS.md`.  
> For detailed architecture, see `docs/component_backend.md` and `docs/component_ai_ml.md`.

---

## Technology Constraints

- **Python version: 3.10.** Do not use features from 3.11+ (no `ExceptionGroup`, no `tomllib` stdlib, no `TaskGroup`). Use `from __future__ import annotations` only if needed, for modern type hint syntax.
- **Framework:** FastAPI (async, ASGI).
- **ORM:** SQLAlchemy 2.x with async engine (`asyncpg` driver).
- **Validation:** Pydantic v2 for all request/response schemas.
- **Task queue:** Celery with Redis broker.
- **Package manager:** `uv` for dependency management and virtual environments.
- **Linting/formatting:** `ruff` (linting + formatting). `mypy` for type checking.

---

## Python Style

### Type Hints

Every function signature must have full type annotations. Use `from __future__ import annotations` if needed, at the top of every file for PEP 604 union syntax (`X | None` instead of `Optional[X]`).

```python
from __future__ import annotations

async def get_event(event_id: UUID, db: AsyncSession) -> Event | None:
    """Retrieve an event by ID, or None if not found."""
    return await db.get(Event, event_id)
```

### Docstrings

Every public class and function must have a docstring. There should also be module level docstrings. Use Google-style:

```python
def process_photo(image_bytes: bytes, event_id: UUID) -> PhotoProcessingResult:
    """Run face detection and embedding extraction on a single photo.

    Args:
        image_bytes: Raw image file content.
        event_id: The event this photo belongs to.

    Returns:
        PhotoProcessingResult with detected faces and their embeddings.

    Raises:
        ProcessingError: If the image cannot be decoded.
    """
```

### Imports

- Standard library → third-party → local. Separated by blank lines.
- `ruff` enforces import sorting automatically.
- Use absolute imports within the `app` package (`from app.services.event_service import EventService`).

---

## FastAPI Patterns

### Route Handlers (Thin Controllers)

Route handlers validate input, call a service, and return a response. No business logic in route handlers.

```python
# ✅ GOOD — thin handler
@router.post("/events", response_model=EventDetail, status_code=201)
async def create_event(
    request: CreateEventRequest,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> EventDetail:
    service = EventService(db)
    event = await service.create_event(photographer.id, request)
    return EventDetail.model_validate(event)

# ❌ BAD — business logic in handler
@router.post("/events")
async def create_event(request: CreateEventRequest, ...):
    slug = slugify(request.name) + "-" + str(uuid4())[:8]
    event = Event(name=request.name, slug=slug, ...)
    db.add(event)
    await db.commit()
    return event
```

### Dependency Injection

Use `Depends()` for all cross-cutting concerns: database sessions, auth, rate limiting. Define dependencies in `app/api/deps.py`.

### Error Responses

Use custom exception classes (defined in `app/core/exceptions.py`). The global exception handler converts them to consistent JSON responses:

```json
{
  "detail": "Event not found",
  "code": "NOT_FOUND"
}
```

---

## Service Layer

- One service class per domain entity (`EventService`, `PhotoService`, `GuestService`, etc.).
- Services receive a database session via constructor injection, not as a method parameter on every call.
- Services are stateless — instantiate per request, don't cache instances.
- Services call other services when needed (compose, don't inherit).

```python
class EventService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_event(
        self, photographer_id: UUID, request: CreateEventRequest
    ) -> Event:
        # Business logic here
        ...
```

---

## Database (SQLAlchemy + pgvector)

### Models

- All models inherit from a `Base` class with common fields (`id`, `created_at`, `updated_at`).
- Use `UUID` primary keys (prevent enumeration attacks).
- Use Enums for finite state fields (`event_status`, `processing_status`).
- Relationships use `relationship()` with `lazy="selectin"` or explicit `.options(selectinload(...))` — never `lazy="joined"` by default (N+1 risk).

### Queries

- Always use the 2.0-style `select()` API, not the legacy `session.query()`.
- Paginate with `offset`/`limit`. Never load unbounded result sets.
- Use `func.count()` subqueries for counts, not Python `len()` on loaded collections.

### Migrations

- Alembic for all schema changes. Never modify the database schema manually.
- Migrations must be **backward-compatible** — old code must work with the new schema during rolling deployments.
- Name migration files descriptively: `add_face_clusters_table`, not `update_schema`.

---

## Celery Tasks

- Tasks are **thin** — they deserialize input, call a service method, and return a result.
- Use `bind=True` and `self.retry()` for transient failures (network, S3 timeout). Set `max_retries`.
- Use separate queues for different workload types: `photo_processing`, `face_processing`, `notifications`.
- GPU-bound tasks (`face_processing` queue) run on dedicated workers with `concurrency=2` to avoid GPU OOM.
- Use Redis distributed locks (`redis.lock()`) for operations that must not run concurrently (e.g., clustering for the same event).

---

## AI/ML Pipeline (`app/ml/`)

### Architecture

The ML pipeline is adapted from the **PicSee clustering pipeline** (`/Users/vatsal/Documents/picsee/clustering_pipeline`). Key components:

| Module | PicSee Origin | Production Wrapper |
|--------|-------------|-------------------|
| `detection/scrfd.py` | SCRFD class + multi-scale autodetect | Service class with batch support |
| `embedding/insightface_r100.py` | R100 backbone + `get_model()` | Batch GPU inference wrapper |
| `quality/blur_detector.py` | TFLite blur model | Quality gate service |
| `quality/pose_estimator.py` | TFLite YPR model | Quality gate service |
| `clustering/incremental_clusterer.py` | DBSCAN + Agglomerative + centroid injection | pgvector-backed storage |
| `matching/selfie_matcher.py` | N/A (new) | Cosine similarity vs cluster centroids |

### Model Management

- All models loaded via `ModelRegistry` singleton (one load per Celery worker process).
- Models stored in `backend/models/` directory (git-ignored; downloaded during setup or CI).
- Default embedding model: **InsightFace R100** (GPU). Fallback: **MobileFaceNet** (CPU).
- All embeddings are **512-dimensional, L2-normalized** float32 vectors. This is invariant across model swaps.

### Processing Conventions

- Face detection threshold: `0.5` (SCRFD).
- Blur rejection threshold: `0.5` (lower = blurrier; reject below).
- Head pose thresholds: yaw `45°`, pitch `35°`, roll `45°`.
- Clustering: DBSCAN `eps=0.45` + Agglomerative `distance_threshold=0.45`, cosine metric.
- Selfie match threshold: `0.55` cosine similarity against cluster centroids.
- All thresholds are configurable via `MLConfig` (environment variables), not hardcoded.

### Batch Processing

- Prefer **batch embedding extraction** (64 faces per GPU forward pass) over one-at-a-time.
- Group photos into batches of 50–100 for Celery tasks to amortize model loading overhead.
- Clustering runs **once per batch**, not per photo.

---

## Configuration

- All configuration via **environment variables**, loaded through Pydantic `BaseSettings`.
- No hardcoded URLs, credentials, bucket names, thresholds, or secrets.
- Configuration class lives in `app/config.py`. ML-specific config in `app/ml/config.py`.
- Use `.env` files for local development only. Production uses AWS SSM Parameter Store.

---

## Testing

- **pytest** with `pytest-asyncio` for async tests.
- **Factory Boy** for test data generation (photographers, events, photos, etc.).
- **httpx `AsyncClient`** with `ASGITransport` for integration testing against the FastAPI app.
- **respx** for mocking external HTTP calls (SMS provider, email service).
- Test database: use a separate PostgreSQL database, created/dropped per test session.
- ML tests: use small fixture images in `tests/ml/fixtures/` with known face counts and identities.

---

## Things to Avoid

- No `print()`. Use `structlog`.
- No `datetime.now()`. Use `datetime.utcnow()` or `datetime.now(tz=timezone.utc)`.
- No synchronous database calls in async handlers. Always use `AsyncSession`.
- No global database session. Always inject via `Depends(get_db)`.
- No `import *`. Always explicit imports.
- No mutable default arguments (`def foo(items=[])`).
- No bare `except:`. Always specify the exception type.
- No business logic in Celery tasks or route handlers. Delegate to services.
