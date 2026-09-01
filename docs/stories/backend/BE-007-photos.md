# BE-007 — Photo listing, move, delete, original download

**Type:** Feature  
**Depends on:** BE-006, BE-008  
**Area:** `backend/app/api/v1/photos.py`, `backend/app/services/photo_service.py`

## Goal

Paginated photo list for an event (optional `folder_id`), move many photos, delete photo (DB + S3 original and proxy), download original via short-lived presigned URL. Record analytics `view` when serving proxy URLs if easy; **views for guests belong in BE-015** — photographer grid may skip view events.

## References

- `docs/component_backend.md` §6.2 Photos, `PhotoSummary` with `proxy_url` presigned
- Processing statuses: pending/processing/completed/failed

## Create / edit

- List: default limit 50, cap 100
- Presign proxy GET for completed photos; null proxy if still processing
- Delete: embeddings cascade; update `events.total_photos` / storage bytes
- Download: 404 if photo missing; 403 if photographer only — this endpoint is photographer dashboard; guest download is BE-013/BE-014

## Requirements

- Never return S3 keys to clients; only presigned URLs
- Offset pagination `has_more`

## Acceptance

- [ ] Filter by folder
- [ ] Move updates folder_id
- [ ] Delete removes S3 objects (mocked)
- [ ] Download URL expires per config
