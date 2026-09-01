# INF-008 — ALB, ACM certificates, DNS

**Type:** Feature  
**Depends on:** INF-007  
**Area:** `infrastructure/modules/alb/`

## Goal

Two ALBs or one ALB two listener rules: frontend host `platform.com`, API `api.platform.com`. HTTPS 443 ACM (request in us-east-1 if CloudFront will use it — **API ALB cert in ap-south-1; CloudFront cert in us-east-1**). HTTP→HTTPS. Route 53 alias.

## References

- `docs/component_infrastructure.md` §2.1, §7.2, §10.1

## Requirements

- Placeholder domain variables
- Do not commit real secrets

## Acceptance

- [ ] curl https health via ALB
- [ ] Certificate validated
