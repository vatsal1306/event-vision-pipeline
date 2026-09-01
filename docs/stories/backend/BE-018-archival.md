# BE-018 — Two-month archival, restore, quota

**Type:** Feature  
**Depends on:** BE-008, BE-017  
**Area:** `archival_service.py`, `tasks/archival_tasks.py`

## Goal

Celery Beat daily 02:00 IST archive overdue events; 10:00 IST send 7-day and 1-day warnings. Archive: originals → Glacier IR, delete proxies, delete embeddings/clusters, status `archived`. Links show archived via public info/auth. Photographer can restore (Glacier IR is instant) and permanently delete. Archived bytes **count toward quota**.

## References

- `docs/component_backend.md` §12 — **rewrite any sync Session usage to async**
- `docs/PRD.md` §5.1.10
- crontab timezone: use `Asia/Kolkata` or store UTC equivalent of 2:00 IST

## Create / edit

- Beat schedule in celery_app
- Restore: set status ready/draft as appropriate, regenerate proxies optional (may leave proxies missing until reprocess — **document**: restore re-queues proxy generation)
- Permanent delete: S3 delete + DB cascade + quota recalc

## Acceptance

- [ ] Event with `archive_at` in the past archives in a unit test calling the task
- [ ] Warnings selected by date windows
- [ ] Guest auth on archived event fails with `EVENT_ARCHIVED`
