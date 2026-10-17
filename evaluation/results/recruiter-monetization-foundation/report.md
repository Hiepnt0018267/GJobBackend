# AUX-MONETIZATION-01A — Backend Plan Catalog & Recruiter Subscription Foundation

## Product Decisions

- Only `RECRUITER` users participate in subscriptions. Candidate and Admin accounts have no plan state.
- Every Recruiter has an effective plan. `FREE` is an implicit catalog-backed fallback and never creates a `recruiter_subscriptions` row.
- This task does not implement payment, SePay, recurring billing, or AI entitlement gating.

## Source Review

- Recruiter identity is `users.id` with `users.role = RECRUITER`; `recruiter_profiles.user_id` is a one-to-one profile relation, not the ownership identifier used by jobs and subscription management.
- The repository uses PostgreSQL UUIDs, timezone-aware timestamps, SQLAlchemy services/repositories, FastAPI role dependencies, and `page`/`page_size` pagination.
- The pre-task Alembic head was `f8b2c4d6e1a3`. Tests have an existing hard guard requiring a distinct PostgreSQL database whose name ends in `_test`.

## Architecture

- `SubscriptionPlan` owns mutable catalog presentation/pricing and stable commercial semantics.
- `RecruiterSubscription` is append-only paid subscription history. Plan changes cancel the old row and create a new row rather than mutating `plan_id`.
- Money uses PostgreSQL `NUMERIC(18,0)` and Python `Decimal`; current currency is constrained to `VND`.
- Application enums use bounded VARCHAR values: billing `NONE|MONTHLY`, status `ACTIVE|CANCELLED|EXPIRED`, source `ADMIN|PAYMENT`.

## Plan Catalog

- Fields: UUID id, normalized unique code, name, description, Decimal price, currency, billing period, duration days, active flag, and UTC timestamps.
- Database and request validation enforce nonnegative money, positive duration when present, valid controlled values, and current FREE/paid semantics.
- There is no public hard-delete endpoint. `is_active=false` prevents new grants without affecting existing terms.

## FREE Fallback

- The service fetches the catalog plan with `code=FREE` whenever no paid subscription satisfies the effective predicate.
- Revoke, cancelled history, expired history, or no history all yield `{effective_plan: FREE, subscription: null}`.
- Verification found zero subscription rows referencing FREE.

## Subscription Lifecycle

- Grant defaults `starts_at` to aware UTC now.
- Explicit `expires_at` takes precedence; otherwise it is computed from `duration_days`. Every non-null expiry must be later than start.
- A plan change preserves history by cancelling the current ACTIVE row and inserting a new ACTIVE row in one transaction.
- Revoke changes persisted ACTIVE rows to CANCELLED and is idempotent when none exists.
- A future-start row may be persisted ACTIVE but is not effective before its start. 01A supports only one persisted ACTIVE row, not overlapping scheduled chains; replacing an existing plan cancels it immediately.

## Effective Subscription Semantics

A paid row is effective only when `status=ACTIVE`, `starts_at <= now`, and `expires_at IS NULL OR expires_at > now`. Plan deactivation is deliberately absent from this predicate, so an already-granted term remains effective.

## Expiry Normalization

Before grant/change/revoke, the service locks the Recruiter scope and changes expired ACTIVE rows to EXPIRED. These rows therefore do not block the next grant.

## Concurrency

- Each mutation locks the target `users` row with `SELECT ... FOR UPDATE`, providing a stable lock even when no subscription row exists.
- A PostgreSQL partial unique index on `recruiter_id WHERE status='ACTIVE'` provides a second invariant layer.
- Expire/cancel/create is flushed and committed once; exceptions roll back the entire transition.
- A real two-session PostgreSQL concurrency test leaves exactly one ACTIVE row, and a forced insert failure test proves the old ACTIVE state is restored.

## Admin APIs

- `GET /api/v1/admin/subscription-plans`
- `GET /api/v1/admin/subscription-plans/{plan_id}`
- `POST /api/v1/admin/subscription-plans`
- `PATCH /api/v1/admin/subscription-plans/{plan_id}`
- `GET /api/v1/admin/recruiters`
- `GET /api/v1/admin/recruiters/{recruiter_id}/subscription`
- `POST /api/v1/admin/recruiters/{recruiter_id}/subscription`
- `POST /api/v1/admin/recruiters/{recruiter_id}/subscription/revoke`

Auth errors remain 401/403. Missing resources are 404; duplicate code, inactive grant, and used-plan semantic mutation are 409; invalid dates, FREE grants, plan semantics, and wrong target roles are 422.

## Recruiter API

- `GET /api/v1/recruiter/subscription` is restricted to the authenticated Recruiter and returns the same effective-plan response without accepting another user id.

## Admin Recruiter Plan Visibility

The dedicated paginated admin list preserves the existing `/admin/users` contract. It uses a fixed query set: one joined effective-subscription query plus count and FREE catalog lookup, with no per-Recruiter query.

## Used-Plan Immutability

- `code` is never accepted by PATCH.
- Once any history exists, `currency`, `billing_period`, and `duration_days` cannot change.
- `name`, `description`, `price`, and `is_active` remain editable.

## Price Policy

FREE is exactly 0 VND. Paid plans must be greater than 0. Price changes affect the current catalog only and do not rewrite subscription rows.

## Future SePay Compatibility

A future payment order must snapshot `plan_id`, `plan_code`, `plan_name`, `amount`, and `currency` when created. Later catalog price changes must not change historical order amounts. No payment model or SePay call exists in 01A.

## Migration

- New revision: `a1c3e5f7b9d2`, based on `f8b2c4d6e1a3`.
- It creates both tables, foreign keys, checks, lookup indexes, the partial ACTIVE unique index, and deterministic FREE/PRO_MONTHLY seeds.
- Seed inserts use `ON CONFLICT (code) DO NOTHING` and never overwrite an existing code.
- On `gjob_test`: clean upgrade PASS; downgrade to `f8b2c4d6e1a3` PASS; re-upgrade PASS; `alembic check` PASS with no new operations.

## Tests

- Monetization focused: 11 passed, 0 failed, 4 warnings, 10.49s before removal of two new-code deprecation warnings.
- Focused regression (monetization, auth, admin users, recruiters, user profile, DB safety): 55 passed, 0 failed, 2 dependency warnings, 25.51s.
- Coverage includes seed/catalog validation, Decimal behavior, FREE fallback, date precedence, expiry normalization, history preservation, inactive plans, authorization, non-N+1 list behavior, rollback, and PostgreSQL concurrency.

## Regression

- Full backend: 965 passed, 0 failed, 4 dependency/existing-code warnings, 136.43s.
- No frontend files or AI/ranking implementation files were changed.

## DB Safety

- All pytest and migration verification targeted `gjob_test@loopback:5433`; pytest used the existing `TEST_DATABASE_URL` guard.
- Development target `gjob_db@loopback:5433` received no migration, test, or data write.
- Monetization synthetic users/plans were cleaned; validation found zero `mon01a_` users, zero `TEST_` plans, and zero FREE subscription rows.
- Workspace pytest temp artifacts were removed.

## Limitations

- No purchase flow, payment activation, invoice, refund, recurring billing, webhook, quota, or entitlement gate exists yet.
- There is no background expiry job; effective reads are time-correct, while persisted stale ACTIVE rows are normalized on the next subscription mutation.
- 01A intentionally does not support multiple scheduled ACTIVE terms.

## Final Status

**AUX-MONETIZATION-01A — BACKEND PLAN CATALOG & RECRUITER SUBSCRIPTION FOUNDATION — VERIFIED**
