# INF-005 — ElastiCache Redis

**Type:** Foundation  
**Depends on:** INF-002  
**Area:** `infrastructure/modules/redis/`

## Goal

`cache.t4g.micro`, Redis 7, private subnets, not publicly accessible, used for Celery broker, OTP, rate limit. No backups (ephemeral OK per DR doc).

## References

- `docs/component_infrastructure.md` §2.2, §5.3 PgBouncer is separate — Redis is this story
- Optional PgBouncer sidecar in INF-007

## Acceptance

- [ ] Redis auth token in SSM
- [ ] Port 6379 from ECS only
