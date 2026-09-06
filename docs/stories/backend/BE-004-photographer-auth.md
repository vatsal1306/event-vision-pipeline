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

- [x] Integration tests: register → send OTP → verify; login; refresh; bad password 401
- [x] OTP reuse after success fails
- [x] Fourth verify attempt returns `OTP_MAX_ATTEMPTS`
- [x] OpenAPI documents the routes

## Implementation notes (agreed deviations from original doc)

- **Register** auto-sends OTP (separate `send-otp` is for resend).
- **Login** is two-step: `login` (email_or_phone + password) → OTP to registered phone → `verify-otp` purpose `login` returns JWTs.
- **verify-otp** returns `TokenResponse` (not `{verified: true}`) for registration and login.
- **Forgot/reset password** uses OTP to registered phone (not email reset link). Email verification deferred to BE-017.
- **Password**: 8–16 chars with upper, lower, digit, special — enforced in API and frontend.
- **Phone** unique constraint on `photographers.phone`.
