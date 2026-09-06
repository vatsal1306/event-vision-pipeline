# INF-007 — Postgres dumps to S3

**Type:** Feature  
**Depends on:** INF-002, INF-005  
**Area:** cron on EC2

## Goal

Daily `pg_dump | gzip` to `s3://…/backups/pg/YYYY-MM-DD.sql.gz` using the app IAM user. Retain 14 days. Document restore onto a new m6i.xlarge.

## References

- `docs/component_infrastructure.md` §14

## Acceptance

- [ ] Cron script in repo
- [ ] Restore steps written
