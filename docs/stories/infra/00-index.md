# Infra / DevOps stories — index (v2)

**App host:** AWS EC2 **m6i.xlarge**, Ubuntu, **ap-south-1**, CPU only.  
**Media:** S3 in a **separate cheap account**, same region.  
**Not in this backlog:** VPC mesh, ECS, RDS, ElastiCache, ALB, CloudFront, GPU Spot.

| ID | Story | Depends on |
|----|--------|------------|
| INF-001 | Terraform state (done / keep) | — |
| INF-002 | S3 media buckets | INF-001 |
| INF-003 | IAM user for EC2 | INF-002 |
| INF-004 | App EC2 m6i.xlarge | — |
| INF-005 | Compose + Caddy + tusd hardening | INF-004, BE-009 |
| INF-006 | SSH deploy + GH tests | INF-005 |
| INF-007 | pg_dump to S3 | INF-002, INF-005 |
| INF-008 | Disk/SSH/S3 spend | INF-005 |

Full architecture: `docs/component_infrastructure.md` v2.
