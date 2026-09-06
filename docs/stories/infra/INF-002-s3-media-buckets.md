# INF-002 — S3 media buckets (storage account)

**Type:** Foundation  
**Depends on:** INF-001  
**Area:** `infrastructure/modules/s3/`, storage-account Terraform

## Goal

Private buckets: originals (lifecycle to STANDARD_IA after 1 day), proxies (Standard), assets, optional backups prefix. SSE-S3, block public, CORS for the real app origin. Region **ap-south-1** only.

## References

- `docs/component_infrastructure.md` §5
- No CloudFront OAI. Access = IAM user + presigned URLs.

## Requirements

- Unique bucket names
- CORS methods for tus/S3: GET, PUT, HEAD, POST, DELETE as needed
- Monthly size: document how to check so $60/year is not blown

## Acceptance

- [ ] `terraform apply` creates buckets
- [ ] Public access is blocked
- [ ] IA lifecycle on originals
