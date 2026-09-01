# FE-022 — Frontend tests

**Type:** Hardening  
**Depends on:** FE-008, FE-011, FE-012, FE-017, FE-019  
**Area:** `frontend/` test folders

## Goal

Add Vitest + Testing Library for critical units/hooks, and Playwright for the two golden paths: photographer create-event + folder (mocked) and guest OTP → selfie → gallery. Use MSW in tests.

## References

- `docs/component_frontend.md` §13

## Create / edit

- Vitest config, example tests for Zod auth schema, upload queue concurrency (pure function)
- Playwright config, `e2e/guest-flow.spec.ts`, `e2e/photographer-auth.spec.ts`
- Scripts in `package.json`: `test`, `test:e2e`

## Requirements

- Do not test that React renders a `div`
- Tests must run with mocks, no live backend

## Acceptance

- [ ] `pnpm test` passes in CI-like local run
- [ ] At least one Playwright happy path for guest and photographer
