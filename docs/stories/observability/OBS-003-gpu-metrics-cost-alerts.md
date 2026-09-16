# OBS-003 — GPU host metrics and cost alerts

**Type:** Feature  
**Depends on:** OBS-001 (Grafana Cloud + Slack alerts contact point), OBS-002 (GPU Slack events already exist), INF-009 (GPU EC2 + `GpuHostService`)  
**Area:** GPU systemd Alloy + NVIDIA exporter, app `/metrics` GPU gauge, Grafana GPU dashboard + two cost alerts  
**Python:** 3.10 for the gauge only

## Business outcome

While the `g4dn.xlarge` is **running**, Grafana shows GPU utilisation, VRAM, and temperature. The operator’s phone gets a `#spotme-alerts` push if:

- The instance is running **and** GPU util stays ~0% for **15 minutes** (paying ~$0.58/h for an idle T4), or
- The instance stays running for **4 hours** (Find faces should not need that; idle stop is 10 minutes when healthy).

Expected start/stop continues to go to `#spotme-events` from OBS-002. This story pages **waste**, not the happy path.

## Purpose

NVIDIA metrics can only be scraped **on the GPU box**, and only while it is up. The **running/stopped** bit must still come from the **app EC2** (`DescribeInstances` / `GpuHostService`), because when the instance is stopped there is no NVIDIA exporter. Alerting on `absent(nvidia_gpu_duty_cycle)` would fire all day in the healthy stopped state — **forbidden**.

## References (read first)

- `docs/component_observability.md` §3, §7.2, §8.2, §9, §13
- `infrastructure/compute/gpu-host.md` — systemd worker, no Compose, no EIP
- `backend/app/services/gpu_host_service.py` — `describe_state()`, `_RUNNING`
- `observability/alloy/app.alloy` (OBS-001) — extend scrape of backend `/metrics` here if OBS-004 has not landed; see Step 4
- OBS-002 — do not duplicate `gpu_started` Slack

## Out of scope

- Loki on GPU (OBS-004 may add journal; if cheaper to add the Alloy loki block here **only** for `spotme-face-worker`, that is allowed — do not ship syslog noise)
- Changing idle stop from 10 minutes
- CloudWatch GPU metrics
- DCGM if a single-process `nvidia-gpu-exporter` is enough for one T4
- Slack from the GPU host

## Non-negotiables

1. Alloy + NVIDIA exporter = **systemd on the GPU EC2**, not Docker Compose (no Compose stack there).
2. Grafana token on the GPU box is Grafana Cloud ingest only — **no Slack webhooks** in GPU env.
3. Cost alerts **must AND** `spotme_gpu_instance_running == 1` (app metric). Never `absent(nvidia_*)` alone.
4. `spotme_gpu_instance_running` is 1 when AWS state is `running` or `pending`, else 0. Update on ensure/stop **and** on a cheap periodic refresh so a console stop is visible within one scrape interval (60s) plus beat (existing `stop_idle_gpu_host` already describes state every minute — set the gauge there).
5. Do not page when the GPU is stopped.
6. Stay under the 10k series cap: one GPU, few NVIDIA metrics, `instance="spotme-gpu"`.

## Implementation plan

### Step 1 — NVIDIA exporter on the GPU host

