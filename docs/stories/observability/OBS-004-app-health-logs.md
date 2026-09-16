# OBS-004 — App health, queues, Loki, public `/health` probe

**Type:** Feature  
**Depends on:** OBS-001 (Alloy + Grafana Cloud + Slack alerts channel)  
**Area:** FastAPI `/metrics`, Caddy deny `/metrics`, Alloy Loki, Grafana synthetic check, 5xx/queue/site-down alerts  
**Python:** 3.10 only

## Business outcome

The operator is paged on `#spotme-alerts` when:

- The **public site** is down (`https://spotme.hpklabs.ai/health` fails from the internet)
- The API is throwing **5xx** for 5 minutes
- **Postgres/Redis** look down from the app’s point of view
- **Celery queues** `photo_processing` or `face_processing` stay stuck high for 15 minutes

They can also search **application logs** in Grafana (Loki) for backend / Celery / tusd without SSH.

## Purpose

OBS-001 pages on disk/RAM (machine full). OBS-002 pages on product actions. This story pages on **the product not working**, and gives logs to debug the Slack message.

A probe from Alloy on the app box to `backend:8000/health` is **not** “site down” (Caddy/TLS/DNS can be dead while uvicorn is fine). Site down **must** be a Grafana Cloud **Synthetic Monitoring** HTTP check against the public URL.

## References (read first)

- `docs/component_observability.md` §6 (log cap), §7.1, §8.2–8.4, §13–15
- `backend/app/api/health.py` — `/health` returns `{"status":"ok"}`; `/health/ready` hits Postgres
- `Caddyfile` — currently `/health` and `/api/*` only
- `docker-compose.prod.yml` — Redis broker db 1 (`CELERY_BROKER_URL=redis://redis:6379/1`), queues `photo_processing`, `notifications`; GPU uses `face_processing` on the same broker
- `observability/alloy/app.alloy` from OBS-001
- OBS-003 may already scrape `/metrics` for `spotme_gpu_*` — **extend that scrape**, do not add a second job against the same path

## Out of scope

- Sentry
- Shipping Caddy/Next **access** logs
- Tracing
- Alerting on every Celery `task_failure` log line (too noisy). 5xx + queue depth + Loki search is enough
- Replacing `OPS_ALERT_EMAIL` for stalled Find-faces

## Non-negotiables

1. `GET /metrics` is **not** on the public internet. Caddy must `respond 404` for `/metrics`.
2. Loki ingest must stay tiny: only listed containers; drop health-check paths.
3. Queue lengths come from **Redis LLEN** on the **broker** (`CELERY_BROKER_URL`, database **1**), not Redis db 0. Wrong DB → always 0 → silent false safety.
4. Synthetic check: `https://spotme.hpklabs.ai/health`, expect 200 and body containing `"status":"ok"`. Interval 1 minute. One location. Slack contact `slack-spotme-alerts`.
5. Do not probe `/metrics` from Grafana Cloud (would require publishing it).
6. Scrape interval remains 60s.

## Implementation plan

### Step 1 — FastAPI `/metrics`

Use `prometheus-fastapi-instrumentator` **or** `prometheus_client` + a small ASGI mount. One library only (if OBS-003 already added `prometheus_client`, extend it; do not double-instrument HTTP).

Metrics required:

| Name | Type | Labels |
|------|------|--------|
| HTTP request count / latency | histogram/counter | `handler`, `method`, `status` — **low cardinality**: use route templates (`/api/v1/events/{id}`), never raw IDs |
| `spotme_celery_queue_length` | gauge | `queue` = `photo_processing` \| `face_processing` \| `notifications` |
| `spotme_gpu_instance_running` | gauge | already OBS-003 |

Update queue gauges on a background interval **or** inside the metrics scrape collector (prefer a custom Collector that LLEN-s three keys on scrape so values are fresh without a thread). Use **sync** Redis against `settings.celery_broker_url`. Keys are exactly the Celery Redis list names: `photo_processing`, `face_processing`, `notifications`.

If `GPU_INSTANCE_ID` is set, keep OBS-003 gauge logic.

Tests: `/metrics` returns `200` and `text/plain` in the ASGI test client; does not require Grafana. Assert queue series exist (mock Redis llen).

### Step 2 — Caddy

In `Caddyfile`, **before** `handle /api/*`:

```caddy
handle /metrics {
	respond 404
}
```

Do not reverse_proxy `/metrics`.

### Step 3 — Alloy Loki (app)

Update `observability/alloy/app.alloy` (uncomment / add, do not create `app-logs.alloy`):

- `loki.source.docker` with docker.sock read-only
- Keep containers: `backend`, `celery-worker`, `celery-beat`, `tusd` only
- Drop log lines matching `/health` or `/health/ready` access if they appear
- `loki.write` to `GRAFANA_CLOUD_LOKI_*`
- Relabel `instance="spotme-app"`, `container` = compose name

If log volume is high, drop `debug` level. Backend uses structlog JSON — keep `info` and above.

