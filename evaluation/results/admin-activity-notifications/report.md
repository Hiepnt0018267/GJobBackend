# Task 16B.1 — Admin Activity Notifications

## Status

**VERIFIED.** Candidate/recruiter registration and recruiter job create/update-to-PENDING now notify every active Admin within the same domain transaction. Existing Task 16A/16B behavior remains intact.

## Source Review

- Public Candidate and Recruiter registration share `AuthService.register`; public ADMIN registration remains rejected. The current registration flow creates the `User` row only—there is no candidate/recruiter profile row in this source path.
- Recruiter job creation and editable updates are owned by `RecruiterJobService`; both result in `JobStatus.PENDING`. Empty update payloads are rejected before mutation.
- Admin identity is `User.role == ADMIN`; active status is `User.is_active == true`. The source model has no soft-delete field.
- Notifications are transaction-owned through `NotificationRepository.create`, which flushes but does not commit. `NotificationType` is stored in VARCHAR, so no Alembic migration is needed.
- Existing application and job-moderation notification behavior remains centralized in `NotificationEventService`.

## Product Rule Change

The backend now creates Admin activity notifications for exactly four domain events:

| Event | Type | Recipient | Target |
|---|---|---|---|
| Candidate registers | `CANDIDATE_REGISTERED` | All active Admins | `NULL / NULL` |
| Recruiter registers | `RECRUITER_REGISTERED` | All active Admins | `NULL / NULL` |
| Recruiter creates a PENDING job | `JOB_PENDING_REVIEW` | All active Admins | `JOB / job.id` |
| Recruiter edits a job back to PENDING | `JOB_PENDING_REVIEW` | All active Admins | `JOB / job.id` |

Candidate application submission continues to notify only the owning Recruiter. Registration creates no self-notification.

## Notification Types

Added exactly:

- `CANDIDATE_REGISTERED`
- `RECRUITER_REGISTERED`
- `JOB_PENDING_REVIEW`

All pre-existing notification types are unchanged. Because the database column is VARCHAR, no schema revision was created.

## Admin Recipient Policy

`UserRepository.list_active_admin_ids()` performs one SQL query filtered by `role == ADMIN` and `is_active == true`, ordered deterministically by user ID. Candidate, Recruiter, and inactive Admin accounts are excluded by SQL rather than filtered in Python.

The resulting IDs are inserted through one shared session. The implementation does not reload each recipient, does not commit per Admin, and safely returns zero when the recipient set is empty.

## Registration Integration

`AuthService.register` now owns the complete registration transaction:

1. validate role and uniqueness;
2. add and flush the new User;
3. resolve active Admin IDs once;
4. insert the appropriate registration notifications;
5. commit once and refresh the User.

Any exception rolls back the User and every staged notification. Candidate and Recruiter registrations use the same transaction path with their respective notification type. Registration notifications intentionally use no target because no existing safe Admin user/profile notification target exists.

## Job Create Integration

`RecruiterJobService.create_job` adds and flushes the PENDING job, broadcasts `JOB_PENDING_REVIEW` with `JOB / job.id`, then commits once. A notification failure rolls back the job and the entire broadcast.

## Job Update Integration

After ownership, closed-state, non-empty payload, and salary validation pass, `RecruiterJobService.update_job` applies the edit, sets the job to PENDING, flushes it, broadcasts the update-specific `JOB_PENDING_REVIEW` copy, and commits once. Failed and empty/no-op updates do not reach notification creation.

An APPROVED job edited back to PENDING creates a new notification for every active Admin, representing a new legitimate review cycle.

## Centralized Copy

All new Vietnamese title/message text is built in `app/services/notification_event_service.py` by `build_registration_notification` and the PENDING branch of `build_job_notification`. Create and update use distinct wording while sharing `JOB_PENDING_REVIEW`. The copy contains no email, phone, name, raw profile data, internal UUID, or Admin note.

## Dedupe Semantics

There is no permanent uniqueness constraint or dedupe by `job_id`. Each successful distinct create/update mutation that results in PENDING may create a new review notification. Rejected/failed/empty updates create none, and rollback prevents failed transaction attempts from leaving duplicates.

