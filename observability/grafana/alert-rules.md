# Grafana alert rules — OBS-001 (app EC2)

Create in Grafana UI: **Alerting → Alert rules → New alert rule**  
Contact point: `slack-spotme-alerts` (notification policy: group by `alertname`, repeat 4h).

Use datasource `grafanacloud-*-prom` (Prometheus). Filter `job="app-node"` to target Alloy metrics only.

---

## Alert A — `SpotMeAppDiskHigh`

| Setting | Value |
|---------|-------|
| Folder | `SpotMe` |
| Evaluation group | `spotme-app` · interval **1m** |
| Pending period (`for`) | **10m** |
| No data | `NoData` → OK (avoid false pages on scrape blip) |
| Execution error | Alerting |

### Query

Single PromQL expression (type: **Prometheus**), threshold **IS ABOVE 0.80**:

```promql
(
  1 - (
    node_filesystem_avail_bytes{instance="spotme-app", job="app-node", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
    /
    node_filesystem_size_bytes{instance="spotme-app", job="app-node", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
  )
)
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |
| `instance` | `spotme-app` |

### Annotations

**Summary** (Slack title):

```
App EC2 root disk above 80%
```

**Description** (Slack body):

```
Root gp3 is *{{ printf "%.1f" $values.A.Value }}%* full (threshold 80%, held 10m).

*What uses this disk:* Docker images/layers, Postgres data, container logs — not photo originals (those are on S3).

*Check:* Grafana dashboard *SpotMe / App EC2* → Root disk panel.
*On host:* `docker system df` · `du -sh /var/lib/docker` · Postgres log rotation.

*Instance:* spotme-app (m6i.xlarge, Mumbai)
```

---

## Alert B — `SpotMeAppMemoryHigh`

| Setting | Value |
|---------|-------|
| Folder | `SpotMe` |
| Evaluation group | `spotme-app` · interval **1m** |
| Pending period (`for`) | **10m** |
| No data | `NoData` → OK |
| Execution error | Alerting |

### Query

Threshold **IS ABOVE 0.85**:

```promql
(
  1 - (
    node_memory_MemAvailable_bytes{instance="spotme-app", job="app-node"}
    /
    node_memory_MemTotal_bytes{instance="spotme-app", job="app-node"}
  )
)
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |
| `instance` | `spotme-app` |

### Annotations

**Summary:**

```
App EC2 RAM above 85%
```

**Description:**

```
Memory used is *{{ printf "%.1f" $values.A.Value }}%* of total (threshold 85%, held 10m).

*Likely consumers:* backend (ML selfie), celery-worker, Postgres, tusd during uploads.

*Check:* Grafana dashboard *SpotMe / App EC2* → Container memory table.

*Instance:* spotme-app (m6i.xlarge, Mumbai)
```

---

## Notification policy (confirm)

| Setting | Value |
|---------|-------|
| Default contact point | `slack-spotme-alerts` |
| Group by | `alertname` |
| Group wait | 30s |
| Group interval | 5m |
| Repeat interval | 4h |

---

## Test paging (without filling disk)

1. **Contact point:** Alerting → Contact points → `slack-spotme-alerts` → **Test** → confirm phone push.
2. **Rule preview:** Each rule → **Preview** → graph should render, no parse error.
3. **Optional live fire:** Temporarily set disk threshold to `> 0.01`, wait 10m, confirm one Slack message, **restore `> 0.80`**.
