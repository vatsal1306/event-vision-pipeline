# INF-005 — Production Compose, Caddy, tusd, upload hardening

**Type:** Feature  
**Depends on:** INF-004, BE-001, BE-009  
**Area:** `docker-compose.prod.yml` (repo root or `infrastructure/compose/`)

## Goal

Run on the EC2: Caddy (Let’s Encrypt), frontend, backend, tusd→S3, Postgres+pgvector, Redis, Celery CPU (concurrency 2–3), Beat. Tune for **bulk uploads**: Caddy long timeouts, tusd 5MB S3 parts, `nofile` 65535, 200 GB disk for Postgres + tusd temp, FastAPI **not** in the byte path.

No face/GPU containers. OTP via logs / debug code.

## References

- `docs/component_infrastructure.md` §6–9
- `docs/stories/backend/BE-009-tusd-ingest.md`

## Acceptance

- [ ] `docker compose -f docker-compose.prod.yml up -d` on a fresh Ubuntu
- [ ] HTTPS on the EIP/domain
- [ ] tusd can PUT to S3 with instance `.env` keys
- [ ] Postgres/Redis not reachable from 0.0.0.0
