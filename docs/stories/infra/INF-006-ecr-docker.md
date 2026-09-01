# INF-006 — Dockerfiles and Amazon ECR

**Type:** Foundation  
**Depends on:** BE-001 (backend image), FE-001 (frontend image)  
**Area:** `backend/Dockerfile`, `frontend/Dockerfile`, `infrastructure` ECR repos

## Goal

ECR repositories: platform-backend, platform-frontend, optionally celery. Backend Dockerfile Python 3.10; frontend Next standalone as in `docs/component_frontend.md` §15.3. Scan on push optional.

## References

- `docs/component_infrastructure.md` §6.1, §6.3
- GitHub OIDC to push (INF-011)

## Create / edit

- `.dockerignore` for backend/frontend
- Image labels git sha

## Acceptance

- [ ] Both images build locally
- [ ] ECR repos exist; policy least privilege
