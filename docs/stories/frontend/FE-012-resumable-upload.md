# FE-012 — Chunked resumable parallel uploads

**Type:** Feature  
**Depends on:** FE-011, FE-006  
**Area:** `frontend/src/app/dashboard/events/[id]/upload/`, `frontend/src/lib/upload/`

## Goal

Browser uploader: drag-and-drop files **and folders** (preserve nested structure), tus chunked uploads (5MB), up to 6 parallel files, pause/cancel/retry, overall progress, persist upload metadata so returning to the tab can resume pending files when Files are re-provided or tus URLs still valid.

## References

- `docs/component_frontend.md` §5.5.2, §10.2 Upload
- `docs/PRD.md` §5.1.4
- Libraries: `react-dropzone`, `tus-js-client`

## Create / edit

- `upload/page.tsx`
- `frontend/src/components/dashboard/upload-dropzone.tsx`, `upload-progress.tsx`
- `frontend/src/lib/upload/tus-client.ts`, `upload-manager.ts`, `file-utils.ts`
- Target folder selector (existing tree)
- Dynamic import `ssr: false` for dropzone

## Requirements

- Formats: JPEG, PNG, HEIC, TIFF, WebP
- Nested folder upload creates matching folders via API (mock) when using folder picker
- Failed files: 3 auto-retries then manual Retry
- Do **not** build a desktop app
- Mock: MSW may not speak real tus; acceptable to mock tus endpoint or simulate progress in the upload manager while still structuring real tus client for production. Prefer a fake tus handler if feasible.

## Acceptance

- [ ] Multiple files queue and run with max 6 concurrent
- [ ] Per-file and overall progress, speed, ETA
- [ ] Pause/cancel/retry work
- [ ] Returning to the event shows completed vs pending from persisted metadata
