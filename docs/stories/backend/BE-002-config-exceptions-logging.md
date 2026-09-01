# BE-002 — Settings, exceptions, structured logging, CORS, middleware

**Type:** Foundation  
**Depends on:** BE-001  
**Area:** `backend/app/config.py`, `backend/app/core/`

## Goal

Production-shaped configuration and cross-cutting HTTP behavior so later stories do not reinvent error format or logging.

## References

- `docs/component_backend.md` §13 (exception hierarchy, handlers, structlog, request ID middleware)
- `docs/component_backend.md` §14 (`Settings` fields — implement all keys even if unused; dummy defaults for local)
- `docs/component_backend.md` §16.2 CORS
- `backend/AGENTS.md` — no print, timezone-aware datetimes

## Create / edit

- `app/config.py` — `pydantic_settings.BaseSettings` matching §14 (`database_url` asyncpg, redis, celery, AWS, JWT, OTP, SMS, SES, proxy dimensions, sentry_dsn)
- `app/core/exceptions.py` — `AppException`, `NotFoundError`, `AuthenticationError`, `AuthorizationError`, `OTPCooldownError`, `OTPMaxAttemptsError`, `StorageLimitError`, `ProcessingError`
- `app/core/middleware.py` — request ID, timing, JSON access log
- `app/main.py` — register exception handlers from §13.2 including Pydantic 422 shape
- CORS: `frontend_url` only (not `*`) in non-debug
- `app/core/constants.py` — OTP length, JWT types (`access`, `refresh`, `guest`, `couple`)
- Sentry init if `sentry_dsn` set (no-op otherwise)

## Requirements

- Error body: `{"detail": "...", "code": "NOT_FOUND"}` plus `errors[]` for validation
- `X-Request-ID` on every response
- structlog JSON in production; console-friendly in debug
- Never log passwords, OTP codes, or tokens

## Acceptance

- [ ] Invalid JSON body returns 422 with field errors
- [ ] Raising `NotFoundError` in a dummy route returns 404 + code
- [ ] CORS allows the configured frontend origin
- [ ] Settings load from env with `.env` local file
