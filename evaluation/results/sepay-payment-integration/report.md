# AUX-MONETIZATION-03 — SePay Payment + Automatic Subscription Activation

## Product Scope

Implemented the local payment contract for Recruiter paid-plan purchases: server-created payment orders, immutable commercial snapshots, VietQR instructions, authenticated SePay webhook ingestion, transaction disposition audit, atomic activation/renewal, and a Recruiter payment page with visibility-aware polling.

Out of scope and not added: Admin payment UI, manual mark-paid, refund, invoice, recurring billing, proration, Candidate monetization, payment approval workflow, and quota management.

## Worktree Snapshot

Both repositories were dirty before this task and those changes were preserved. The Backend already contained uncommitted subscription/entitlement foundation work plus unrelated CV/ranking changes. The Frontend already contained uncommitted Recruiter monetization/navigation/UI work plus unrelated matching and layout changes. No reset, checkout, clean, or destructive workspace command was used.

Initial `git diff --check` was clean. Final `git diff --check` is also clean; Git only reports the existing Windows LF-to-CRLF conversion warnings.

## Source Review

Reviewed the existing subscription service/repository transaction ownership, expiry normalization, one-active-subscription constraint, ADMIN/PAYMENT source enum, entitlement resolution, auth/role dependencies, response conventions, DB UUID/timestamp/NUMERIC patterns, Alembic setup, guarded pytest fixture, Recruiter plan catalog/page, current-plan badge, Axios client, shared refresh signal, and frontend node:test/SSR conventions.

The existing Admin grant flow owned its commit. It was refactored around a no-commit mutation primitive so the payment webhook can own one atomic transaction without changing Admin behavior.

## TEST_DATABASE_URL Gate

PASS before backend source modification.

- DEV identity: `gjob_db@loopback:5433`
- TEST identity: `gjob_db_test@loopback:5433`
- They are distinct PostgreSQL databases.
- `SELECT current_database()` on the guarded test connection returned `gjob_db_test`.
- `.env.test.example` is a template and is not loaded automatically. Its checked-in URL contains a placeholder password, so verification commands injected a derived local TEST URL into the process only; no credential was printed or committed.

## Pre-change Baseline

Backend focused baseline:

- subscriptions, entitlements, auth: `30 passed`, 2 dependency warnings, pytest 18.66 s (21.51 s wrapper).
- The first attempt hit the Windows default pytest temp-directory ACL. It was repeated with a unique workspace-local `--basetemp`; this was an environment issue, not a product failure.

Frontend baseline:

- focused monetization tests: `17 passed, 1 failed`.
- The one failure was a stale assertion that prohibited the already-intended current-plan topbar link to `/recruiter/plans`; the source behavior was valid and the test was updated with the new payment contract.
- `npx tsc -b`: PASS, 16.7 s.
- Vite reported the already-present HMR port `24678` warning during multi-file node tests.

## Payment Architecture

Flow:

1. Authenticated Recruiter selects an active paid plan.
2. Backend locks Recruiter → plan → active subscriptions → pending orders, validates the purchase, reuses an unexpired same-plan order or creates a new 30-minute order.
3. Frontend displays only backend-returned amount, account, transfer code, expiry, and QR URL.
4. SePay sends a public webhook. The endpoint verifies HMAC over raw bytes before JSON parsing.
5. The payment service locks in the same global order, classifies the event, and commits transaction + order + subscription exactly once.
6. Frontend polls the owned order. Only a backend `PAID` state triggers current-subscription and entitlement refetch.

## PaymentOrder

`payment_orders` contains Recruiter/plan references, code/name/amount/currency/billing-period/duration snapshots, unique non-PII payment code, `PENDING|PAID|EXPIRED|CANCELLED`, expiry, paid time, and UTC timestamps. Money is `NUMERIC(18,0)` / `Decimal`, transported to the frontend as a string.

The server derives all authoritative fields from the plan. The create request accepts only `plan_id` and rejects extra fields.

## PaymentTransaction

`payment_transactions` records provider transaction identity, optional matched order, amount, transaction time, reference, content, destination account, and one frozen disposition:

- `APPLIED`
- `UNMATCHED`
- `AMOUNT_MISMATCH`
- `ORDER_EXPIRED`
- `ORDER_CANCELLED`
- `OUTGOING_IGNORED`
- `ACCOUNT_MISMATCH`

`UNIQUE(provider, provider_transaction_id)` is enforced by PostgreSQL. Duplicate delivery does not create a `DUPLICATE` row.

## Commercial Snapshot

Fulfillment uses the order's immutable code, name, amount, currency, billing period, and duration. The mandatory regression created an order at 99,000 VND / 30 days, changed the plan to 129,000 VND / 45 days, then proved the old order still applied 99,000 VND / 30 days.

Plan and payment history use restrictive foreign keys, so deactivation does not erase historical meaning.

## Subscription Transaction Refactor

`apply_grant_or_change_no_commit` and `apply_payment_no_commit` mutate and flush without committing or rolling back. Admin orchestration still commits once with source `ADMIN`. Payment orchestration commits once with source `PAYMENT`.

