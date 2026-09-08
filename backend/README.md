# Backend — notes for later stories (AI agents)

This file is a working reference for agents implementing later backend stories.
It is not user-facing product documentation.

## Layout

- FastAPI app factory: `app/main.py` → `create_app()`.
- Settings: `app/config.py` → `get_settings()` (Pydantic Settings, `.env` + environment).
- Cross-cutting HTTP: `app/core/` (exceptions, handlers, middleware, logging, constants, Sentry).
- API prefix: `/api/v1/`. Liveness: `GET /health` (no database).

## Configuration (BE-002)

- Env file is always `backend/.env` (resolved from this package), not the repo-root `.env`.
- Every key from `docs/component_backend.md` §14 lives on `Settings` with **local dummy defaults**.
- Local/dev does **not** require AWS keys, SMS, SES, or Sentry. Empty strings mean “disabled / not configured”.
- `aws_region` default is `ap-south-1`.
- `get_settings` is `@lru_cache`. Tests that change env must call `get_settings.cache_clear()` (and again in `finally`).
- **Couple JWTs** use the same lifetime as guest JWTs: `Settings.jwt_couple_token_expire_days` is a property alias of `jwt_guest_token_expire_days` (default 30). Do not add a separate env var unless product wants different couple session length.

## Errors

Raise `app.core.exceptions` types from services (not ad-hoc `HTTPException` for domain errors):

| Class | HTTP | `code` |
|---|---|---|
| `NotFoundError` | 404 | `NOT_FOUND` |
| `BadRequestError` | 422 | `VALIDATION_ERROR` |
| `ConflictError` | 409 | `CONFLICT` |
| `PhoneNotVerifiedError` | 401 | `PHONE_NOT_VERIFIED` |
| `AuthorizationError` | 403 | `FORBIDDEN` |
| `OTPCooldownError` | 429 | `OTP_COOLDOWN` |
| `OTPMaxAttemptsError` | 429 | `OTP_MAX_ATTEMPTS` |
| `StorageLimitError` | 402 | `STORAGE_LIMIT` |
| `ProcessingError` | 500 | `PROCESSING_ERROR` |

JSON body: `{"detail": "...", "code": "NOT_FOUND"}`. Validation (Pydantic / invalid JSON) is `422` with `code=VALIDATION_ERROR` and `errors: [{field, message}, ...]`. Unexpected crashes: `500` `INTERNAL_ERROR` with a generic detail (message is logged, not returned). FastAPI/Starlette still re-raise the exception after sending that JSON so the process logger (and Sentry) can see it.

Dummy `/__test__/*` routes exist **only in tests**, not in the running app.

## Logging and request IDs

- Use `structlog` via `app.core.logging.get_logger()`. No `print()`.
- Debug (`DEBUG=true`): console renderer. Non-debug: JSON.
- FastAPI `debug` is always `False` so clients get JSON errors instead of HTML tracebacks; `/docs` still follows `DEBUG`.
- Every response includes `X-Request-ID`. Incoming `X-Request-ID` is reused if it is printable and ≤ 128 chars.
- Access logs record method, path (not query string), status, elapsed_ms. Do not log passwords, OTP codes, or tokens; `redact_sensitive_data` strips common secret field names.

## Debug vs non-debug (`DEBUG` in `backend/.env`)

Same API behavior for health, error JSON, request IDs, and settings. Differences:

| | `DEBUG=true` (local) | `DEBUG=false` (server later) |
|---|---|---|
| Logs | Console-friendly | JSON |
| CORS | `*` (`allow_credentials=False`) | `FRONTEND_URL` only, credentials on |
| `/docs` `/redoc` `/openapi.json` | On | Off |

One `.env` file for both; flip `DEBUG` when you want to simulate the server. Leave `SENTRY_DSN` empty until a Sentry project exists.

## Sentry

- `init_sentry` no-ops when `SENTRY_DSN` is empty (local default).
- When a DSN is set (typically on the server), crashes are sent to Sentry. Still use structlog locally; Sentry is the hosted error inbox, not a replacement for request logs.

## Constants

`app.core.constants`: `OTP_LENGTH = 6`, `JWTType` (`access`, `refresh`, `guest`, `couple`), `REQUEST_ID_HEADER`.

## How to run tests

From `backend/`: `uv sync --extra dev` then `make test` (or `uv run pytest`).

`make test` runs pytest with a terminal coverage report (`term-missing`) for `app/` (ML code excluded). Coverage must stay at or above 60% or the run fails.

- BE-002 unit tests run without PostgreSQL.
- BE-003 integration tests require Docker Postgres (`docker compose up db`) and will skip if it is unreachable.
- Integration tests use a separate database `photoshare_test` on the same Postgres instance; your main `photoshare` database is migrated too for `/health/ready`.
- Migrations run in a sync session fixture (`migrated_databases`); per-test DB work uses `run_migrations_async()` so Alembic's `asyncio.run()` is not nested inside pytest's event loop.

