# INF-001 — Terraform state (storage account) — keep

**Type:** Foundation  
**Depends on:** none  
**Area:** `infrastructure/bootstrap/`

## Goal

Already implemented: S3 state bucket + DynamoDB lock in **ap-south-1** on the **storage (cheap) account**. Keep it. Do not add versioning if you skipped it for cost. This stays off the compute account.

## Context

v2 infra: no VPC/ECS/RDS Terraform in this account. Later stories only add S3 media buckets + IAM.

## References

- `docs/component_infrastructure.md` §1, §15
- `infrastructure/README.md`

## Requirements

- Do not create NAT, ECS, RDS as a follow-on in this account
- README must not promise INF-002 VPC

## Acceptance

- [ ] Remote backend init still works
- [ ] README environment section matches “storage vs compute accounts”
