# Backend stories — index

Implement in ID order unless a later story is explicitly stubbed.

**Docs:** `backend/AGENTS.md`, `docs/component_backend.md`, `docs/PRD.md` Phase 1.

**Package layout** must match `docs/component_backend.md` §3 (`backend/app/...`).

**API prefix:** `/api/v1/`. Error JSON: `{ "detail", "code", "errors"? }`.

**Local/prod services:** PostgreSQL 16 + pgvector, Redis 7, FastAPI, Celery CPU, tusd — all Docker. Production runs on **EC2 m6i.xlarge ap-south-1**. S3 is a separate AWS account. See `docs/component_infrastructure.md`.

See `docs/stories/00-index.md` for the full ID table.
