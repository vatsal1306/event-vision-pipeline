# BE-017 — Notifications: OTP SMS, processing complete, archival warnings

**Type:** Feature  
**Depends on:** BE-010  
**Area:** `notification_service.py`, `tasks/notification_tasks.py`

## Goal

Phase 1: **no paid SMS/SES required.** OTP: Redis + **log the code** (or accept `123456` when `debug=True`). Processing complete / archival: log + optional in-app; email adapters may exist but must no-op without credentials.

## References

- `docs/component_backend.md` §10
- Templates: processing_complete, archival_warning (HTML + text)
- Photographer email from account

## Create / edit

- Provider adapters; local: capture emails in list / log
- `notify_processing_complete.delay(event_id)`
- Do not SMS guests in Phase 1

## Acceptance

- [ ] Tests assert processing-complete is **logged** (or no-op email) when event becomes ready
- [ ] OTP send does not call a paid SMS API when unset
