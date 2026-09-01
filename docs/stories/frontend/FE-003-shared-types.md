# FE-003 — Shared TypeScript domain types

**Type:** Foundation  
**Depends on:** FE-001  
**Area:** `frontend/src/types/`

## Goal

Define TypeScript types that match the Phase 1 API contract so UI and mocks stay aligned. No runtime API yet.

## References

- `docs/component_frontend.md` §10.2 (endpoints and Pydantic-shaped responses)
- `docs/component_backend.md` §6 (canonical field names — keep frontend types in sync)
- `docs/PRD.md` — event statuses, folder hierarchy, guest vs couple

## Create / edit

- `frontend/src/types/event.ts` — Event, EventStatus (`draft` | `uploading` | `processing` | `ready` | `archived`), EventType, Folder, FolderNode, Photo, ProcessingStatus
- `frontend/src/types/user.ts` — Photographer, GuestSession, CoupleSession
- `frontend/src/types/api.ts` — paginated list wrappers, analytics types, auth token responses, `ApiError`
- `frontend/src/types/upload.ts` — UploadFile, FileProgress, upload status union
- `frontend/src/lib/constants.ts` — status labels, OTP length (6), max concurrent uploads (6), chunk size 5MB

## Requirements

- UUIDs as `string`
- Photo has `proxyUrl` / `webProxyUrl` (pick one name and use it everywhere), `blurhash`, dimensions, `faceCount`, `folderId`
- Guest match result includes `matchedPhotoCount` / `status`
- No `any`

## Acceptance

- [ ] Types cover photographer, event, folder, photo, guest, couple, analytics, upload
- [ ] Status enums match PRD
- [ ] Constants exist for magic numbers used in later stories
