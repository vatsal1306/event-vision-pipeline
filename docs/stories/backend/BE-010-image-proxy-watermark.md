# BE-010 — Dual-resolution proxy, HEIC, watermark (Celery)

**Type:** Feature  
**Depends on:** BE-009  
**Area:** `backend/app/services/image_processing_service.py`, `watermark_service.py`, `backend/app/tasks/photo_tasks.py`

## Goal

For each ingested original: generate WebP proxy (max edge 2048, target ~500KB, quality loop), EXIF transpose, HEIC via pillow-heif, blurhash, optional watermark bottom-right 40% opacity / 20% width, upload proxy to Standard bucket, update photo row `completed` or `failed`. Do **not** call face ML yet — enqueue `detect_faces_task` only if ML-008 exists; otherwise skip with a logged TODO or no-op task.

## References

- `docs/component_backend.md` §7.4, §8, §9 (copy algorithms; do not invent different watermark placement)
- `docs/PRD.md` dual-resolution
- Celery `bind=True`, max_retries 3, retry 60s

## Create / edit

- Register HEIF opener once at worker start
- `update_event_processing_status` from §7.5 — when all complete, status `ready` and delay `notify_processing_complete` (stub if BE-017 missing)
- Originals: after successful proxy, set S3 storage class IA (or upload originals as IA from tusd config)

## Requirements

- Originals never watermarked
- GPU not required
- Worker concurrency default 4 on CPU queue
- Structured logs: photo_id, event_id, duration_ms

## Acceptance

- [ ] JPEG fixture produces webp proxy + blurhash + dimensions
- [ ] Watermark applied when photographer has `watermark_url`
- [ ] Failure sets `processing_status=failed` and `processing_error`
- [ ] Event becomes `ready` when all photos completed
