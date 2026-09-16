# Observability stories — index

**Pager:** Slack Free (`#spotme-alerts`, `#spotme-events`).  
**Metrics/logs:** Grafana Cloud Free + Grafana Alloy.  
**Not this backlog:** Sentry, CloudWatch Agent, INF-008, self-hosted Prometheus/Loki/Grafana.

**Always read** `docs/component_observability.md` before any OBS story. That file is the source of truth; these stories are the implementation plans.

Implement **in ID order**. Do not put Alloy on the laptop Compose stack.

| ID | Story | Depends on | Status |
|----|--------|------------|--------|
| OBS-001 | Grafana Cloud + Slack + Alloy on app EC2 + disk/RAM alerts | INF-005 | |
| OBS-002 | Product/ops events to Slack | OBS-001, BE-016, INF-007, INF-009 | |
| OBS-003 | GPU host metrics + cost alerts | OBS-001, OBS-002, INF-009 | |
| OBS-004 | App health, queues, Loki, synthetic `/health` | OBS-001 | |
| OBS-005 | Daily S3 size vs budget Slack | OBS-001, OBS-002, INF-002 | |

Full architecture: `docs/component_observability.md`.
