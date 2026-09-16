# OBS-002 — Product and ops events to Slack

**Type:** Feature  
**Depends on:** OBS-001 (webhooks exist in `.env`), BE-016 (quota fields), INF-009 (`GpuHostService`), INF-007 (`scripts/postgres-backup.sh`)  
**Area:** `backend/app/services/observability_notifier.py`, `backend/app/tasks/observability_tasks.py`, auth / face / GPU / upload hooks, `scripts/slack-ops-alert.sh`  
**Python:** 3.10 only

## Business outcome

The operator’s phone gets a Slack push when:

- A photographer **finishes signup** (phone + email OTP verified)
- A photographer clicks **Find faces** and the API accepts it
- The app EC2 **actually starts** or **actually stops** the GPU instance, or **fails** to start it
- A photographer crosses **80% / 95% / 100%** of their storage quota
- The daily **Postgres backup script fails**

These are discrete facts about the product, not Grafana charts.

## Purpose

Add one notifier used by all later OBS stories. Keep photographer HTTP requests fast: Slack I/O runs on Celery queue `notifications` (already consumed by the app worker). Empty webhooks (laptop) must no-op so local signup tests do not hang on Slack.

## References (read first)

- `docs/component_observability.md` §4, §8.1, §9, §14, §18
- `backend/app/services/auth_service.py` — `_verify_registration_otps` (not `register`)
- `backend/app/services/face_processing_service.py` — `start_face_processing`
- `backend/app/services/gpu_host_service.py` — `ensure_running` / `stop_if_idle` return strings
- `backend/app/services/upload_service.py` and `photo_service.py` — quota increment
- `backend/app/models/photographer.py` — `storage_used_bytes`, `storage_limit_bytes` (default 200 GB)
- `backend/app/tasks/celery_app.py` — queue `notifications`
- `backend/app/config.py` — add settings next to `sentry_dsn`
- `scripts/postgres-backup.sh` — `die` function
- Existing tests: `backend/tests/test_gpu_host_service.py`, auth tests, `test_upload_hook.py`

## Out of scope

- Grafana alert rules
- GPU NVIDIA metrics (OBS-003)
- `/metrics`, Loki (OBS-004)
- S3 budget (OBS-005)
- Replacing `OPS_ALERT_EMAIL` stalled-job emails
- Posting photographer **phone numbers** or OTPs to Slack
- Calling Slack from FastAPI route handlers or from the GPU host

## Non-negotiables

1. Channel split from the component catalog (§8.1). Do not send Find-faces to `#spotme-alerts`. Do not send `gpu_start_failed` to `#spotme-events`.
2. `gpu_started` only when `ensure_running()` returns **`started`**. Already `running` / `pending` / `skipped` → no Slack (Find-faces event already covers the click).
3. `gpu_stopped` only when `stop_if_idle()` returns **`stopped`**.
4. `photographer_verified` only after **both** registration OTPs succeed, not when `register()` creates an unverified row (that path retries OTPs).
5. Quota: **once per band** with **5 percentage-point hysteresis** (component §14). Redis key `spotme:quota_alert:{photographer_id}`.
6. Slack HTTP failure must not fail signup, Find faces, GPU start/stop, or upload ingest. Log and move on.
7. Queue: **`notifications`**. Do not put Slack posts on `face_processing` or block `wait_until_running`.
8. No new Python 3.11+ syntax. Service layer + thin Celery task. Docstrings on public classes/functions.

## Implementation plan

### Step 1 — Settings

In `backend/app/config.py` add:

```python
slack_webhook_alerts_url: str = ""
slack_webhook_events_url: str = ""
```

Empty string default. `backend/.env.example` and `.env.prod.example` already have the keys from OBS-001; if OBS-001 missed Pydantic fields, add them here.

### Step 2 — Event keys and payload schema

Create `backend/app/core/observability_events.py` (or constants on the notifier) with **enum or constants** (no magic strings at call sites):

| `event_key` | Webhook setting |
|-------------|-----------------|
| `photographer_verified` | events |
| `find_faces_started` | events |
| `gpu_started` | events |
| `gpu_stopped` | events |
| `gpu_start_failed` | alerts |
| `gpu_sync_failed` | alerts (TODO: INF-009 boot sync — `scripts/sync-gpu-face-worker.sh` non-zero exit; post from app beat or GPU-side hook) |
| `storage_quota` | events |
| `backup_failed` | alerts |

