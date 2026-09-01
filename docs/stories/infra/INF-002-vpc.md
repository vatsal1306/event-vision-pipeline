# INF-002 — VPC, subnets, NAT, security groups

**Type:** Foundation  
**Depends on:** INF-001  
**Area:** `infrastructure/modules/vpc/`

## Goal

VPC 10.0.0.0/16, public 10.0.1.0/24 and 10.0.2.0/24, private 10.0.10.0/24 and 10.0.20.0/24, **one** NAT for cost. Security groups: ALB 80/443 world; ECS from ALB; RDS 5432 from ECS SG; Redis 6379 from ECS SG.

## References

- `docs/component_infrastructure.md` §7.1, §10.1

## Create / edit

- Module variables for env name
- Flow logs optional (cost) — skip unless needed

## Acceptance

- [ ] Plan shows expected CIDRs
- [ ] No RDS/Redis in public subnets
