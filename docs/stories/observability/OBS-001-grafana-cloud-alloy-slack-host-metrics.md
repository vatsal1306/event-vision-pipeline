# OBS-001 — Grafana Cloud, Slack, Alloy on the app EC2, disk/RAM pager

**Type:** Feature  
**Depends on:** INF-005 (production Compose on the app EC2)  
**Area:** `observability/`, `docker-compose.observability.yml`, `.env.prod.example`, `infrastructure/compute/README.md`  
**Python:** none in this story

## Business outcome

The operator can open Slack on their phone and receive a push if the **app EC2 root disk stays above 80% for 10 minutes** or **RAM stays above 85% for 10 minutes**. They can also open Grafana Cloud and see CPU, RAM, disk, and per-container memory for the production Compose services.

Without this story, a 15k-upload night can still succeed on S3 while Docker logs / images fill gp3 and take down Postgres with no page.

## Purpose

Stand up the **only** metrics backend we will use (Grafana Cloud Free) and the **only** pager we will use (Slack Free), then ship host telemetry from the always-on app box. Later OBS stories add events, GPU, logs, and S3 spend on top of this plumbing. They must not create a second Grafana stack or a third Slack workspace.

## References (read first)

- `docs/component_observability.md` — **entire file**, especially §3–6, §10–13, §15
- `docs/component_infrastructure.md` §3 (16 GB / disk), §7 (Compose services)
- `docker-compose.prod.yml` — service names to keep in relabel
- `infrastructure/compute/README.md` — how prod Compose is started today

## Out of scope (do not do in OBS-001)

- Backend `ObservabilityNotifier`, product Slack events (OBS-002)
- GPU host Alloy / NVIDIA (OBS-003)
- FastAPI `/metrics`, Loki, synthetic checks (OBS-004)
- S3 bucket size (OBS-005)
- Sentry, CloudWatch Agent, INF-008 fail2ban
- Adding Alloy to `backend/docker-compose.yml` or any laptop path
- Publishing Alloy or Node-exporter ports on `0.0.0.0`
- Changing `docker-compose.prod.yml` resource limits of tusd/Postgres except **adding a named comment** if required to document the merge command

## Non-negotiables

1. Grafana Cloud **Free**. No credit card. If the portal asks to start a Pro trial, stay on Free.
2. Two Slack channels: `#spotme-alerts` and `#spotme-events`. OBS-001 only **creates** `#spotme-events`; it does not post to it yet. Grafana contact point uses **`#spotme-alerts` only**.
3. `docker-compose.observability.yml` is a **second file**, merged with prod. Never fold Alloy into `docker-compose.prod.yml`.
4. Scrape interval **60s**. Relabel to stay under **10,000** series (component §6 and §13).
5. Secrets only in the server `.env` (`chmod 600`). Alloy config in git uses `env()` / placeholders.
6. Alloy `mem_limit` **512m** or lower.
7. Operator still starts the app stack; the runbook must show the **merged** compose command so a later `docker compose -f docker-compose.prod.yml up -d` does not silently drop Alloy.

## Implementation plan

Follow these steps in order. Do not skip the account runbook — there are no existing Slack or Grafana Cloud accounts.

### Step 1 — Slack workspace (operator, once)

Document every click in `observability/README.md` under “Create Slack (once)”:

1. Open https://slack.com/get-started and create a **new workspace** (free). Suggested name: `hpklabs` (operator may pick another; do not hardcode the workspace name in code).
2. Create channel `#spotme-alerts`. Purpose: fires and cost.
3. Create channel `#spotme-events`. Purpose: expected product activity (unused until OBS-002).
4. Open https://api.slack.com/apps → **Create New App** → From scratch → name `spotme-observability` → the new workspace.
5. Incoming Webhooks → On → Add New Webhook to Workspace → `#spotme-alerts` → copy URL. Repeat for `#spotme-events`.
6. Install the Slack **mobile** app. Join both channels. Channel settings → Notifications → **All new messages** (not just mentions). Disable “Notify me about replies to threads” if it doubles noise.
7. Record both webhook URLs in the **app EC2** `~/event-vision-pipeline/.env` (not git):

```
SLACK_WEBHOOK_ALERTS_URL=https://hooks.slack.com/services/...
SLACK_WEBHOOK_EVENTS_URL=https://hooks.slack.com/services/...
```

OBS-001 does not post from the backend yet. Grafana will use `SLACK_WEBHOOK_ALERTS_URL` as a contact point (paste in Grafana UI; Grafana Cloud stores it).

### Step 2 — Grafana Cloud Free stack (operator, once)

