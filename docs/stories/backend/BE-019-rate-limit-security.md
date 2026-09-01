# BE-019 — Rate limiting and HTTP security headers

**Type:** Hardening  
**Depends on:** BE-004  
**Area:** `backend/app/core/middleware.py` or dedicated limiter

## Goal

Redis sliding-window limiter per §16.1. Security headers: `X-Content-Type-Options`, `X-Frame-Options`, HSTS when HTTPS. File upload validation already in BE-009.

## References

- `docs/component_backend.md` §16
- Limits: auth 5/min, OTP send 3/5min, OTP verify 5/5min, photo list 60/min, download 30/min, webhook 100/min

## Create / edit

- Key by IP + route group; authenticated photographer id when present
- 429 JSON `RATE_LIMITED`
- Trust `X-Forwarded-For` only from known proxy (document)

## Acceptance

- [ ] Exceeding OTP send limit returns 429
- [ ] Headers present on API responses
