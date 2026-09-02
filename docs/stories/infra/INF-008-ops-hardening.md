# INF-008 — Disk, SSH, S3 spend checks

**Type:** Hardening  
**Depends on:** INF-005  
**Area:** EC2 + storage account

## Goal

fail2ban, unattended-upgrades, alert when disk > 80% (uploads fill gp3). Monthly reminder to check S3 bucket size on the cheap account. Optional CloudWatch disk alarm on **compute** account.

## References

- `docs/component_infrastructure.md` §12–13

## Acceptance

- [ ] SSH fail2ban enabled in setup notes
- [ ] Disk check documented
- [ ] S3 size check documented
