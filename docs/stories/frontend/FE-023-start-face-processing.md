# FE-023 — Photographer “start face processing” control

**Type:** Feature
**Depends on:** FE-011, FE-012, ML-009
**Area:** `frontend/src/app/dashboard/events/[id]/`

## Goal

Give the photographer a clear way to say **“I’m done uploading — run face
recognition now.”** Do not auto-start AI on each file. Do not invent a second
upload product.

Backend already exists (ML-009):

`POST /api/v1/events/{id}/start-face-processing`

Client helper: `api.startFaceProcessing(eventId)` in `frontend/src/lib/api-client.ts`.

## Photographer-facing statuses (do not add more)

| Status | What they should see |
|--------|----------------------|
| Draft | Event created, no photos |
| Uploading | Photos in the event; AI **not** started (still dropping files **or** done dropping but hasn’t clicked) |
| Processing | They clicked start; faces + clustering running |
| Ready | Gallery can be shared; guests can selfie-match |
| Archived | Old event |

## UX direction (design in this story)

The exact layout is still open — keep it simple:

- On the event Photos / Upload hub, show a primary action when
  `pendingFacePhotos > 0` and status is `uploading` (or `ready` after more
  photos were added).
- Label idea: **Find faces** / **Start face matching** (copy TBD).
- While `processing`: disable the button, show that clustering is running.
  Poll event status (existing 5s refetch for uploading/processing).
- If API returns `503 FACE_PROCESSING_DISABLED`: explain that face processing
  is not enabled on this environment (local `.env` / GPU worker).
- If `already_running: true`: no extra enqueue; keep showing Processing.
- After Ready, hide the button until new photos arrive (`pendingFacePhotos`).

Guests: if they open a link before Ready, backend returns `EVENT_NOT_READY`.
Reuse empty/error UI — do not send them into selfie capture.

## References

- `docs/component_frontend.md` event hub
- `docs/stories/ml/ML-009-face-service-celery.md`
- `backend/README_ML.md` ML-009 section

## Create / edit

- Event detail toolbar / upload tab CTA
- MSW handler for `POST /events/:id/start-face-processing`
- Wire `pendingFacePhotos` from `mapEventFromApi`

## Out of scope

- Starting/stopping the GPU EC2 (INF-009)
- Per-photo “process this image” controls
- Changing guest selfie capture UI beyond the not-ready state

## Acceptance

- [ ] Photographer can trigger processing once uploads are in
- [ ] Button disabled / hidden when there is nothing to process
- [ ] Status badge moves Uploading → Processing → Ready from API data
- [ ] Disabled-ML error is understandable
- [ ] MSW mock covers success, already-running, and 503
