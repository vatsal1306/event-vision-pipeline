# BE-012 — Guest and couple OTP sessions

**Type:** Feature  
**Depends on:** BE-005, BE-004 (OTP + SMS interface)  
**Area:** `backend/app/api/v1/guest.py` (auth parts), `couple.py` (auth parts), `guest_service.py`, `couple_service.py`

## Goal

- **Master/Couple Authentication:**
  - `POST /api/v1/event/{slug}/master/auth`: Validates event and master link status, generates a 6-digit OTP, stores it in Redis with a 5-minute expiry, and creates a pending `CoupleSession` row.
  - `POST /api/v1/event/{slug}/master/verify`: Verifies the OTP, updates the `CoupleSession` to verified, and returns a couple JWT.

- **Guest Authentication:**
  - `POST /api/v1/event/{slug}/auth`: Validates event and guest link status, generates OTP, stores in Redis, and creates a pending `GuestSession` row.
  - `POST /api/v1/event/{slug}/auth/verify`: Verifies the OTP, updates the `GuestSession` to verified, and returns a guest JWT.

## References

- `docs/component_backend.md` §5.1 guest JWT, §6.2 Guest endpoints auth
- `docs/PRD.md` §5.2.1, §5.3.1, §5.3.5 return visits
- Unique phone per event

## Create / edit

- `get_current_guest_session` / `get_current_couple_session` deps; reject wrong `type`
- If `guest_link_active`/`master_link_active` false → 403 `LINK_INACTIVE`
- Do not require photographer JWT
- Name stored on first verify

## Requirements

- Same OTP service, purpose `guest_auth`
- Session token payload includes `event_id`

## Acceptance

- [ ] Couple verify returns token, `needs_selfie=false`
- [ ] Guest first verify `needs_selfie=true`; second device same phone after match false (after BE-013)
- [ ] Expired/invalid OTP handled
