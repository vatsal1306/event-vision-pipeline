# Observability — notes for AI agents

Working reference for agents implementing `OBS-*` stories. Not a step-by-step operator runbook.

**Source of truth:** `docs/component_observability.md`  
**OBS-001 execution plan:** `docs/stories/observability/OBS-001-grafana-cloud-alloy-slack-host-metrics.md`

## What exists (OBS-001) — shipped

- **Grafana Cloud Free** — Prometheus remote write via Alloy. Loki token on EC2 `.env` but not wired until OBS-004.
- **Slack** — `#spotme-alerts` contact point `slack-spotme-alerts` + template `spotme_slack` (see `grafana/slack-notification-template.md`). `#spotme-events` webhook on EC2 for OBS-002.
- **Alloy** — `docker-compose.observability.yml` merged with prod; `job="app-node"`, `instance="spotme-app"`, scrape **60s**.
- **Host metrics** — `prometheus.exporter.unix` in Alloy.
- **Container RSS** — `container-metrics` sidecar → textfile → Alloy `textfile` collector. Metric: `spotme_container_memory_rss_bytes{name="backend",…}`. Script: `scripts/docker-container-memory-textfile.sh` (cgroup v2; no cAdvisor on Ubuntu 24.04).
- **Grafana UI (operator, not in git):** rules `SpotMeAppDiskHigh` / `SpotMeAppMemoryHigh`, dashboard import `grafana/dashboards/app-host.json`, datasource `grafanacloud-*-prom`.
- **Alert queries** — PromQL `* 100` (percent); thresholds **> 80** disk, **> 85** RAM; `for: 10m`. Annotation `usage` = `{{ printf "%.1f" $values.A.Value }}` for Slack body.

## Layout

```
observability/
├── alloy/app.alloy
├── scripts/docker-container-memory-textfile.sh
├── grafana/
│   ├── dashboards/app-host.json
│   ├── alert-rules.md
│   └── slack-notification-template.md
└── README.md

docker-compose.observability.yml   # container-metrics + alloy (512m)
```

## Conventions agents must not break

- Merge command: `docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d`. Prod-only compose drops Alloy.
- Secrets in app EC2 `~/event-vision-pipeline/.env` only (`chmod 600`). Keys in `.env.prod.example` (empty).
- No Alloy in `backend/docker-compose.yml` or on the laptop. No published Alloy ports.
- Relabel rules in `app.alloy` must stay under Grafana Cloud **10k series** cap (see component doc §6, §13).
- **container-metrics** sidecar: docker.sock ro + cgroup ro, writes textfile. **Alloy**: no docker.sock, no published ports.

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
