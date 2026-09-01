# Frontend stories — index

Work these in order. Each story is a standalone markdown file an AI agent can implement without inventing product scope.

**Product docs (always read first):**

- Root `AGENTS.md`
- `frontend/AGENTS.md`
- `docs/component_frontend.md` (screens, APIs, mocks, design)
- `docs/PRD.md` §5 (Phase 1 features only)

**Phase 1 constraints (do not implement):** custom domains, QR at venue, WhatsApp, social sharing, photo selling, video, desktop upload app, real-time camera-to-cloud, multi-photographer roles, guest uploads.

**Mock-first:** all API calls go through the typed client. MSW intercepts until `NEXT_PUBLIC_MOCK_API=false`.

## Order

| ID | Story | Depends on |
|----|--------|------------|
| FE-001 | Next.js scaffold and tooling | — |
| FE-002 | Design system and shared UI | FE-001 |
| FE-003 | Shared TypeScript types | FE-001 |
| FE-004 | API client, React Query, env | FE-003 |
| FE-005 | MSW mocks and placeholder data | FE-004 |
| FE-006 | Client stores (auth, upload, gallery, UI) | FE-003 |
| FE-007 | Marketing landing and 404 | FE-002 |
| FE-008 | Photographer register, login, OTP, password reset | FE-004, FE-005, FE-006 |
| FE-009 | Dashboard shell and route protection | FE-008 |
| FE-010 | Event list and create event | FE-009 |
| FE-011 | Event detail: folders and photos | FE-010 |
| FE-012 | Chunked resumable upload | FE-011 |
| FE-013 | Event analytics and lead table | FE-011 |
| FE-014 | Share links and download toggle | FE-011 |
| FE-015 | Photographer profile, logo, watermark, storage | FE-009 |
| FE-016 | Shared gallery grid, viewer, download | FE-002, FE-005 |
| FE-017 | Couple master auth and full gallery | FE-016 |
| FE-018 | Couple favorites | FE-017 |
| FE-019 | Guest OTP auth, selfie, processing, matched gallery | FE-016 |
| FE-020 | PWA manifest and service worker | FE-007, FE-019 |
| FE-021 | Empty/error/loading polish and a11y | FE-010–FE-019 |
| FE-022 | Frontend tests | FE-008, FE-011, FE-012, FE-017, FE-019 |

## Suggested implementation batches

1. Foundation: FE-001 → FE-006  
2. Photographer: FE-007 → FE-015  
3. End-user galleries: FE-016 → FE-020  
4. Hardening: FE-021 → FE-022  