Recipient IDs are defensively de-duplicated within a single broadcast before insertion.

## Transaction Semantics and Broadcast Atomicity

User/job repositories gained non-committing `add`/`flush` methods for caller-owned transactions. Existing committing methods remain available to unrelated flows.

Broadcast is a one-query, small-N insert loop in the same SQLAlchemy session. If an insert fails after an earlier Admin notification has already flushed, service-level rollback removes all notifications and the associated User or Job mutation. No partial Admin delivery can persist.

## Tests

New focused coverage in `tests/test_admin_activity_notifications.py` verifies:

- exact enum values and centralized create/update copy;
- active Admin SQL filtering;
- Candidate and Recruiter API registration broadcast;
- null registration targets and absence of PII/self-notification;
- job create and APPROVED→edit→PENDING review cycles;
- JOB target mapping;
- inactive Admin exclusion;
- rejected empty update leaves counts unchanged;
- zero-active-Admin success;
- second-recipient registration failure rolls back User and all notifications;
- second-recipient job failure rolls back Job and all notifications.

The old contradictory `no_admin_pending_broadcast` assertion was removed from `tests/test_notification_domain_events.py`; its remaining moderation test still verifies owner notifications, missing-owner handling, and repeat-transition safety.

### Focused regression

Command scope included:

- `tests/test_admin_activity_notifications.py`
- `tests/test_notification_domain_events.py`
- `tests/test_notifications.py`
- `tests/test_auth.py`
- `tests/test_recruiter_jobs.py`
- `tests/test_admin_jobs.py`

Result: **68 passed, 2 warnings in 34.32s**.

This covers registration/auth regressions, recruiter job create/update/ownership/validation, Admin approve/reject, Task 16A notification ownership/read APIs, and Task 16B application/job-moderation events.

### Full backend regression

Result: **954 passed, 4 warnings in 196.73s (0:03:16)**.

Warnings are existing dependency deprecations from google-genai and Starlette/httpx/HTTP 422 naming; there were no test failures.

## DB and External-Service Safety

- Automated tests ran only against the guarded `gjob_db_test` derived into a child-process `TEST_DATABASE_URL`.
- DEV DB writes: **0**.
- Gemini/Qwen/Ollama/BGE/SePay/email/push/WebSocket/SSE calls: **0**.
- Task fixtures removed their marker Users/Jobs. Because legacy full-suite fixtures exercised the newly integrated registration/job paths against a test database containing many active test Admins, the suite generated `110220` notifications of the three new types; a guarded post-suite cleanup first verified `current_database() == 'gjob_db_test'`, deleted only those three notification types, and verified `0` remained. Isolated pytest temporary directories were also removed after each run.
- No frontend file, API contract, endpoint, request/response schema, or prior report was changed.
- The unrelated pre-existing untracked uploaded PDF was preserved untouched.

## Files Changed

- `app/models/notification.py`
- `app/repositories/user_repository.py`
- `app/repositories/job_repository.py`
- `app/services/notification_service.py`
- `app/services/notification_event_service.py`
- `app/services/auth_service.py`
- `app/services/recruiter_job_service.py`
- `tests/test_notification_domain_events.py`
- `tests/test_admin_activity_notifications.py`
- `evaluation/results/admin-activity-notifications/report.md`

## Limitations

- Broadcast is synchronous and appropriate for the current small Admin population; this task intentionally adds no queue or realtime transport.
- Registration notifications are deliberately non-clickable until the product has a supported Admin user/profile target mapping.
- The backend creates and exposes notifications through the existing shared notification APIs; frontend presentation and realtime refresh are outside Task 16B.1.

## Final Status

**TASK 16B.1 — ADMIN ACTIVITY NOTIFICATIONS — VERIFIED.**

The backend notification domain is complete for the frozen Task 16B.1 matrix: all active Admins receive atomic registration and pending-review events, zero-Admin operation succeeds, multiple genuine review cycles remain observable, and all focused/full regressions pass.
