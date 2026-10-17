# AUX-MONETIZATION-02 — Recruiter AI Feature Entitlements + Plan Experience

## Verification status

**CONTRACT VERIFIED** — backend, frontend, production build, and a mutating HTTP lifecycle were verified against the guarded `gjob_test` database. Browser verification was attempted through Computer Use, but the environment exposed no browser (`apps=[]`, `browsers=[]`), so this report does not claim browser-verified status.

## Delivered contract

- Central recruiter feature keys: `AI_CANDIDATE_RANKING` and `DETAILED_CV_JD_MATCH`.
- `FREE` denies both features; `PRO_MONTHLY` enables both; unknown/custom plans fail closed.
- `sort=ai_match` is gated before owner-list queries, ranking construction, cache reads, or result exposure. Normal recruiter applicant lists remain available on FREE.
- Recruiter CV–JD match is gated before `CVJobMatchService` construction/calls. Candidate match and recommendation paths are unchanged.
- `GET /api/v1/recruiter/subscription` additively returns `entitlements`.
- `GET /api/v1/recruiter/subscription-plans` returns active plans with backend-authored feature labels and `included` flags.
- Recruiter topbar shows the authoritative effective plan only after loading and links to `/recruiter/plans`.
- Recruiter plan page is catalog-driven; monetary values remain decimal strings and there is no payment action.
- Missing/FREE entitlement locks ranking and detailed match without issuing a premium request.
- A stale `403 FEATURE_NOT_INCLUDED` causes an entitlement refetch, removes the premium ranking query or locks match, and is not retried as a premium request.
- Admin grant/revoke broadcasts the shared data-refresh signal to recruiter tabs.
- No migration was added for this task. Shared ranking precompute, AI engines, and Candidate recommendation logic were not modified.

## Automated verification

- Safe database gate: development `gjob_db` and TEST `gjob_test` were distinct loopback PostgreSQL databases; Alembic TEST head was `a1c3e5f7b9d2`.
- Backend focused regression: **121 passed**, 3 dependency/deprecation warnings, 40.96 s.
- Frontend tests: **93 passed**, 0 failed, 5.19 s. Repeated Vite HMR port warnings were non-fatal.
- Frontend TypeScript build: passed (`tsc -b` + Vite production build, 2,078 modules transformed).
- ESLint on every changed entitlement file: passed with zero warnings/errors.
- Full-repository ESLint remains blocked by the unchanged baseline error in `src/components/motion/ScrollReveal.tsx:24` (`react-hooks/set-state-in-effect`).
- `git diff --check`: no whitespace errors; only Git line-ending notices.
- Tests did not contact BGE, Ollama, Gemini, Qwen, SePay, or payment services.

## Mutating TEST lifecycle

Synthetic users, job, CV, and application were created only in `gjob_test`, then removed after verification.

1. FREE subscription: normal applicant list `200`; `sort=ai_match` `403`.
2. Admin grant to `PRO_MONTHLY`: both entitlements `true`; `sort=ai_match` `200`.
3. Admin revoke: effective plan returned to `FREE`; `sort=ai_match` returned `403` again.

No match request was executed in this lifecycle, preventing any real embedding-provider call. Match access and the pre-service gate are covered by isolated automated tests with synthetic/mocked services.

## Browser attempt

Computer Use was initialized after reading its guidance and confirmation policy. Both the in-app browser and Chrome were unavailable, and inventory returned no browser or app. Per the task's acceptance rule, the final status is therefore **contract verified**, not fully browser verified.
