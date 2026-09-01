# INF-013 — IAM least privilege and SSM parameters

**Type:** Hardening  
**Depends on:** INF-007  
**Area:** IAM roles, `aws_ssm_parameter` SecureString

## Goal

Task execution + task roles: S3 prefix-scoped, SQS none unless used, SES send, no `*` on IAM. SSM: database_url, redis_url, secret_key, sms_api_key, sentry_dsn. ECS injects secrets. Rotate documented.

## References

- `docs/component_infrastructure.md` §10.2
- Prefer instance/task role over access keys in containers

## Acceptance

- [ ] Backend task cannot list unrelated S3 buckets
- [ ] Parameters encrypted
