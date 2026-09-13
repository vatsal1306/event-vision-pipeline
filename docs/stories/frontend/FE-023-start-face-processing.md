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

## Photographer-facing statuses (do not add more backend values)

Backend still stores `draft | uploading | processing | ready | archived`.
The dashboard **label** is more specific so “Uploading” is not shown after
files have landed:

| Backend | What they should see |
|--------|----------------------|
| Draft | Draft — event created, no photos |
| Uploading, proxies still running | Preparing photos |
| Uploading, photos in, Find faces not clicked | Awaiting faces |
| Processing | Finding faces |
| Ready | Ready (green) — galleries can be shared |
| Archived | Archived |

## UX direction (design in this story)

The exact layout is still open — keep it simple:

- On the event Photos / Upload hub, show a primary action when
  `pendingFacePhotos > 0` and status is `uploading` (or `ready` after more
  photos were added).
- Label: **Find faces**.
- While `processing`: hide the button, show a progress strip (percent +
  photo counts + ETA). Poll event status and
  `GET /face-processing-progress` every **60 seconds**. After click, refresh
  immediately so the badge moves to Processing without waiting a minute.
- If API returns `503 FACE_PROCESSING_DISABLED`: explain that face processing
  is not enabled on this environment (local `.env` / GPU worker).
- If `already_running: true`: no extra enqueue; keep showing Processing.
- After Ready, hide the button until new photos arrive (`pendingFacePhotos`).

Guests **and** the couple master gallery: if they open a link before Ready,
show the shared “Photos aren't ready yet” empty state. Do not send guests
into selfie capture. Backend returns `EVENT_NOT_READY` on guest and couple
auth/gallery APIs.

Local E2E (no MSW): `NEXT_PUBLIC_MOCK_API=false`,
`ML_FACE_PROCESSING_ENABLED=true`, CPU Celery on `photo_processing`, and a
second worker on `face_processing`. See `backend/README_ML.md`.

## References

- `docs/component_frontend.md` event hub
- `docs/stories/ml/ML-009-face-service-celery.md`
- `backend/README_ML.md` ML-009 section

## Create / edit

- Event detail header CTA (`FindFacesControl`)
- Wire `pendingFacePhotos` from `mapEventFromApi` (already present)
- Guest + couple not-ready empty state
- Couple API `EVENT_NOT_READY` (same as guests)

## Out of scope

- Starting/stopping the GPU EC2 (INF-009)
- Per-photo “process this image” controls
- Changing guest selfie capture UI beyond the not-ready state

## Acceptance

- [ ] Photographer can trigger processing once uploads are in
- [ ] Button disabled / hidden when there is nothing to process
- [ ] Status badge moves Uploading → Processing → Ready from API data
- [ ] Disabled-ML error is understandable
- [ ] Guest and couple links before Ready show not-ready UI (no selfie)
- [ ] Progress polls every 60s against the live API (no MSW for this story)

## Implementation notes (what we actually built)

- CTA copy: **Find faces**, in the event header next to Options (visible on
  every tab).
- Progress uses `GET /api/v1/events/{id}/face-processing-progress` with a CSS
  transition on the bar. Event list/detail refetch while uploading/processing
  is **60s**, not 5s.
- Live backend only (`NEXT_PUBLIC_MOCK_API=false`). No new MSW handlers.
- Couple master gallery uses the same not-ready screen; `CoupleService`
  raises `EVENT_NOT_READY` until Ready.
- GPU EC2 start/stop stays INF-009. Laptop: face Celery worker +
  `ML_FACE_PROCESSING_ENABLED=true`.