Document in the same README under “Create Grafana Cloud (once)”:

1. https://grafana.com → Get started for free → Grafana Cloud **Free Forever** (no credit card).
2. Create **one** stack. Prefer Asia Pacific if listed; otherwise EU. Note the stack URL (e.g. `https://<stack>.grafana.net`).
3. Connections → **Alloy** (or “Add new connection” → Alloy). Open the screen that shows:
   - Prometheus remote write URL
   - Prometheus username (numeric instance id)
   - Loki URL
   - Loki username
4. Administration → Users and access → Cloud Access Policies → New token named `spotme-alloy` with scopes **`metrics:write`** and **`logs:write`** (logs write is unused until OBS-004 but create one token so OBS-004 does not mint a second).
5. Put on the app EC2 `.env`:

```
GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-....grafana.net/api/prom/push
GRAFANA_CLOUD_PROMETHEUS_USERNAME=<numeric>
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-....grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USERNAME=<numeric>
GRAFANA_CLOUD_TOKEN=<token>
```

6. Grafana → Alerting → Contact points → New → **Slack**. Webhook URL = alerts channel. Name: `slack-spotme-alerts`. Test the contact point; confirm a push on the phone.
7. Notification policy: default contact point = `slack-spotme-alerts`. Group by `alertname`. Group wait 30s, group interval 5m, repeat interval **4h** (do not re-page every minute).

### Step 3 — Env example files (repo)

Add the keys from Step 1–2 with **empty values** and comments to:

- `.env.prod.example`
- `backend/.env.example` (so local Settings accepts them with `extra=ignore` still; OBS-002 will add typed Settings fields — **OBS-001 may skip Pydantic fields** because nothing in Python reads them yet)

Do not add the keys to `.env.gpu.example` in this story.

### Step 4 — Alloy config for the app host

Create `observability/alloy/app.alloy` that:

1. Reads Grafana Cloud URL/username/token from environment (Alloy `sys.env(...)` or `environment` block). **No literals.**
2. `prometheus.exporter.unix` with `include_exporter_metrics = false`. Filesystem: enable; exclude `tmpfs`, `overlay`, `autofs`.
3. Docker discovery via `/var/run/docker.sock` (read-only). Keep containers whose Compose `name` is in:

   `caddy`, `frontend`, `backend`, `tusd`, `celery-worker`, `celery-beat`, `db`, `redis`

   Drop `alloy` high-cardinality metrics; `up{job="app-alloy"}` is enough if needed.
4. Relabel as in component §13. Set `instance="spotme-app"`.
5. `prometheus.scrape` interval `60s`.
6. `prometheus.remote_write` to Grafana Cloud with basic auth (username + token).
7. **Do not** enable Loki in this story (OBS-004). Leave a commented `// OBS-004: loki.write` so the next agent does not invent a second Alloy file.

Validate: `alloy fmt observability/alloy/app.alloy` if the CLI is available; otherwise keep River/Alloy syntax matching current Grafana Alloy docker image docs (**pin the image tag**, e.g. `grafana/alloy:v1.8.3` or the latest stable **pinned** at implementation time — never `:latest`).

### Step 5 — `docker-compose.observability.yml`

Repo root, next to `docker-compose.prod.yml`.

```yaml
# Merge only: docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d
# Do not start this file by itself.
```

Service `alloy`:

- Image: pinned `grafana/alloy`
- `restart: unless-stopped`
- `env_file: .env`
- Command runs `/etc/alloy/app.alloy`
- Volumes: `./observability/alloy/app.alloy:/etc/alloy/app.alloy:ro`, docker socket **read-only**, and the host fs mounts Grafana documents for `prometheus.exporter.unix` in containers (`/proc`, `/sys`, rootfs as `/rootfs:ro` — follow current Alloy unix-exporter-in-docker example; do not guess missing mounts).
- **No `ports:` mapping.**
- `mem_limit: 512m`
- `pid: host` only if required by the unix exporter in Docker; if it requires extra capabilities, document them. Prefer the official Grafana “Alloy in Docker” unix exporter snippet over inventing cap-add lists.
- User: do not run as root if the official image supports a documented non-root + docker.sock pattern; if socket access forces root, say so in the README.

### Step 6 — App-host dashboard JSON

Create `observability/grafana/dashboards/app-host.json` (Grafana 10+ dashboard, datasource = default Prometheus/Mimir in Cloud):

Required panels:

1. CPU % (host)
2. Memory % (host, prefer `MemAvailable`)
3. Root disk used % (exclude overlay/tmpfs)
4. Network receive/transmit
5. Table or timeseries: container memory RSS for the keep-list names
6. `up` for scrape jobs

