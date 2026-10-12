# Task 16B — Notification Domain Event Integration

## Status

**VERIFIED.** The frozen eight domain mutations now create persisted notifications
inside the same database transaction as their application/job mutation and existing
history or audit row. Exactly five notification types were added. Missing recipients
are skipped without creating orphan rows. No frontend, realtime delivery, external
service call, model call, DEV database write, or Task 16A report edit was made.

## Source Review

The implementation reviewed the real submit, withdrawal, recruiter-transition, and
admin-moderation services and repositories before modification. Application submit
and admin moderation already had a service-owned final commit. Withdrawal and
recruiter transition previously committed inside their repositories, preventing an
atomic notification side effect.

All callers of the two changed repository methods were located. Their production
callers are `CandidateApplicationService` and `RecruiterApplicationService`.
One existing repository-level concurrency test called both methods directly and was
updated to commit explicitly at its caller boundary. No other caller still depends
on the removed internal commits.

## Frozen Event Matrix

| # | Domain mutation | Recipient | Notification type | Target |
|---:|---|---|---|---|
| 1 | Candidate submits an application | Job owner recruiter | `APPLICATION_SUBMITTED` | `APPLICATION` + application ID |
| 2 | Recruiter moves application to `REVIEWING` | Application candidate | `APPLICATION_STATUS_CHANGED` | `APPLICATION` + application ID |
| 3 | Recruiter moves application to `SHORTLISTED` | Application candidate | `APPLICATION_STATUS_CHANGED` | `APPLICATION` + application ID |
| 4 | Recruiter moves application to `REJECTED` | Application candidate | `APPLICATION_STATUS_CHANGED` | `APPLICATION` + application ID |
| 5 | Recruiter moves application to `HIRED` | Application candidate | `APPLICATION_STATUS_CHANGED` | `APPLICATION` + application ID |
| 6 | Candidate withdraws an application | Job owner recruiter | `APPLICATION_WITHDRAWN` | `APPLICATION` + application ID |
| 7 | Admin approves a pending job | Job owner recruiter | `JOB_APPROVED` | `JOB` + job ID |
| 8 | Admin rejects a pending job | Job owner recruiter | `JOB_REJECTED` | `JOB` + job ID |

No notification is created by reads, ranking/recommendation, recruiter job closing,
job creation/update into `PENDING`, or the Admin moderation queue. In particular,
there is no broadcast to Admin users when a job enters `PENDING`.

## Notification Types

The shared `NotificationType` StrEnum now contains exactly the five Task 16B values:

- `APPLICATION_SUBMITTED`
- `APPLICATION_STATUS_CHANGED`
- `APPLICATION_WITHDRAWN`
- `JOB_APPROVED`
- `JOB_REJECTED`

Persistence remains VARCHAR, so Task 16B requires no schema migration and adds none.

## Repository Transaction Refactor and Caller Audit

`CandidateApplicationRepository.withdraw_if_eligible()` and
`RecruiterApplicationRepository.transition_if_current()` now issue their mutation
and history writes without committing. Their services own the one final commit after
notification creation. A failed compare-and-set is rolled back before returning the
existing conflict response. External endpoint and expected-status behavior remain
unchanged.

Application submission creates the application and existing history, creates the
recruiter notification, then commits once. Recruiter transitions update status,
write existing history, create the candidate notification, then commit once.
Withdrawal updates status, writes history, creates the recruiter notification, then
commits once. Admin approval/rejection updates the job, writes the existing audit,
creates the recruiter notification, then uses the existing final commit.

## Recipient Resolution and Missing Recipient Policy

Application submission/withdrawal and job moderation use the job's canonical
`recruiter_id` user owner. Recruiter application actions use the application's
canonical `candidate_id`. The event helper verifies that the user still exists.

If the recipient ID is null or the user no longer exists, notification creation is
skipped. The valid domain mutation retains its existing behavior; no null-user row,
fallback recipient, Admin broadcast, or HTTP 500 is introduced solely because the
recipient is missing.

## Message Contract

All deterministic Vietnamese product copy is centralized in
`app/services/notification_event_service.py`; routers contain no notification copy.
The fixed titles/messages cover submitted, reviewing, shortlisted, rejected, hired,
withdrawn, approved, and rejected-job events. Only a sanitized job title is inserted.
HTML-like tags and excess whitespace are removed from that title. Candidate name,
email, phone, raw CV/cover-letter text, internal notes, and internal IDs are excluded.

