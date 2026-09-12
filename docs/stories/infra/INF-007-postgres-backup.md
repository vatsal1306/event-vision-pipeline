# INF-007 — Postgres dumps to S3

**Type:** Feature  
**Depends on:** INF-002, INF-005  
**Area:** cron on EC2

## Goal

Daily `pg_dump | gzip` to `s3://…/backups/pg/YYYY-MM-DD.sql.gz` using the app IAM user. Retain 7 days. Document restore onto a new m6i.xlarge.

## References

- `docs/component_infrastructure.md` §14

## Acceptance

- [x] Cron script in repo (`scripts/postgres-backup.sh`, `scripts/install-postgres-backup-cron.sh`)
- [x] Restore steps written (`infrastructure/README.md` § Step 7)