Slack message text must be one short paragraph plus a few `*key:* value` lines. Prefix with a tag: `[SpotMe events]` or `[SpotMe alerts]`. Include `environment` from settings (`production` / `development`) so a mistaken local webhook is obvious.

Pydantic model or TypedDict for payload dicts is fine; keep payloads JSON-serializable for Celery.

### Step 3 — `ObservabilityNotifier` service

File: `backend/app/services/observability_notifier.py`

Constructor injects `Settings` (and optionally a Celery delay callable for tests).

Public methods (names may match event keys):

- `photographer_verified(photographer_id, studio_name, email)`
- `find_faces_started(event_id, studio_name, photos_queued, already_running)`
- `gpu_started(instance_id, reason: str)`
- `gpu_stopped(instance_id, idle_minutes: int)`
- `gpu_start_failed(instance_id, error: str)`
- `storage_quota(photographer_id, studio_name, used_bytes, limit_bytes, percent, band)`
- `backup_failed` is **not** required on this class if the shell script posts directly (Step 8). Prefer a tiny shared JSON shape documented in `observability/README.md`.

Each method:

1. If the chosen webhook URL is empty → return immediately (debug log once at info is too noisy; use debug).
2. `observability_post.delay(event_key, payload)` (or `apply_async` on `notifications`).

Do **not** HTTP in this service if the process is FastAPI; always enqueue. `GpuHostService` runs inside Celery `photo_processing` already: **still enqueue** `notifications` so a Slack outage cannot sit on the GPU start task. Exception: if Redis is down, enqueue fails — catch, log, do not raise.

### Step 4 — Celery task

File: `backend/app/tasks/observability_tasks.py`

- Queue `notifications`
- Name: `app.tasks.observability_tasks.post_slack_event`
- `httpx.Client(timeout=5.0)` POST JSON `{"text": "..."}` (Slack incoming webhook format). Markdown in `text` is enough; no Block Kit required.
- Retry: `bind=True`, `max_retries=3`, `default_retry_delay=15` **only** when response status >= 500 or transport error. Status 400/404/410: log error, **do not retry** (bad webhook).
- Never log the full webhook URL (redact).

Ensure the task module is imported from `celery_app` autodiscover / existing import list so the worker registers it.

### Step 5 — Hook: photographer verified

In `AuthService._verify_registration_otps`, **after** `phone_verified = True` and `email_verified = True` and flush, before or after `_build_token_response`:

Call notifier with `id`, `studio_name`, `email`. Do not fire if verification failed.

Tests: extend auth tests — mock notifier; unverified `register()` does not call it; successful verify calls it once.

### Step 6 — Hook: Find faces

In `FaceProcessingService.start_face_processing`, after a **successful** return path (both `already_running=True` and the enqueue path). Do not fire on `FaceProcessingDisabledError` or `BadRequestError`.

Load studio name from the event’s photographer relation if already loaded; otherwise a small lookup. Do not add N+1 in a loop (this is one event).

If `already_running` is true, still notify (the photographer pressed the button) and set `already_running=true` in the Slack text so it is not mistaken for a second GPU boot.

Tests: existing `test_face_processing_api.py` — mock delay; 400 does not notify; 200 does.

### Step 7 — Hook: GPU lifecycle

In `GpuHostService.ensure_running`:

- After successful `_start_instances` + `_wait_running` (the `return "started"` path) → `gpu_started` with `reason` that distinguishes photographer/reconcile if easy; if the caller is not plumbed, `reason=ensure_running` is acceptable.
- On `return "error"` (including `GpuHostError` handler and `shutting-down` skip) → `gpu_start_failed` with the error string. Do not include AWS key material.

In `stop_if_idle`, on `return "stopped"` after `_stop_instances` → `gpu_stopped`.

Do **not** notify for `skipped`, `busy`, `waiting`, `running`.

Extend `backend/tests/test_gpu_host_service.py` with mocks: started/stopped/error enqueue; already-running does not.

`ensure_gpu_host_running` task currently returns `"error"` on `GpuHostError` without raising — the service method must notify **inside the service** so both the task and `FaceProcessingReconciler` (`ensure_running` direct call) share behaviour.

