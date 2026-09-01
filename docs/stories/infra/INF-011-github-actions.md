# INF-011 — GitHub Actions: test, build, migrate, deploy

**Type:** Feature  
**Depends on:** INF-006  
**Area:** `.github/workflows/deploy.yml`

## Goal

PR: backend pytest+ruff+mypy with pgvector service; frontend lint/type/test. Main: OIDC to AWS, build/push ECR sha tags, run Alembic ECS task, rolling ECS update. No long-lived AWS keys.

## References

- `docs/component_infrastructure.md` §8
- ML tests skipped by default

## Create / edit

- `deploy.yml` from spec (fix `role-to-arn` → `role-to-assume`)
- Environments staging/production

## Acceptance

- [ ] Workflow file valid
- [ ] README for required GitHub secrets/variables
