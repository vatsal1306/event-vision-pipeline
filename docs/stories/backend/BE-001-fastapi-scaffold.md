# BE-001 — FastAPI scaffold, uv, Docker Compose, health

**Type:** Foundation  
**Depends on:** none  
**Area:** `backend/`

## Goal

Create a Python 3.10 FastAPI application that boots locally with `uv`, Ruff, mypy, a Makefile, and Docker Compose for PostgreSQL (pgvector image) + Redis. Expose `GET /health` (and `/api/v1` empty router). No domain APIs yet.

## Context

Monorepo: all API/ML/Celery code lives under `backend/`. Frontend is separate. Agents must not use Python 3.11+ syntax.

## References

- `docs/component_backend.md` §1, §3, §14 (settings shape — implement a minimal Settings now, expand in BE-002)
- `docs/component_infrastructure.md` §6.2 Docker Compose (mirror service names: `backend`, `db`, `redis`; frontend compose can wait for INF/FE)
- `backend/AGENTS.md` — uv, ruff, mypy, Python 3.10

## Create / edit

- `backend/pyproject.toml` — project name, `requires-python = ">=3.10,<3.11"`, deps: fastapi, uvicorn[standard], pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic (can pin in BE-003), redis, celery (optional until workers — include celery[redis] now to avoid rework)
- `backend/.python-version` → `3.10`
- `backend/app/main.py` — app factory `create_app()`, include health router
- `backend/app/api/health.py` — `{ "status": "ok" }`
- `backend/Dockerfile` — multi-stage, Python 3.10-slim, non-root user
- `backend/docker-compose.yml` — `db` (`pgvector/pgvector:pg16`), `redis:7-alpine`, `backend` (or document `uv run uvicorn` on host)
- `backend/Makefile` — `dev`, `lint`, `format`, `typecheck`, `test`, `migrate`
- `backend/.env.example` — DATABASE_URL, REDIS_URL, SECRET_KEY placeholder
- Root `.gitignore` — `.venv/`, `__pycache__/`, `backend/.env`, `backend/models/*.onnx` later

## Requirements

- `from __future__ import annotations` in new modules
- No `print()`; if logging is not ready, use stdlib logging until BE-002
- Health must not require DB (liveness). Optional `GET /health/ready` can check DB in BE-003
- OpenAPI at `/docs` in development only if `debug=True`

## Out of scope

- JWT, S3, Celery workers running, ML models

## Acceptance

- [ ] `uv sync` works on Python 3.10
- [ ] `uv run uvicorn app.main:app --reload --app-dir backend` (or documented equivalent) serves health 200
- [ ] `docker compose up db redis` starts Postgres + Redis
- [ ] Ruff and mypy configs exist and pass on the scaffold
- [ ] Dockerfile builds
