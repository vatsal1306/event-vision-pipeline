# INF-004 — RDS PostgreSQL 16 with pgvector

**Type:** Foundation  
**Depends on:** INF-002  
**Area:** `infrastructure/modules/rds/`

## Goal

`db.t4g.medium`, gp3 100GB max 500, encryption, private, backups 7 days window 03:00 UTC, parameter group `shared_preload_libraries=vector`, work_mem/maintenance/effective_cache as spec. **multi_az = false** Phase 1. Password in SSM (INF-013 can create the parameter; generate in TF with random_password stored SSM).

## References

- `docs/component_infrastructure.md` §5.1
- App uses asyncpg URL — document hostname via SSM

## Requirements

- `publicly_accessible = false`
- Subnet group private only
- After apply: note that `CREATE EXTENSION vector` may need a one-off (RDS pgvector availability — use custom parameter / rds.extensions). **If Amazon RDS pg16 does not include pgvector, document using a custom engine or self-hosted Postgres on ECS/EC2.** Agent must verify current AWS pgvector support and choose: RDS if supported, else EC2/ECS Postgres with official pgvector image for staging only.

## Acceptance

- [ ] Instance reachable from ECS SG only
- [ ] Parameter group attached
- [ ] Extension strategy documented if AWS limitation