## Database (BE-003)

- ORM models: `app/models/` — UUID PKs, timezone-aware timestamps. `updated_at` only on tables where the schema defines it.
- Async engine/session: `app/core/database.py` → `get_db()` (commit on success, rollback on error). Re-exported from `app/api/deps.py`.
- Migrations: `alembic/` — initial revision `enable_pgvector_and_core_tables` enables `vector`, creates all core tables, enums, partial indexes, and HNSW on `face_embeddings.embedding`.
- `events.cover_photo_id` is an unlinked UUID (no FK) to avoid circular dependency with `photos`.
- Folder names are unique per event via partial indexes: root folders `(event_id, name) WHERE parent_id IS NULL`, nested `(event_id, parent_id, name) WHERE parent_id IS NOT NULL`.
- Readiness: `GET /health/ready` runs `SELECT 1` against Postgres; returns `503` when the database is down.

### Migrate locally

```bash
cd backend
docker compose up -d db
uv sync
make migrate
```

Verify extension and tables:

```bash
docker compose exec db psql -U postgres -d photoshare -c "\\dx"
docker compose exec db psql -U postgres -d photoshare -c "\\dt"
```

## Photographer auth (BE-004)

- Routes: `app/api/v1/auth.py` under `/api/v1/auth/*` (register, login, send-otp, verify-otp, refresh, logout, forgot-password, reset-password).
- Business logic: `app/services/auth_service.py`. OTP: `app/utils/otp.py` + Redis. JWT/password: `app/core/security.py`.
- Dependency: `get_current_photographer` in `app/api/deps.py` — requires JWT `type=access`.
- Redis client: `app/core/redis_client.py` (`get_redis` / `get_redis_dep`). Used for OTP keys and refresh-token denylist (`jwt:denylist:{jti}`).
- SMS: `app/services/sms_service.py` logs messages locally (`sms_provider=log`). Real MSG91 in BE-017.
- Schemas: `app/schemas/auth.py`. Password: 8–16 chars with upper, lower, digit, special (`PASSWORD_PATTERN` in constants).
- Phone numbers are unique on `photographers.phone` (migration `add_unique_photographers_phone`).

### Flows (implemented)

| Flow | Steps |
|---|---|
| Register | `register` (auto-sends OTP, no JWT) → `verify-otp` purpose `registration` (returns tokens) |
| Login | `login` email_or_phone + password (sends OTP) → `verify-otp` purpose `login` (returns tokens). Blocked with `PHONE_NOT_VERIFIED` until registration OTP done. |
| Reset password | `forgot-password` → OTP to registered phone → `reset-password` with OTP + new password |
| Refresh / logout | `refresh` rotates tokens; `logout` denylists refresh `jti` |

OTP: 6 digits, 300s expiry, 3 attempts, 60s send cooldown (Redis). Fourth verify attempt → `OTP_MAX_ATTEMPTS`.

When `DEBUG=true`, OTP is logged at INFO as `local_only` on event `otp.dev_delivery` (for local testing only).

### Auth integration tests

`tests/test_auth.py` requires Docker Postgres **and** Redis (`docker compose up -d db redis`). Tests read OTP from Redis via `OTPService.peek_otp`.

```bash
cd backend
docker compose up -d db redis
uv sync --extra dev
make migrate
make test
```

### Frontend wiring

