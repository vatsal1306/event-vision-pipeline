# FE-010 — Event list and create event

**Type:** Feature  
**Depends on:** FE-009  
**Area:** `frontend/src/app/dashboard/events/`

## Goal

List photographer events with search/sort and create-event dialog (name, date range, type, description). Navigate to event detail on click.

## References

- `docs/component_frontend.md` §5.3, §5.4
- `docs/PRD.md` §5.1.2
- API: `GET/POST /api/events`

## Create / edit

- `frontend/src/app/dashboard/events/page.tsx`
- `frontend/src/components/dashboard/event-card.tsx`, `event-form.tsx`
- React Query `useEvents`, `useCreateEvent` (invalidate list on create)

## Requirements

- Status badges: Draft, Uploading, Processing (optional %), Ready, Archived — colors per spec
- Card: cover, name, dates, photo count, folder count, guest count
- Create: name 3–200 chars, required dates, type Wedding/Corporate/Birthday/Other
- Empty state when no events
- After create, go to `/dashboard/events/[id]`

## Acceptance

- [ ] Mock events render
- [ ] Search filters by name
- [ ] Sort newest/oldest/name/status
- [ ] Create appears in list (mock memory or refetch)
