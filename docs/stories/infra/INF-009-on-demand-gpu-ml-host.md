# INF-009 — On-demand GPU ML host (start / stop)

**Type:** Feature
**Depends on:** INF-004, ML-009
**Area:** compute AWS account — GPU EC2 + worker that consumes `face_processing`

## Goal

Leave the photographer app on the CPU-only `m6i.xlarge`. Run bulk face
detection, embeddings, and clustering on a **separate GPU instance that is not
running 24/7**.

When the photographer finishes uploading and calls
`POST /api/v1/events/{id}/start-face-processing` (ML-009), the platform should:

1. Start (or wake) the GPU EC2.
2. Wait until a Celery worker is subscribed to Redis queue `face_processing`.
3. Let `process_event_photos` / `run_event_clustering` finish.
4. Stop (or hibernate) the GPU EC2 so idle GPU spend is near zero.

Guest selfie matching does **not** use this host. It stays on the app EC2 CPU.

## Why this exists

ML-009 wires FaceService + Celery. It does **not** provision or lifecycle the
GPU box. Photographers may upload 15k photos over hours; keeping a GPU on
during that window is wasteful. The photographer “I’m done uploading” trigger
is the right moment to boot GPU.

## References

- `docs/component_ai_ml.md` §10 (ML-009 notes)
- `docs/component_infrastructure.md` §10
- `backend/README_ML.md` (ML-009)
- `docs/stories/ml/ML-009-face-service-celery.md`
- Story format: same as `docs/stories/infra/INF-004-app-ec2.md`

## Suggested design (implementation may refine)

- Separate GPU instance in **ap-south-1** (size TBD: e.g. `g4dn.xlarge` or
  `g6.xlarge` — pick from current AWS India pricing, not from this story).
- Same Redis broker and Postgres as the app stack (VPC / SG: GPU host may
  reach Redis + Postgres on the app instance or a private IP; **do not**
  expose 5432/6379 to the world).
- Worker command:
  `celery -A app.tasks.celery_app worker -Q face_processing -c 2`
- App EC2 workers stay `-Q photo_processing` only.
- `ML_FACE_PROCESSING_ENABLED=true` only when this worker can actually run
  (or when starting the instance is automated).
- Idle policy: stop instance after the face pipeline lock is released **and**
  the `face_processing` queue is empty for N minutes.
- Boot policy: API/worker on app host starts the instance (AWS SDK) when the
  photographer trigger succeeds; do not boot on every tus upload.

Local/dev: no GPU instance. Run the face worker on the laptop
(`ML_FACE_PROCESSING_ENABLED=true`).

## Out of scope

- Changing the app `m6i.xlarge` to a GPU type
- Running `face_processing` on the app Compose CPU worker
- Spot fleet / SageMaker / ECS (keep one EC2 unless a later story says otherwise)

## Acceptance

- [ ] GPU instance is documented (AMI, type, disk, SG, region)
- [ ] Photographer start-face-processing can boot the instance
- [ ] Celery `face_processing` worker comes up and processes a real event
- [ ] Instance stops after the job (or after a documented idle timeout)
- [ ] App EC2 never subscribes to `face_processing`
- [ ] Guest selfie still works with the GPU instance **stopped**
- [ ] Cost note: GPU billed only while running
