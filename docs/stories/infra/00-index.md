# Infra / DevOps stories — index

Region: **ap-south-1**. Cost-first: single NAT, single-AZ RDS until scale, Spot GPU min 0. No public S3.

Terraform layout: `docs/component_infrastructure.md` §14.1.

Do not apply production destroy casually. State in S3 + DynamoDB lock.
