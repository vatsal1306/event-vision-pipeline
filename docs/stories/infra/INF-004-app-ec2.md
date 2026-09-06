# INF-004 — App EC2 (compute account): m6i.xlarge ap-south-1

**Type:** Feature  
**Depends on:** none (compute account). Pair with INF-003 for S3 keys.  
**Area:** console or `infrastructure/compute/` Terraform in the **compute** AWS account

## Goal

Provision Ubuntu 24.04 **m6i.xlarge**, **ap-south-1**, gp3 **200 GB**, Elastic IP, security group: SSH from operator IP, 80/443 world, **no** 5432/6379. CPU only — no GPU AMI, no g4dn.

## Why this instance

4 vCPU / 16 GB non-burstable network for **one or two photographers** uploading 15k–20k large JPEGs via tusd, plus Postgres/Redis/Next/FastAPI/Celery CPU proxies. Do **not** use t3/t4g.

If proxy generation is too slow later: **c6i.2xlarge**, same region.

## References

- `docs/component_infrastructure.md` §2–3, §6

## Acceptance

- [ ] Instance in ap-south-1
- [ ] EIP attached
- [ ] Disk 200 GB gp3
- [ ] SSH locked down
