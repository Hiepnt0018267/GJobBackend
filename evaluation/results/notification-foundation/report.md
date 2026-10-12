# Task 16A — Multi-role Notification Backend Foundation

## Status

**VERIFIED.** One shared, authenticated notification foundation now serves Candidate,
Recruiter, and Admin with user-owned isolation. Focused tests pass 41/41; final full
backend regression passes 938/938. Migration upgrade/downgrade/re-upgrade and Alembic
metadata drift checks pass on the guarded TEST database. No DEV database, model, or
external-service operation was used.

## Source Review

The implementation follows the existing FastAPI router/service/repository layering,
PostgreSQL UUID identifiers, timezone-aware timestamps, JWT `get_current_user`
dependency, and canonical pagination envelope. Existing user-owned records use
`ON DELETE CASCADE`; audit history uses `SET NULL`. Notifications are user-owned
product data rather than immutable audit history, so their user foreign key cascades.

## Architecture

`notifications` is the only notification table. The same model, repository, service,
schemas, and `/api/v1/notifications` router apply to every authenticated role. The
router performs authentication and request validation, the service owns authorization
and read-state behavior, and the repository performs SQL filtering and mutations.

The internal `NotificationService.create_notification(...)` validates and flushes but
does not commit. This deliberately lets Task 16B compose a domain mutation and its
notification in the caller's transaction. No public create route exists.

## Ownership Model

`notifications.user_id` references `users.id` and is the sole ownership key. Every
public query and update derives that key from the authenticated user. No `user_id` or
recipient override is accepted. Candidate, Recruiter, and Admin see only their own
rows; Admin has no implicit bypass. Foreign and nonexistent notification IDs both
return the same 404 response.

## Read-State Source of Truth

Only nullable, timezone-aware `read_at` is persisted. `is_read` is derived in the API
as `read_at is not None`; there is no second database flag. Mark-one updates only an
owned row whose `read_at IS NULL`, so the first timestamp is preserved. Re-reading an
owned row returns 200 with the original timestamp.

## Notification Type Contract

`NotificationType` is a Python `StrEnum`, persisted as `VARCHAR(64)`. Task 16A defines
only `SYSTEM`; later tasks can add intentional domain types without PostgreSQL native
ENUM lifecycle coupling. Title is `VARCHAR(200)` and message is `VARCHAR(2000)`.
Internal validation trims text, rejects blank values and HTML-like markup, and never
accepts arbitrary metadata or provider output.

## Target Contract

Navigation uses only `target_type + target_id`. `NotificationTargetType` is a
`StrEnum` with existing product entities `APPLICATION`, `JOB`, and `CV`, persisted as
`VARCHAR(32)` plus UUID. Pydantic validation and `ck_notifications_target_pair`
require both fields or neither. No action path, external URL, route JSON, or multiple
nullable domain foreign keys are stored. Generic target existence cannot be enforced
by the database; Task 16B must pass an authorized, valid domain ID.

## API Contract

- `GET /api/v1/notifications` returns
  `{items,total,page,page_size,total_pages}`.
- `GET /api/v1/notifications/unread-count` returns `{unread_count}`.
- `PATCH /api/v1/notifications/read-all` returns `{updated_count}`.
- `PATCH /api/v1/notifications/{notification_id}/read` returns the updated
  notification.

Notification responses expose `id,type,title,message,read_at,is_read,target_type,
target_id,created_at`; recipient `user_id` is not exposed. Static `/read-all` is
declared before the UUID dynamic route. There is no public POST, generic edit, or
delete endpoint.

## Pagination

List defaults to page 1 and page size 20; page must be at least 1 and page size is
bounded to 1–100. SQL applies offset/limit and deterministic ordering by
`created_at DESC, id DESC`. `unread_only=true` adds `read_at IS NULL`. Empty lists
return zero totals and `total_pages=0`.

## Atomic Read Semantics

Mark-one executes one ownership-scoped atomic update:

`UPDATE ... WHERE id=:id AND user_id=:current_user AND read_at IS NULL RETURNING id`.

If it updates no row, an ownership-safe lookup distinguishes an already-read own row
from foreign/nonexistent rows without leaking existence. Mark-all is one bulk update
over the current user's unread rows. It never touches another user or changes an
existing `read_at`; an empty set returns HTTP 200 with `updated_count=0`.

## Authorization

All four routes use the shared JWT `get_current_user` dependency rather than a role
guard, allowing all three roles through the same contract. Tests cover unauthenticated
401 responses, per-role isolation, Admin non-bypass, foreign/nonexistent 404 parity,
absence of a client ownership parameter, and absence of a public create operation.

## Indexes

- `(user_id, created_at, id)` supports owned latest-list scans; PostgreSQL can scan
  the B-tree backward for the all-DESC order.
- Partial `(user_id) WHERE read_at IS NULL` supports unread count/filter and the
  ownership predicate of mark-all without duplicating a broad single-column index.

## Migration

Alembic revision `f8b2c4d6e1a3`, based on `e7a1c3d5f9b2`, creates the table, named
user FK with `ON DELETE CASCADE`, primary key, bounded columns, target-pair and
nonblank-text checks, both indexes, and timezone-aware timestamps. On the guarded
TEST database, `head -> e7a1c3d5f9b2 -> head` passed. `alembic check` reports no new
upgrade operations.

## Tests

New `tests/test_notifications.py` uses synthetic users and notifications and cleans
them after every test. Its seven grouped tests cover the requested schema/model,
internal creation, three roles, ownership, ordering/tie-break, pagination defaults
and bounds, unread filtering/count, atomic/idempotent mark-one, bulk mark-all, route
collision, auth, target integrity, plain text, and no-public-create cases.

- Notification tests: **7 passed, 2 warnings in 1.22s**.
- Focused notification/auth/users/admin-users: **41 passed, 2 warnings in 14.33s**.
- Final full backend: **938 passed, 4 warnings in 119.26s (0:01:59)**.

Warnings are existing google-genai, Starlette/httpx, and HTTP 422 deprecations. Tests
did not call any live AI or external provider.

## Regression

The change is additive: no existing auth, user, candidate, recruiter, admin, job,
application, CV extraction, matching, ranking, or recommendation behavior was
modified. Final AST parsing and `git diff --check` pass; only existing line-ending
conversion warnings remain.

## DB Safety

All database tests and migration operations used the existing guarded
`TEST_DATABASE_URL` flow, which verifies it differs from `DATABASE_URL` and checks the
actual connected database identity. DEV DB writes: **0**. Test rows use the
`task16a_` prefix and are deleted by an autouse cleanup fixture. No Gemini, Qwen,
Ollama, BGE, email, push, WebSocket, SSE, or other external call occurred.

## Limitations

Task 16A provides persistence and own-user read APIs only. It does not wire application
status, job moderation, CV, recruiter, candidate, or Admin domain events. Therefore a
real production user may correctly receive an empty notification list. Real domain
notification creation is **not verified until Task 16B**. Frontend bell/page, realtime
delivery, email/push, preferences, digests, deletion, event bus, outbox, and scheduler
remain out of scope.

## Final Status

**TASK 16A — MULTI-ROLE NOTIFICATION BACKEND FOUNDATION — VERIFIED.**

Recommended Task 16B input: use the existing internal creation service inside each
domain transaction, define only evidence-backed new notification types, validate the
recipient and logical target before creation, and keep notification failure semantics
explicit without adding a public arbitrary-create API.
