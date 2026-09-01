# BE-015 — Analytics summary, top photos, guest leads, CSV

**Type:** Feature  
**Depends on:** BE-012  
**Area:** `backend/app/api/v1/analytics.py`, `analytics_service.py`, `utils/csv_export.py`

## Goal

Photographer-only analytics for an event: summary counts, top photos by views or downloads, paginated guest list with download counts, CSV export of leads.

## References

- `docs/component_backend.md` §11 (use the query patterns; fix sync `db.query` in archival sample — **always async**)
- `docs/PRD.md` §5.1.8
- Guests: verified sessions only

## Create / edit

- `record_view` / `record_download` used by couple/guest download (and view endpoint)
- Export: `text/csv` attachment
- Indexes already on analytics_events

## Requirements

- Do not return guests for other photographers’ events
- Phone numbers visible to owning photographer only (lead capture is the product)

## Acceptance

- [ ] Summary matches inserted analytics rows
- [ ] Top photos ordered correctly
- [ ] CSV columns: Name, Phone, First Visited, Photos Matched, Photos Downloaded
