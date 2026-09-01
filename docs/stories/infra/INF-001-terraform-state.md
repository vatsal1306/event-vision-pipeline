# INF-001 — Terraform bootstrap: state bucket and lock table

**Type:** Foundation  
**Depends on:** none (needs AWS account + IAM user/role)  
**Area:** `infrastructure/` bootstrap (can live outside main state)

## Goal

Create S3 bucket `platform-terraform-state` (versioned, encrypted, public access blocked) and DynamoDB `terraform-locks` in ap-south-1. Document backend.hcl. Never commit state files.

## References

- `docs/component_infrastructure.md` §14.2, §14.3 steps 1–3

## Create / edit

- `infrastructure/bootstrap/` small TF or scripted AWS CLI with warnings
- `infrastructure/backend.tf` template
- `infrastructure/versions.tf` AWS provider pin

## Requirements

- MFA delete optional; encryption required
- Separate AWS account note for prod vs personal

## Acceptance

- [ ] `terraform init` against remote backend works
- [ ] README: who can assume the role