Pick **one** well-maintained exporter that works with a Tesla T4 on Ubuntu 24.04. Preferred: [nvidia_gpu_exporter](https://github.com/utkuozdemir/nvidia_gpu_exporter) **pinned release**, listen **127.0.0.1:9835** (not `0.0.0.0`).

`scripts/install-gpu-alloy.sh` (or split install-nvidia-exporter) must:

1. Install the binary under `/usr/local/bin`
2. systemd unit `nvidia-gpu-exporter.service`: After `nvidia-persistenced.service` if present; Restart=always; bind localhost
3. **Not** open SG port 9835. App SG / GPU SG stay as INF-009 (SSH from operator IP only)

If `nvidia-smi` is missing, the script must fail loudly (this host is supposed to have NVIDIA drivers from INF-009).

### Step 2 — Alloy systemd on the GPU host

Create `observability/alloy/gpu.alloy`:

- `prometheus.exporter.unix` with the same filesystem drop list as app
- Scrape `127.0.0.1:9835` job `gpu-nvidia`
- `instance="spotme-gpu"`
- remote_write to the **same** Grafana Cloud stack (same env var names as OBS-001)
- scrape 60s
- Do not scrape the app Redis/Postgres from the GPU

Install Grafana Alloy via the **official apt repo** (document exact commands in `infrastructure/compute/gpu-host.md` § new “Observability”). systemd `alloy.service` EnvironmentFile=`/etc/alloy/env` (chmod 600) with `GRAFANA_CLOUD_*` only.

`scripts/install-gpu-alloy.sh`:

- Install alloy + unit
- Copy `gpu.alloy` from the repo
- Enable `alloy.service` and `nvidia-gpu-exporter.service` so they start on every **StartInstances** boot

After StopInstances, they are simply off — that is correct.

Add Grafana Cloud keys to `.env.gpu.example` as empty placeholders. Operator copies them onto the GPU `backend/.env` or `/etc/alloy/env`. Prefer `/etc/alloy/env` so the Celery worker does not need Grafana credentials.

### Step 3 — Gauge on the app: `spotme_gpu_instance_running`

OBS-004 adds the full `/metrics` surface. **This story must expose the gauge even if OBS-004 is not done**, otherwise cost alerts cannot be written.

If `/metrics` does not exist yet:

1. Add `prometheus_client` (or `prometheus-fastapi-instrumentator` — if you add instrumentator now, keep HTTP metrics disabled until OBS-004 to avoid extra series, **or** enable them and let OBS-004 own dashboards; do not add two competing libraries).
2. Expose `GET /metrics` on the FastAPI app **without** adding it to Caddy. Confirm `Caddyfile` has no `/metrics` handle (OBS-004 will add an explicit 404).
3. Metric:

```text
spotme_gpu_instance_running 0|1
```

Optional: `spotme_gpu_instance_info{state="running"}` — **do not** use `state` as a high-cardinality label with instance ids other than the one GPU.

Update the gauge in `GpuHostService.ensure_running` / `stop_if_idle` / `describe_state` paths. Also set it at process startup if `GPU_INSTANCE_ID` is empty → **do not export 0 forever as “stopped” on the laptop**; when not configured, **omit the metric** or export `spotme_gpu_configured 0` and skip the running gauge so Grafana alerts with `instance="spotme-app"` in production are not confused by local scrapes (laptop has no Alloy).

Alloy app config: add scrape `http://backend:8000/metrics` job `app-backend` **in this story** (required for the gauge). Relabel keep only `spotme_gpu_*` until OBS-004; dropping other process metrics is optional if series count stays low (`process_*` is fine).

### Step 4 — GPU dashboard

`observability/grafana/dashboards/gpu-host.json`:

- GPU util %
- VRAM used / total
- GPU temperature
- Host RAM
- Stat panel: `spotme_gpu_instance_running` (from app job)

Title: `SpotMe / GPU EC2`. No-data while stopped is **expected**; panel description must say so.

### Step 5 — Cost alerts → `#spotme-alerts`

Append to `observability/grafana/alert-rules.md` and create in Grafana UI (same contact point as OBS-001).

**Alert C — `SpotMeGpuIdleWhileRunning`**

Intent: instance on, GPU util < 1% for 15m.

NVIDIA metric names depend on the exporter — **verify in Explore** after the first GPU boot (`{instance="spotme-gpu"}`). Example shape (replace with real names):

```promql
spotme_gpu_instance_running{instance="spotme-app"} == 1
and
(max_over_time(nvidia_smi_utilization_gpu_ratio{instance="spotme-gpu"}[15m]) < 0.01
 or absent(nvidia_smi_utilization_gpu_ratio{instance="spotme-gpu"}))
```

The `absent()` branch is only valid **together with** `spotme_gpu_instance_running == 1` (exporter broken while AWS says running). If that double condition is hard to express, use two alerts:

1. `running == 1` AND util < 1% for 15m (when NVIDIA series exist)
2. `running == 1` AND `up{job="gpu-nvidia"} == 0` for 10m (exporter/Alloy died after boot)

**Do not** fire (2) when `running == 0`.

**Alert D — `SpotMeGpuRunningTooLong`**

```promql
spotme_gpu_instance_running{instance="spotme-app"} == 1
```

- `for`: **4h**
- Summary: `GPU EC2 running > 4 hours`
- Description: idle stop should have fired after 10 minutes empty queue; check `stop_idle_gpu_host`, Redis locks, `face_processing` LLEN.

Constant: document `SPOTME_GPU_RUNNING_ALERT_HOURS=4` in `alert-rules.md` (Grafana UI does not read `.env` for `for:`).

### Step 6 — GPU host runbook

Update `infrastructure/compute/gpu-host.md`:

- Install script commands
- `/etc/alloy/env` keys
- After first boot, `systemctl status alloy nvidia-gpu-exporter`
- `curl -s http://127.0.0.1:9835/metrics | head`
- Reminder: stop the instance when done; Alloy will go away

Operator must **StartInstances once** (or click Find faces) to verify NVIDIA series, then allow idle stop.

## Acceptance

- [ ] GPU boot starts `alloy` and `nvidia-gpu-exporter` via systemd
- [ ] Explore: `{instance="spotme-gpu"}` has util/VRAM/temp while running; **no data** while stopped
- [ ] Explore: `spotme_gpu_instance_running` on `spotme-app` is 1 when AWS running, 0 when stopped (within ~2 minutes)
- [ ] Alerts C and D exist, Slack `#spotme-alerts`, cannot fire when GPU is stopped
- [ ] GPU SG still has no 9835/12345 from the world
- [ ] `.env.gpu.example` documents Grafana vars; no Slack vars on GPU
- [ ] pytest: gauge/helper does not break `test_gpu_host_service.py`; unconfigured GPU does not require Prometheus

## Verification

1. Note GPU state in AWS. Grafana gauge matches.
2. Start GPU, wait for systemd, confirm NVIDIA series.
3. Stop GPU (or wait idle 10 min). NVIDIA series go stale; gauge 0; alerts C/D not firing.
4. Optional: Grafana “preview” of alert D — do not leave a 1-minute `for` in production.

## Done when

Idle-GPU and long-running-GPU pages exist, NVIDIA charts work during jobs, and a stopped GPU is silent.
