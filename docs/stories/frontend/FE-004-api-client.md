# FE-004 — API client and React Query

**Type:** Foundation  
**Depends on:** FE-003  
**Area:** `frontend/src/lib/api-client.ts`, `frontend/src/app/layout.tsx`

## Goal

Central typed HTTP client and React Query provider. Components never call `fetch` directly.

## References

- `docs/component_frontend.md` §9.3, §10.1, §10.2
- `frontend/AGENTS.md` — State Management, API Integration

## Create / edit

- `frontend/src/lib/api-client.ts` — `ApiClient` with `get/post/put/delete`, Bearer token from a getter, `ApiError`, JSON body, AbortSignal
- Typed methods (or a thin `api` object) for every endpoint in §10.2 (stubs that hit `/api/...` paths)
- `frontend/src/components/providers/query-provider.tsx` — QueryClient defaults: staleTime 5m, retry 2, no refetchOnWindowFocus
- Wire provider in root `layout.tsx`
- `frontend/src/hooks/` starters: `use-event-photos.ts` infinite query shape from §9.3 (can return unused until screens exist)

## Requirements

- Base URL from `NEXT_PUBLIC_API_BASE_URL`
- 401 handling hook/placeholder for token refresh (implement refresh call; photographer tokens from auth store in FE-006/FE-008)
- Guest/couple use `session_token` the same way
- Do not store server data in Zustand

## Acceptance

- [ ] All listed REST paths are callable through the client
- [ ] QueryClient provider wraps the app
- [ ] Errors are `ApiError` with status + code + message