### Step 8 — Hook: storage quota bands

Add `backend/app/services/storage_quota_alert_service.py` (keep notifier file smaller) **or** methods on the notifier:

Constants:

```python
QUOTA_BANDS: tuple[float, ...] = (0.80, 0.95, 1.00)
QUOTA_HYSTERESIS_POINTS = 5.0  # percent
REDIS_KEY_PREFIX = "spotme:quota_alert:"
```

Algorithm:

1. `percent = 100.0 * used / limit` (if limit <= 0, return).
2. Read Redis JSON `{ "last_band": 0.80 | 0.95 | 1.00 | null }`.
3. Let `band` be the **highest** threshold `t` such that `percent >= t * 100`, or none.
4. If `band` is None: if last_band is set and `percent <= last_band * 100 - 5`, **clear** Redis (re-arm). Return without Slack.
5. If `band` is set and `band > last_band` (treat missing last as 0): Slack `storage_quota` and SET last_band = band.
6. If `band == last_band`: no Slack.
7. If usage jumps 70% → 96%, fire **once** at 0.95 (highest crossed is enough) **or** fire 80 then 95. Prefer **one Slack per ingest with the highest new band** plus mention “crossed 80 and 95” in the text so a 15k ingest does not send three messages. Specify: **single message, highest band reached this call**.

Call this after `storage_used_bytes` is updated in:

- `UploadService` post-finish increment
- `PhotoService` fallback ingest increment
- Any other path that increases used bytes (do not miss tusd hook)

Use **sync Redis** from Celery and **async Redis** from FastAPI consistently with the rest of the app (`create_redis_client` / existing helpers). Do not add a new Redis database number; use `REDIS_URL` (db 0).

Tests: table-driven unit tests as in component §18. Mock Redis.

### Step 9 — Backup script → `#spotme-alerts`

INF-007 is implemented (`scripts/postgres-backup.sh`).

Create `scripts/slack-ops-alert.sh`:

- Source/load `SLACK_WEBHOOK_ALERTS_URL` from `$ENV_FILE` the same way `postgres-backup.sh` loads keys (`load_env_var`).
- If empty, return 0.
- POST a `backup_failed` text body with the error message argument.
- **Must not** `set -e` fail the caller if Slack is down (`curl -fsS --max-time 5 || true`).

In `postgres-backup.sh`, change `die()` to call `slack-ops-alert.sh` (or an inline function) **before** `exit 1`. Do not Slack on success (no “backup OK” spam).

### Step 10 — README

Add “Product events” to `observability/README.md`: table of event keys, which channel, how to send a test:

```bash
# on app EC2, with webhooks set — use a one-off documented curl, not a fake photographer
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"[SpotMe events] test from OBS-002"}' \
  "$SLACK_WEBHOOK_EVENTS_URL"
```

Phone must receive the events-channel test (operator confirms notifications are on for **both** channels).

## Acceptance

- [ ] Empty webhooks: register + verify + start-face-processing + GPU tests pass without HTTP to Slack
- [ ] Verified signup → one `#spotme-events` message with studio name + email + id; `register()` alone does not
- [ ] Find faces 200 → events message including `already_running` when relevant; 400 → none
- [ ] GPU `started` / `stopped` / `error` only, correct channels
- [ ] Quota 80/95/100 once per band; jump to 96% → one message; drop below 75% re-arms 80%
- [ ] Failed backup `die` → `#spotme-alerts`; Slack down does not change backup exit code
- [ ] Worker `-Q photo_processing,notifications` still includes `notifications` (already true in `docker-compose.prod.yml`)
- [ ] pytest covers notifier, quota, GPU hooks, auth hook; no real Slack

## Verification

1. Staging/prod `.env` has both webhooks (from OBS-001).
2. Operator: events-channel curl test on phone.
3. Create a throwaway photographer on production **or** staging, complete OTP, confirm Slack, delete if needed.
4. Confirm a Find-faces click (or mock) posts once.
5. `docker compose logs celery-worker` shows `post_slack_event` success, not the webhook URL.

## Done when

The five product/ops event types in the catalog reach the correct Slack channel without slowing uploads or GPU start, and pytest locks the “when to fire” rules.
