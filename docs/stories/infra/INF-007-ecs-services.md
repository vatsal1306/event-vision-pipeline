# INF-007 — ECS Fargate cluster: API, worker CPU, frontend

**Type:** Feature  
**Depends on:** INF-006, INF-004, INF-005  
**Area:** `infrastructure/modules/ecs/`

## Goal

ECS cluster Fargate: backend 1 vCPU 2GB min 2 tasks (staging min 1), frontend 0.5 vCPU 1GB, celery CPU worker photo_processing+notifications. Secrets from SSM. Health check `/health`. Logs awslogs groups `/ecs/platform-*`. tusd as Fargate task or sidecar with S3 IAM.

## References

- `docs/component_infrastructure.md` §4.2 scale min/max, §6.3 task JSON
- Celery beat as separate tiny service

## Requirements

- `assign_public_ip` only if using public subnet without NAT for Fargate — **prefer private + NAT**
- Env `ENVIRONMENT=production`

## Acceptance

- [ ] Services stay running
- [ ] Backend health from inside VPC
- [ ] Worker consumes Redis