Templating: none required. Title: `SpotMe / App EC2`. Tag: `spotme`.

Import instructions in `observability/README.md` (Grafana → Dashboards → Import).

### Step 7 — Alert rules (code + UI)

Write `observability/grafana/alert-rules.md` with **copy-pasteable** PromQL. Grafana Cloud Free may not load provisioning YAML from this repo; the implementing agent must create the rules in Grafana Alerting UI **exactly** as specified.

**Alert A — `SpotMeAppDiskHigh`**

- Expr (adapt label names to what Alloy actually emits; verify with Explore after scrape works):

```promql
(
  1 - (
    node_filesystem_avail_bytes{instance="spotme-app",mountpoint="/",fstype!~"tmpfs|overlay|squashfs"}
    /
    node_filesystem_size_bytes{instance="spotme-app",mountpoint="/",fstype!~"tmpfs|overlay|squashfs"}
  )
) > 0.80
```

- `for`: 10m  
- Labels: `severity=critical`, `channel=alerts`  
- Summary: `App EC2 root disk > 80%`  
- Description: include `{{ $value }}` and remind that originals go to S3; this is gp3 (Docker/Postgres/logs).  
- Contact: `slack-spotme-alerts`

**Alert B — `SpotMeAppMemoryHigh`**

```promql
(
  1 - (
    node_memory_MemAvailable_bytes{instance="spotme-app"}
    /
    node_memory_MemTotal_bytes{instance="spotme-app"}
  )
) > 0.85
```

- `for`: 10m  
- Summary: `App EC2 RAM > 85%`

If the unix exporter uses `node_*` vs `windows_*` vs prefixed names, **fix the PromQL to match Explore**, then update `alert-rules.md` to the working query. Do not leave a query that does not run.

No other alerts in OBS-001.

### Step 8 — Operator runbook

`observability/README.md` must include:

- Account creation (Steps 1–2)
- `.env` keys
- Start/stop:

```bash
cd ~/event-vision-pipeline
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml ps
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml logs -f alloy --tail=100
```

- Warning: `docker compose -f docker-compose.prod.yml up -d` **without** the observability file will not start Alloy. Update `infrastructure/compute/README.md` “Deploy stack” to the **merged** command (keep `docker-compose.prod.yml` as the app file; add one sentence + the merged command).
- How to confirm series in Grafana Explore: `{instance="spotme-app"}`
- How to fire a **test** disk alert without filling the disk: Grafana Alerting → `SpotMeAppDiskHigh` → mute is not the test; use “Preview” and Slack contact-point Test. Optional: temporarily set threshold to `> 0.01` for 2 minutes, confirm phone push, **restore 0.80**. The runbook must say restore.

### Step 9 — Security group / network

No new inbound ports. Alloy only **outbound HTTPS 443** to Grafana Cloud (already allowed). Do not open 12345, 9100, or 9080.

## Acceptance

- [ ] Slack workspace exists with `#spotme-alerts` and `#spotme-events`; phone receives the Grafana contact-point test message
- [ ] Grafana Cloud Free stack exists; Access Policy token is only on the server `.env`
- [ ] `observability/alloy/app.alloy`, `docker-compose.observability.yml`, dashboard JSON, `alert-rules.md`, `observability/README.md` are in git **without secrets**
- [ ] `.env.prod.example` lists the new keys empty
- [ ] On the app EC2, merged compose runs Alloy; Explore shows host CPU/RAM/disk for `instance="spotme-app"`
- [ ] Container memory exists for named app services, not thousands of overlay series
- [ ] `SpotMeAppDiskHigh` and `SpotMeAppMemoryHigh` exist with `for: 10m` and Slack contact point
- [ ] `curl` from the public internet to any Alloy port fails (nothing published)
- [ ] Laptop `docker compose` (backend) is unchanged

## Verification (agent + operator)

1. SSH to app EC2. Merged `up -d`. `docker compose ... logs alloy` has no auth 401 to Grafana Cloud.
2. Grafana Explore: `node_memory_MemAvailable_bytes{instance="spotme-app"}` returns data within 2 minutes.
3. Series count: Grafana Cloud Billing/Usage (or `count({instance="spotme-app"})`) is **hundreds**, not >5000. If >2000, fix relabel before finishing.
4. Slack test message from Grafana contact point on the phone.
5. Temporarily lower disk threshold, wait `for`, confirm one Slack message, restore threshold.

## Done when

Host charts work in Grafana Cloud and the phone can be paged for disk and RAM. No product events yet.
