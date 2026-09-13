# BE-017 — Notifications: OTP SMS, processing complete, archival warnings

**Type:** Feature  
**Depends on:** BE-010  
**Area:** `notification_service.py`, `tasks/notification_tasks.py`, `sms_service.py`, `utils/otp.py`

## Goal

OTP SMS: Redis still owns the 6-digit code. Delivery is **`SMS_PROVIDER=log`** (no HTTP) or **`SMS_PROVIDER=fast2sms`** (real Indian SMS via Fast2SMS Quick OTP). When `DEBUG=true`, `123456` still verifies. Processing complete / archival: log + optional in-app; email adapters may exist but must no-op without credentials.

## References

- `docs/component_backend.md` §10
- Templates: processing_complete, archival_warning (HTML + text)
- Photographer email from account

## Create / edit

- Provider adapters; local: capture emails in list / log
- `notify_processing_complete.delay(event_id)`
- OTP SMS: `SMSService.send_otp` — log or Fast2SMS. Same path for photographer, guest, and couple.

## Acceptance

- [ ] Tests assert processing-complete is **logged** (or no-op email) when event becomes ready
- [ ] OTP send does not call Fast2SMS when `SMS_PROVIDER=log` or `SMS_API_KEY` is empty
- [ ] Fast2SMS tests mock HTTP with respx (no live SMS)

## Implementation notes (agreed deviations from original doc)

- Original Phase 1 said “no paid SMS” and “do not SMS guests”. We now send real OTP SMS to **all** OTP flows when `SMS_PROVIDER=fast2sms`.
- MSG91 is **not** wired yet; Fast2SMS is the first real provider. We POST `/dev/bulkV2` with `route=otp` first. If Fast2SMS returns KYC/DLT codes (996, 998, 408), we retry **Quick SMS** (`route=q`) with `Your verification code is: {otp}`.
- Failed SMS: debug keeps Redis OTP + `123456`; production (`DEBUG=false`) returns `SMS_DELIVERY_FAILED` (502) and deletes the Redis OTP.
