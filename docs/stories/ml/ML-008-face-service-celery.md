# ML-008 — FaceService and Celery face_processing tasks

**Type:** Feature  
**Depends on:** BE-010, ML-007  

## Goal

Wire FaceService + Celery `face_processing` **for a future ML machine**. On the **app EC2**, do not register this queue. `process_uploaded_photo` must not require GPU.

## References

- `docs/component_ai_ml.md` §10
- Queue `face_processing`, worker concurrency 2
- API workers must not import torch if possible — keep FaceService imports inside task module

## Create / edit

- **Do not** enqueue from `process_uploaded_photo` on the app EC2. Optional feature flag `FACE_PROCESSING_ENABLED=false` by default.
- Increment `events.total_faces`
- Sync session in Celery: use dedicated sync engine **or** `asyncio.run` with async session — pick one, document, do not mix leaked sessions

## Acceptance

- [ ] Eager task on fixture photo inserts ≥0 embeddings without crash
- [ ] Concurrent cluster tasks: second waits/retries lock
- [ ] Photo with no faces completes processing
