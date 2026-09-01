# Backend stories — index

Implement in ID order unless a later story is explicitly stubbed.

**Docs:** `backend/AGENTS.md`, `docs/component_backend.md`, `docs/PRD.md` Phase 1.

**Package layout** must match `docs/component_backend.md` §3 (`backend/app/...`).

**API prefix:** `/api/v1/`. Error JSON: `{ "detail", "code", "errors"? }`.

**Local services:** PostgreSQL 16 with pgvector, Redis 7, FastAPI, Celery, tusd (sidecar). Prefer `backend/docker-compose.yml` as in infrastructure doc §6.2.

See `docs/stories/00-index.md` for the full ID table.
