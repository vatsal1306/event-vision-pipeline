# INF-009 — CloudFront for app and proxy images

**Type:** Feature  
**Depends on:** INF-003, INF-008  
**Area:** `infrastructure/modules/cloudfront/`

## Goal

Distribution PriceClass_200, IPv6. Origins: frontend ALB + S3 proxies with OAC. Cache `/photos/*` 24h default. Default behavior to ALB no cache. TLS 1.2_2021. Compress.

## References

- `docs/component_infrastructure.md` §7.2 HCL
- Path pattern must match how frontend requests proxies (may be CloudFront URL not `/photos/*` — **align with storage_service public URL design**; document mapping)

## Acceptance

- [ ] HTTPS to CloudFront serves frontend
- [ ] S3 not world-readable; only CloudFront