New notification rows use `read_at = NULL`, so the Task 16A response contract derives
`is_read = false`. Application events use the existing `APPLICATION` target and job
moderation events use the existing `JOB` target. No metadata/action-path or new target
type was added. All inserts reuse `NotificationService.create_notification()`.

## Transaction Semantics and Rollback Verification

The required operation is one transaction:

1. validate the domain action and ownership;
2. issue the domain mutation;
3. add the existing history/audit row;
4. create the notification when its recipient exists;
5. commit once at the service boundary.

When a real recipient exists and notification persistence raises, the service rolls
back the complete transaction. Integration tests monkeypatch
`NotificationRepository.create()` to raise after the mutation has been issued and
then query database state. They prove rollback of:

- application submission and its history;
- recruiter status transition and its history;
- candidate withdrawal and its history;
- both job approval and rejection plus their audit rows;
- the attempted notification row itself.

## Idempotency and Domain Behavior

Notifications are created only after a valid state transition succeeds. Duplicate
submit and invalid transition tests create no notification. Repeated review, hire,
withdraw, approve, and reject requests retain their existing conflict semantics and
leave notification counts unchanged. Actors do not receive unintended
self-notifications, and unrelated recruiters/Admins receive none.

## Test Results

- New Task 16B integration suite: **9 passed, 1 warning in 0.85s**.
- Task 16A plus touched-domain focused regression: **86 passed, 2 warnings in 75.51s**.
- Full guarded backend regression: **947 passed, 4 warnings in 206.38s**.
- Python AST validation: **10 changed Task 16B source/test files parsed successfully**.
- `git diff --check`: **PASS**, with existing line-ending conversion warnings only.

The focused suite covers Task 16A list/unread/count/read-one/read-all/ownership/
pagination/read-state behavior, application submit and withdrawal, recruiter fixed
status actions and concurrency, job moderation, Admin job APIs, auth, the complete
event matrix, copy safety, missing recipient, no Admin pending broadcast, retries,
invalid actions, and forced rollback.

`alembic heads` reports the existing Task 16A notification migration
`f8b2c4d6e1a3` as the sole head. The persistent local TEST database is stamped at the
preceding revision, so `alembic check` correctly reports that database as not up to
date; it was not stamped or upgraded merely to make the check green. Task 16B itself
has no schema operation. Full tests create/validate their isolated schema through the
existing guarded fixture.

## DB and External-Service Safety

Every automated test ran only with guarded `TEST_DATABASE_URL` targeting
`gjob_db_test`; the guard also checked the actual connected database identity.
DEV database writes: **0**. External/model calls: **0 Gemini, 0 Qwen, 0 Ollama,
0 BGE, 0 `/api/chat`, 0 `/api/embed`**. There is no email, push, WebSocket, SSE,
background task, event bus, or outbox. Synthetic test entities use Task 16B markers
and existing fixture cleanup. No valid application/job/notification data was deleted.

## Files Changed for Task 16B

- `app/models/notification.py`
- `app/services/notification_event_service.py`
- `app/services/application_service.py`
- `app/repositories/candidate_application_repository.py`
- `app/services/candidate_application_service.py`
- `app/repositories/recruiter_application_repository.py`
- `app/services/recruiter_application_service.py`
- `app/services/admin_job_service.py`
- `tests/test_recruiter_applications.py`
- `tests/test_notification_domain_events.py`
- `evaluation/results/notification-domain-events/report.md`

The uncommitted working tree also contains the already-verified Task 16A foundation;
its historical report was not edited by Task 16B.

## Limitations and Next Task

Task 16B verifies real backend domain mutation to persisted notification through
automated integration tests. It does not verify a browser bell/badge/page, frontend
mark-read behavior, realtime delivery, email, or push. Recommended Task 16C input is
the unchanged Task 16A read APIs plus these persisted event rows, with frontend
ownership/read-state/browser verification and no alteration to the frozen event
matrix.

## Final Status

**TASK 16B — NOTIFICATION DOMAIN EVENT INTEGRATION — VERIFIED.**
