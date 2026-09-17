# Observability — notes for AI agents

Working reference for agents implementing `OBS-*` stories. Not a step-by-step operator runbook.

**Source of truth:** `docs/component_observability.md`  
**OBS-001 execution plan:** `docs/stories/observability/OBS-001-grafana-cloud-alloy-slack-host-metrics.md`

## What exists (OBS-001)

- **Grafana Cloud Free** — metrics backend (Prometheus remote write). Loki token created but not wired until OBS-004.
- **Slack** — `#spotme-alerts` (Grafana contact point + future ops pages), `#spotme-events` (OBS-002 product events).
- **Alloy** on app EC2 — `docker-compose.observability.yml` merged with prod; never standalone.
- **Scrapes:** host (`prometheus.exporter.unix`, job `app-node`) + filtered Docker containers (`prometheus.exporter.cadvisor`, job `app-docker`). Interval **60s**. `instance="spotme-app"`.
- **Keep-list compose services:** `caddy`, `frontend`, `backend`, `tusd`, `celery-worker`, `celery-beat`, `db`, `redis`. Alloy self-metrics dropped.
- **Alerts (Grafana UI):** `SpotMeAppDiskHigh` (>80% root disk, 10m), `SpotMeAppMemoryHigh` (>85% RAM, 10m) — see `grafana/alert-rules.md`.
- **Dashboard:** `grafana/dashboards/app-host.json` — import into Grafana Cloud.

## Layout

```
observability/
├── alloy/
│   └── app.alloy              # env via sys.env(); no secrets in git
├── grafana/
│   ├── dashboards/app-host.json
│   └── alert-rules.md         # PromQL + UI labels for Grafana Alerting
└── README.md

docker-compose.observability.yml   # repo root; service: alloy (grafana/alloy:v1.8.3, mem_limit 512m)
```

## Conventions agents must not break

- Merge command: `docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d`. Prod-only compose drops Alloy.
- Secrets in app EC2 `~/event-vision-pipeline/.env` only (`chmod 600`). Keys in `.env.prod.example` (empty).
- No Alloy in `backend/docker-compose.yml` or on the laptop. No published Alloy ports.
- Relabel rules in `app.alloy` must stay under Grafana Cloud **10k series** cap (see component doc §6, §13).
- Alloy runs **privileged** (cAdvisor); docker.sock **read-only**. `/var/lib/docker` is also mounted at `/rootfs/var/lib/docker` for cAdvisor layerdb.

## Env vars (app EC2 `.env`)

| Variable | Purpose |
|----------|---------|
| `SLACK_WEBHOOK_ALERTS_URL` | `#spotme-alerts` |
| `SLACK_WEBHOOK_EVENTS_URL` | `#spotme-events` (OBS-002) |
| `GRAFANA_CLOUD_PROMETHEUS_URL` | remote_write |
| `GRAFANA_CLOUD_PROMETHEUS_USERNAME` | instance id |
| `GRAFANA_CLOUD_LOKI_URL` | OBS-004 |
| `GRAFANA_CLOUD_LOKI_USERNAME` | OBS-004 |
| `GRAFANA_CLOUD_TOKEN` | Access Policy `spotme-alloy` |

## Story map (not yet implemented here)

| Story | Adds |
|-------|------|
| OBS-002 | `ObservabilityNotifier`, product Slack events |
| OBS-003 | `gpu.alloy`, NVIDIA metrics, GPU cost alerts |
| OBS-004 | `loki.write`, `loki.source.docker`, FastAPI `/metrics`, synthetic `/health` |
| OBS-005 | S3 bucket size cron |

Deploy/runbook for the app EC2: `infrastructure/compute/README.md`.