GPU journal for `spotme-face-worker` (if not done in OBS-003): add `loki.source.journal` match unit in `gpu.alloy`. Optional but useful; do it if OBS-003 left a comment.

### Step 4 — Dashboards

Extend `app-host.json` or add `observability/grafana/dashboards/app-health.json`:

- RPS
- p95 latency
- 5xx rate
- queue length timeseries (three queues)
- Log panel (Loki) for `{container="backend"}` errors

Import in Cloud.

### Step 5 — Grafana alerts

Append `observability/grafana/alert-rules.md` and create UI rules. Contact: `slack-spotme-alerts`.

**Alert E — `SpotMeApi5xx`**

- 5xx rate > **1 per minute** for 5m (tune if Explore shows health-check noise — there should be none on `/metrics`)
- Ignore 4xx

**Alert F — `SpotMeBackendDown`**

- `up{job="app-backend"} == 0` for 2m  
  This is uvicorn scrape failure (process dead). Complements synthetic (Caddy/DNS).

**Alert G — `SpotMeQueueStuck`**

```promql
spotme_celery_queue_length{queue=~"photo_processing|face_processing"} > 50
```

- `for`: 15m  
- Description: 50 is a starting floor; a 15k Find-faces job **will** legitimately queue photos. **Revise the threshold after the first real event** and write the chosen number back into `alert-rules.md`. Until then, use **`> 50` AND `increase(...) == 0`** over 15m (depth high **and not draining**):

```promql
spotme_celery_queue_length{queue=~"photo_processing|face_processing"} > 50
unless
(delta(spotme_celery_queue_length{queue=~"photo_processing|face_processing"}[15m]) < 0)
```

Implement the **not draining** form so a healthy 15k drain does not page. If `delta` is awkward, `deriv(...) >= 0` for 15m while `> 50`. Verify in Explore with a synthetic llen if needed.

**Alert H — site down** is **not** PromQL. Step 6.

Postgres-down: `/health/ready` is not public-checked yet. Add **either**:

- Synthetic check #2 on `https://spotme.hpklabs.ai/health/ready` (200 + `"ready"`), **or**
- Rely on Alert F plus site `/health`

Prefer a **second** synthetic on `/health/ready` (covers DB). Same Slack contact. Name: `SpotMeReadyCheck`.

### Step 6 — Grafana Cloud Synthetic Monitoring

README click-path:

1. Grafana Cloud → Synthetic Monitoring (or “Checks”)
2. Add HTTP check `SpotMeHealth`
3. URL `https://spotme.hpklabs.ai/health`
4. Method GET, timeout 10s, frequency 60s
5. Probe location: closest to India if listed (e.g. Singapore / Mumbai)
6. Validation: status 200; body regex `ok`
7. Alerting: fail after **2** consecutive failures → Slack contact point `slack-spotme-alerts`
8. Repeat for `/health/ready` if Step 5 chose it

If Free stack **does not include** Synthetic Monitoring: document that in README and use Grafana Cloud’s **Hosted Probe** alternative only if it is still free. **Do not** substitute with Alloy scraping `https://spotme.hpklabs.ai` from the same EC2 as a “public” check. **Do not** add UptimeRobot unless synthetics are unavailable — if unavailable, stop and record the portal limitation in the PR; do not invent a third vendor without updating this component doc.

### Step 7 — Relabel HTTP metrics

Instrumentator can explode series (`handler` + `worker`). Force:

- `should_group_status_codes=True` if available
- Exclude `/metrics` and `/health` from histograms
- No `untemplated` paths

Re-check Grafana Cloud series count after deploy. If HTTP metrics push the stack near 10k, drop histograms and keep counters only.

## Acceptance

- [ ] `GET https://spotme.hpklabs.ai/metrics` is **404** (or connection not proxied); `GET http://backend:8000/metrics` from Alloy works
- [ ] `/metrics` includes queue gauges; broker db 1 confirmed
- [ ] Loki shows backend/celery/tusd logs; Caddy access logs **absent**
- [ ] Alerts E, F, G created with Slack; G does not fire merely because a large job is draining
- [ ] Synthetic `SpotMeHealth` created; killing Caddy (operator test in a maintenance window) or a Grafana “test fail” pages Slack — do **not** take production down if the operator forbids it; then verify with Grafana’s check test feature
- [ ] pytest for `/metrics` and Caddyfile contains the 404 handle
- [ ] Series count still comfortable (< ~2000 extra)

## Verification

1. Explore Loki: `{container="backend"} |= "error"` returns structlog JSON, not empty because wrong labels.
2. `docker compose exec alloy wget -qO- http://backend:8000/metrics | grep spotme_celery_queue_length`
3. `curl -sI https://spotme.hpklabs.ai/metrics` is 404
4. Synthetic check history is green
5. Phone: Grafana contact-point test still works after adding alerts (policy not overwritten)

## Done when

Site-down, 5xx, backend scrape down, and stuck queues can page Slack, and Loki is usable for those four containers without blowing the 50 GB log cap.
