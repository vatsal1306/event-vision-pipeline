# BE-004 — Photographer auth: password, JWT, OTP, refresh

**Type:** Feature  
**Depends on:** BE-003  
**Area:** `backend/app/api/v1/auth.py`, `backend/app/services/auth_service.py`, `backend/app/utils/otp.py`, `backend/app/core/security.py`

## Goal

Photographer register / login / logout / refresh / forgot-reset password / send-verify OTP. Redis-backed OTP with cooldown and max attempts. JWT access 15m, refresh 7d, rotate refresh on use.

## References

- `docs/component_backend.md` §5.1, §5.2, §6.2 Authentication schemas
- `docs/PRD.md` §5.1.1
- Phone pattern `^\+91\d{10}$`
- Rate limits documented in §16.1 — implement fully in BE-019; here at least OTP cooldown in Redis

## Create / edit

- `security.py` — bcrypt via passlib, `create_access_token`, `decode_jwt`, refresh tokens (store jti in Redis denylist on logout)
- `OTPService` as specified (6 digits, 300s expiry, 3 attempts, 60s cooldown)
- SMS: interface `SMSService.send`; **local/dev** log OTP at INFO **only when `debug=True`** and never in production settings. Real MSG91 in BE-017
- Routes under `/api/v1/auth/*`
- `get_current_photographer` in `app/api/deps.py`
- Pydantic schemas in `app/schemas/auth.py`

## Requirements

- Register does not return long-lived JWT until phone verified (match §6.2 RegisterResponse + OTP flow)
- Login returns photographer profile + tokens
- Password min 8; extra complexity can be validated in schema
- `token.type` must be `access` for API deps
- Thin routers

## Out of scope

- Guest/couple JWT (BE-012)

## Acceptance

- [ ] Integration tests: register → send OTP → verify; login; refresh; bad password 401
- [ ] OTP reuse after success fails
- [ ] Fourth verify attempt returns `OTP_MAX_ATTEMPTS`
- [ ] OpenAPI documents the routes
