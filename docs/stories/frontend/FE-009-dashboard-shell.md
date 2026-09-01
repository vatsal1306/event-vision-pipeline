# FE-009 — Dashboard shell and route protection

**Type:** Feature  
**Depends on:** FE-008  
**Area:** `frontend/src/app/dashboard/`

## Goal

Protected photographer chrome: sidebar (Events, Profile), header (brand, notifications placeholder, avatar menu logout), storage usage snippet, redirect unauthenticated users to `/login`.

## References

- `docs/component_frontend.md` §5.2
- Routes: `/dashboard` → redirect to `/dashboard/events`

## Create / edit

- `frontend/src/app/dashboard/layout.tsx` (client guard or server cookie — JWT in localStorage implies client guard + loading skeleton)
- `frontend/src/components/dashboard/sidebar.tsx`, `header.tsx`
- Collapsible sidebar at tablet widths (`md`)

## Requirements

- Light theme
- Notification bell can be non-functional placeholder (real emails are backend); optional mock “Processing complete” toast later
- Do not expose dashboard routes meaningfully without token

## Acceptance

- [ ] Logged-out visit to `/dashboard/events` redirects to login
- [ ] Logged-in user sees shell on all dashboard child routes
- [ ] Logout clears store and returns to login
