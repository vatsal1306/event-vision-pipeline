# BE-017 — Notifications: OTP SMS, processing complete, archival warnings

**Type:** Feature  
**Depends on:** BE-010  
**Area:** `notification_service.py`, `tasks/notification_tasks.py`

## Goal

SMS for OTP (production provider MSG91/Twilio/SNS from `sms_provider` setting). Email via SES for processing complete and archival warnings. Celery queue `notifications`.

## References

- `docs/component_backend.md` §10
- Templates: processing_complete, archival_warning (HTML + text)
- Photographer email from account

## Create / edit

- Provider adapters; local: capture emails in list / log
- `notify_processing_complete.delay(event_id)`
- Do not SMS guests in Phase 1

## Acceptance

- [ ] Tests assert email task called when event becomes ready (mock SES)
- [ ] SMS adapter called on send_otp in non-debug without leaking body in logs
