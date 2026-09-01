# FE-006 — Zustand client stores

**Type:** Foundation  
**Depends on:** FE-003  
**Area:** `frontend/src/stores/`

## Goal

Implement client-only stores from the component doc. No API caching in these stores.

## References

- `docs/component_frontend.md` §9.2
- `frontend/AGENTS.md` — Zustand vs React Query

## Create / edit

- `frontend/src/stores/auth-store.ts` — photographer, accessToken, isAuthenticated, logout, setPhotographer
- `frontend/src/stores/guest-auth-store.ts` (or combined) — guest/couple session token, isVerified, needsSelfie
- `frontend/src/stores/upload-store.ts` — queue, maxConcurrent 6, pause/resume/cancel, per-file tus URL, persist completed/pending file ids to `localStorage` keyed by event id (full File objects cannot persist; persist metadata + instruct FE-012 to re-select files)
- `frontend/src/stores/gallery-store.ts` — folder filter, selection, viewer open
- `frontend/src/stores/ui-store.ts` — sidebar collapsed, theme if needed
- `frontend/src/hooks/use-auth.ts`, `use-upload.ts` wrappers

## Requirements

- Persist photographer tokens in memory + `localStorage` (never log tokens)
- Guest session persist for return visits (same device)
- Upload store: statuses `queued | uploading | processing | complete | failed`

## Acceptance

- [ ] Store shapes match §9.2
- [ ] Server lists/photos are not duplicated in Zustand