Auth API paths use `/api/v1/auth/*` with snake_case JSON (`access_token`, `studio_name`, etc.). Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` and `NEXT_PUBLIC_MOCK_API=false` to hit the real backend.

New exceptions: `PhoneNotVerifiedError` (`PHONE_NOT_VERIFIED`), `ConflictError` (`CONFLICT`).

Dependencies added: `python-jose[cryptography]`, `passlib[bcrypt]`, `email-validator`, `bcrypt>=4.0.1,<4.1` (passlib compatibility pin).

### Dashboard APIs (BE-005 + shell)

Photographers can:

- `GET/POST /api/v1/events`, `GET/PUT/DELETE /api/v1/events/{id}`
- List query params: `offset`, `limit`, `status`, `sort_by` (`created_at`|`name`|`date_start`|`status`), `sort_order` (`asc`|`desc`). Default sort: `created_at desc`. No server-side name search in BE-005.
- `PUT /api/v1/events/{id}/settings`, `PUT /api/v1/events/{id}/links/{guest|master}/toggle`
- Nested folders: `GET/POST /api/v1/events/{id}/folders`, `PUT/DELETE .../folders/{folder_id}`
- `GET /api/v1/events/{id}/photos` returns empty items until upload ingest
- Analytics GETs return zeros/empty lists until BE-015
- `PUT /api/v1/profile` updates `studio_name` / `phone`
- Logo/watermark POST returns `501 NOT_IMPLEMENTED` until BE-016

Event rules (BE-005):

- Slug: `slugify(name) + short random suffix`; collision retry up to 5 attempts. Slug is **not** changed on rename.
- `archive_at` = `created_at + 2 calendar months` (set after insert flush).
- `date_end` must be on or after `date_start` (create schema + update service validation).
- Wrong-owner access returns **404** (`get_photographer_event`), not 403.
- Delete is **hard delete** (DB CASCADE). S3/storage quota cleanup deferred to BE-008/BE-016/BE-018.
- `Event` child relationships use `cascade="all, delete-orphan"` + `passive_deletes=True` so ORM delete matches Postgres `ON DELETE CASCADE` (avoids nulling non-null FKs).

Tests: `tests/test_events.py` (Postgres + Redis). Existing smoke in `tests/test_dashboard_api.py`.

Frontend event cards still use camelCase; `frontend/src/lib/map-api.ts` maps snake_case API JSON.

## Folders (BE-006)

- Nested folders logic is integrated with the `events` router (`/api/v1/events/{id}/folders`).
- Folders are strictly scoped to the event and photographer, maintaining a maximum nested depth of 10 (`MAX_FOLDER_DEPTH = 10`).
- Sibling folders (folders sharing the same parent under the same event) enforce unique names via PostgreSQL partial indexes.
- Prevents creating cycles when reparenting (e.g., trying to move a parent folder under its own descendant).
- Deletion behavior:
  - Without query parameter: `DELETE /folders/{id}` removes the folder and its descendant folders, cascading cleanly. Photos inside deleted folders are moved to the event root (their `folder_id` becomes `NULL` via `ON DELETE SET NULL`).
  - With query parameter: `DELETE /folders/{id}?delete_photos=true` recursively deletes all photos within the folder and any of its descendant folders using a recursive CTE, then deletes the folders.
- Tests: `tests/test_folders.py`.

## Photos (BE-007)

- Routes: `app/api/v1/photos.py` under `/api/v1/events/{event_id}/photos` (list, move, delete, download).
- `list_photos`: Paginated offset-based listing. Optionally filtered by `folder_id`.
  - Mocks `proxy_url` generation for S3 (until BE-008). 
- `move_photos`: Bulk updates `folder_id` for given `photo_ids`. Handles folder existence and event ownership validation correctly.
- `delete_photo`: Reuses the `delete_photos` utility from BE-006 inside `app/services/photo_service.py` to keep counters consistent.
- `get_download_url`: Mocks `original_s3_key` presigned URL generation (until BE-008).
- Tests: `tests/test_photos.py`. Cartesian product issue with `select_from(subquery)` using `func.count(Photo.id)` was resolved by correctly using `func.count()`.

## Storage (BE-008)

- Unified `StorageService` interface handling object creation, deletion, getting, presigned URLs, and storage class management.
- Implementations include `S3StorageService` (using async `aioboto3`) for production AWS S3 and `LocalStorageService` (storing to `.data/s3` directory) for offline testing without AWS.
- Standard storage exceptions wrapped in `StorageError`.
- Tests mock S3 operations using python `unittest.mock.AsyncMock` because `aioboto3` async streams can be complicated to mock perfectly with `moto` in unit tests.

## Upload Pipeline (BE-009)

- Uses `tusd` sidecar to handle chunked/resumable uploads via the `tus` protocol, storing files directly in `.data/s3/platform-uploads` locally.
- Webhooks from `tusd` point to `POST /api/v1/upload/hook`.
  - `pre-create` hook: Validates metadata UUIDs and checks photographer storage quota.
  - `post-finish` hook: Idempotently creates a `Photo` record and enqueues a Celery task.
- `celery-worker` is available in `docker-compose.yml`. It runs on the `photo_processing` queue.
- To test the full pipeline locally:
  ```bash
  cd backend
  docker compose up -d db redis tusd celery-worker
  uv run uvicorn app.main:app --reload
  ```

## Upload Pipeline (BE-010)
- Processing migrated to use OpenCV for proxies, watermarking, and HEIC ingestion.
- Background jobs handled reliably by Celery with proper failure isolation.

## Sharing (BE-011)
- Added `GET /api/v1/event/{slug}/info` which returns public `EventPublicInfo` for rendering unauthenticated guest and master landing pages.
- Dynamic presigned URL generation for the photographer's studio logo using `StorageService` with configurable expiration (`settings.s3_presigned_url_expiry`).
- Share link toggles and other settings modifications live in `PUT /api/v1/events/{id}/settings` and `PUT /api/v1/events/{id}/links/{type}/toggle` from BE-005.

## Guest/Couple Auth (BE-012)
- Added OTP + DB session row + long-lived JWT authentication for guests and couples.
- **Guest API:** `POST /api/v1/event/{slug}/auth` (sends OTP) and `POST /api/v1/event/{slug}/auth/verify` (verifies OTP, issues guest session JWT).
- **Couple API:** `POST /api/v1/event/{slug}/master/auth` (sends OTP) and `POST /api/v1/event/{slug}/master/verify` (verifies OTP, issues couple session JWT).
- JWTs for these sessions use types `guest` and `couple`.
- Guest verification checks if the guest has a `selfie_s3_key` or `matched_cluster_ids` to return `needs_selfie=True` or `False`.

## Guest Selfie Matching (BE-013)
- **POST `/api/v1/event/{slug}/selfie`**: Guests upload a selfie. A stub `FaceService` simulates matching by currently returning `no_match` (or fake matches later), saving `matched_cluster_ids` into the `GuestSession`.
- **GET `/api/v1/event/{slug}/guest/photos`**: Retrieves paginated event photos belonging to the `GuestSession`'s matched clusters and formatted as `PhotoResponse`.
- **GET `/api/v1/event/{slug}/photos/{photo_id}/download`**: Generates a mock presigned URL to download the original photo, and logs the download action as an `AnalyticsEvent` (`action=DOWNLOAD`).

## Master Gallery & Favorites (BE-014)
- **Couple API**: `/api/v1/event/{slug}/master/*` exposes full event photo access for couples with a valid `CoupleSession` token.
- **Photos**: `GET /master/photos` lists all `COMPLETED` photos with pagination and folder filtering.
- **Folders**: `GET /master/folders` returns the folder tree (using `FolderService.list_tree`).
- **Favorites**: `POST /master/favorite` toggles the favorite status of a `COMPLETED` photo for the current couple session. `GET /master/favorites` lists all favorited photos.
- **Download**: `GET /master/photos/{photo_id}/download` returns a mock presigned URL for the original photo, provided the event's `download_enabled` is `True`. Records an `AnalyticsEvent` for download.
- **Analytics View**: `POST /photos/{photo_id}/view` records a photo view for both Guest and Couple sessions. It delegates validation to `PhotoService.record_photo_view`.

## Analytics Dashboard (BE-015)
- **GET `/api/v1/event/{slug}/analytics/summary`**: Returns total verified guests, total photo views, total downloads, and a basic engagement rate.
- **GET `/api/v1/event/{slug}/analytics/photos/top`**: Returns top 10 to 50 photos ranked by either `views` or `downloads`.
- **GET `/api/v1/event/{slug}/analytics/guests`**: Returns a paginated list of guest leads (name, phone, first visit time, match count, and download count) for verified guests only.
- **GET `/api/v1/event/{slug}/analytics/guests/export`**: Returns the guest leads as a downloadable CSV file attachment (`text/csv`).

## Profile Storage (BE-016)
- **GET `/api/v1/profile`**: Returns the authenticated photographer's profile (email, studio name, generated S3 URLs for logo and watermark).
- **PUT `/api/v1/profile`**: Updates `studio_name` and `phone` (with verified flip) of the photographer.
- **POST `/api/v1/profile/logo`**: Handles multipart upload of JPEG, PNG, or WEBP studio logo validating magic bytes and saving to S3.
- **POST `/api/v1/profile/watermark`**: Handles multipart upload of PNG watermark validating magic bytes and saving to S3.
- **GET `/api/v1/profile/storage`**: Calculates and returns the precise active vs archived storage usage of all photos for a photographer, keeping the `storage_used_bytes` cached value up-to-date and returning the limit and percentage used.

## Notifications (BE-017)
- Email delivery via `EmailService` which logs emails locally using `LogEmailAdapter` (Phase 1 no-op without credentials requirement).
- OTP verification in `OTPService` bypasses Redis if `DEBUG=true` and `otp="123456"` to support development testing without incurring external API or mock usage costs.
- Celery background tasks `notify_processing_complete_task` and `notify_archival_warning_task` handle formatting and dispatching emails to photographers when events become `READY` or approach their `archive_at` dates.
- These notifications use simple text bodies for Phase 1 as no HTML templates were provided.
- A local log provider handles email during dev (`email_provider=log`).
- `send_processing_complete` notifies photographers when processing is complete.

## Archival (BE-018)

- Archival transitions `archive_at` events to `GLACIER_IR`, deletes web proxies, and cascades face data.
- Storage efficiency dictates batching S3 `delete_objects`.
- Restore moves objects back to `STANDARD`, resets status to `PROCESSING`, and queues proxy/face generation.
- Guest and Couple links block access to archived events with `EVENT_ARCHIVED`.
