# FE-013 — Event analytics and lead capture table

**Type:** Feature  
**Depends on:** FE-011  
**Area:** `frontend/src/app/dashboard/events/[id]/analytics/`

## Goal

Simple analytics only: total guests, views, downloads; top viewed photos; paginated guest list (name, phone, first visit, photos matched, downloads); CSV export.

## References

- `docs/component_frontend.md` §5.5.3
- `docs/PRD.md` §5.1.8
- API: `/analytics/summary`, `top-photos`, `guests`, `guests/export`

## Create / edit

- `analytics/page.tsx`
- `frontend/src/components/dashboard/analytics-overview.tsx`, `lead-table.tsx`
- Tab on event detail must navigate here

## Requirements

- Do not add charts libraries unless trivial
- Table sortable
- Export downloads CSV from mock

## Acceptance

- [ ] Summary cards match mock
- [ ] Top photos list with thumbs
- [ ] Guest table paginates
- [ ] CSV export works in browser
