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
| `AuthenticationError` | 401 | `AUTH_FAILED` |
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

