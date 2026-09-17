# Grafana alert rules — OBS-001 (app EC2)

Grafana Cloud Free does not load these from git. Create each rule in the Grafana UI:

**Alerting → Alert rules → New alert rule**

Default contact point must be `slack-spotme-alerts` (notification policy from OBS-001 setup).

Verify label names in **Explore** after Alloy has scraped for 2 minutes:

```promql
{instance="spotme-app"}
```

All queries below use `node_*` metrics from `prometheus.exporter.unix` with `instance="spotme-app"`.

---

## Alert A — `SpotMeAppDiskHigh`

| Field | Value |
|-------|-------|
| **Folder** | SpotMe (create if missing) |
| **Evaluation group** | `spotme-app` (interval 1m) |
| **Rule name** | `SpotMeAppDiskHigh` |
| **for** | `10m` |
| **Contact point** | `slack-spotme-alerts` |

### Expression (PromQL)

```promql
(
  1 - (
    node_filesystem_avail_bytes{instance="spotme-app", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
    /
    node_filesystem_size_bytes{instance="spotme-app", mountpoint="/", fstype!~"tmpfs|overlay|squashfs|autofs"}
  )
) > 0.80
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |

### Annotations

| Key | Text |
|-----|------|
| **Summary** | `App EC2 root disk > 80%` |
| **Description** | `Root gp3 is {{ $value | humanizePercentage }} full. Photo originals are on S3; this disk is Docker images, Postgres, and logs. Prune images/logs or expand the volume.` |

---

## Alert B — `SpotMeAppMemoryHigh`

| Field | Value |
|-------|-------|
| **Folder** | SpotMe |
| **Evaluation group** | `spotme-app` (interval 1m) |
| **Rule name** | `SpotMeAppMemoryHigh` |
| **for** | `10m` |
| **Contact point** | `slack-spotme-alerts` |

### Expression (PromQL)

```promql
(
  1 - (
    node_memory_MemAvailable_bytes{instance="spotme-app"}
    /
    node_memory_MemTotal_bytes{instance="spotme-app"}
  )
) > 0.85
```

### Labels

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `channel` | `alerts` |

### Annotations

| Key | Text |
|-----|------|
| **Summary** | `App EC2 RAM > 85%` |
| **Description** | `Memory used is {{ $value | humanizePercentage }} of total. Check container RSS on the app-host dashboard; tusd/Postgres spikes during large uploads.` |

---

## Test without filling the disk

1. **Contact point only:** Alerting → Contact points → `slack-spotme-alerts` → **Test** → confirm Slack push on your phone.
2. **Rule preview:** Open `SpotMeAppDiskHigh` → **Preview** → confirm the expression runs (no “parse error”).
3. **Optional live fire:** Temporarily change the disk threshold to `> 0.01`, wait `10m` + notification delay, confirm one Slack message, then **restore `> 0.80`** immediately.

Do not leave a `0.01` threshold in production.
