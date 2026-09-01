# BE-003 — Database engine, ORM models, Alembic, pgvector

**Type:** Foundation  
**Depends on:** BE-002  
**Area:** `backend/app/models/`, `backend/alembic/`, `backend/app/core/database.py`

## Goal

Async SQLAlchemy 2.x models and an initial Alembic migration matching `docs/component_backend.md` §4. Enable `vector` extension. `get_db` async session dependency.

## Context

`face_embeddings.embedding` and `face_clusters.centroid` are `vector(512)`. Create `face_clusters` before the FK from embeddings if the SQL in the doc is ordered poorly — embeddings reference clusters.

## References

- `docs/component_backend.md` §4.1–4.3 (tables, indexes, enums, HNSW)
- `backend/AGENTS.md` — UUID PKs, `select()`, `lazy="selectin"`
- Image: `pgvector/pgvector:pg16`

## Create / edit

- `app/models/base.py` — UUID pk, `created_at`/`updated_at` timezone-aware
- Models: photographer, event, folder, photo, face_embedding, face_cluster, guest_session, couple_session, favorite, analytics_event — fields **exactly** as §4.2 (names may be snake_case Python mapped to SQL)
- Enums: `event_status`, `event_type`, `processing_status`, `analytics_action`
- Folder unique `(event_id, parent_id, name)` — handle SQL NULL parent uniqueness (partial unique index if needed)
- `app/core/database.py` — `create_async_engine`, `async_sessionmaker`, `get_db` yield session, commit/rollback pattern
- Alembic async env; first revision `enable_pgvector_and_core_tables`
- HNSW index as specified (`m=16`, `ef_construction=64`)
- Factories skeleton in `tests/factories/` optional here or BE-020

## Requirements

- Photographers: unique email; default `storage_limit_bytes` 200GB as in SQL comment
- Events: unique `slug`; `archive_at` set on create in BE-005 (column exists now)
- Guest/couple unique `(event_id, phone)`
- Favorites unique `(couple_session_id, photo_id)`
- No raw SQL in app code except pgvector operators in ML-006/BE-013 if SQLAlchemy cannot express them — isolate in one module

## Acceptance

- [ ] `make migrate` / `alembic upgrade head` against Compose Postgres
- [ ] All tables and indexes exist (`\d` or information_schema)
- [ ] `vector` extension installed
- [ ] App can open a session in a smoke test
