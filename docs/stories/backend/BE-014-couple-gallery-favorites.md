# BE-014 — Couple master gallery and favorites

**Type:** Feature  
**Depends on:** BE-012  
**Area:** `backend/app/api/v1/couple.py`, `couple_service.py`

## Goal

Couple JWT: list all completed photos (folder filter, pagination), folder tree, toggle favorite, list favorites. Download original if `download_enabled`. Record analytics download/view (view optional per photo open — implement download for sure; view on photo list fetch is too noisy; record view on a dedicated `POST /view` or on download only until FE exists — **record `download` on download; record `view` when GET single photo or query param** — simplest: increment view when generating proxy URL for couple/guest photo list items is wrong. Implement `POST /api/v1/event/{slug}/photos/{id}/view` if needed; otherwise record view once per photo_id per session per day in list handler is OK for Phase 1. Prefer explicit view in photo viewer API: `POST .../view`.)

## References

- `docs/component_backend.md` §6.2 Couple
- `docs/PRD.md` §5.2.2–5.2.3

## Create / edit

- Favorites table unique constraint
- Download: presign original; 403 if downloads disabled

## Acceptance

- [ ] Couple cannot access another event’s token
- [ ] Favorites persist
- [ ] Folder tree matches photographer structure
