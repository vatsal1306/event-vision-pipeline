# INF-010 — GPU Spot workers for face_processing

**Type:** Feature  
**Depends on:** INF-007, ML-008  
**Area:** `infrastructure` ASG or ECS EC2 + GPU

## Goal

g4dn.xlarge Spot, min 0 max 2, scale on Celery queue depth > 100, scale to 0 after 10 min empty. User data: NVIDIA + docker run face worker concurrency 2. Interruption: tasks retry.

## References

- `docs/component_infrastructure.md` §4.1
- Queue `face_processing`

## Requirements

- Do not run GPU 24/7
- IAM for S3 + ECR pull + SSM

## Acceptance

- [ ] Manual scale-up processes a queued task
- [ ] Scale-in to zero documented
