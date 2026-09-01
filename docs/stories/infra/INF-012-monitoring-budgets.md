# INF-012 — CloudWatch, alarms, Sentry, AWS Budgets

**Type:** Feature  
**Depends on:** INF-007  
**Area:** `infrastructure/modules/monitoring/`

## Goal

Log groups 30 day retention. Alarms: API 5xx, RDS CPU, ECS count 0, queue depth. SNS email. Budget $700 80%/100%. Sentry DSN in SSM already used by app.

## References

- `docs/component_infrastructure.md` §9, §11.2

## Acceptance

- [ ] Alarm actions to SNS
- [ ] Budget resource created