Lock ordering is consistent across order creation, Admin subscription changes, and webhook application: Recruiter → plan → active subscriptions → payment order/pending orders. This avoids an order-vs-Recruiter lock inversion under concurrent create/webhook activity.

## Activation Policy

A valid unexpired exact-amount incoming payment to the configured destination account activates one `ACTIVE` subscription with source `PAYMENT`, starting at processing time and expiring by the snapshotted duration. Existing entitlement resolution observes that subscription normally; there is no direct entitlement mutation.

FREE, inactive, zero-price, unsupported-currency/period/duration, different-active-plan, and perpetual same-plan conflicts are rejected safely. The frontend cannot activate a plan.

## Renewal Policy

For the same active plan, the existing row is extended from `max(current expiry, now)` by the snapshotted duration. Remaining paid time is preserved, the row is not replaced, and duplicate webhook delivery cannot extend it twice. A perpetual subscription is not extended by this flow.

## SePay HMAC Contract

The public endpoint is `POST /api/v1/payments/sepay/webhook` and requires no JWT. It reads at most 64 KiB of raw request bytes, then verifies:

- `X-SePay-Timestamp`
- `X-SePay-Signature: sha256=<hex>`
- signing input `{timestamp}.{raw_body}`
- HMAC-SHA256 with `SEPAY_WEBHOOK_SECRET`
- constant-time `compare_digest`
- maximum clock skew of 300 seconds

