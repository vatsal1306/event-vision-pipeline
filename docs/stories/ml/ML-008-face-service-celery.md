# ML-008 — FaceService and Celery face_processing tasks

**Type:** Feature  
**Depends on:** BE-010, ML-007  
**Area:** `backend/app/services/face_service.py`, `backend/app/tasks/face_tasks.py`

## Goal

`FaceService.process_photo` orchestrates detect → crop → quality → embed. Persist `FaceEmbedding` only if quality passed. Update `photo.face_count` (detected, including rejects). `detect_and_embed_faces` Celery task retries. `update_event_clusters` with Redis lock `clustering_lock:{event_id}` timeout 300s, non-blocking acquire retry 30s.

## References

- `docs/component_ai_ml.md` §10
- Queue `face_processing`, worker concurrency 2
- API workers must not import torch if possible — keep FaceService imports inside task module

## Create / edit

- Enqueue from `process_uploaded_photo` after proxy success
- Increment `events.total_faces`
- Sync session in Celery: use dedicated sync engine **or** `asyncio.run` with async session — pick one, document, do not mix leaked sessions

## Acceptance

- [ ] Eager task on fixture photo inserts ≥0 embeddings without crash
- [ ] Concurrent cluster tasks: second waits/retries lock
- [ ] Photo with no faces completes processing
