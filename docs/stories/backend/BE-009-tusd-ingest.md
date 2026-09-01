# BE-009 — tusd webhook and photo ingest

**Type:** Feature  
**Depends on:** BE-007  
**Area:** `backend/app/api/v1/upload.py`, `backend/app/services/upload_service.py`, `backend/app/tasks/celery_app.py`

## Goal

Accept tusd `post-finish` webhook, create `Photo` row (`processing_status=pending`), increment event counters, set event status `uploading`/`processing`, enqueue `process_uploaded_photo`. Wire Celery app with Redis broker.

## References

- `docs/component_backend.md` §7.1–7.5
- Frontend metadata: `filename`, `filetype`, `event_id`, `folder_id`, `photographer_id`
- Verify photographer owns event; reject mismatched metadata

## Create / edit

- HMAC or shared secret header for webhook if tusd supports it; at minimum validate metadata UUIDs
- `TusHookPayload` schema
- `post-terminate`: optional cleanup of incomplete S3 parts (log if not possible)
- Celery: queues `photo_processing`, `notifications`; `task_routes` from ML doc
- docker-compose: `celery-worker` command for photo queue (CPU)
- tusd service in compose with hook URL `http://backend:8000/api/v1/upload/hook`

## Requirements

- Idempotent webhook: same tus id should not duplicate photos (store tus upload id on photo if needed — add nullable `tus_upload_id` column via migration if not in original schema; **preferred** so retries are safe)
- MIME allowlist: jpeg, png, heic, tiff, webp; reject others
- Storage quota check before accept (`StorageLimitError` 402)
- Max size 50MB from settings

## Acceptance

- [ ] Simulated webhook creates Photo and Celery task (eager Celery in tests)
- [ ] Unauthorized event_id rejected
- [ ] Duplicate hook does not create two rows