Only after successful verification is JSON parsed. Missing configuration fails closed with 503; missing, malformed, stale, or invalid authentication returns 401; malformed authenticated JSON returns 400. This matches the current [official SePay webhook authentication contract](https://developer.sepay.vn/en/sepay-webhooks/xac-thuc).

## Payload Mapping

A dedicated Pydantic adapter maps SePay `id`, `code`, `content`, `transferAmount`, `transferType`, `transactionDate`, `referenceCode`, and `accountNumber` to domain names. SePay's space-separated local timestamp is parsed as UTC+07:00 and persisted timezone-aware.

## Payment Matching

Non-empty SePay `code` has priority. Only when it is empty does content parsing run. The fallback uses exact alphanumeric token boundaries around the configured prefix plus 12 uppercase random characters; fuzzy substring collisions do not match.

## Account Validation

Incoming destination account is normalized and compared with `SEPAY_BANK_ACCOUNT`. An account mismatch is recorded as `ACCOUNT_MISMATCH`, performs no activation, and returns the successful acknowledgement required to stop business-case retries.

## Disposition Handling

Authenticated outgoing, unmatched, wrong-amount, expired, cancelled, and account-mismatch events are recorded safely and acknowledge `200 {"success": true}`. They never mutate subscription state. Unexpected transactional failures are not acknowledged and roll back.

## Idempotency

Provider transaction identity is checked before processing and protected by a composite DB unique index. The payment order row serializes application. If concurrent duplicate deliveries race at the unique constraint, the loser rolls back and acknowledges the already-persisted transaction. Tests prove one transaction row and one activation/renewal effect.

## Atomicity

PaymentTransaction insertion, PaymentOrder transition, and RecruiterSubscription activation/renewal share one SQLAlchemy transaction and one final commit. A forced subscription failure test proves no transaction row, no `PAID` order, and no subscription mutation remains after rollback.

## Lazy Expiry

No worker or cron was added. GET lazily transitions stale `PENDING` orders to `EXPIRED`; create normalizes stale pending orders before issuing a new one; webhook checks `expires_at` directly and records `ORDER_EXPIRED` even if status had not yet been normalized.

## Recruiter APIs

- `POST /api/v1/recruiter/payment-orders` — Recruiter-only, body `{ "plan_id": "<uuid>" }`, returns 201.
- `GET /api/v1/recruiter/payment-orders/{order_id}` — Recruiter-only, ownership-safe 404 for foreign orders.
- `POST /api/v1/payments/sepay/webhook` — public but HMAC-authenticated.

## Frontend Payment Page

`/recruiter/plans` now shows `Đăng ký` only for an active, non-FREE, non-current paid plan. Clicking it creates the server order and navigates to `/recruiter/payments/:orderId`; it does not refresh or unlock entitlements.

The payment page shows plan snapshot, Decimal-string amount, bank/account holder, account number, prominent exact transfer content, backend-generated VietQR URL, copy actions, display-only countdown, and distinct PENDING/PAID/EXPIRED/CANCELLED states. A transient polling failure preserves the existing payment instructions.

## Polling

Polling runs every 5 seconds only for `PENDING` while the document is visible. Hidden tabs pause. Returning visible triggers an immediate fetch and resumes the interval. PAID, EXPIRED, CANCELLED, order changes, and unmount clean up timers and in-flight requests. PAID calls current-subscription refetch plus the shared data-refresh signal; there is no optimistic `PRO` assignment.

## Backend Tests

- Final payment/webhook focus: `14 passed`, 2 dependency warnings, 7.17 s.
- Earlier combined subscription/entitlement/auth/payment focus: `42 passed`, 2 dependency warnings, 25.85 s.
- Final full regression: `983 passed`, 4 dependency/deprecation warnings, 217.17 s.
- `compileall`: PASS.

Covered server authority, pending reuse, ownership/roles, FREE/inactive/cross-plan rejection, HMAC failures, malformed authenticated payload, full commercial snapshot, exact payload mapping, code priority/boundaries, every frozen business disposition, lazy expiry, FREE→PRO, entitlements, same-plan renewal, sequential duplicate, concurrent duplicate, and forced atomic rollback.

## Frontend Tests

- Focused payment/entitlement/subscription run: `25 passed`.
- Final full node:test: `104 passed`, 0 failed, 3.76 s.
- Targeted ESLint for all payment files/tests: PASS.
- Full ESLint: one pre-existing error remains at `src/components/motion/ScrollReveal.tsx:24` (`react-hooks/set-state-in-effect`); no payment file warning/error remains.
- Production build (`tsc -b && vite build`): PASS, 2,080 modules; Vite reports the existing >500 kB chunk advisory.
- Node tests continue to print the existing Vite HMR port `24678` warning; tests pass.

## Migration Verification

On `gjob_db_test` only:

- upgrade to `b2d4f6a8c0e1`: PASS
- downgrade to `a1c3e5f7b9d2`: PASS
- re-upgrade to head: PASS
- `alembic check`: `No new upgrade operations detected.`

## DB Safety

Automated mutations ran only through the guarded TEST engine against `gjob_db_test`. DEV database writes: 0. Test users, orders, transactions, subscriptions, and synthetic plans use scoped identifiers and are cleaned by fixtures. Workspace-local unique pytest temp directories were removed after runs.

## External-call Safety

- Real SePay calls: 0
- Real bank transfers/calls: 0
- Real BGE/Ollama/Gemini/Qwen calls: 0
- All webhook inputs were synthetic and locally HMAC-signed.
- No real secret, bank account, or ngrok host was added to source.

## Manual Setup Required

Populate local backend environment values (never commit them):

```dotenv
SEPAY_WEBHOOK_SECRET=<from SePay>
SEPAY_BANK_NAME=<bank display name>
SEPAY_BANK_BIN=<bank BIN/code>
SEPAY_BANK_ACCOUNT=<receiving account>
SEPAY_ACCOUNT_NAME=<account holder>
SEPAY_PAYMENT_CODE_PREFIX=GJOB
PAYMENT_ORDER_TTL_MINUTES=30
```

Restart FastAPI after editing the environment.

## ngrok Instructions

User-only manual steps:

```powershell
ngrok config add-authtoken <YOUR_TOKEN>
uvicorn app.main:app --reload --port 8000
ngrok http 8000
```

Copy the HTTPS forwarding host. Do not put it in source. The webhook URL is:

```text
https://<NGROK_HOST>/api/v1/payments/sepay/webhook
```

## SePay Dashboard Instructions

Configure manually:

- Webhook name: `GJob Recruiter Payment`
- Webhook URL: `https://<NGROK_HOST>/api/v1/payments/sepay/webhook`
- Transaction type/event: `Tiền vào` / Money in
- Payload/content type: `JSON`
- Automatic retry: `ON`
- Security/authentication: `HMAC-SHA256`
- Receiving account: select the same account represented by `SEPAY_BANK_ACCOUNT`
- Copy the generated Secret Key immediately into `SEPAY_WEBHOOK_SECRET`, then restart backend.

The official SePay test-mode setup describes selecting HMAC-SHA256 and simulated transaction delivery: [Create a webhook in SePay Test mode](https://developer.sepay.vn/en/tien-ich-khac/test-mode/tao-webhook).

Expected manual test result: the delivery reaches backend, returns `200 {"success": true}`, creates one `APPLIED` transaction, changes the order to `PAID`, activates/renews one subscription with source `PAYMENT`, and unlocks existing entitlements after frontend refetch. Replaying the same SePay transaction ID must not change expiry again.

## Baseline vs Final

Backend moved from 30 focused baseline passes to 983 full passes including 14 new payment tests. Frontend moved from one known stale focused assertion to 104/104 full passes, with the new purchase/payment/polling contract covered. No new lint regression was introduced; the sole full-lint failure is the pre-existing ScrollReveal issue.

## Limitations

- No real ngrok/SePay delivery has been performed, so external connectivity, actual dashboard secret, and the selected bank account are not verified.
- VietQR is a backend-built authoritative URL rendered from `img.vietqr.io`; availability of that image host is external to GJob.
- Reconciliation jobs, IP allowlisting, Admin payment audit UI, refund/invoice/proration, and recurring billing are intentionally outside Task 03.
- The existing global frontend bundle-size advisory and ScrollReveal lint failure remain unrelated follow-up work.

## Final Status

**AUX-MONETIZATION-03 — SEPAY PAYMENT + AUTOMATIC SUBSCRIPTION ACTIVATION — LOCAL CONTRACT VERIFIED**

The status may be upgraded to **NGROK/SEPAY VERIFIED** only after user-provided evidence shows a real/test-mode SePay delivery reached ngrok/backend, HMAC passed, transaction became `APPLIED`, order became `PAID`, subscription/entitlement updated, and duplicate replay did not renew twice.
