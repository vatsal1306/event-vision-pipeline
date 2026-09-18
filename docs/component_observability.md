# Component Document: Observability

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Scope:** Production metrics, logs, product events, and phone alerts for SpotMe  
> **Development order:** Component 5 — after the app EC2 (INF-005) and GPU host lifecycle (INF-009). Independent of INF-008.  
> **Pager:** Slack free-tier push (not Grafana mobile, not SMS, not CloudWatch).  
> **Metrics/logs backend:** Grafana Cloud Free (not self-hosted Prometheus/Loki/Grafana on the app box).

**Always read this document before implementing any `OBS-*` story.** Stories are execution plans. This file is the source of truth for *what* we collect, *from where*, *who pages the phone*, and *what we refuse to do*.

---

## Table of Contents

1. [Purpose and business outcome](#1-purpose-and-business-outcome)
2. [What this is not](#2-what-this-is-not)
3. [Architecture](#3-architecture)
4. [Two pipelines: events vs thresholds](#4-two-pipelines-events-vs-thresholds)
5. [Accounts and Slack channels](#5-accounts-and-slack-channels)
6. [Grafana Cloud Free limits](#6-grafana-cloud-free-limits)
7. [Where telemetry comes from](#7-where-telemetry-comes-from)
8. [Catalog: events, alerts, metrics, logs](#8-catalog-events-alerts-metrics-logs)
9. [Why GPU start/stop is emitted from the app EC2](#9-why-gpu-startstop-is-emitted-from-the-app-ec2)
10. [Disk vs 15k photo uploads](#10-disk-vs-15k-photo-uploads)
11. [Repository layout](#11-repository-layout)
12. [Configuration and secrets](#12-configuration-and-secrets)
13. [Alloy placement and scrape rules](#13-alloy-placement-and-scrape-rules)
14. [Backend notifier contract](#14-backend-notifier-contract)
15. [Security](#15-security)
16. [Story map](#16-story-map)
17. [Out of scope](#17-out-of-scope)
18. [Testing strategy](#18-testing-strategy)

---

## 1. Purpose and business outcome

SpotMe runs on one always-on app EC2 (`c6a.xlarge`, 8 GB RAM, ~100–200 GB gp3) plus an on-demand GPU EC2 (`g4dn.xlarge`) that is **stopped** when idle. Failures that hurt the business are not “CPU looked interesting on a laptop chart.” They are:

- The app disk filling so tusd/Postgres die during a night upload.
- The GPU instance left **running** (about **$0.58/hour** in Mumbai) after Find faces finishes.
- The public site down so photographers and guests cannot log in.
- A photographer hitting storage quota mid-upload.
- A new photographer signing up, or Find faces being triggered, without the operator knowing.

**Outcome:** the operator’s phone gets a Slack push for those events and for health/cost threshold fires. Grafana Cloud is for charts when investigating. Slack is the pager.

---

## 2. What this is not

| Do not | Why |
|--------|-----|
| Put Prometheus, Loki, or Grafana OSS on the app `c6a.xlarge` | 8 GB is already Postgres + Redis + Next + FastAPI + tusd + Celery |
| CloudWatch Agent, CloudWatch custom metrics, SNS SMS | Metered; SMS to India is paid; we already chose Grafana Cloud + Slack |
| Sentry | SDK is wired (`init_sentry`) but `SENTRY_DSN` is empty. Out of scope for OBS-\* |
| INF-008 | Separate leftover story (fail2ban / unattended-upgrades). Do not fold it in |
| Alloy on the laptop | Burns Grafana Cloud’s 10k series cap with `dev` junk |
| Public `/metrics` | Must never be published through Caddy |
| Slack as a metrics database | Only discrete events and firing alerts |
| Page on CPU 60%, every HTTP 200, or every Celery success | Operator will mute the channel |

Existing `OPS_ALERT_EMAIL` (stalled Find-faces email) stays. Slack does not replace it in v1.

---

## 3. Architecture

```
Photographers / guests
        │  HTTPS
        ▼
┌──────────────────────────────────────────┐     ┌─────────────────────────────┐
│ App EC2 (always on)                      │     │ GPU EC2 (often STOPPED)     │
│  docker-compose.prod.yml                 │     │  systemd: spotme-face-worker│
│  docker-compose.observability.yml        │     │  systemd: alloy + nvidia    │
│    Alloy (unix + docker + backend scrape │     │    exporter (only while up) │
│     + Loki docker logs)                  │     │                             │
│  FastAPI /metrics (internal only)        │     │  NVIDIA util / VRAM / temp  │
│  SlackNotifier → Celery `notifications`  │     │                             │
│  GpuHostService Start/StopInstances      │     │  CANNOT page reliably       │
└──────────────────┬───────────────────────┘     └──────────────┬──────────────┘
                   │  remote_write / loki.push                  │
                   └────────────┬───────────────────────────────┘
                                ▼
                     Grafana Cloud Free
                     (Prometheus + Loki + Grafana + alerting
                      + 1 synthetic HTTP check)
                                │
                    threshold alerts ──► Slack #spotme-alerts
                                │
App SlackNotifier ── product events ──► Slack #spotme-events
App SlackNotifier ── ops events     ──► Slack #spotme-alerts
                                │
                     Slack iOS/Android push
```

**Hard rule:** the GPU host is powered off most of the time. Anything installed on it is also off. Product/ops messages about GPU **lifecycle** are sent from the **app EC2**. NVIDIA utilisation is collected from the GPU host **only while it is running**.

---

## 4. Two pipelines: events vs thresholds

| Pipeline | Transport | When it fires | Slack channel |
|----------|-----------|---------------|---------------|
| **Product / ops events** | Backend `ObservabilityNotifier` → Celery `notifications` → Slack incoming webhook | The moment the code path succeeds or fails | Events or Alerts (see catalog) |
| **Threshold alerts** | Alloy → Grafana Cloud → Grafana alert rule (`for: 5m` or `10m`) → Slack contact point | Condition stays true long enough | `#spotme-alerts` only |
| **Site down** | Grafana Cloud Synthetic Monitoring HTTP check against `https://spotme.hpklabs.ai/health` | Probe fails from the public internet | `#spotme-alerts` |

Do **not** implement “new photographer” as a Prometheus `increase() > 0` alert. Alertmanager/Grafana threshold alerting is the wrong tool for one-shot product events.

---

## 5. Accounts and Slack channels

No Grafana Cloud or Slack accounts exist yet. **OBS-001** creates both. No credit card for Grafana Cloud Free or Slack Free.

### Slack (free workspace)

1. Create a workspace (name e.g. `hpklabs` / `spotme` — operator’s choice; record it in the OBS-001 runbook notes, not in git).
2. Create **two** public channels:
   - `#spotme-alerts` — pages that mean “something may be on fire or costing money”
   - `#spotme-events` — expected product activity
3. Create a Slack App with Incoming Webhooks. Add **two** webhook URLs, one per channel.
4. Phone: Slack app, both channels set to **All new messages** (not just mentions).

Free-tier limit is **90-day message history**, not push. Push notifications on the Slack mobile app are included.

### Grafana Cloud (free stack)

1. Sign up at [grafana.com](https://grafana.com) → Grafana Cloud Free (no credit card).
2. Create one stack. Prefer an Asia-Pacific region if the portal offers it; otherwise EU. Record the stack URL in the server `.env` comments, never commit tokens.
3. Create one **Cloud Access Policy** token named `spotme-alloy` with `metrics:write` and `logs:write`.
4. Copy Prometheus remote-write URL + numeric username, Loki push URL + username, and the token into the app EC2 `.env` (OBS-001) and the GPU host env (OBS-003).
5. Contact point: Slack incoming webhook for **`#spotme-alerts` only**. Product events never go through Grafana.

Three Grafana Cloud users is enough (operator + optional future teammate).

---

## 6. Grafana Cloud Free limits

Treat these as hard caps. Exceeding them silently starts a paid invoice or drops data.

| Resource | Free cap | How we stay under |
|----------|----------|-------------------|
| Active metric series | **10,000** | Scrape 60s; drop cAdvisor per-CPU / overlay / id hashes; keep container `name` only |
| Log ingest | **50 GB / month** | Ship backend + celery + tusd JSON; drop Caddy/Next access logs and health-check noise |
| Retention | **14 days** | Acceptable for ops; not a long-term archive |
| Users | **3** | Operator |
| k6 VUh | 500 / month | Do **not** use k6 for uptime. Use Synthetic Monitoring (one HTTP check) |

Default Alloy scrape interval: **60s** (1 DPM). Do not scrape every 15s.

---

## 7. Where telemetry comes from

### 7.1 App EC2 (always on) — OBS-001, then OBS-002/004/005

| Source | What | Story |
|--------|------|--------|
| Grafana Alloy `prometheus.exporter.unix` | CPU, load, RAM, disk %, disk IO, network | OBS-001 |
| Alloy docker discovery (filtered) | Container CPU/RAM for named Compose services only | OBS-001 |
| FastAPI `GET /metrics` (docker network only) | HTTP RPS/latency/5xx, Celery queue lengths, GPU running gauge | OBS-003 (GPU gauge), OBS-004 (HTTP + queues) |
| Alloy `loki.source.docker` | backend, celery-worker, celery-beat, tusd logs | OBS-004 |
| `ObservabilityNotifier` | Product/ops Slack events | OBS-002 |
| Cron `scripts/s3-bucket-size.sh` | Daily S3 used-bytes → Slack if over cap; optional textfile metric | OBS-005 |
| Cron `scripts/postgres-backup.sh` | Backup failure → `#spotme-alerts` | OBS-002 |
| Grafana Cloud synthetic | `GET https://spotme.hpklabs.ai/health` | OBS-004 |

Compose service names to keep (drop everything else): `caddy`, `frontend`, `backend`, `tusd`, `celery-worker`, `celery-beat`, `db`, `redis`. Alloy itself may be scraped for `up` only.

### 7.2 GPU EC2 (only while running) — OBS-003

| Source | What |
|--------|------|
| Alloy `prometheus.exporter.unix` | Host CPU/RAM/disk |
| `nvidia-gpu-exporter` (or DCGM if already installed) | GPU util %, VRAM used/total, temperature |
| Alloy Loki | `journalctl` for `spotme-face-worker.service` |

Install Alloy **and** the NVIDIA exporter as **systemd** units (this host has no Compose stack). They start on boot so they exist for the 10–40 minutes the instance is up, then die with `StopInstances`.

### 7.3 AWS, without a CloudWatch bill

- **Do not** install the CloudWatch Agent.
- **Do not** publish custom CloudWatch metrics.
- **OBS-005** may **read** the AWS-provided `AWS/S3` `BucketSizeBytes` daily metric via `get-metric-statistics`. S3 publishes this itself (once per day). That is not a custom metric and is not SNS. Recursive `aws s3 ls --summarize` on a 15k-object bucket is **forbidden** (LIST request cost).

GPU instance state for Grafana (`spotme_gpu_instance_running`) is **not** CloudWatch. It is `DescribeInstances` from `GpuHostService` (credentials already on the app box) exported on `/metrics`.

---

## 8. Catalog: events, alerts, metrics, logs

This is the complete v1 set. Stories must not add extras (guest selfie mismatch, every 4xx, Docker prune nag, Celery task-success).

### 8.1 Slack events (`ObservabilityNotifier`)

| Event key | Channel | When to fire | Payload (no secrets) | Story |
|-----------|---------|--------------|----------------------|-------|
| `photographer_verified` | `#spotme-events` | After registration OTPs succeed (`AuthService._verify_registration_otps`), **not** on `register()` | `photographer_id`, `studio_name`, `email` | OBS-002 |
| `find_faces_started` | `#spotme-events` | Every accepted `start_face_processing` (including `already_running=true`). Not on 400 “no photos” | `event_id`, `studio_name`, `photos_queued`, `already_running` | OBS-002 |
| `gpu_started` | `#spotme-events` | `GpuHostService.ensure_running()` returns **`started`** only (not `running` / `skipped`) | `instance_id`, `reason=find_faces_or_reconcile` | OBS-002 |
| `gpu_stopped` | `#spotme-events` | `stop_if_idle()` returns **`stopped`** | `instance_id`, `reason=idle_timeout`, `idle_minutes` | OBS-002 |
| `gpu_start_failed` | `#spotme-alerts` | `ensure_running()` returns **`error`** | `instance_id`, `error` (no AWS keys) | OBS-002 |
| `storage_quota` | `#spotme-events` | Photographer used-bytes crosses **80%**, **95%**, or **100%** of `storage_limit_bytes`. Once per band until usage falls 5 points below that band | `photographer_id`, `studio_name`, `used_bytes`, `limit_bytes`, `percent`, `band` | OBS-002 |
| `backup_failed` | `#spotme-alerts` | `scripts/postgres-backup.sh` `die` | hostname, error line | OBS-002 |

Laptop: empty webhook URLs → notifier is a no-op (same pattern as empty `SENTRY_DSN`).

### 8.2 Grafana → Slack `#spotme-alerts`

| Alert | PromQL intent | `for` | Story |
|-------|---------------|-------|-------|
| App disk > 80% | Root filesystem (not overlay/tmpfs) used ratio > 0.80 | 10m | OBS-001 |
| App RAM > 85% | `1 - MemAvailable/MemTotal > 0.85` | 10m | OBS-001 |
| API 5xx | Rate of HTTP 5xx on FastAPI > small floor (e.g. 1/min) | 5m | OBS-004 |
| Redis or Postgres down | `up{job="backend"} == 0` **or** `/health/ready` synthetic fail; plus queue scrape failure | 2m | OBS-004 |
| Celery queue stuck | `spotme_celery_queue_length` for `photo_processing` or `face_processing` high and not falling | 15m | OBS-004 |
| GPU running + util ~0% | `spotme_gpu_instance_running == 1` AND NVIDIA util < 1% | 15m | OBS-003 |
| GPU running too long | `spotme_gpu_instance_running == 1` for **4 hours** | 4h | OBS-003 |
| Site down | Synthetic `https://spotme.hpklabs.ai/health` not 200 / body missing `"status":"ok"` | 2m | OBS-004 |

Do not alert on `absent(nvidia_*)` when the GPU instance is stopped — that is the healthy state. Always combine with `spotme_gpu_instance_running` from the **app** `/metrics`.

### 8.3 Metrics (Grafana dashboards, not Slack)

**App host dashboard (OBS-001, extended in OBS-004):** CPU %, load, RAM %, root disk %, network bits, per-container RSS for the keep-list, HTTP RPS / p95 / 5xx (OBS-004), queue lengths (OBS-004), `spotme_gpu_instance_running` (OBS-003).

**GPU host dashboard (OBS-003):** NVIDIA util, VRAM, temperature, host RAM. Empty/no-data while the instance is stopped is expected.

**Business counters (optional, OBS-004 if cheap):** Prometheus counters `spotme_photographers_verified_total`, `spotme_find_faces_started_total` — increment in the same service methods as Slack. Do not page on them.

### 8.4 Logs (Loki, OBS-004)

Keep: `backend`, `celery-worker`, `celery-beat`, `tusd`, GPU `spotme-face-worker` journal.

Drop: Caddy access log, Next.js, container health-check probes, Alloy debug.

---

## 9. Why GPU start/stop is emitted from the app EC2

The GPU EC2 is **stopped** (disk kept) when Find faces is not running. `GpuHostService` on the **app** box is the only process that calls `StartInstances` / `StopInstances` (`backend/app/services/gpu_host_service.py`, tasks on queue `photo_processing`).

If a Slack webhook ran **on the GPU host**:

- **Start:** Alloy/systemd is not up for 1–3 minutes after boot, so the “started” message is late or lost.
- **Stop:** the machine is being powered off; the process may never flush HTTP.
- **Console stop / failed start:** the GPU box never ran, so it cannot say “I failed to start.”

NVIDIA util/VRAM still come from the GPU host, because that hardware exists only there, and only while the instance is `running`.

---

## 10. Disk vs 15k photo uploads

Production tusd is S3-backed (`-s3-bucket`, 5 MB parts in `docker-compose.prod.yml`). A 15k × 10–30 MB album (**~150–450 GB**) lands in the originals **bucket**, not on gp3.

What *does* use the 100–200 GB disk: Postgres data, Docker images/layers, container json-file logs, a few in-flight proxy temps (Celery concurrency 2), ML weights for guest selfie on the app box.

**Therefore:** disk > 80% is still a real pager (logs and images fill the disk over weeks; a tusd misconfig pointing at local disk would fill it during one upload). It is **not** “the 15k originals sat on EC2.”

---

## 11. Repository layout

Created by the OBS stories (do not invent a second tree):

```
event-vision-pipeline/
├── docker-compose.observability.yml   # OBS-001 — merge with prod; never used alone
├── observability/
│   ├── alloy/
│   │   ├── app.alloy                  # env() placeholders; no tokens
│   │   └── gpu.alloy
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── app-host.json
│   │   │   └── gpu-host.json
│   │   └── alert-rules.md             # exact PromQL + `for` + summary text
│   └── README.md                      # operator: accounts, merge compose, GPU systemd
├── scripts/
│   ├── slack-ops-alert.sh             # OBS-002 — used by postgres-backup.sh
│   ├── install-gpu-alloy.sh           # OBS-003
│   └── s3-bucket-size.sh              # OBS-005
└── backend/app/services/observability_notifier.py   # OBS-002
```

Local `backend/docker-compose.yml` must **not** include Alloy.

---

## 12. Configuration and secrets

Add to `.env.prod.example` and `backend/.env.example` (empty defaults). Never commit values.

| Variable | Where | Purpose |
|----------|-------|---------|
| `SLACK_WEBHOOK_ALERTS_URL` | App `.env` only | `#spotme-alerts` |
| `SLACK_WEBHOOK_EVENTS_URL` | App `.env` only | `#spotme-events` |
| `GRAFANA_CLOUD_PROMETHEUS_URL` | App `.env` + GPU env | remote_write |
| `GRAFANA_CLOUD_PROMETHEUS_USERNAME` | App + GPU | instance id |
| `GRAFANA_CLOUD_LOKI_URL` | App + GPU | Loki push |
| `GRAFANA_CLOUD_LOKI_USERNAME` | App + GPU | instance id |
| `GRAFANA_CLOUD_TOKEN` | App + GPU | Access Policy token |
| `SPOTME_S3_BUDGET_GB` | App `.env` | OBS-005 Slack threshold (default **350**) |
| `SPOTME_GPU_RUNNING_ALERT_HOURS` | Grafana rule / comment | **4** (cost) |

Empty Slack URLs: no HTTP, no exception to the photographer.

GPU host: Grafana Cloud vars only. **No** Slack URLs on the GPU box.

---

## 13. Alloy placement and scrape rules

**App EC2:** service `alloy` in `docker-compose.observability.yml`. Operator always runs:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d
```

Same Compose project directory ⇒ shared default network ⇒ Alloy can reach `backend:8000` and the Docker socket. Starting observability compose **alone** is invalid (no network, no backend).

Resource cap: Alloy `mem_limit: 512m` (or equivalent deploy.resources). Do not let it compete with Postgres.

**GPU EC2:** Grafana Alloy **apt/systemd** + nvidia exporter systemd (no Docker). See OBS-003.

**Relabel (mandatory for the 10k cap):**

- Drop `container_cpu_usage_seconds_total` with `cpu` label (keep aggregate only if needed).
- Drop filesystem series where `fstype` is `tmpfs`, `overlay`, `squashfs`.
- Keep docker `name` label; drop `id`, `image_id`.
- `job` labels: `app-node`, `app-docker`, `app-backend`, `gpu-node`, `gpu-nvidia`.
- `instance` labels: `spotme-app` and `spotme-gpu` (stable, not ephemeral IPs).

---

## 14. Backend notifier contract

Python 3.10, service layer, no Slack HTTP in route handlers.

- `backend/app/services/observability_notifier.py` — builds payloads, chooses channel, enqueues Celery.
- `backend/app/tasks/observability_tasks.py` — thin task, queue **`notifications`** (already on the app worker: `photo_processing,notifications`).
- Sync `httpx` in the task (Celery is sync). Timeout **5s**. Retry 5xx three times. Never retry 4xx. Slack failure must **not** fail the business operation; log with structlog (`event`, `channel`, `error`).
- Custom exception only if needed for tests; production path swallows HTTP errors after retries and logs.
- Quota bands: constants `0.80`, `0.95`, `1.00`. Hysteresis: re-arm a band only after usage falls **5 percentage points** below it. Store last-fired band in Redis key `spotme:quota_alert:{photographer_id}` (not a new table).
- `GET /metrics` must **not** be routed by Caddy. OBS-004 adds an explicit Caddy `handle /metrics { respond 404 }` so a future Caddy mistake cannot leak it.

Do not reuse `BE-017` email/OTP notification types for Slack. Different audience (operator vs photographer).

---

## 15. Security

- Incoming Slack webhook URLs are secrets (`chmod 600` `.env`).
- Grafana token is a write-only ingest credential; still a secret.
- No public scrape ports. Alloy has no `ports:` to `0.0.0.0`.
- `/metrics` internal only.
- Slack payloads: no passwords, no OTP, no AWS keys, no JWT. Photographer **phone** is omitted (email + studio name is enough).
- Docker socket for Alloy: read-only mount.

---

## 16. Story map

| ID | Phase | Depends on | Delivers |
|----|--------|------------|----------|
| [OBS-001](stories/observability/OBS-001-grafana-cloud-alloy-slack-host-metrics.md) | Pager + host metrics | INF-005 (app EC2 Compose) | Grafana Cloud, Slack workspace, Alloy on app, disk/RAM alerts, app-host dashboard |
| [OBS-002](stories/observability/OBS-002-product-events-slack.md) | Product events | OBS-001, BE-016, INF-009, INF-007 | Notifier + hooks: signup, Find faces, GPU lifecycle, quota bands, backup fail |
| [OBS-003](stories/observability/OBS-003-gpu-metrics-cost-alerts.md) | GPU + cost | OBS-001, OBS-002, INF-009 | GPU Alloy + NVIDIA, `spotme_gpu_instance_running`, idle/long-running alerts |
| [OBS-004](stories/observability/OBS-004-app-health-logs.md) | App health | OBS-001 | `/metrics` HTTP + queues, Loki, synthetic `/health`, 5xx/queue/site-down alerts |
| [OBS-005](stories/observability/OBS-005-s3-spend.md) | S3 budget | OBS-001, OBS-002, INF-002 | Daily bucket size, Slack if over `SPOTME_S3_BUDGET_GB` |

Implement **in ID order**. Each story is independently shippable and must leave Slack quieter, not noisier.

---

## 17. Out of scope

- Sentry project / `SENTRY_DSN`
- INF-008 fail2ban and unattended-upgrades
- CloudWatch Agent, SNS, SES as pager
- Self-hosted Prometheus, Loki, Grafana, Alertmanager, ntfy, Telegram
- Tracing (Tempo) and profiles
- Frontend RUM / Grafana Faro
- Billing/plan Slack events (no billing in Phase 1)
- Guest or couple-facing notifications
- Alloy in local Docker Compose

---

## 18. Testing strategy

- **Notifier:** unit tests with `respx`/`httpx` mock; empty URL no-ops; 5xx retries; 4xx no retry; payload shape.
- **Quota bands:** table-driven tests for 79→80, 80→80 (no duplicate), 94→95, 100, drop to 74 re-arms 80.
- **GPU hooks:** existing `test_gpu_host_service.py` extended — Slack enqueue on `started` / `stopped` / `error` only.
- **Auth:** enqueue on verified registration, not on `register()`.
- **Alloy/Grafana:** cannot be CI-tested against Grafana Cloud. OBS-001/003/004 acceptance is a **runbook verification** on the EC2 (metrics appear, test alert, test Slack).
- No live Slack calls from pytest.

---

*End of Observability Component Document v1.0*
