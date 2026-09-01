# FE-005 — MSW mock API and placeholder photos

**Type:** Foundation  
**Depends on:** FE-004  
**Area:** `frontend/src/mocks/`

## Goal

Intercept all frontend API calls with MSW when `NEXT_PUBLIC_MOCK_API=true`, including realistic event/photo/guest data and simulated delays (OTP, selfie match, upload hook if used).

## References

- `docs/component_frontend.md` §11
- Sample event: “Rahul & Priya Wedding”, slug `rahul-priya-2026`, ~200 mock photos is enough (doc shows 200; not 3450 DOM nodes)

## Create / edit

- `frontend/src/mocks/handlers.ts` — handlers for auth, events, folders, photos, analytics, profile, guest/couple endpoints
- `frontend/src/mocks/events.ts`, `photos.ts`, `users.ts`, `analytics.ts`
- `frontend/src/mocks/browser.ts` — `setupWorker`
- Init in client entry / provider only when mock flag is true
- `frontend/public/images/placeholder-photos/` optional; Picsum URLs allowed per spec
- Simulate selfie match delay ~1500ms
- Simulate OTP always accepting a documented test code (e.g. `123456`) in mock only — document in README or `.env.example`

## Requirements

- Pagination: `offset`/`limit`, `hasMore`
- Folder filter on photos
- Unique `(event, phone)` guest sessions in in-memory mock state where needed
- Unhandled requests: `warn` in worker start options

## Acceptance

- [ ] App runs with mocks, no backend
- [ ] Switching `NEXT_PUBLIC_MOCK_API=false` requires no component changes
- [ ] Mock data includes draft/processing/ready/archived events
