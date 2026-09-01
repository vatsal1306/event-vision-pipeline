# INF-014 — Staging environment (scaled down)

**Type:** Feature  
**Depends on:** INF-007–INF-013 modules  
**Area:** `infrastructure/environments/staging/`

## Goal

Same modules, smaller: Fargate 1 task, `db.t4g.micro`, S3 lifecycle delete staging objects after 7 days, separate bucket names, `cache.t4g.micro`. Cost target ~$45 from doc.

## References

- `docs/component_infrastructure.md` §13

## Acceptance

- [ ] Isolated VPC or at least isolated SGs/buckets
- [ ] tfvars documented
