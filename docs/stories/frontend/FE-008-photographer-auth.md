# FE-008 — Photographer authentication

**Type:** Feature  
**Depends on:** FE-004, FE-005, FE-006  
**Area:** `frontend/src/app/(auth)/`, `frontend/src/components/` (auth forms)

## Goal

Photographer register (studio name, email, password, Indian mobile + OTP) and login (email/password, remember me, forgot password). Session tokens stored via auth store.

## References

- `docs/component_frontend.md` §5.1 (wireframes + validation)
- `docs/PRD.md` §5.1.1
- API: `POST /api/auth/register|login|logout|refresh|forgot-password|reset-password|send-otp|verify-otp`

## Create / edit

- `frontend/src/app/(auth)/layout.tsx` — centered card, light theme
- `login/page.tsx`, `register/page.tsx`, forgot/reset pages as needed
- Zod schemas + React Hook Form
- OTP input (6 digits), cooldown/error states from API/mocks
- After success: set tokens, redirect `/dashboard/events`

## Requirements

- Password: min 8, upper, lower, digit
- Phone: `+91` + 10 digits
- Mock OTP documented (FE-005)
- Accessible labels, errors via `aria-describedby`

## Acceptance

- [ ] Register → OTP → logged in (mock)
- [ ] Login → dashboard
- [ ] Invalid credentials show API error, not a blank screen
- [ ] Forgot password flow exists (mock success)
