# INF-015 — Production hardening checklist and runbooks

**Type:** Hardening  
**Depends on:** INF-014  
**Area:** `infrastructure/docs/` or `docs/runbooks/`

## Goal

Written runbooks: restore RDS snapshot, Spot interrupt, rotate JWT secret, archival failure, domain cutover. Confirm WAF optional (skip Phase 1). Confirm backups per §12. MFA on root. This is documentation + any missing TF (`deletion_protection` on RDS, ALB access logs).

## References

- `docs/component_infrastructure.md` §12, §14.3 remaining checklist items

## Acceptance

- [ ] Runbook markdown exists for RDS restore and ECS rollback
- [ ] RDS deletion protection on in production tfvars
- [ ] Checklist in §14.3 ticked or explicitly deferred with reason
