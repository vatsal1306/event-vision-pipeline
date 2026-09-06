# INF-006 — Deploy: GitHub tests + SSH to EC2

**Type:** Feature  
**Depends on:** INF-005  
**Area:** `.github/workflows/`

## Goal

PR CI: frontend + backend tests with Compose Postgres (no AWS deploy). Production: SSH to EC2, `git pull`, `docker compose build && up -d`, `alembic upgrade head`. No ECR, no ECS.

## References

- `docs/component_infrastructure.md` §11

## Acceptance

- [ ] Workflow YAML valid
- [ ] README lists SSH deploy steps
