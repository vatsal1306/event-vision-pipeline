# Slack notification template — SpotMe alerts

Configured in Grafana Cloud (not in git). Recreate from here if the stack is rebuilt.

## Prerequisites

- Alert rules use PromQL `* 100` (percent). Thresholds: disk **> 80**, memory **> 85**.
- Each rule has annotation **`usage`** = `{{ printf "%.1f" $values.A.Value }}` (alert-rule templating, not Slack templating).
- Notification policy **Group by:** `alertname` only.

## 1. Notification template `spotme_slack`

**Alerting → Contact points → Notification templates**

```go
{{ define "spotme_slack.title" }}
{{ if eq .Status "firing" }}
{{ if eq .CommonLabels.alertname "SpotMeAppDiskHigh" }}SpotMe — App disk high
{{ else if eq .CommonLabels.alertname "SpotMeAppMemoryHigh" }}SpotMe — App memory high
{{ else }}{{ .CommonLabels.alertname }}
{{ end }}
{{ else }}
{{ if eq .CommonLabels.alertname "SpotMeAppDiskHigh" }}SpotMe — App disk OK
{{ else if eq .CommonLabels.alertname "SpotMeAppMemoryHigh" }}SpotMe — App memory OK
{{ else }}{{ .CommonLabels.alertname }} resolved
{{ end }}
{{ end }}
{{ end }}

{{ define "spotme_slack.message" }}
{{ range .Alerts }}
{{ if eq .Status "firing" }}
*{{ .Annotations.summary }}*

{{ if eq .Labels.alertname "SpotMeAppDiskHigh" }}💾 *Root disk:* {{ .Annotations.usage }}% used
{{ else if eq .Labels.alertname "SpotMeAppMemoryHigh" }}🧠 *Memory:* {{ .Annotations.usage }}% used
{{ end }}

*Severity:* {{ .Labels.severity }}

{{ .Annotations.description }}

<{{ .GeneratorURL }}|View in Grafana>
{{ else }}
*{{ .Annotations.summary }}*

`{{ .Labels.instance }}` is back within threshold.
{{ end }}
{{ end }}
{{ end }}
```

Do not use `{{-` trim markers. Do not use `.Value` in the Slack template (use `.Annotations.usage`).

## 2. Contact point `slack-spotme-alerts`

| Field | Value |
|-------|-------|
| **Title** | `{{ template "spotme_slack.title" . }}` |
| **Message** | `{{ template "spotme_slack.message" . }}` |

Both required. Empty Title → Grafana default `[FIRING:1] … (labels)` header.

## 3. Notification policy

| Setting | Value |
|---------|-------|
| Default contact point | `slack-spotme-alerts` |
| Group by | `alertname` |
| Group wait | 30s |
| Group interval | 5m |
| Repeat interval | 4h |

## Expected Slack (firing)

**Title:** `SpotMe — App disk high`

**Body:**
```
App EC2 root disk above 80%

💾 Root disk: 9.7% used

Severity: critical

Images are on S3. This gp3 volume holds Docker images, Postgres, and logs.

View in Grafana
```

Memory alert title: `SpotMe — App memory high`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `[FIRING:1] SpotMeApp… (device /dev/root …)` | Set custom Title; group by `alertname` only |
| Empty `Root disk:` / `Memory:` | Add `usage` annotation with `$values.A.Value` on the alert rule |
| `0.1%` instead of `9.7%` | Query must `* 100`; threshold `> 80` not `> 0.80` |
| Title glued to summary in Grafana log | Normal in Grafana UI; check phone Slack app |
