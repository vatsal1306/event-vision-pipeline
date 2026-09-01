# BE-020 — Backend test harness and coverage of core APIs

**Type:** Hardening  
**Depends on:** BE-004 (expand as features land)  
**Area:** `backend/tests/`

## Goal

pytest-asyncio, httpx ASGI client, dedicated test DB, factories, respx for HTTP. Tests named `test_{method}_{scenario}_{expected}`. Cover auth, event ownership, folder cycle, upload webhook idempotency, analytics CSV.

## References

- `docs/component_backend.md` §15
- `backend/AGENTS.md` Testing

## Create / edit

- `conftest.py` as in spec (create/drop metadata or alembic)
- `pytest.ini` / pyproject tool.pytest
- CI job later in INF-011

## Requirements

- No real AWS/SMS in unit tests
- Celery `task_always_eager=True` for ingest tests

## Acceptance

- [ ] `make test` / `uv run pytest` green locally against Compose DB
- [ ] Ownership isolation test from spec §15.3 exists
