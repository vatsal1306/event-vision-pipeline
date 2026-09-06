# BE-005 — Event CRUD, slugs, ownership, counters

**Type:** Feature  
**Depends on:** BE-004  
**Area:** `backend/app/api/v1/events.py`, `backend/app/services/event_service.py`, `backend/app/utils/slug.py`

## Goal

Authenticated photographers create, list, get, update, and delete **their** events. Unique URL slugs. Status starts `draft`. `archive_at` = created_at + 2 months. Master/guest link flags default true. Download enabled default true.

## References

- `docs/component_backend.md` §5.4, §6.2 Events, §4.3 denormalized counters
- `docs/PRD.md` §5.1.2
- List query: offset, limit, sort, status filter

## Create / edit

- Slug: slugify name + short unique suffix; collision retry
- `get_photographer_event` dependency 404 if wrong owner (do not leak 403)
- Delete: hard-delete event (CASCADE) and decrement storage in BE-016/BE-018 — for now delete row; S3 cleanup in BE-008 hook or BE-018
- `EventDetail` includes computed `master_link_url` / `guest_link_url` from `frontend_url` + slug
- Schemas `app/schemas/event.py`

## Requirements

- Name 3–255 (API spec 3–255; frontend said 3–200 — **use backend spec 3–255**, min 3)
- `event_type` enum wedding/corporate/birthday/other
- List **only** own events
- `total_photos`, `processed_photos`, `total_faces` maintained later by upload/ML; initialize 0

## Acceptance

- [x] CRUD works with JWT
- [x] Other photographer’s UUID returns 404
- [x] Slug unique; URLs in detail payload
- [x] Delete removes event and child rows via FK

## Implementation notes (agreed deviations)

- **List:** `sort_by` / `sort_order` added (`created_at`, `name`, `date_start`, `status`). No server-side name search in BE-005 (frontend filters client-side).
- **Delete:** Hard delete with DB CASCADE; no S3 or storage quota adjustment yet (BE-008/BE-018).
- **`archive_at`:** Set to `created_at + 2 calendar months` after insert (not `now()` at create).
- **Rename:** Slug is immutable after create so share links stay stable.
- **Date range:** `date_end` must be on or after `date_start` (Pydantic on create, service on partial update).
- **Settings + link toggle** included in this story (dashboard needs them before BE-011).
- Folder/photo/analytics routes on `events.py` are stubs or forward to later stories; core CRUD tests live in `tests/test_events.py`.
