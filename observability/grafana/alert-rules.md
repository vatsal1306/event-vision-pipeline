# Grafana alert rules — OBS-001 (app EC2)

Create in Grafana UI: **Alerting → Alert rules → New alert rule**  
Contact point: `slack-spotme-alerts` (notification policy: group by `alertname`, repeat 4h).

Datasource: `grafanacloud-*-prom`. Filter `job="app-node"`.

**Slack formatting:** `observability/grafana/slack-notification-template.md` (required).

Queries return **percent 0–100** (`* 100`). Thresholds are **> 80** and **> 85** (not 0.80 / 0.85).

---

## Alert A — `SpotMeAppDiskHigh`

| Setting | Value |
|---------|-------|
| Folder | `SpotMe` |
| Evaluation group | `spotme-app` · interval **1m** |
| Pending period (`for`) | **10m** |
| No data | `NoData` → OK |
| Execution error | Alerting |

### Query

Threshold **IS ABOVE 80**:

```promql
(
  1 - (
    node_filesystem_avail_bytes{instance="spotme-app", job="app-node", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
    /
    node_filesystem_size_bytes{instance="spotme-app", job="app-node", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
  )
) * 100
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |
| `instance` | `spotme-app` |

### Annotations

| Key | Value |
|-----|-------|
| **summary** | `App EC2 root disk above 80%` |
| **usage** | `{{ printf "%.1f" $values.A.Value }}` |
| **description** | `Images are on S3. This gp3 volume holds Docker images, Postgres, and logs.` |

`usage` is evaluated by Grafana when the alert fires; the Slack template reads `.Annotations.usage` (see `slack-notification-template.md`).

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

Threshold **IS ABOVE 85**:

```promql
(
  1 - (
    node_memory_MemAvailable_bytes{instance="spotme-app", job="app-node"}
    /
    node_memory_MemTotal_bytes{instance="spotme-app", job="app-node"}
  )
) * 100
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |
| `instance` | `spotme-app` |

### Annotations

| Key | Value |
|-----|-------|
| **summary** | `App EC2 RAM above 85%` |
| **usage** | `{{ printf "%.1f" $values.A.Value }}` |
| **description** | `Check container RSS on dashboard SpotMe / App EC2. Likely backend, celery-worker, or Postgres during uploads.` |

---

## Notification policy

| Setting | Value |
|---------|-------|
| Default contact point | `slack-spotme-alerts` |
| Group by | `alertname` |
| Group wait | 30s |
| Group interval | 5m |
| Repeat interval | 4h |

---

## Test paging

1. Contact point **Test** — webhook only (sample text is not SpotMe-shaped).
2. Rule **Preview** — confirm graph and value ~5–15 (percent) at idle.
3. Optional live fire: threshold **> 5** for 10m, confirm Slack, **restore disk > 80** / **memory > 85**.
