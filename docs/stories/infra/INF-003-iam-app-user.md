# INF-003 — IAM user for the app EC2 (keys on compute box)

**Type:** Foundation  
**Depends on:** INF-002  
**Area:** `infrastructure/modules/iam-app-user/`

## Goal

IAM user in the **storage account** with least privilege on the four buckets (Get/Put/Delete/AbortMultipart, ListBucket). Access key lives only on the **compute EC2** `/opt/platform/.env`. Never commit keys.

## References

- `docs/component_infrastructure.md` §5, §13

## Acceptance

- [ ] Policy cannot `s3:*` on `*`
- [ ] Document rotation
