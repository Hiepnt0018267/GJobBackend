# CV Extraction Output Budget & Timeout Contract Hardening

## 1. Status

**FRONTEND PARTIAL-DATE CONFIRMATION FIX PASS; actual browser save/reload verified.**
The reviewed extraction for CV549f31bf-6143-469a-a26d-acca54773045 now renders
professional partial dates without object coercion, confirms once through the
existing endpoint, and remains confirmed after reload.32 frontend tests,
TypeScript,build,ESLint,Impeccable detector and diff check pass. No extraction or
AI request was started;the existing compatible ranked vector was reused. See the
final Frontend Partial-Date Confirmation Contract section.

**CERTIFICATE SOURCE ALIGNMENT HARDENING VERIFIED at contract level.** Date-before,
date-after,inline,issuer-order,record-boundary and safe diagnostic behavior pass
focused176/full901 tests;95/95 accepted artifacts remain exact no-ops. One permitted
live workflow correctly failed closed because multiple certificate anchors occupy the
same flattened logical line,so live extraction success is not claimed. See the final
Certificate Source Alignment Hardening section.

Historical source-grounded reconciliation status follows:

**SOURCE-GROUNDED STRUCTURED DATE RECONCILIATION VERIFIED at contract level.**
The deterministic resolver now runs after sparse wire validation and before strict
canonical chronology validation. Focused152/full877 tests pass and95/95 accepted
canonical CVs remain exact no-ops. One permitted nonpersistent live workflow failed
closed with SOURCE_DATE_UNMATCHED at certificates[0];this is expected safe behavior,
not live extraction success. See the final Source-Grounded Date Reconciliation section.

Historical regression-audit status follows:

**Regression audit COMPLETE; strongest cause is the interactive provider/runtime change.**
Pre-14B factory was Gemini-only;Task14B eab0d62 added shared Qwen support and an
Ollama example setting. Current local config selects Qwen. Runtime10–20s baseline
and output-growth claim cannot be certified from retained Git evidence alone.
No production/config change or model call in this audit. See Pre-14B Regression Audit.
Prior patch verification is a controlled fixture result,not real-CV upload acceptance.

## 2. Incident Summary

User supplied6435 generated tokens, approximately175seconds at36.8tokens/s,
context shift discarding4093tokens, Ollama500 after2m59s and subsequent extraction502.
Original provider timeout180s versus frontend120s was mismatched. These log lines
alone do not establish the same request, final inner exception or client-disconnect
order. No raw CV/provider output/contact value is reproduced here.

## 3. Root Cause Evidence

Previous read-only DEV transaction inspected the latest attempt for
CVee0b92e2-707f-4d31-b19e-8c9350133a55: extraction81cac686-6165-4567-8f00-75c6ce4ff1ce,
FAILED,AI_RESPONSE_INVALID,ollama/qwen3:8b, duration85.73seconds; no structured payload.
Current persistence code maps CVExtractionValidationError to502. This establishes
the invalid-result branch, NOT whether JSON parsing/schema validation/correction
failed or whether it corresponds to the supplied2m59s log. A provider timeout normally
maps through provider-unavailable instead. Historical inner exception/provenance was
not retained sufficiently to prove the exact original termination.

## 4. Previous Contract

Before initial partial edits: num_ctx8192,no explicit num_predict,streamfalse,
thinkfalse,temp0,raw Pydantic schema supplied as format and included in user prompt.
Provider timeout covered one request/retry group, not both schema generations.
Maximum one schema correction; frontend120s. Context saturation checked completed
response metadata, not full rendered prompt+output reservation before generation.

Resume found additional existing edits after interruption: .env provider110s,
num_predict3072,safety256,total operation150s,correction minimum60s; frontend200s.
Settings still allow total300s, so fixed frontend200s is not a general configuration
contract. No .env values were changed on this resume; secrets were neither printed
nor placed in commands/report. These partial edits have not been treated as PASS.

## 5. New Output Budget

Earlier measured95 accepted workflow metrics: output min102,median1859,p903095,max5266.
Generated tokens include formatting; this is not a minimum payload-size proof.
Authoritative compact JSON measurement separately covered94 schema-valid minimized
structured fixtures: min146,median1504,p902371,max4088;2 exceed3072,0 exceed4096.
One fixture needing source-validation context was explicitly excluded from this
size diagnostic; no dataset row/artifact was changed or dropped.

The current .env cap3072 is therefore not sufficient for the full inspected fixture
range. No output was shortened, repaired, null-forced or accepted partially.4096
is an evidence-backed candidate, not a silently applied new configuration or a
guarantee that every real model completion fits (historical generation reached5266).

## 6. Context Preflight Formula

Required: exact rendered prompt tokens+measured special-token overhead+configured
reserved output+safety margin <= effective per-sequence context.
Ollama0.34.2's verified _debug_render_only path renders actual messages/template
without completion; same-model native /tokenize counts that rendered text. Model
path matched /api/show's FROM identity and runner /props; CLI context8192 verified.
Synthetic full production-prompt/schema count2873,with special tokens2873.
For a4096 candidate plus256margin:7225<=8192; this does NOT certify the failing CV fits.
References: [exact-version API](https://github.com/ollama/ollama/blob/v0.34.2/api/types.go),
[chat handling](https://github.com/ollama/ollama/blob/v0.34.2/server/routes.go),
[native tokenizer](https://github.com/ollama/ollama/blob/v0.34.2/llm/llama_server.go).

Partial adapter in app/ai/ollama_token_budget.py is version-bound/local-Windows and
uses no generation/character estimate. However current provider has a later-added
chars/3+512 fallback which CAN authorize generation when exact counting fails.
That is not accepted as authoritative preflight. It must become diagnostic-only
and fail closed before generation. No safe-admission claim for that fallback.

## 7. Safety Margin

Current256 tokens, nonzero. Full template/schema are already counted by the
authoritative path; measured special overhead is separate. Margin covers remaining
runtime-accounting differences. It cannot make a character approximation exact.

## 8. Total Operation Deadline

Current partial extract_from_text wraps both generations in150s asyncio.timeout.
Document extraction still happens synchronously outside that window; CPU-bound
validation needs a post-validation deadline check. Total deadline taxonomy/API
mapping is incomplete. No maximum-window/end-to-end guarantee is claimed yet.

## 9. Correction Pass Budget

One correction maximum remains. Existing partial elapsed-time check requires about
60s remaining, but boundary behavior, counter increments and deadline tests have not
been finished. Deterministic context/output failures must not be schema-corrected.

## 10. Frontend Timeout Contract

Current frontend200s exceeds currently configured150s, but backend supports settings
up to300s and has no shared public contract. A central returned timeout policy or
equivalent bounded shared contract is still required. No queue redesign was started.
Existing loading finally-blocks and backend per-CV PROCESSING unique constraint
were reviewed; immediate duplicate-click guards still need focused verification.

## 11. Exception Taxonomy

Partial provider types: context budget/output budget/token-accounting unavailable,
JSON parse/schema validation. Done-reason/known cap checks exist in partial code.
Service/persistence still collapse several types, including total deadline into
provider-unavailable; separate provider timeout,total deadline,correction and safe
persisted API codes remain unfinished. Candidate-facing errors must not expose
provider internals. No schema or prompt redesign is authorized/implemented here.

## 12. Configuration Changes

Initial interrupted turn added central predict/margin/total/correction settings,
factory wiring, exact-token adapter and partial provider handling. Resume discovered
additional edits and explicit .env3072/110/150 values; these were preserved.
No canonical matching version,Semantic-v1,BGE profile/recruiter ranking change.
Budget-profile identifier cv-extraction-budget-v1 is partial, not a completed freeze.
Previously accepted extraction/canonical artifacts were not regenerated/refingerprinted.

## 13. Tests

**No new automated test result or full-suite PASS claimed.** Implementation stopped
at user-prescribed budget hard stop before behavior consolidation/tests. Existing
provider mock tests need injected token counters and done_reason/output-cap fixtures
before safe validation; no live provider call may enter unit tests. Full guarded
TEST_DATABASE_URL pytest and frontend test/type-check/build/lint remain required.

## 14. Optional Live Sanity

**0 live completion generations,0 extraction retries,0 BGE/Gemini calls.** Previous
diagnostics used3 synthetic render-only request attempts (one wrong response-key
assertion, one ReadTimeout, final render/tokenize success) and deterministic native
tokenizations. Exact counting is model/template-bound, not an approximate library.
The first scripts failed on a fixture requiring source context; final size diagnostic
reported94valid/1not-used explicitly. No production CV was sent for a retry/sanity,
no response/prompt/token IDs/vocabulary/raw CV copied to report or diagnostic files.
Render-only loaded the existing model; it did not generate extraction output.

## 15. Model / DB Safety

Incident DB read was SET TRANSACTION READ ONLY with rollback. No DEV record mutation,
uploads,extractions,confirmations,deletions,junk data,migration or bulk retry.
All evaluation/frozen labels/cache inputs unchanged. Native process discovery and
protected runtime reads used approved read-only access. Shared Ollama not stopped.
No active task-owned extraction batch/lock or diagnostic file remains.

## 16. Known Limitations

Hardening incomplete. Current3072 cap cannot support two demonstrated valid compact
payloads; exact counting is currently Windows/Ollama0.34.2-specific and fail-closed
integration is unfinished. Larger/context-heavy CVs may also fail a correct preflight;
no automatic limit expansion is allowed. Historical original exception is not proven.
No claim that a synthetic count predicts completion length or live extraction success.

## 17. Exact Commands Run

This resume read attachment/source/config selected non-secret fields and created
this single report only. Previous diagnostic commands were in-memory Python via
venv\Scripts\python.exe -B -c and approved PowerShell Get-CimInstance runtime inventory;
local /api/version,/api/show,/api/ps,_debug_render_only,/props,/tokenize only.
No new generation/scoring/persistence/full-pytest command executed on this resume.

## 18. Final Status

**BLOCKED / NOT PASS.** Need an explicit output-budget decision before continuing.
Recommended candidate: authorize num_predict4096 while keeping context8192 and
currently chosen150s total deadline; fail early for any prompt/output reservation
that still cannot fit. Then remove approximate admission, finish timeout/error/
duplicate guards, run synthetic/full guarded tests and report remaining limits.
Do not claim the previously failing real CV is fixed without its own authorized
validation. Do not silently increase context/output/timeouts or retry the model.


## 19. Final Completion — User-Authorized Cap 4608

### Current contract

No pipeline rollback. num_predict=4608, num_ctx=8192, total operation=150s,
safety margin=256, correction minimum=60s. Effective provider timeout110s retained;
Settings original default90/max180 preserved. Only the .env cap changed3072→4608.
Structured requests explicitly use stream=false,think=false,temp0,shift=false,
truncate=false. One cap value drives reservation and request payload.

Exact admission: rendered prompt+special overhead+4608+256 <= effective context.
When exact tokenizer is unavailable, chars/3+512 is diagnostic ONLY, never admission.
Bounded requests may run through a version-verified no-shift/no-truncation runtime;
unknown runtime safety is a typed service-readiness failure, not a CV-size assertion.
Runtime context rejection is not retried; reported source loss/unsafe totals rejected.
Known length-stop/count>cap or malformed JSON at cap is typed output failure. Complete
schema-valid JSON at cap with normal stop may pass other guards. No partial JSON accepted.

150s deadline includes threaded document reading, preflight, generation, validation
and optional single correction. Same deadline carried between stages; post-validation
clock check prevents late acceptance. Correction starts only with at least60s remaining;
deterministic context/output errors do not start correction. A canceled file-reader
thread may finish reading but cannot launch generation. DB/persistence/network overhead
is outside the AI window; margin does not guarantee against an indefinitely stalled DB.

Candidate-authenticated GET /api/v1/candidate/cvs/extraction-policy returns ONLY
operation_timeout_ms=150000 and request_timeout_ms=180000 (150+30s). Frontend fetches
this contract before POST, validates margin, and no longer hardcodes120s. Ref-based
exclusive locks protect list/review callbacks before disabled-state rerender; loading
awaits resolve/reject, releases in finally. Existing backend PROCESSING unique index
and row lock retain cross-tab/request deduplication. No queue redesign.

### Taxonomy / provenance

Distinct safe persisted/API codes: AI_PROVIDER_TIMEOUT504,
AI_OPERATION_DEADLINE_EXCEEDED504,AI_CONTEXT_BUDGET_EXCEEDED422,
AI_OUTPUT_BUDGET_EXCEEDED502,AI_JSON_INVALID502,AI_SCHEMA_INVALID502,
AI_CORRECTION_FAILED502,AI_TOKEN_ACCOUNTING_UNAVAILABLE503. Cancellation records a
terminal canceled failure. Logs show IDs/counts/stage/type/known done_reason, not raw
CV/output/contact fields; candidate messages expose no provider internals.

Budget profile=cv-extraction-budget-v2-bounded-runtime-fallback. Schema/prompt/model/
provider and canonical matching version unchanged. Historical extraction profiles
must not be silently relabeled; no frozen evaluation manifest or accepted artifact
regenerated. Existing matching/BGE/ranking/recommendation code and policy untouched.

### Tests before real retry

- Focused evaluation+extraction/providers/budget/deadline/private-checkpoint/semantic/
  embeddings: **352 passed,2 warnings in7.24s**, synthetic/mock,--noconftest.
- Full backend: **784 passed,3 warnings in115.04s (0:01:55)**, existing guarded
  gjob_db_test. TEST_DATABASE_URL validated against DEV and actual DB identity;
  credentials only in child memory/redacted, no DEV fallback/new DB.
- Frontend: **23 passed,0 failed in3.49s**, timing contract, pending lock/double click,
  cleanup/error messages and ranking regressions. TypeScript-b, build2042modules,
  ESLint PASS; existing bundle-size warning remains (~1.47MB/360KB gzip).

First full run781pass/3fail: evaluation counter fixture and exhausted mock clocks.
Fixed tokenizer mocks/controllable clocks, then full suite passed. Earlier focused
194pass/3fail: staticmethod fixture/default Settings contract corrected without
weakening guards. A mock.invalid metadata GET failed DNS, not live Qwen inference;
final tests mock all accounting. No live model in automated tests. Final frontend
runs sequential; new SSR fixture disables HMR to avoid earlier test-port contention.

### Exactly one real-CV retry and STOP

After ALL tests/typecheck/build/lint passed, approved operator invoked normal
CandidateCVExtractionService with existing owner checks/document/provider pipeline.
No fake candidate/raw-text adapter/confirmation/embedding hook. Not browser-login E2E.

| Evidence | Actual result |
|---|---|
| CV | ee0b92e2-707f-4d31-b19e-8c9350133a55 |
| New extraction | 53604a66-25f0-45d0-93ea-6aaaf1de1e98 |
| Exact prompt/special/effective context | 3928 /0 /8192 |
| Output reservation/safety | 4608 /256 |
| Required/deficit | 8792 /600 |
| Failure | CVAIContextBudgetError,AI_CONTEXT_BUDGET_EXCEEDED,mapped422 |
| Duration | 12.583244s |
| Generation HTTP calls | **0** |
| Render-only request | **1**,200,no completion |
| Correction | **0** |
| Final DB state/payload | FAILED/no structured payload |
| CV columns | before/after hash identical |

No completion/JSON/schema validation was reached; no generation context shift could
occur. This is NOT extraction success. STOP after this result, no second CV/attempt
or cap/context/deadline inflation. Initial operator launch had a syntax error before
execution/import/DB/model; fixed/compiled before the single actual workflow, not an
extra extraction retry. Original failed attempt retained.

### Files / safety / cleanup

Backend:config.py, AI factory/exceptions/provider/new ollama_token_budget.py,
structured/persistent CV extraction services,CV router,new test_cv_budget.py and
existing provider/deadline/private/evaluation mock fixtures. Frontend:cvService.ts,
new utils/extractionOperation.ts,CandidateCVsPage.tsx,CVAIReviewPanel.tsx,apiError.ts,
new tests/cv-extraction-budget.test.mjs. Existing UX preserved; impeccable harden
principles applied to loading/concurrency/safe copy, no visual redesign.

Final completion0 Qwen generations/0 Gemini/0 BGE. One intentional FAILED extraction
record is user-authorized audit state, not junk. No CV/file/confirmed fields,
application status,new migration,benchmark/ground truth/cache mutation. Synthetic
fixtures clean up. No permanent diagnostic script/raw-data copy/process/lock remains.
Shared Ollama not stopped; valid data/cache not deleted. This SAME sole report updated.

Commands: focused pytest listed above; full pytest -B -p no:cacheprovider -q --tb=short
via guarded secret-redacted child environment; node --test --test-concurrency=1
for cv-extraction-budget/recruiter-ranking tests; tsc -b; vite build; eslint .;
frontend git diff --check. Backend has no Git metadata: its diff is N/A, not PASS.

README/.env.test.example document the same config/timing/fallback contract.
Final frontend git diff --check PASS; direct whitespace scan on edited backend code
found0 trailing-whitespace lines. Semantic-v1 core hash unchanged:
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.

**FINAL: hardening/regression complete; real-CV extraction BLOCKED by exact600-token
deficit. No live-success PASS. Separate budget decision required; no further retry
or limit change under current authorization.**

## 20. Extraction Context Capacity Verification

### Installed capacity / branch decision

2026-10-08 (Asia/Saigon). Chose ONLY branch A; no prompt-overhead audit or source
compression. Metadata inspection performed before generation confirms installed
qwen3:8b, GGUF8.2B/Q4_K_M, model bytes5225388164, Ollama0.34.2. Exact digest:
500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41.
Installed /api/show reports architectureqwen3 and qwen3.context_length40960;
model parameters contain no num_ctx8192 cap. This is installed-model evidence,
not a model-family capacity assumption.

Exact-version runtime source passes explicit NumCtx into the native context
allocation and reports it through ContextLength;8192 is not a hard ceiling there.
[Ollama runtime source](https://raw.githubusercontent.com/ollama/ollama/v0.34.2/llm/llama_server.go),
[chat route](https://raw.githubusercontent.com/ollama/ollama/v0.34.2/server/routes.go).
The authorized retry later verifies actual runtime context10240 before both
generations and authoritative preflight effective_ctx10240. Metadata support is
therefore distinguished from subsequently observed allocation/admission.

### Shared context contract / exact preflight

Shared Qwen extraction default and explicit local OLLAMA_LLM_NUM_CTX now10240;
num_predict4608, safety256, provider timeout110s and total deadline150s preserved.
Settings provider timeout default90/max180 remain unchanged. No model/prompt/schema,
identity/date/chronology or fallback-policy change. AI_CONTEXT_BUDGET_EXCEEDED
remains unchanged: authoritative counts that exceed effective capacity still reject.
Unknown exact counts are still diagnostic-only, not heuristic admission rejection.
stream=false,think=false,temp0,shift=false,truncate=false retained.

Initial exact reservation:3928+0specials+4608+256=8792<=10240; headroom1448.
Existing correction prompt:4054+0+4608+256=8918<=10240; headroom1322.
No output-cap or safety reduction was used to obtain admission.

Budget profile=cv-extraction-budget-v3-context10240. Provider profile binds version,
model,context,output,safety,shift/truncate/think/temperature and provider timeout.
Observed fingerprint:
0b279d2b3e9172c3846abe0c53167e50a87da0d4b1c124db16aedac8e9c819e6.
Old8192 profiles are not relabeled. Canonical matching version/fingerprint semantics,
Semantic-v1 and BGE context8192/batch4096 remain unchanged.

Changed files: app/core/config.py, app/ai/ollama_provider.py,
app/ai/ollama_token_budget.py, local .env context key, README.md,
.env.test.example, tests/test_cv_budget.py and generation-default assertion in
tests/embeddings/test_embedding_config.py. No secret value is reproduced here.

### Local runtime / VRAM implications

Initial /api/ps had no resident model. Approved GPU inventory observed NVIDIA
GeForce RTX4060 Laptop GPU,8188MiB total,0MiB used,7956MiB free; WDDM counters
are observations, not an exact allocation guarantee. Installed metadata has36
layers,8KV heads and128-dimensional K/V heads. Assuming full f16 KV, increasing
8192 to10240 adds approximately288MiB (1.125 to1.40625GiB KV). This is an estimate,
not measured KV type/offload or proof that every workload fits available VRAM.

During both actual requests /api/ps reported the same digest,context10240 and
size_vram6337719173bytes (approximately5.90GiB). This proves allocation for the
tested single sequential operation, not concurrent-load or150s latency guarantees.
A later unprivileged NVIDIA read returned NVML initialization error and supplies
no additional memory evidence. No GPU/KV/flash-attention/server-global setting,
parallelism or OS configuration changed; shared Ollama was not restarted/stopped.

### Tests BEFORE the single retry

- Focused evaluation/extraction/providers/budget/deadline/private-recovery/canonical/
  semantic/embedding tests: **355 passed,2 warnings in7.50s**, exit0.
- Full backend: **787 passed,3 warnings in181.46s (0:03:01)**, exit0.
  Existing guarded gjob_db_test only; TEST_DATABASE_URL and actual current_database
  verified, credentials in redacted child memory, no DEV fallback/new DB.
- New regression reproduces3928-token prompt:8192 rejects and10240 accepts the
  same full source/output/safety contract. Factory/profile fingerprint changes
  with context while embedding settings remain unchanged.

Automated providers/accounting are mocked; no real completion in pytest. Existing
google-genai, Starlette/httpx and deprecated422 warnings remain. No frontend code
change or new frontend test run; historical23-pass/typecheck/build/lint evidence
is not mislabeled as current. Frontend git diff --check passes with existing
line-ending warnings. Backend has no Git metadata, so its Git diff check is N/A;
direct edited-file scan found0 trailing-whitespace lines. Semantic core SHA remains
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.

### Exactly one nonpersistent retry / hard stop

Only after tests passed, read the existing blocked CV
ee0b92e2-707f-4d31-b19e-8c9350133a55 through a read-only transaction, copied the
existing uploaded-document source descriptor and closed the session. Invoked the
production factory and CVStructuredExtractionService.extract_uploaded_cv once.
No CandidateCVExtractionService persistence or new extraction row was invoked.
Read-only before/after checks prove CV columns and extraction row count unchanged.
This honors NO DEV DB WRITES; it is not authenticated browser upload E2E.

| Observation | Actual result |
|---|---|
| Workflow attempts | 1 |
| Render-only requests | 2, both200, no completion |
| Generation requests | 2, both200, no transport retry |
| Existing schema corrections | 1, no extra outer attempt |
| Primary prompt/output tokens | 3928/1064 |
| Correction prompt/output tokens | 4054/1914 |
| Both completion reasons | stop, done=true, complete JSON |
| Total elapsed | 101.214831s, within150s |
| Final result | CVExtractionCorrectionError caused by AISchemaValidationError/ValidationError |
| Persistence | none; CV columns/extraction row count unchanged |

Capacity preflight and generation now work at10240. Neither generation hit4608,
neither was reported length-stopped, and no context-shift/truncation fallback was
allowed. Complete JSON is not schema acceptance: the normal existing correction
also failed domain/schema validation. The safe observer retained exception types,
not raw response values or final field diagnostics; this evidence does not identify
the precise rejected field or prove whether the cause is date/identity/other schema.
Do not invent that diagnosis or claim extraction success.

STOP after this single workflow: no further CV, generation, context/output/deadline
increase, prompt rewrite or branch-B experiment. No Qwen call before tests; no
Gemini/BGE, bulk retry, DEV write, migration, frontend edit, raw-source truncation,
benchmark/ground-truth/cache artifact change. No new Markdown or permanent operator
script. Operator exited; shared model residency is intentional, not a task lock.
Existing stored FAILED extraction/UI state remains unchanged because retry was
nonpersistent. Further schema diagnosis requires separately scoped safe validation
evidence, not another unapproved live attempt.

Commands: focused pytest --noconftest -p no:cacheprovider over evaluation/tests,
tests/test_cv_budget.py, deadline/structured/recovery/private tests, tests/ai,
matching/semantic and embeddings; full pytest -B -p no:cacheprovider -q --tb=short
in the guarded test child; read-only /api/version,/api/show,/api/ps,native /props/
tokenize and GPU inventory; one in-memory production extraction workflow;
frontend git diff --check and backend whitespace/hash checks.

**FINAL: CONTEXT CAPACITY VERIFICATION PASS; shared10240/regression PASS.
REAL-CV EXTRACTION NOT PASS: schema validation still fails. One workflow completed,
2 generations including the existing correction,0 DEV writes. STOP honored.**

## Stage Timing Diagnostics

2026-10-09 (Asia/Saigon). Source-read/plan-first review covered document parsing,
service prompt/correction construction, runtime accounting/admission, HTTP/retry
group, response parsing/domain validation, deadline/correction admission and terminal
repository persistence. Request-local ContextVar diagnostics do not store source,
prompt, generated JSON, values, auth or provider error messages.

Implemented document_parse_ms,prompt_build_ms,token_count_ms,preflight_ms,
provider_call_1_ms,json_parse_1_ms,schema_validate_1_ms,correction_build_ms,
provider_call_2_ms,json_parse_2_ms,schema_validate_2_ms,persistence_ms and
total_operation_ms. Unexecuted stages are null. Timers close in finally even on
cancellation; terminal stage distinguishes token accounting/provider/schema from
correction_admission. Total operation covers the AI window, not DB terminal update;
persistence_ms measures terminal commit separately, not initial PROCESSING creation.
Provider HTTP timers and actual retry-group duration are distinguished. Native
render-only/template/tokenization is included in token_count_ms; these are not
completion calls. Prompt timers include existing schema serialization, not a new
prompt. Small unclassified orchestration/envelope overhead means stage sums are
not falsely asserted equal to total operation.

Safe generation metadata includes counts,prompt/eval/total duration_ns,done/known
done_reason,configured output cap,configured/effective provider timeout,elapsed
operation and remaining budget before call,actual provider duration and transport
attempt count. Missing response metadata remains unavailable, not copied from a
previous request. Existing raw-response observer is not enabled by diagnostics.

Structured service retains last_diagnostics in memory; normal persistent flow logs
the same safe summary with extraction_id after terminal persistence. Failure
summaries use WARNING so ordinary application logging exposes them; successful
summaries use INFO. This is log-based observability, NOT a new durable DB diagnostic
column or raw structured checkpoint. Log retention is deployment-owned; restart
loses an in-memory summary. No API/schema/migration/frontend change.

Final full suite **799 passed,3 warnings in180.96s (0:03:00)**, exit0, before the
single live workflow. Existing guarded gjob_db_test only, current_database and
TEST_DATABASE_URL validated, credentials redacted/in-memory. Focused final
**367 passed,2 warnings in9.89s**, exit0. No source edit after the final full run.

One nonpersistent live workflow on d6b04284-1835-4fcc-85a4-1029b1ec17f6:

| Stage | Observed ms |
|---|---:|
| document_parse | 38.902 |
| prompt_build | 5.218 |
| token_count (render/runtime tokenization) | 6546.303 |
| preflight arithmetic | 0.094 |
| provider_call_1 (HTTP stage) | 109496.937 |
| actual provider retry-group duration | 110010.624 |
| JSON/schema1,correction,provider2,JSON/schema2 | null/not_run |
| persistence | null/not_run |
| total AI operation | 116601.388 |

Outer observer lifetime116604.765ms. Small client/orchestration overhead accounts
for HTTP-stage versus retry-group timing; these are not pure inference durations.
Primary starts at elapsed6590.745ms,remaining143409.252ms; configured/effective
provider timeout110000ms. No stale response metrics:eval_count,eval_duration,
done_reason and JSON/schema result are unavailable because no response completed.
The failure is CVAIProviderTimeoutError→AITimeoutError→TimeoutError/CancelledError,
terminal_stage=provider_call_1_ms; NOT a measured150s total-deadline expiration.
Provider errors do not initiate schema correction. No second generation/workflow.

Exact prompt4444,specials0,reserve4608,safety256,total9308<=10240,headroom932.
One render-only HTTP200 and one generation POST,one transport attempt; no generation
response status was obtained before cancellation. Runtime confirms context10240,
unchanged model digest and size_vram6337719173. No returned-token count is inferred
from timeout or prior speeds. Stage timings prove generation wait dominates this
specific workflow,not document parsing or tokenization.

## Schema Validation Diagnostics

Pydantic summaries retain original error_count and at most50 errors with trusted
schema-key/numeric-index paths and built-in error codes. Unknown extra keys, union
branch names and custom codes become unknown. Input,msg,ctx,url and raw JSON are
excluded. Count/code/path describe structure only; generic value_error does not
prove a particular date/identity rule. Initial and correction summaries are kept
under separate attempt keys; existing correction feedback/prompt is unchanged.

Read-only inspection of the configured DEV DB found extraction
09105b46-5563-4090-b315-77b97626fcdc FAILED/AI_OPERATION_DEADLINE_EXCEEDED,
elapsed wall timestamps95.585556s,no structured payload,no diagnostic column.
Extraction e3b5ea10-7167-41ca-a74b-f23f385ae45d was not found in that DB; no cause
of absence is asserted. No retained backend .log file was found in readable backend
paths; .pytest_cache inventory was permission restricted and is not incident evidence.
The user-supplied correction/schema log establishes failure category, not exact
historical field paths. Diagnostics cannot retroactively recover discarded outputs.
The one authorized current deadline-case workflow did not reach validation, so
there are NO new real schema paths to report. Synthetic initial/correction errors
are test evidence only,not substituted for these real CV errors. No second live
workflow on the schema-failure CV was launched to fill this evidence gap.

## Deadline Contract Review

No timing/cap tuning: context10240,output4608,safety256,total150s,frontend180s,
configured local provider110s and correction minimum60s remain. Outer asyncio
deadline already bounded both generations, preflight, document read and validation.
Added explicit effective provider timeout=min(configured timeout,remaining total)
after preflight. Each existing HTTP retry also receives only the remaining group/
operation window; it cannot reset a110s budget. No extra retry was introduced.
Typed provider timeout remains distinct from total deadline; HTTP/API mappings
AI_CORRECTION_FAILED502 and AI_OPERATION_DEADLINE_EXCEEDED504 are unchanged.

Important: the latter code ALSO covers insufficient correction-admission budget,
not only an elapsed150s cancellation. Thus the historical95.59s record is compatible
with a primary failure leaving fewer than60s, but that cause is NOT proven without
its missing stage/cause data. In-memory current settings do not prove historical
server settings. New correction/terminal-stage fields make this distinction explicit.

## Correction Viability

Current correction needs>=60s before it starts. A primary taking>=90s plus preflight/
document overhead can exhaust that admission window even while total remains<150s.
A legal110s primary leaves<=40s: correction cannot start under this contract.
Even60s admission does not guarantee another4608-token completion. This is a
bounded optional recovery, not a promise of two full-cap generations within150s.

Historical36.8tokens/s implies approximately125.2s to emit4608tokens alone, before
prompt/loading/validation. That speed is not current per-CV measurement or proof
that any particular valid CV requires4608 generated tokens. Prior accepted compact
fixtures and model-formatting lengths cannot be conflated. Final recommendation
will distinguish measured operation from this conditional capacity arithmetic.
The historical10240 workflow produced1064tokens in34.483s and1914tokens in59.104s
(whole provider durations,not eval-only speed). It shows shorter generations can
fit,not that4608tokens plus correction fits. For this new CV,eval_count and native
generation duration are missing,so no speed/worst-case valid-output completion
requirement can be estimated authoritatively. General150s sufficiency classification:
**D — insufficient evidence**. The structural correction-admission limitation is
independently proven; the historical exact failure paths remain unknown.

## Recommendation

**C — separate correction-policy contract review recommended; not implemented.**
Current110s provider allowance and60s correction minimum do not guarantee correction
inside150s even before document/preflight overhead. Review explicit correction-time
reservation or an asynchronous operation as a separate task; do not automatically
reduce correction output/schema/source or enlarge the deadline. This recommendation
addresses internal viability,NOT proof that it fixes the observed primary timeout.

No justified numeric deadline increase can be calculated from this run:it timed
out without a valid completion or eval_count. Therefore neither “150s sufficient
for all valid CVs” nor “increase to an arbitrary300s” is supported. The new measured
blocker is primary provider timeout; original deadline-stage and schema-field
diagnoses are still incomplete. Next evidence should come from the newly instrumented
ordinary flow/log retention,not another automatic diagnostic retry. No claim of
schema-contract cluster or fabricated exact-field diagnosis.

Current tests: focused367passed,2warnings in9.89s. Synthetic tests cover safe stage
timings/null stages,document/persistence separation,WARNING visibility,value/extra-key
redaction,initial2-errors versus different correction1-error,cancellation,concurrent
operation isolation,correction refusal and provider/HTTP-retry remaining-budget math.
An added missing-field fixture initially assumed full_name required; corrected to
a synthetic required schema without changing production validation. No live provider
in pytest. Intermediate full796/798-pass runs preceded the final hook/test set;
they are not labeled final-source full evidence. Existing warnings only.

Files this diagnostic task: new app/ai/extraction_diagnostics.py and
tests/test_extraction_diagnostics.py; instrumentation in Ollama provider,structured
service and persistent service. No frontend/config/model/prompt/schema/identity/date/
chronology change. Explicit remaining-budget timeout capping does not add/reset
retries; existing outer deadline and candidate API taxonomy remain.

Normal failure summaries log safe structural data; there is no new raw response
checkpoint,diagnostic DB column,candidate response field or benchmark metadata.
Budgets/profile fingerprint remain
0b279d2b3e9172c3846abe0c53167e50a87da0d4b1c124db16aedac8e9c819e6.
Instrumentation changes source hashes,not model input semantics; historical
generating profiles/frozen evaluation artifacts are not rewritten/relabelled.

Operator DB reads used SET TRANSACTION READ ONLY/rollback,closed before generation.
Before/after CV-column hash and extraction-row count match; no new extraction record,
confirmation,upload or business mutation. No Gemini/BGE/model fallback,DEV pollution,
migration,bulk retry,context shift,truncation,raw-output log or extra Markdown.
Operator ended; no task-owned batch/lock/script remains. Existing shared services
and valid data/cache were not stopped/deleted. Only this SAME report updated.

Commands: focused pytest --noconftest -p no:cacheprovider over evaluation/tests,
new diagnostics/budget/deadline/AI/structured/recovery/private/matching/semantic/
embedding tests; guarded full python -B -m pytest -p no:cacheprovider -q --tb=short;
read-only incident metadata query; one in-memory instrumented production extraction
workflow; frontend git diff --check and direct backend whitespace/semantic-core
checks. Tests use mocks; no provider call during pytest. Backend Git check N/A
(no Git metadata); direct edited-file whitespace scan0. Frontend checkPASS with
existing line-ending warnings; no frontend test/build rerun because no frontend edit.

**FINAL: diagnostics/regression PASS; historical root-cause completion PARTIAL.
One live workflow,1 generation,0 correction,provider timeout110s,total116.60s,
0 DEV writes. No extraction success or UI/E2E PASS. Hard stop honored.**

## Timeout Contract Realignment

2026-10-09 (Asia/Saigon). Source-read-first review of Settings,factory,structured
service,Ollama provider,candidate extraction-policy endpoint,frontend cvService and
extractionRequestTimeout. Plan: first verify correction capacity,then only if it
fits choose shared timeouts,test all boundaries/full suites and authorize at most
one live operation. The explicit correction-capacity hard stop is reached before
implementation; no timing/model experiment was launched.

### Source-proven correction requirement

The existing correction is full re-extraction from the SAME complete source,
same StructuredCVExtractionResult schema and same provider instance. It appends
existing safe validation feedback,not a date-only/patch-only response. Both calls
set num_predict from the same4608 setting. There is no dedicated correction output
cap or invariant bounding its required output below the primary's. Thus correction
CAN need a near-full structured response. This is a contract risk,not a claim that
the previous specific correction produced4608tokens or that every CV needs that much.
The observed~4088 compact valid JSON maximum is not an upper bound on the model's
formatted completion or this larger unseen CV. Historical generated lengths also
cannot be equated with minimal valid payload size.

### Candidate evaluation

44.49tokens/s and92%GPU are user-supplied runtime evidence,not newly measured in
this task; GPU utilization alone does not certify latency. Assuming this eval rate
stays constant,decode-only arithmetic is:

| Quantity | Seconds |
|---|---:|
|4088tokens /44.49|91.89|
|4608tokens /44.49|103.57|
|130s minus full-cap decode|26.43|
|Two full-cap decode passes|207.15|
|Two full-cap passes +2x6.55s accounting +0.04s document|220.29|
|Two4088-token passes +same preprocessing|196.91|

130s is a plausible PRIMARY candidate with26.43s nominal decode headroom,not a
validated completion guarantee:prompt evaluation,loading,contention,HTTP/retries
and validation still matter.210s/240s correctly gives30s frontend network margin,
but does not solve correction capacity. The220.29s estimate is a scenario using
observed preprocessing,NOT a proposed new deadline or guaranteed minimum for all
requests. Even two full-cap decodes alone leave only2.85s inside210s. Two4088-token
passes could fit the optimistic arithmetic but leave13.09s for unmeasured overhead;
they cannot establish a safe upper bound for both legal4608-token calls.

After a primary that uses130s and initial observed6.59s preprocessing,210s leaves
approximately73.41s. A second6.55s accounting stage would leave66.86s for correction
generation/validation,versus103.57s decode at the unchanged cap/rate. Existing60s
correction minimum could admit this doomed full-cap scenario; merely raising total
to210s without a correction-specific contract is not sufficient realignment.

### Decision / unchanged contract

**STOP under the user's explicit full-cap-correction rule. Candidate NOT applied.**
Keep current provider110s,total150s,frontend policy180s,correction minimum60s,
num_ctx10240,num_predict4608,safety256,model/schema/prompt and bounded retries.
Settings currently caps total at150s;this limit was not expanded. Frontend obtains
total+network margin from authenticated extraction-policy,not a hardcoded timeout;
no frontend change is necessary until a new shared backend contract is authorized.
Exact admission,shift=false,truncate=false and safe failure mappings remain intact.

Next prerequisite: a separately specified dedicated correction response/output
budget with source/schema-semantic preservation and demonstrated feasibility. Do
not arbitrarily lower a full re-extraction's cap:that could reproduce incomplete
JSON/output-budget failures. A targeted correction design may need its own shared
contract;this task does not silently change prompt/schema or implement one. There
is no evidence-backed numeric smaller cap selected here. An alternative policy
would require explicit authorization,not blind deadline growth beyond210s.

### Tests / live calls / safety

No implementation changed,so requested new boundary/full backend/frontend suites
were not run and no new test PASS is claimed. Prior367focused/799full and frontend
results remain historical only. The failed prerequisite prevents the authorized
post-test live phase: **0 new Qwen generations,0 live CV workflows,0 Gemini/BGE,
0 DEV reads/writes in this task**. No bulk retry,configuration edit,profile relabel,
data/cache mutation,migration,frontend change or new Markdown. Only this SAME report
updated. Arithmetic/source review is the current evidence,not live timeout acceptance.

**FINAL: TIMEOUT REALIGNMENT BLOCKED BEFORE IMPLEMENTATION. Full-response correction
has the same4608 cap;130/210/240s is not validated for that contract. STOP honored;
need a dedicated correction-budget decision before changing timeouts or retrying.**

## Correction Architecture Review

2026-10-09 (Asia/Saigon). Reviewed primary instructions/provider,parsed validation
exception,service correction/deadlines,factory/config,persistence API mapping,
diagnostics and current regressions before coding. Current correction:

| Question | Source answer |
|---|---|
|Resends full CV?|Yes,same normalized source|
|Resends invalid JSON?|No;decoded data is discarded by provider schema exception|
|Gets field errors?|Yes,trusted field/index/type feedback|
|Same schema?|Yes,StructuredCVExtractionResult|
|Same cap/timeout?|Yes,4608 and configured110s|
|Same extraction function?|Yes,generate_structured with full extraction prompt|
|In-memory invalid payload possible?|Yes,ephemeral exception/service-local retention;not currently wired|

Plan:selected leaf-patch architecture,retain decoded primary only in memory,
safe errors plus previous object as repair data,dedicated small provider/context
preflight,one repair maximum,copy then full existing-schema validation. Unknown
dates,chronology,parent errors,missing facts or unparseable JSON fail closed;no
full-source fallback. Primary-valid path must bypass all repair overhead.

## Valid Output Token Distribution

Fresh read-only size study over95 existing accepted structured_result fixtures:
min146,median1497,p90 nearest-rank2363,max4083 content tokens. These are minimized
checkpoint payloads,not a guarantee that complete primary outputs have identical
sizes. No accepted item was dropped or regenerated. Installed qwen3:8b's verified
native /tokenize used after same-model path verification,not chars/3 or an unrelated
tokenizer. One synthetic render-only request loaded/rendered the model;0 completion
generations. No values,text,token IDs,model path or raw source copied into diagnostics.

Two bounded synthetic four-patch JSON serialization probes:ASCII89tokens,
non-ASCII141tokens;ASCII example481UTF8bytes. Examples measure serialization size,
not live repair quality. Full-object repair would still need near-primary output;
it was not selected. Existing historical146/1504/2371/4088 measurements remain
historical and are not replaced silently by this fresh fixture distribution.

## Chosen Repair Design

**PATCH design selected;only independent pure engine implemented so far.**
New app/services/cv_json_repair.py defines strict RepairResponse/RepairPatch transport,
candidate generation,untrusted-data repair prompt and deterministic copy/application.
Patch transport is not a new CV extraction schema. StructuredCVExtractionResult
remains the final authoritative schema;pure tests explicitly validate the resulting
full object. No live primary uses this engine yet.

Engine admits1..4 existing leaf errors,each from a known model field and existing
parent. Supported lossless changes:case-insensitive exact enum spelling,singleton
string-list to the same string,and scalar project technologies string to a singleton
list holding that exact string. Backend independently derives the ONLY permitted
value,so a model cannot invent a schema-valid but factually different replacement.
It does not use synonyms,split professional text,guess dates,force null or delete
items. Unsupported/missing/ambiguous/source-dependent cases reject before generation.

## Repair Security Rules

Only exact error paths may change;no root/section/item replacement,unknown keys,
negative/out-of-range/bool/string indexes,path-traversal syntax,duplicate/conflicting
patches,new facts or incomplete patch set. Strict path types,extra=forbid and
deterministic traversal;no eval. Original object remains immutable. Candidate
strings<=64UTF8bytes,no control characters;complete compact permitted patch response
<=768UTF8bytes. These are protocol bounds,NOT heuristic token-admission guards.

Dates/date_consistency are deliberately unsupported without independent evidence.
Required factual fields missing cannot be invented. Chronology/model-level errors
cannot authorize replacing a whole experience. These cases need source-aware
adjudication,not an LLM suggestion accepted solely because it passes Pydantic.
Normal full-object final validation must still reject any remaining error;no
second repair or extraction fallback is planned.

## Repair Token Budget

Candidate1024 output tokens is justified by small bounded patch serialization and
measured89/141-token probes,not assumed adequate for a4k-token full object. A real
model can still waste output/formatting tokens;normal output-cap/complete-JSON guards
must reject such output rather than accept partial JSON. Exact runtime preflight
must include repair object/prompt/schema+1024+safety256 under unchanged10240 context.
Large repair inputs may still fail context admission;no slicing or source resend.
No cap/config has been frozen or activated before integration/regression.

## Repair Timeout Budget

Candidate1024/44.49=23.02s decode. Candidate dedicated provider40s provides16.98s
for prompt/runtime overhead;candidate whole-repair50s allows observed~6.55s accounting
plus40s provider and~3.45s orchestration/validation margin. Throughput is user-supplied
and variable;these are bounded candidates,not completion guarantees. Repair provider
must have max_retries=0,and one operation/one patch response only. None is active.

## Total Deadline Recalculation

With PATCH (not old full re-extraction),candidate primary130s has26.43s headroom
above4608/44.49=103.57s. Primary preprocessing~6.59s +130s +whole repair50s=186.59s;
candidate total210s leaves~23.41s additional margin. Candidate frontend240s preserves
30s network margin through existing extraction-policy. Repair admission must require
at least its whole execution budget;preserving current60s gate would exceed proposed
50s repair window. Exact remaining operation must cap provider request/retry group.

No candidate was applied. Production defaults were restored after the blocked
integration proposal;local .env not edited. Actual provider110/total150/frontend180,
context10240/primary4608/safety256 and primary prompt/schema remain unchanged.

## Tests

Independent patch engine: **25 passed in0.69s**. Focused engine+existing diagnostics/
budget/recovery/providers: **122 passed,1 warning in2.11s**, exit0. Security covers
single/multiple paths,enum equivalence,copy immutability,fact-changing values,
unknown/unauthorized/root/parent/invalid-index/traversal/nested keys,conflicts,
missing facts,dates/chronology,oversized values,path count and full-schema rejection.
Tests are synthetic;0 live providers/DEV DB. Full isolated regression:
**824 passed,3 warnings in115.39s (0:01:55)**, exit0, existing guarded gjob_db_test,
TEST_DATABASE_URL/current_database verified and credentials redacted/in-memory.
This verifies unused engine plus unchanged production,NOT integrated repair flow.

No integrated provider repair/context/timeout/persistence tests are claimed:the
production hook did not pass permission review and was not applied. No frontend
test/typecheck/build/lint rerun because frontend/config behavior remains unchanged.
Existing tests that expect full re-extraction remain historical/current old-flow
tests,not evidence of integrated patch acceptance.

## Optional Live Verification

**0 live repair/primary generations,0 live CV workflows,0 DEV reads/writes.**
Size study used metadata/render/tokenization only. Since production integration
is blocked,post-integration live verification was not started. No bulk retry,
Gemini/BGE,raw data log or new extraction row. Existing evaluation fixtures unchanged.

## Final Decision

**PARTIAL / NOT PASS — integration approval required.** The permission reviewer
rejected a broad rewrite of extraction orchestration/exception flow as too risky
before validation. No indirect execution/write workaround was used. Proposed
integration was not applied;temporary config/factory/provider-hook changes were
restored. Equality check confirms production structured service byte-identical to
its pre-task source;retention hook,repair factory and repair settings are absent.
Only pure engine/tests and this SAME report remain as current work.

Need explicit approval to proceed with a narrow,reviewable primary-invalid hook
and bounded repair helper while preserving primary request/prompt/schema and existing
persistence flow. Then integrated boundary/context/timeout/no-second-repair tests,
full backend regression and at most one synthetic live repair are still required.
The current system STILL has old full re-extraction correction;do not call repair
deployed,completed or measurably cheaper in live use. No new Markdown report.

## Approved Narrow Production Integration

2026-10-09 (Asia/Saigon),explicit user approval supersedes the prior permission blocker.
Source reviewed again before targeted edits. Primary prompt/schema/4608/context10240/
preflight and successful-primary repository path remain unchanged. No global timeout,
frontend,.env,provider model,identity/date/chronology or semantic policy change.

Only parseable schema-invalid primary data can invoke repair. Provider retains
decoded object on the schema exception temporarily;service consumes/clears it and
uses existing sanitized validation diagnostics. Unparseable JSON,primary timeout,
context/output budget,unavailability and operation deadline do not enter repair.
Missing facts/unknown parent paths/chronology/date ambiguity are rejected before
generation. No full-source re-extraction fallback. Legacy correction_only full-source
mode is explicitly disabled;historical evaluation CLI modes requiring it cannot
silently launch another extraction. No evaluation artifact/profile was relabeled.

Added helper cv_patch_repair_service.repair_once using already-tested pure engine.
Repair cap1024,provider40s,whole-execution50s,max_retries0. Arithmetic:
1024/44.49=23.02s +16.98s headroom=40s provider;observed6.55s accounting+40s
provider+3.45s margin=50s execution. Throughput is supplied evidence,not a promise
under concurrent load. Existing admission minimum60s is preserved and must also
cover the execution budget. Provider requests are capped by min(operation remaining,
repair execution remaining,configured provider timeout). ExactRepairCounter forbids
primary's bounded-runtime fallback:without exact accounting,repair does not generate.

Patch schema is a transport contract only;final full StructuredCVExtractionResult
remains authoritative. Copy/application rejects unrelated values/paths and whole
object validates before normal persistence. At most primary+one repair. Raw invalid
payload is neither stored as accepted output nor logged. Primary JSON validation and
safe API mapping remain;repair failures use existing AI_CORRECTION_FAILED502 with
fixed internal reason distinguishing unsupported facts,context,timeout,invalid patch,
output exhaustion and final-schema failure. Operation deadline/admission remains504.

Safe diagnostics include attempted,patch_count,validation_success,reason,duration,
primary/final error summaries and existing per-call token/time metadata. Primary
fields are absent/null where no response exists;no invented token counts. Factory
repair config/fingerprint includes actual1024/40/context/safety through existing
provider identity. Primary profile identity is unchanged by timing config. Source
hashes change with implementation;old generating provenance is not rewritten.

Focused integration/extraction/AI/evaluation/canonical/semantic/embedding regression:
**405 passed,2 warnings in7.36s**, exit0. New tests exercise valid-primary exact prompt
and schema/JSON compatibility,no repair,normal mocked persistence after primary or
repair,one scoped patch,unauthorized/malformed/factual-changing patch,final-schema
rejection,provider/whole-repair timeout,exact-context overflow/accounting unavailable,
deadline admission and primary non-schema failures. No live provider or DEV DB in tests.
Initial focused failures were obsolete full-source correction/JSON-retry expectations
and fixture/message-path assertions;updated for approved semantics without loosening
validators. Full backend regression **845 passed,3 warnings in116.46s (0:01:56)**,
exit0,existing guarded gjob_db_test,TEST_DATABASE_URL/current_database validation,
credentials redacted/in-memory. Full suite passed BEFORE the live case;no production
code changed afterward. No live Qwen/Gemini/BGE in automated tests.

Current changed production scope:provider schema-error retention,new bounded helper,
primary-invalid hook,repair-only config fields and safe diagnostics. Persistence
service itself was not changed this integration. Frontend/tests/build not rerun
because frontend/global timing untouched;git diff --check passes with existing
line-ending warnings. Backend Git metadata absent;no backend Git PASS claimed.

### Single Controlled Live Verification / Hard Stop

After all regressions passed,one workflow used a parseable synthetic primary object
with one enum-case validation error;the service's ordinary primary-invalid branch
invoked the real shared local Qwen patch provider. Primary was an explicit in-memory
fixture,NOT a real primary generation;its prompt/eval token counts and eval duration
are N/A,not fabricated. No uploaded CV/raw source/PII or DB session used. This is
controlled integration verification,NOT browser upload E2E or real-CV quality proof.

| Observation | Actual |
|---|---|
|Primary fixture/validation|1 call,1 schema error|
|Repair attempted|true,once|
|Repair prompt/special/reserved/safety|317/0/1024/256 tokens|
|Exact preflight|required1597<=10240;headroom8643|
|Repair generated tokens|36,far below1024|
|Repair native eval duration|0.912842s|
|Short-output native eval rate|39.4373tokens/s|
|Native prompt eval/total duration|0.295723s/1.2233191s|
|Provider elapsed|1.645727s|
|Token accounting|6.949964s|
|Complete repair helper|8.596533s|
|Operation/observer lifetime|8.602896s/8.603130s|
|Patch count/final full schema|1/PASS;final errors0|
|Provider done reason|stop,done=true|
|Result state|SCHEMA_VALID_IN_MEMORY|
|Persistence/API invocation|NOT_RUN/NOT_RUN,no DB|

Exactly1 render-only request and1 generation HTTP200;0 hidden HTTP retries,0 primary
generations,0 second workflow. Per-call remaining budget is the EFFECTIVE minimum
of outer operation and50s repair window (43.049s before generation),not falsely
reported as the outer150s remainder. Configured/effective provider40s. Short-output
observed39.44tokens/s is not a throughput benchmark or a guaranteed full-cap rate.
1024/39.44~25.97s remains below40s nominal window;no timeout/cap adjustment followed.
Prompt/response/patch values were never printed or persisted. Stop honored after
this success;no second live verification or real CV retry.

### Final Identity / Safety / Commands

Primary fingerprint unchanged:
0b279d2b3e9172c3846abe0c53167e50a87da0d4b1c124db16aedac8e9c819e6.
Repair profile fingerprint (1024/40/context10240/safety256):
71b01c6ed4f7cb32d00e8d893e27ab685ef4429a9cddc1b96b52498950782484.
Semantic-v1 core remains
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.
Direct backend edited-file whitespace scan0. An audit command initially used an
invalid encoding alias and was corrected;it never generated or changed data.
No DEV read/write,extraction record,confirmation,junk,migration,new config file,
frontend edit,cache/ground-truth/frozen artifact modification. Shared Ollama left
running;operator exited,no permanent diagnostic script/task lock or raw copy.
Only this SAME report updated;new helper/test Python modules are implementation,
not extra reports. No other Markdown report created.

Commands: focused python -B -m pytest --noconftest -p no:cacheprovider over repair/
integration/budget/recovery/diagnostics/deadline/structured/provider/evaluation/
matching/semantic/embedding tests;full python -B -m pytest -p no:cacheprovider
-q --tb=short in guarded secret-redacted child;one in-memory budget-guarded synthetic
primary+real repair workflow;read-only identity/whitespace checks;frontend git diff
--check. No source rewrite through indirect tooling or repeated model command.

### Current Limitations / Final Decision

Representation-only support remains intentionally narrow. Missing factual fields,
source/date/chronology ambiguity,parent-section errors,more than4 paths or oversized
values fail safely without model repair;not all schema-invalid CVs are fixable here.
Malformed JSON still fails without generic syntactic repair or full extraction
fallback. Original schema incident paths were not recovered retroactively. Primary
110s timeout/150s total problem remains a separate decision. No global timeout
realignment or general “CV analysis now works” claim. Log retention is still
deployment-owned;diagnostics do not become a new durable raw-payload store.

**PATCH REPAIR INTEGRATION — VERIFIED** for narrow approved semantics and one
controlled live-repair case. Primary/persistence compatibility and full regression
PASS;1 live generation,36output tokens,1 patch,full schemaPASS,0 DEV writes.
No further live attempts or automatic limit increases authorized/executed.

## Pre-14B Regression Audit

2026-10-09 (Asia/Saigon). Read-only CV extraction history audit;STOP after report.
Backend Git metadata is now available. Earlier Git-N/A notes describe prior task
observations,not this audit. No production/config/schema/model/timeout change.

### Baselines / Evidence Boundaries

- Backend9e099b4 (2026-09-14):Task13 CV extraction feature,documented Gemini native
  structured output,owned persistence and synthetic extraction/provider tests.
- Backend82c5840 (2026-09-20):nearest pre-14B baseline,retains Gemini-only extraction
  factory. Domain extraction schema/document parser/prompt match Task13;Gemini
  schema sanitization/retry handling had been hardened during embedding work.
- Backend HEAD eab0d62 (2026-10-06):Task14B commit. Frontend corresponding baselines
  aae5228 (Task13),b85e7bd (pre14B),HEAD1f05ffe (Task14B).
- CURRENT runtime source includes many UNCOMMITTED changes beyond HEAD. Git blame
  marks them Not Committed Yet;no fictitious14C/hardening commit is assigned.

These are feature-working baseline candidates supported by source/docs/tests,NOT
an independently measured known-good10–20s live benchmark. Git contains no matched
same-CV before/after request timings or historical Gemini token counts. The user's
10–20s observation is retained as user evidence,not reconstructed measurement.
Historical .env is ignored/untracked;its actual model/key configuration cannot be
recovered from Git. Committed defaults/examples only were used;no secrets exposed.

### Setting / Behavior Diff

Current column separates committed HEAD from active working source/config.

| Setting / Behavior | Pre-14B82c5840 | Current HEAD → working/config | Performance impact |
|---|---|---|---|
|AI_PROVIDER|Factory supports ONLY Gemini;defaultgemini|HEAD adds Ollama;default stillgemini;test exampleollama;current configollama|Largest execution-environment change;cloud versus local8B decoding|
|Model|Committed default labelgemini-3.8-flash;actual historical .env model unknown|qwen3:8b default/active local config|Historical cloud model/rate not pinned;cannot assume equal latency|
|Thinking|Gemini SDK has no explicit thinking configuration|Qwen think=false from its first HEAD implementation and stillfalse|No evidence of lost think=false switch|
|Request API/payload|Gemini generate_content;application/json/native sanitized schema|Ollama POST/api/chat,system/user messages,streamfalse,format raw schema;working adds shiftfalse/truncatefalse|Different inference backend and constraints path|
|Schema in prompt|Gemini receives schema through config,not appended literal JSON prompt|Ollama includes same schema in format AND literal compact JSON in prompt from HEAD|Extra prompt/context overhead;not a new working-tree duplication bug|
|System prompt chars|1228|HEAD1769;working2788|Completeness then identity/precision instructions increase prompt cost|
|User wrapper/source construction|263 chars excluding full source|Same263;function AST identical in all four revisions|No new CV-text concatenation/multiplication in primary|
|Domain schema compact bytes|6152;8 roots,9defs,46defined properties|HEADidentical6152;working8507,8roots,12defs,57properties|Working +38.3%schema bytes;not a committed14B schema enlargement|
|Date/extra fields|Full date/null|Working date/PartialDate/OpenEndedDate unions and experience date_consistency|Partial-date objects can add output tokens;source fidelity retained|
|Long content limits|Educationdesc5000,experience/projectdesc10000,objective5000;collections100|Same limits;no new larger description cap|No evidence of accidental long-content limit increase|
|num_ctx|No Ollama setting/path|HEAD8192;working10240|Larger KV allocation possible;not direct proof of100s regression|
|num_predict|No explicit provider output cap|HEADno explicit cap;working primary4608,repair1024|Cap is a ceiling,not a target output length|
|Temperature|0.0|0.0|Unchanged|
|Retries/correction|No schema-correction;Gemini transient retries<=2 (<=3attempts)|HEADOllama retries<=1,one generation/no schema-correction;working one bounded leaf patch ifeligible,repair HTTP retries0|Working historical full re-extraction could add latency;current patch no full-source fallback|
|Provider timeout|Gemini default30s per SDK request|HEADOllama90s group;current config110s primary/40s repair|Longer tolerated failure duration,not inherently slower successful inference|
|Total operation timeout|No encompassing operation deadline|HEADnone;working150s incldocument/preflight/validation|Bounds operation;does not force generation to run150s|
|Frontend extraction timeout|b85e7bd120s;earlierTask13 inherited10s Axios default|HEAD120s;working authenticated policy180s|Waiting/failure contract changes,not model generation speed|
|Document preprocessing|PDFsort/whitespace/control cleanup,DOCXparagraph/table traversal,no OCR|Parser/text service/storage/dependency files unchanged;document read now threaded|Measured~0.04s parser does not explain100s|
|Amount of CV source|Entire normalized text once;max200000characters|Same primary full-text once/max200000;repair receives previous object,not CV|No slicing/new duplicated raw CV in primary|
|Expected/generated JSON|Full eight-section Builder-compatible object already present;actual token counts not recorded|Same sections;later Qwen generated outputs up to5266;accepted compact fixtures max4083(Qwen tokenizer)|Cannot prove hundreds→thousands increase on matched CV;tokenizers also differ|

Schema sizes were generated from historical source in isolated in-memory namespaces
using the SAME installed Pydantic engine,then counted as compact UTF8JSON bytes.
They are controlled source-comparison measurements,NOT historical wire captures or
token counts. No model/runtime tokenizer was called in this audit. Main schema file
cv_extraction.py is byte-identical across baseline/HEAD/working;its referenced cv.py
models explain the working schema expansion. User-prompt function AST hash agrees
across Task13/pre14B/HEAD/working:
ebc823bb1b3f5d69f703e5639212e2937dfc4a2644eb9229a1c4ba230f595057.

### Commit Attribution / Specific A–F Answers

A. **Yes at the repository implementation level:**pre14B factory contains only
Gemini and would reject ollama under normal production construction. Actual old
private .env/model and latency cannot be proven. Committed model label is a default,
not a claim that this exact model ID was the working cloud deployment.

B. **Qwen was not yet a production extraction option pre14B.** When introduced,
eab0d62 already sends think=false,stream=false,temp0,num_ctx8192. Working request
still sends think=false;no reasoning-toggle regression identified.

C. **Not in committed14B;yes in later uncommitted models.** Extraction schema
6152bytes remained unchanged from pre14B to HEAD. Current8507bytes results from
partial dates,open-ended dates,source-consistency metadata and identity description.
Rootsections and text length caps did not grow. These working changes have no
identifiable introducing commit;git blame explicitly records uncommitted lines.

D. **Yes:**eab0d62 adds541 system characters (44.1%) for completeness/retaining
items. Working identity/date instructions add another1019;overall1228→2788.
Ollama's literal schema prompt duplication also begins in eab0d62. Added overhead
is real,but the measured local primary generation wait dominates later failures.

E. **Unproven:**no historical paired Gemini completion metrics. Whole structured
CV sections/descriptions existed before14B. Completeness/date precision may enlarge
some outputs,but cannot support a claimed universal hundreds→thousands regression.
At supplied44.49tokens/s,4083tokens take~91.8s and4608~103.6s decode alone;this
explains local-runtime feasibility,not a measured requirement for every CV.

F. **Yes,shared extraction code changed in the matching commit.** eab0d62 adds
OllamaProvider,the shared factory branch,config defaults,Qwen test example and
completeness instructions;also adds Gemini text-mode fallback after provider
failure. It was not isolated to matching/BGE. Whether this was accidental intent
cannot be inferred from Git. The actual .env switch is untracked:the commit enabled
it and its example recommends it,but did NOT change ai_provider default fromGemini.

Additional attribution:
- a1e7f85 (2026-09-10):Gemini factory/default model/30s/max2 retries.
- 9e099b4:CV extraction service/schema/full-source prompt/persistence and tests.
- 82c5840:Gemini sanitization/retry policy and embedding settings;no Qwen generation.
- eab0d62:Qwen generation support/shared selection,prompt literal schema/thinkfalse,
  extra completeness instructions,90s/8192 defaults and Ollama example env.
- Frontend aae5228:extraction endpoint integration;Axios10s inherited.
- Frontend b85e7bd:explicit120s extraction override;unchanged in1f05ffe.
- Current10240/4608/exact preflight/150s/patch repair/180s/partial-date changes:
  **UNCOMMITTED**,not attributable to a Git commit. Prior reports describe their
  task chronology,but are not substitutes for git commit provenance.

### Most Likely Cause / ONE Minimal Fix Recommendation

**Most likely cause:interactive CV extraction now inherits the shared Ollama/Qwen
provider selection instead of its pre14B Gemini-only execution path.** Strong code/
configuration evidence supports this ranking. Local output decoding at~44tokens/s
can itself require~90–104s for large structured responses. Longer prompt/schema and
historical correction amplify some requests but do not establish the main paired
regression independently. Parsing,frontend timeout and missing think=false are not
supported primary causes. An exact causal speed ratio needs matched historical
records;none was manufactured or generated here.

**Recommend ONE narrow routing fix:**give interactive CV extraction its own provider
selection and restore the previously working Gemini route there,without changing
Qwen evaluation/BGE matching/ranking,primary schema or safety contracts. Historical
cloud model identity/credentials and explicit permission to send CV data to Gemini
must be confirmed before activation;do not blindly copy the committed default label,
claim Gemini availability or add silent cloud fallback. This is a recommendation,
NOT implemented/configured/called in this audit. It targets the provider coupling,
not whole-pipeline rollback or arbitrary timeout inflation.

### Safety / Completion

Commands:git log/show/diff/blame/ls-tree/check-ignore scoped to extraction and
frontend extraction timeout;allowlisted example/runtime config reads;in-memory
historical schema/prompt byte/property measurements and source hashes. .env secrets,
CV text,payload values and credentials were never printed. No API/model/tokenizer
calls,DEV reads/writes,migration,uploads,retries,benchmark/scoring or package changes.
No test suite rerun:production code was not changed. Prior845-pass result remains
historical,not a new audit test result. Only this SAME report updated;no new report.
Before/after12 scoped production source hashes match. One initially mistyped expected
hash was corrected in the read-only comparison;the source itself was unchanged.

**AUDIT COMPLETE / STOP.** Most-likely regression identified with provenance;
historical10–20s and exact model/token growth remain explicitly unverified.

# CV Extraction Output Inflation Attribution

## Historical Qwen Baseline

This section supersedes the Gemini-only inference in the preceding historical
audit. The user's recollection is supported by the original 2026-09-28 Codex
transcript. The exact working tree was not committed that day; it was based on
82c5840 plus uncommitted Ollama patches later captured together in eab0d62.

The final successful smoke run used qwen3:8b through Ollama,stream=false,
think=false,temperature0,num_ctx8192 and full Pydantic validation. The provider
sent the compact JSON schema both as native `format` and as literal user-prompt
text. It had no explicit num_predict. The three synthetic fixtures recorded:

| Fixture | Prompt tokens | Output tokens | Wall time | Extracted shape |
|---|---:|---:|---:|---|
|Short Vietnamese|2137|263|12.29s|1 education,1 experience,3 skills,1 language|
|Long Vietnamese|2351|654|17.63s|1 education,2 experiences,9 skills,2 projects,1 certificate,2 languages|
|Bilingual|2175|428|12.10s|1 education,1 experience,6 skills,1 project,2 languages|

The transcript retains aggregate metrics and section counts,not response JSON.
Therefore historical section-level token attribution cannot be reconstructed.
No historical accepted payload was found in Git. These are also not the same
files as the later95-CV evaluation corpus or the user's current upload.

## Current Contract

Current primary extraction still uses qwen3:8b,stream=false,think=false,
temperature0 and one full-source request. num_ctx10240,num_predict4608 and the
separate bounded patch repair are current uncommitted hardening changes. Installed
model metadata is Qwen3 8.2B/Q4_K_M,digest
500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41.
The historical digest/runtime build was not recorded,so exact weight identity is
not provable; no request-setting evidence points to thinking,streaming or
temperature as the regression.

Current real prompts are approximately3928–4444 tokens. The known current
completions include1064 and1914 tokens;another request was still incomplete at
3439 tokens when its provider window expired. The older pre-hardening >6000-token
observation is retained as incident evidence,not a schema-valid output size.

Adding num_predict4608 did **not** instruct the model to produce4608 tokens. It is
only a maximum/reservation. Successful calls stopped normally below the cap,while
the3439-token request timed out below it. Native structured `format`,normal EOS,
and stop validation remain;there is no evidence of a cap-driven stop regression.

## Schema Growth

The eight top-level properties and their array sections are unchanged and all
remain optional/defaulted. Compact provider schema growth is exact:

| Shape | Known-good Qwen | Current | Delta |
|---|---:|---:|---:|
|UTF-8 bytes|6152|8507|+2355 (+38.3%)|
|Qwen tokens|1592|2185|+593 (+37.2%)|
|Definitions|9|12|+3|
|Defined properties|46|57|+11|
|Top-level required fields|0|0|0|
|Required fields across definitions|7|13|+6|

Exact additions are:

| Path/object | Type / required | Repetition and output effect | Provenance/reason |
|---|---|---|---|
|`PartialDate`|object:year(required),month,day,precision(required)|Used by eight date slots;object form can repeat twice per dated education/experience/project/certificate|Uncommitted date-precision work;preserves partial source dates without invented month/day|
|`OpenEndedDate`|object:`state` required|Alternative for the same eight slots|Uncommitted date work;preserves Current/Present|
|`SourceDateConsistency`|five-property object;three required|Optional `experiences[].date_consistency`,so schema cost can multiply by experience count|Uncommitted source-conflict work;internal evidence only|
|`experiences[].date_consistency`|optional object|null/default per experience if serialized|Uncommitted source-conflict work|
|`personal_info.full_name` description|same optional string field|No new output field;prompt/schema input only|Uncommitted identity/privacy hardening|

The new definitions account for all eleven added properties:4+1+5 properties
plus the one optional experience property. No achievements,responsibilities,
highlights,notes or identity-metadata output fields were added. Existing arbitrary
text maxima are unchanged:objective5000,education description5000,and experience/
project description10000 characters.

Repeated-array multiplier is material even without new prose fields. The current
accepted corpus has median5 experiences and31 skills (max14 and100). One emitted
`level:null` per skill and three date/default fields per experience therefore
repeat dozens of times. By contrast,the known-good smoke cases had only1–2
experiences and3–9 skills.

Date fields changed from full `date|null` to `date|PartialDate|OpenEndedDate` in
education start/end,experience start/end,project start/end and certificate issue/
expiration. Across95 accepted fixtures there are94 partial-date objects,but they
occur in only6 records. Relative to the old partial-date-as-null behavior,their
aggregate extra cost is1698 tokens:median/p90 across all records0,max324,mean17.9.
Thus date fidelity is significant for a few records but is not the typical output
inflation leader. Removing null month/day keys from those objects would save about
95 tokens on average among records that contain partial dates,but that is not a
proposed production change.

Chronology is predominantly validation-only. The prompt forbids AI-generated
`date_consistency`,and the pre-validator strips it. One final benchmark record has
one source-grounded consistency object added by deterministic recovery (111 tokens);
it is not evidence that Qwen routinely generates chronology metadata. Identity
hardening adds prompt/schema input only and no output object;personal-information
fields themselves predate Qwen.

## Prompt Growth

The known-good Qwen system instruction was1769 characters/343 Qwen tokens. The
current instruction is3521 characters/747 tokens. The empty user wrapper remains
exactly263 characters/55 tokens. With one compact schema copy,the fixed message
content rises from1990 to2987 tokens:about+997 tokens before CV text and chat
template overhead.

Important instruction attribution:

- **Output expansion:** eab0d62 says `Do not omit an explicitly stated education,
  experience, skill, project, certificate, or language...` and `Completeness is
  required... each explicitly listed skill to its own skills item.` Current text
  additionally says partial dates are valid and must not be discarded or forced
  to null. These rules increase item count and repeated object/default emission.
- **Free-text expansion:** both historical and current prompts say `Preserve the
  source language and wording; only normalize insignificant whitespace.` Combined
  with complete work-history extraction,this copies long experience prose rather
  than summarizing it. This is the largest output-bearing instruction,but it was
  already present in the known-good smoke baseline;larger real sources expose its
  cost.
- **Input overhead only:** the long full-name exclusions,date examples,mixed-
  precision explanation and internal `date_consistency` warning enlarge prompt/
  prefill but do not create normal output fields.
- **Validation/safety:** prompt-injection boundaries,no inference,no fabricated
  dates,chronology/current constraints and full-name privacy constraints should
  not be blamed as generated prose.
- **Duplication risk:** there is no instruction to emit separate responsibilities,
  achievements or highlights,and no such fields exist. Repeated skill emission is
  the practical duplication risk.

The full schema is still sent in native `format` **and** appended literally to the
user message,as it was in the final historical Qwen smoke. Therefore this is not a
new output regression,but the larger current schema adds593 input tokens. Current
schema titles,descriptions,defaults and examples cost591 tokens;removing those
metadata would leave1594 schema tokens. Excluding the provider-irrelevant internal
consistency definition/property as well would save another152. These are input-
only opportunities and are not the selected output optimization.

## Output Token Distribution

The current frozen accepted corpus contains95/95 structured results. Counts below
use the exact installed Qwen tokenizer against compact JSON and disclose no field
values:

| Measure | Count | Min | Median | P75 | P90 | Max |
|---|---:|---:|---:|---:|---:|---:|
|Compact accepted payload tokens|95|146|1497|1973|2360|4083|
|Original generation `eval_count`|95|102|1859|2478|3049|5266|
|Compact payload UTF-8 bytes|95|614|7223|9583|11988|18783|

Generation counts and compact artifact counts are not interchangeable. The
provider output may contain JSON whitespace,and evaluation artifacts minimize
personal information;raw accepted responses were not retained for all95. The
count difference must not be labeled purely as removable formatting.

Recursively omitting nulls and empty arrays/objects from the accepted structures
produces compact sizes min80,median1299,p902212,max4014. The exact per-record
null/empty overhead is min66,median153,p90371,max525. Across the corpus there are
3844 explicit null fields and249 empty arrays. Both old and current top-level
schemas have zero required fields;the historical and current prompts nevertheless
explicitly demand null for absent singulars and `[]` for absent collections.

The evidence does not support a universal263–654 to1000–4000 contract-only jump.
Historical fixtures were short synthetic CVs;current fixtures contain far more
repeated items. Fixed contract input grew substantially,but output also scales with
source/cardinality. No same-file before/after result exists,so the two effects
cannot be separated into a causal percentage without a new generation experiment.

## Section Token Attribution

Each row was serialized per top-level section and tokenized with the same Qwen
tokenizer. Fragment punctuation means section tokens are attribution measures,
not values that must sum exactly to the whole payload.

| Section | Min | Median | P90 | Max | Median share of row |
|---|---:|---:|---:|---:|---:|
|Personal info|47|47|47|47|3.1%|
|Objective|7|52|128|384|3.9%|
|Education|5|110|233|362|7.1%|
|Experience|5|903|1526|1897|59.1%|
|Skills|4|324|726|2425|20.0%|
|Projects|4|4|4|661|0.3%|
|Certificates|5|5|131|355|0.4%|
|Languages|4|4|15|128|0.3%|

Within experience,the median projected description content is717 tokens;company/
position core is67 and date/current structure140. Experience prose is therefore
the single largest current contributor. Within skills,names cost median167 tokens
and repeated level/default objects130. Education description is only8 median;
its core/date projections are46/50. Projects,certificates and languages are sparse
for most rows and are not typical drivers.

## Duplication Findings

No raw text was printed. Normalized hashes/word sets were compared only in memory.
Across95 accepted outputs:

-5 records contain at least one exact repeated objective/education/experience/
  project description;11 exact duplicate pairs total.
-2 records contain a description pair with word-set Jaccard overlap>=0.8 and at
  least5 unique words;4 such pairs total. This is not a systemic responsibilities/
  achievements duplication pattern because those fields do not exist.
-8 records contain exact duplicate normalized skill names;165 redundant skill
  items total. This explains some high-skill outliers but not the median record.
-No record has an exact normalized overlap between `skills[].name` and
  `projects[].technologies` in this privacy-minimized corpus.

## Commit Attribution

| Rankable change | Commit/task | File(s) | Attribution |
|---|---|---|---|
|Base eight-section schema,long descriptions,null/empty policy|9e099b4,Task13 AI CV extraction|schemas/cv.py,schemas/cv_extraction.py,prompt|Created the fundamental full structured output;already present before Qwen smoke|
|Local Qwen path,literal schema copy,completeness/every-skill wording|82c5840 working tree on2026-09-28;later committed inside eab0d62 Task14B|ai/ollama_provider.py,ai/cv_extraction_prompt.py,config/factory|Exact known-good Qwen baseline already includes these;completeness multiplies real item counts|
|Partial/open-ended dates and source consistency|UNCOMMITTED after eab0d62;task chronology in canonical/date recovery reports|schemas/partial_date.py,source_date_consistency.py,cv.py|+3defs/+11props;large only for6 date-rich fixtures|
|Identity/full-name prompt and schema description|UNCOMMITTED after eab0d62|schemas/cv.py,ai/cv_extraction_prompt.py|Prompt/schema input overhead;no new output field|
|10240/4608/exact preflight/separate patch repair|UNCOMMITTED hardening|config,ollama provider,structured service|Capacity/safety/repair bounds;does not force long primary output|

Because the September28 state was uncommitted,no hash is falsely assigned to that
exact smoke run. eab0d62 is the first commit containing its Qwen implementation,
but its October6 Task14B label does not mean every included change originated on
October6.

## Ranked Inflation Sources

1. **Real-source cardinality plus source-faithful experience prose.** Current
   median is5 experiences versus1–2 in smoke;experience consumes median903 tokens/
   59.1%,of which descriptions account for717. This is the largest contributor.
2. **Skills cardinality and repeated object/default shape.** Current median31
   skills versus3–9 in smoke;skills consume324 tokens/20.0%. Exact duplicate skills
   create severe outliers in8 records.
3. **Explicit null/empty/default skeletons.** They cost median153,p90371,max525
   tokens and multiply inside arrays. This behavior predates Qwen but becomes much
   more expensive when current outputs contain more items.
4. **Partial-date richness.** It adds mean17.9 tokens across all records but up to
   324 in one date-rich record. It is not a median-case cause.
5. **Larger prompt/schema metadata.** About+997 fixed input tokens versus known-good
   Qwen;it explains prefill/context growth,not thousands of generated tokens.
   Exact token counting's observed~5.5s is separate overhead,not the >100s decode.

The model/runtime is therefore not the primary supported explanation. The strongest
evidence is output shape/source complexity,amplified by completeness/fidelity and
default-heavy JSON. Runtime equivalence is not absolute because the historical
digest was not captured,but think/stream/temperature/model tag are aligned.

## Latency Impact

Pure decode estimates from the measured32.59–44.49tokens/s range:

| Output tokens | At44.49tok/s | At32.59tok/s |
|---:|---:|---:|
|500|11.2s|15.3s|
|1000|22.5s|30.7s|
|1200|27.0s|36.8s|
|2000|45.0s|61.4s|
|4000|89.9s|122.7s|
|4608 cap|103.6s|141.4s|

The accepted generation median1859 implies about41.8–57.0s of decoding before
prefill/token accounting/validation. A4000-token response alone explains roughly
90–123s. The separately observed exact preflight cost around5.5s is real but cannot
explain the main >100s regression.

## Minimal Fix Recommendation

Recommend exactly one direction: **introduce a sparse,minified provider-facing
serialization contract while retaining the same final Pydantic domain model and
validation.** Optional absent/default fields should be omittable on the wire and
restored by Pydantic defaults after parsing;the response should be compact JSON.
Do not remove sections,truncate source prose,relax validation,date precision,
identity safety or chronology rules.

This directly targets measured non-semantic expansion. On retained accepted
structures,sparse compact JSON has median1299 tokens versus1497 compact full-shape,
with exact per-row savings median153 and up to525 from absent/default values alone.
Raw-response whitespace savings cannot be asserted because all raw responses were
not retained. At1299 tokens,decode is approximately29.2–39.9s rather than the
41.8–57.0s implied by the current1859-token generation median,plus unchanged
preflight/validation time.

A realistic no-information-loss target is therefore about1200–1400 tokens for the
median current corpus,not a blind654-token ceiling. Short CVs can still fit700–1200;
the current p90 sparse payload is2212 and max4014,so forcing every complete real CV
into700–1200 would require dropping or summarizing professional prose and would
violate the current source-wording/completeness contract. Removing the duplicate
literal schema or metadata could separately reduce input overhead,but is not the
one output optimization recommended here.

## Limitations

- Exact September28 source was reconstructed from transcript patches and aggregate
  output lines;it was not a commit. Later eab0d62 is only the first committed copy.
- Historical raw outputs are unavailable,so no historical section token table,
  bytes,duplicate analysis or same-file current comparison is fabricated.
- Current section attribution uses accepted privacy-minimized benchmark structures;
  original generation eval counts are reported separately. Identity content is not
  recoverable from these public artifacts and was not sought in private raw data.
- Current accepted fixtures differ materially from the three synthetic smoke cases.
  Source complexity and contract changes cannot be assigned exact causal shares.
- Schema metadata savings are exact tokenizer counts but input-only estimates;
  no request tested their effect. The sparse-output target is an artifact replay,
  not a live generation result.

No production/config/schema/prompt/timeout/context/model change,no tests,no DEV DB
access/write and no completion generation occurred. One render-only request loaded
the installed model solely to expose its exact native tokenizer;all subsequent
calls were tokenization-only and emitted aggregate counts. Temporary historical
schema archives were validated and safely removed. Only this existing report was
updated.

**ATTRIBUTION PASS / STOP.** Output growth is dominated by complete experience prose
and much larger repeated-section cardinality,then skills/default-heavy JSON. Dates
and identity are secondary;num_predict is a cap,not the cause. The one recommended
next experiment is a sparse,minified provider serialization contract,not another
timeout increase,provider switch or schema loosening.

# Sparse Provider Contract

## Design

**IMPLEMENTATION / CORPUS / REGRESSION VERIFIED, 2026-10-10 (Asia/Saigon).**
The extraction boundary now separates `CVExtractionProviderResponse`, a typed sparse
wire model, from the unchanged downstream `StructuredCVExtractionResult`. Ollama's
native `format` and literal prompt schema use the wire schema. A provider result is
wire-validated, deterministically expanded through Pydantic defaults, then validated
again by the full canonical model before the existing persistence/downstream path.

The wire item models copy the canonical field annotations, constraints, enums and
required fields. Their JSON Schema removes titles, descriptions, examples and
defaults only; object/list shape, `additionalProperties=false`, max lengths,
nullability and date structure remain. Internal source-verified `date_consistency`
is absent from the provider schema and rejected on the provider path. A separate
context-required artifact replay helper exists only so the one already-frozen,
source-proven chronology conflict can participate in the 95-artifact invariant.
It does not let Qwen self-authorize internal metadata.

No canonical model field/schema, persistence schema, frontend response, model,
context, output cap, safety margin, timeout or repair budget changed. Config remains
qwen3:8b,think=false,stream=false,temperature0,num_ctx10240,num_predict4608;
patch repair remains1024 tokens/40s provider/50s execution. No array/string cap,
summarizer,source truncation or alternate provider was added.

## Omission Rules

Wire serialization omits only values already equivalent under canonical defaults:

- optional `None` text/date/contact fields;
- empty top-level collections and empty optional nested `personal_info`;
- repeated-item optional/default values such as `is_current=false`, absent level,
  absent description and empty project technologies;
- absent partial-date components, while retaining `precision` and every populated
  year/month/day component.

Prompt wording now requests compact JSON and omission of absent/default values,
including an absent `full_name`, rather than explicit null/empty skeletons. Required
facts remain required: education school, experience company+position, skill name,
project name, certificate name and language name cannot be invented or restored.
Blank optional objective already canonicalizes to `None`; nonblank strings and every
populated value stay on wire. Missing and null are collapsed only where the canonical
default makes them equivalent. Internal proof metadata and required factual fields
are explicit exceptions.

## Canonical Normalization

The normalization is pure and has no DB/model access:

```text
sparse JSON -> CVExtractionProviderResponse validation
            -> default restoration/model dump
            -> StructuredCVExtractionResult validation
```

Canonical revalidation remains authoritative for chronology,partial-date precision,
identity/privacy string validation,required facts and extra-field rejection. The
canonical schema file is unchanged relative to the repository; an unrelated dirty-
tree pre-validator that stripped verified metadata/nulled reversed dates was removed
during regression triage because it contradicted four existing source/date tests.
That restoration leaves source-grounded conflicts proof-bound and ordinary reversed
provider dates invalid, rather than weakening chronology.

## Round-Trip Results

All **95/95** accepted frozen structured artifacts passed:

```text
canonical -> sparse serialization -> wire validation/default restoration
          -> canonical validation -> exact canonical JSON equality
```

For every artifact,experience/education/project/skill/certificate/language counts,
all populated strings,all dates and all factual values were byte-for-value equal
after normalization. No experience,skill,description or project was removed or
shortened. The one source chronology-conflict artifact replayed through its original
source evidence and verified validation context; the normal provider path still
rejects the same internal metadata without proof. No frozen artifact was rewritten.

## Token Savings

Counts use the installed qwen3:8b native runtime `/tokenize` path with
`add_special=false`; no character estimate and no generation was used for corpus
measurement.

| Measure | Min | Median | P75 | P90 | Max |
|---|---:|---:|---:|---:|---:|
|Current compact canonical tokens|146|1504|1981|2371|4088|
|Sparse provider tokens|80|1272|1748|2183|3974|
|Tokens saved|66|190|298|402|574|
|Percent saved|2.79%|13.85%|19.78%|25.12%|45.21%|

The actual median1272 is inside the evidence-based1200–1400 target. Provider-schema
tokens fall from2185 canonical to1524 wire:661 tokens/30.25% input-schema savings.
At the measured32.59–44.49tok/s range,compact-payload decode arithmetic changes from
about33.81–46.15s to28.59–39.03s, a supported median saving of about5.22–7.12s.
This is token arithmetic only,not a claim about total wall time,prefill or raw-output
whitespace. Historical generation median1859 remains a separate runtime measure.

## Section Savings

Per-section medians use independently tokenized `{section:value}` fragments,so they
are attribution measures and need not sum to the whole-row median.

| Section | Current median | Sparse median | Median reduction |
|---|---:|---:|---:|
|personal_info|47|1|46|
|career_objective|52|52|0|
|educations|110|84|26|
|experiences|906|886|20|
|skills|324|189|135|
|projects|4|1|3|
|certificates|5|1|4|
|languages|4|1|3|

The largest median structural saving is repeated optional/default skill metadata;
experiences remain large because their populated source-faithful descriptions are
real content and deliberately preserved. Empty common sections collapse to omission.

## Patch Repair Compatibility

Valid sparse primary output returns after wire+canonical validation with no repair.
Parseable invalid output retains the existing ephemeral payload flow; bounded patch
repair operates on that sparse object, applies only authorized representation patches,
then runs the same wire normalization and full canonical validation. Missing factual
fields,unknown enums,unsupported structural errors,context/output/time failures and
unsafe patches retain their typed failure behavior. There is still at most one
1024-token patch request; no full-source correction or additional retry was added.

## Tests

- Final focused AI/provider/extraction/deadline/diagnostics/sparse/repair/identity/
  partial-date/source-consistency/private-recovery regression:
  **225 passed,1 warning in2.77s**,exit0.
- Final full backend: **853 passed,3 warnings in195.01s (0:03:15)**,exit0.
  `TEST_DATABASE_URL` was supplied only to the child process; conftest verified the
  `*_test` identity and `current_database()` before fixtures. No DEV fallback/write.
- Corpus audit: **95/95 exact round-trips**,same-model native tokenizer; one
  render-only load plus tokenization-only requests,no completion generation.
- Automated tests use mocks and made no Qwen/Gemini/BGE call. Existing google-genai,
  Starlette/httpx and deprecated422 warnings only.

New focused coverage includes optional-null/empty-list/nested-empty omission,
populated-field/count preservation,required-field failure,partial-date precision,
schema constraint/minification/internal-metadata rejection,valid-primary no repair,
invalid sparse patch repair and source-verified artifact-only replay.

## Optional Live Verification

One in-memory operator workflow was launched only after the first full853-pass run,
using an existing median-sized corpus source and the production Qwen factory/service;
it had no DB/persistence path. The chat/tool session was interrupted after launch and
its terminal JSON was not recoverable. Retained filtered Ollama logs prove a200
render-only `/api/chat` but do not prove a completion request/result or canonical
success. The live budget is therefore conservatively treated as consumed once;
**no second workflow/model retry was made and no live PASS is claimed.** Optional live
evidence is not substituted for the complete95-artifact round-trip/token audit.

No task operator remains. Temporary `.tmp_sparse_audit.py`,`.tmp_sparse_live.py` and
its task-owned pyc were removed. No DEV record,extraction row,cache,ground truth,
frontend file or frozen artifact was created/changed. Existing local model residency
was allowed to expire normally; shared Ollama was not stopped or reconfigured.

## Final Status

**CV EXTRACTION SPARSE PROVIDER CONTRACT — VERIFIED.** Provider output is now typed,
sparse and schema-minified;canonical data and downstream contracts remain complete.
All95 accepted artifacts preserve exact semantics,median output representation drops
1504→1272 tokens,wire schema drops2185→1524 tokens,patch repair remains bounded and
full backend regression passes. No content loss,validation weakening,timeout/model/
context/cap change,DEV DB write or frontend contract change. Optional live success
is explicitly not asserted because its interrupted evidence could not be recovered.

# Timeout Contract Adjustment

## Evidence

**TIMEOUT CONTRACT VERIFIED, 2026-10-10 (Asia/Saigon).** The latest long-CV
evidence had5352 prompt tokens and reached at least3328 generated tokens before the
old request was cancelled at about109 seconds,while total context remained below
10240 and runtime reported no truncation. At the observed31–33tokens/s,allowing the
configured4608-token output cap can require about146 seconds. This is a completion-
reliability adjustment,not a throughput optimization;generation speed is unchanged.

Source tracing confirmed the hierarchy:

```text
CV frontend triggerExtraction
  -> authenticated extraction-policy GET
  -> extraction POST with per-request Axios timeout
  -> CandidateCVExtractionService
  -> one absolute CVStructuredExtractionService deadline
  -> OllamaProvider /api/chat timeout capped by remaining operation budget
```

The old approximately110-second cancellation was owned by `OllamaProvider` around
the awaited `/api/chat` request. The enclosing extraction deadline does not reset
between document parsing,prompt/token accounting,generation,validation and optional
patch repair. Cancellation continues to cancel the awaited HTTP operation;no detached
generation task or automatic second primary generation was introduced. Provider
timeout,operation deadline,context/schema failures and connection failures retain
their distinct typed mappings.

## Previous Timeouts

| Layer | Previous effective local value | Scope |
|---|---:|---|
|Primary Ollama/Qwen provider|110s|Primary structured extraction factory|
|Settings default for primary provider|90s|No environment override|
|Total extraction operation|150s|One absolute parse-through-validation deadline|
|Frontend extraction request|180s|150s operation +30s policy margin|
|Patch repair provider|40s|Separate repair-only provider|
|Patch repair operation|50s|Separate one-pass execution window|

The general Axios default remained10s for ordinary API calls;the extraction POST
already used an explicit timeout returned by the backend policy endpoint.

## New Timeouts

| Layer | Current value | Change |
|---|---:|---|
|Primary Ollama/Qwen provider|165s|local110/default90 ->165|
|Total extraction operation|230s|150 ->230|
|Frontend extraction request|250s|180 ->250|
|Network margin|20s|30 ->20,so230+20=250 exactly|
|Patch repair provider|40s|unchanged|
|Patch repair operation|50s|unchanged|

Ordering is now **165s <230s <250s**. A primary request that uses its full provider
budget leaves65 seconds inside the backend operation for validation,normalization
and the already-bounded repair admission decision. The client retains20 seconds for
response/network overhead. `ExtractionDiagnostics.begin_call` still caps provider
time by the operation time actually remaining;repair still receives its own40s
provider and50s execution limits and never inherits165s.

Unchanged extraction contract:qwen3:8b,think=false,stream=false,temperature0,
num_ctx10240,primary num_predict4608,safety256,sparse provider wire schema,canonical
schema,prompt semantics,context admission,persistence,matching and ranking. Repair
num_predict remains1024 and has max_retries0. No fallback provider,primary retry,
context weakening or output-cap change was added. `AI_PROVIDER_TIMEOUT` and
`AI_OPERATION_DEADLINE_EXCEEDED` remain typed HTTP504 outcomes;timeouts can persist
only a terminal FAILED audit record through the normal API workflow,never a partial
successful extraction payload.

Files changed for this adjustment:

- `app/core/config.py`: primary/operation/margin defaults and operation upper bound.
- `.env`: explicit local165/230/20 contract.
- `.env.test.example` and `README.md`: documented matching contract.
- `tests/test_cv_budget.py`, `tests/test_cv_patch_integration.py` and
  `tests/embeddings/test_embedding_config.py`: timeout/boundary/isolation coverage.
- Frontend `tests/cv-extraction-budget.test.mjs`: policy-driven250000ms assertion.
- This existing report only;no new report file.

No frontend production file changed:`cvService.triggerExtraction` already fetches
the policy and applies `request_timeout_ms` only to the extraction POST. Global Axios
timeout and all unrelated requests remain unchanged.

## Timeout Hierarchy

Mock-clock coverage proves a primary result completing at logical second160 succeeds
and leaves70 seconds of the230-second operation. A provider timeout remains
`CVAIProviderTimeoutError` and does not enter repair. A valid provider response whose
post-generation validation clock reaches231 seconds becomes
`CVExtractionDeadlineError`;the total deadline is not extended. The former repair-
admission fixture now completes primary at second180,leaving50 seconds,which remains
below the60-second correction-minimum guard and therefore does not start repair.

The public candidate policy returns exactly:

```json
{"operation_timeout_ms":230000,"request_timeout_ms":250000}
```

Frontend validation still rejects a policy whose request timeout is less than the
operation deadline plus10 seconds. No numeric250-second timeout is hardcoded into
Axios or unrelated services.

## Tests

- Focused backend provider/extraction/deadline/diagnostics/repair/embedding:
  **167 passed,1 warning in2.06s**,exit0. All provider calls mocked;no live model or DB.
- Full backend:**857 passed,3 warnings in117.15s (0:01:57)**,exit0. The child-process
  `TEST_DATABASE_URL` was derived in memory;existing conftest verified it differs
  from DEV,ends in`_test`,and matches `current_database()` before fixtures.
- Frontend extraction+ranking regression:**23 passed,0 failed in7.86s**.
  TypeScript build-mode PASS,full ESLint PASS,Vite production build PASS with2042
  modules. Existing large aggregate-chunk warning only.
- No automated test slept165 seconds or contacted Qwen/Gemini/BGE. Boundary behavior
  uses logical clocks and synthetic providers.

The first focused run had165 passes/1 failure because an existing repair fixture
encoded the old150-second deadline implicitly(100s elapsed left50s). It was updated
to180s elapsed under230s,again leaving exactly50s and preserving the same guard.
The final focused and full suites then passed;no assertion or runtime safety rule was
weakened.

## Live Verification

Exactly one post-test live workflow used the production Ollama factory and
`CVStructuredExtractionService` on one existing representative uploaded CV. Source
metadata was detached under a read-only transaction;the persistence service/API was
not invoked. Only safe counts,timings and exception types were retained—no raw CV,
provider JSON,identity/contact value or storage path was logged in this report.

| Observation | Result |
|---|---|
|Model/profile|qwen3:8b,num_ctx10240,num_predict4608,timeout165s|
|Prompt tokens|5352|
|Generated tokens|4422|
|Generation rate|30.9461 tokens/s|
|Provider duration|146.2245s|
|Completion|done=true,done_reason=stop|
|Transport attempts|1|
|Repair|not invoked;0 schema retries|
|Total workflow duration|153.4717s(<230s)|
|Timeout|none|
|Context loss|none accepted;provider guards did not report truncation/context shift|
|Final extraction result|FAILED schema/domain validation at experiences[3]|
|Terminal type|CVExtractionCorrectionError;unsupported factual/structural repair|
|DB extraction rows|8 before /8 after;0 writes|

This is positive acceptance evidence for the timeout contract:the primary generation
ran about36 seconds beyond the former110-second limit yet completed normally below
165 seconds. It is deliberately **not** a claim that the CV extracted successfully.
The complete response then failed an independent chronology/domain validator and was
not eligible for representation-only patch repair. Per hard stop,no second live CV,
retry,timeout increase or schema/prompt alteration was attempted.

The temporary nonpersistent operator script was removed. No DEV row,file,cache,
canonical artifact,ground truth or benchmark input was created or changed. Existing
test fixtures cleaned up normally;shared Ollama was not stopped or reconfigured.

## Final Status

**CV EXTRACTION TIMEOUT CONTRACT ADJUSTMENT — VERIFIED.** Primary provider165s,
total operation230s and extraction-client250s are implemented and regression-tested;
repair remains40s/50s and every model/context/output/schema/downstream invariant is
unchanged. The one live primary completed in146.2245s without timeout,proving the
old cancellation regression is resolved for this observed workload. Remaining
limitation:timeout reliability does not increase the approximately30.95tokens/s
throughput and does not resolve independent schema/domain validation failures.

# Source-Grounded Date Reconciliation

## Failure Evidence

Recent complete Qwen responses parsed as JSON and passed the sparse provider shape,
then failed strict canonical chronology at `experiences[3]` or
`certificates[0..2]`. Existing representation-only patch repair correctly rejected
these factual/date errors, so a second model call could not safely repair them.
Source review confirmed that dynamic wire item models carry field shapes but do not
run canonical item chronology validators;therefore a safe insertion point exists
before canonical validation. No chronology validator was changed.

## Architecture

Current extraction order is:

```text
provider JSON parse
-> CVExtractionProviderResponse wire validation
-> reconcile_source_grounded_dates(source_text, wire_payload)
-> exact StructuredCVExtractionResult canonical validation
-> existing representation-only patch repair for unrelated eligible errors
-> existing persistence flow
```

`CVStructuredExtractionService` invokes the pure in-memory resolver immediately
after the provider returns its already wire-validated model and before
`StructuredCVExtractionResult.model_validate`. The resolver returns a deep-copied
payload,private validation proof context and PII-minimized audit records. It can be
replayed deterministically from source text plus a wire payload without Qwen.
No raw provider payload checkpoint was added:the current extraction row does not
retain such a payload by default,and in-request reconciliation is sufficient without
introducing indefinite PII retention.

Existing source-grounding components are reused:partial-date adapters and exact
range/current patterns from `cv_date_evidence`,monotonic role/company/responsibility/
date alignment from `cv_experience_alignment`,and the existing internal verified
source-conflict binding/context from `source_date_consistency`. Provider schema,
public canonical schema and persisted business fields are unchanged.

## Experience Resolution

Only experiences whose provider dates fail chronology are candidates. Mapping is
not by index or company alone:the existing aligner uses position,company,nearby
responsibility text,date evidence and one-to-one source ordering. An unambiguous
explicit range replaces only `start_date`,`end_date` and the derived `is_current`;
year/month/day precision is preserved. `Present`/`Current` becomes the existing
`OpenEndedDate` representation and never a fabricated calendar date.

If the matched source itself is reversed,the dates are retained as source truth and
the pre-existing backend-private `SourceDateConsistency` proof is attached through
validated context;canonical validation accepts only the exact bound proof and marks
chronology unusable. Ambiguous and unmatched mappings raise respectively
`SOURCE_DATE_AMBIGUOUS` and `SOURCE_DATE_UNMATCHED` without mutating input,swapping,
nulling or dropping the record.

## Certificate Resolution

Certificate reconciliation is independent per invalid record. Candidate spans are
selected by certificate name,issuer when present,the local span beginning at that
name and ending before the next certificate anchor,and nearby date expressions.
Identical names with distinct issuers remain isolated. A single grounded date maps
to issue date with no invented expiration;minimal issued/awarded and expires/expiry/
valid-until keywords distinguish issue and expiration;an explicit local range maps
first to issue and second to expiration. `Present` cannot become issue date,and an
open-ended range uses the existing canonical open-ended expiration representation.

Multiple distinct local dates without sufficient semantics are ambiguous. Missing
matching evidence is unmatched. A source range that is itself reversed returns
`SOURCE_DATA_CONFLICT`;certificate chronology is not waived because there is no
existing certificate conflict-proof contract. These cases fail closed. The matcher
currently requires supported evidence at or after the matched certificate name in
its bounded local span;date-before-name or otherwise unsupported layouts remain a
typed limitation rather than a guessed correction.

## Safety Rules

The resolver never calls a model and never implements generic `start > end => swap`.
It never nulls an invalid field merely to pass,never deletes a record,and preserves
all non-date fields byte-for-byte at the payload level. Model,provider,prompt,
`num_ctx=10240`,`num_predict=4608`,safety margin,timeouts,canonical validators,
matching/ranking,frontend contract and persistence semantics are unchanged.

Date paths remain explicitly prohibited from model patch repair. Resolver failures
retain public compatibility through the existing `CVExtractionCorrectionError` /
`AI_CORRECTION_FAILED` mapping while exposing safe internal reason and entity path.
Normal logs contain only reason codes,section names and indices,no date values,
certificate/company names,source text or provider JSON. No new public field exists.

## Diagnostics

Added `source_date_resolution_ms` and a private `date_resolution` summary with status,
reason code,entity path,affected field names,resolver version and source-span hash.
No raw source slice is retained. If exact token counting fails but the verified
bounded runtime fallback succeeds,the handled `token_count_ms` terminal marker is
now cleared. A later canonical or resolver failure therefore reports its actual
stage instead of stale `token_count_ms`.

## Tests

- Resolver matrix:**20 passed,1 warning in1.30s**. It covers explicit and open-ended
  experience ranges,same-company/different-role alignment,source conflict,ambiguous
  and unmatched failures,certificate issue/expiration/range/Present cases,three
  independent certificates,same-name/different-issuer mapping,partial precision,
  no-op/idempotence,no mutation/drop,service call counts,PII-safe diagnostics and
  terminal-stage correction. All providers are synthetic/mocked.
- Focused extraction/date/alignment/source-consistency/canonical/repair/diagnostics:
  **152 passed,1 warning in2.37s**,exit0.
- Offline accepted-artifact audit against the existing Resume.csv source:
  **95/95 canonical CVs validate,0 changed payloads,0 new audit items**. The one
  existing verified experience source conflict remains valid and unchanged.
- Full backend on guarded `gjob_db_test` through `TEST_DATABASE_URL`:
  **877 passed,3 warnings in117.79s (0:01:57)**,exit0. Existing google-genai,
  Starlette/httpx and HTTP422 deprecation warnings only. The initial full-suite
  launcher safely refused the DEV-shaped URL before pytest;the final launcher
  derived only `gjob_db_test`,and repo guards verified database identity.
- Frontend tests were not rerun:no frontend production/schema/error contract changed.

`git diff --check` found one pre-existing blank-line-at-EOF issue in
`app/ai/factory.py`,which was not changed by this reconciliation task. Direct compile
and whitespace checks for the reconciliation files pass. Automated tests made zero
Qwen/Gemini/BGE calls and created no DEV records.

## Optional Live Verification

After all automated tests passed,exactly one nonpersistent workflow used the current
production Qwen factory on the previously failing certificate CV
`a08a8a7d-8d28-44fa-845c-2ed00d82f02d`. Source metadata and extraction-row counts
were read under `SET TRANSACTION READ ONLY`;the persistence/API service was not used.

| Observation | Result |
|---|---|
|Primary Qwen generations|1;one HTTP transport attempt|
|Provider completion|HTTP200 internally;done=true,done_reason=stop|
|Prompt/output tokens|3702 /2602|
|Provider duration|79.1602s|
|Resolver stage|ran once at `certificates[0]`|
|Resolution outcome|`SOURCE_DATE_UNMATCHED`,fail closed|
|Canonical validation|not reached for the unresolved payload|
|AI correction/patch repair|not run;0 second model calls|
|Total workflow duration|86.3724s|
|Public HTTP result|N/A;nonpersistent service workflow,not API retry|
|DEV extraction rows|1 before /1 after;0 writes|

This is not live extraction success. It is correct hard-stop evidence that the
specific source layout cannot currently be mapped with the resolver's supported
certificate span rules. No second CV,model retry,broadened matcher,blind fallback,
timeout/context/schema change or DB persistence followed. The temporary operator
script was removed;no raw source/provider response or contact value was logged or
stored. Existing uploaded files and the one historical failed row were untouched.

## Final Status

**SOURCE-GROUNDED STRUCTURED DATE RECONCILIATION — VERIFIED.** The insertion point,
experience and certificate evidence rules,strict canonical revalidation,typed
ambiguity/conflict behavior,no-model date policy,idempotence,diagnostics and full
regression satisfy the contract. The single live CV produced the explicitly allowed
fail-closed `SOURCE_DATE_UNMATCHED` outcome,so no claim of live extraction success is
made. Remaining limitation:unsupported or date-before-name certificate layouts need
a separately justified deterministic evidence rule;they must not be guessed under
this task.

# Certificate Source Alignment Hardening

## Failure Evidence

The pre-hardening live failure completed one Qwen request normally,parsed JSON and
passed sparse wire validation,then returned `SOURCE_DATE_UNMATCHED` at
`certificates[0]`. Source review—not an assumed model/runtime diagnosis—confirmed
the old certificate matcher flattened all whitespace,found exact tokenized name
anchors,required a supplied issuer inside the candidate window,and built each window
from the certificate name only toward the right for at most256 characters. It could
not consume a date or issuer before the name and had no line/bullet boundary model.

No timeout,context,output or transport setting was implicated. No model/provider,
prompt,public schema,canonical validator,persistence,frontend,matching or ranking
setting changed in this hardening.

## Existing Matcher Limitation

The old flow used `phrase_pattern` for the name but then normalized the entire source
to one whitespace-collapsed string. Candidate spans began at the name anchor and
stopped at the next name anchor or name+256. Therefore layouts such as
`DATE — NAME — ISSUER`,issuer-before-name,and multiline date-before-name could be
unmatched. Exact raw punctuation/case was not required,but logical record boundaries
were unavailable and issuer matching was effectively right-looking.

## Record Boundary Strategy

The hardened matcher performs Unicode NFKC normalization,case folding,horizontal
space collapse and deterministic normalization of common dash characters. Bullet
characters become logical line separators;existing newlines are retained. Certificate
names and issuers still use token-boundary `phrase_pattern` matching,so superficial
case,punctuation,dash and line-split differences are accepted without semantic fuzzy
matching or aliases.

For each provider certificate,the matcher:

1. finds all name anchors from identity text,never provider array position;
2. requires a unique adjacent issuer anchor when that issuer exists in source;
3. permits unique-name matching when the source omits issuer entirely;
4. forms an identity span from name plus an issuer on the same/adjacent logical unit;
5. admits at most two contiguous date/issuer units before or after identity;
6. stops at previous/next certificate anchors and section-local logical boundaries.

A leading date is admitted before the first certificate anchor,or when the current
issuer itself establishes that leading unit. It is not admitted across a previous
certificate anchor. Trailing evidence stops before the next known certificate anchor.
Two certificate names on the same flattened logical line are rejected unless a
bullet/newline has established separate logical units;the matcher does not invent a
delimiter or select a globally nearest date.

## Date-Before-Name Support

Supported deterministic forms now include date-before-name on one line,date on the
immediately preceding local unit,date after name/date after issuer,issuer before or
after name,and bullet/dash/case punctuation variants. Two consecutive records such
as `2022 — Certificate A — Issuer A` and
`2023 — Certificate B — Issuer B` resolve independently. Same-name records require
their distinct local issuer evidence.

Within one accepted record span,the existing evidence parser remains authoritative:
a single date without expiration semantics becomes issue date only;explicit issue
and expiration keywords map independently;an explicit validity range maps issue then
expiration;`Present`/`Current` cannot become issue date. Partial-date precision is
preserved. No expiration is fabricated.

## Ambiguity Rules

Multiple equivalent identity spans,multiple distinct local date mappings,repeated
name without issuer disambiguation,or competing dates between two anchors return
`SOURCE_DATE_AMBIGUOUS`. Evidence outside a record boundary remains
`SOURCE_DATE_UNMATCHED`. The matcher never resolves by nearest date,array order or
arbitrary positional tie-break.

Date reconciliation still never swaps provider dates blindly,nulls an invalid field
without source proof,drops a certificate,weakens chronology validation or invokes a
second model. Input payloads are deep-copied;non-date fields remain unchanged;the
resolver remains idempotent.

## Safe Diagnostics

Failure diagnostics now retain only safe codes and integer counts:

- `detail_reason`: `NO_NAME_ANCHOR`,`NO_ISSUER_ANCHOR`,
  `NO_LOCAL_DATE_EVIDENCE`,`DATE_OUTSIDE_RECORD_BOUNDARY`,
  `IDENTITY_NOT_UNIQUE`,`MULTIPLE_LOCAL_DATE_MAPPINGS` or `UNSUPPORTED_LAYOUT`;
- `name_anchor_count`,`issuer_anchor_count`,`candidate_span_count`;
- `date_before_name_count`,`date_inline_count`,`date_after_name_count`;
- `candidate_date_count`,`ambiguous_candidate_count`,`boundary_rejection_count`.

Successful private audit entries may contain the same counts plus source-span hash.
Logs/API diagnostics contain no certificate name,issuer,actual date,raw source text,
provider JSON or contact value. Public compatibility remains the existing
`CVExtractionCorrectionError`/`AI_CORRECTION_FAILED` mapping.

## Tests

- Certificate boundary plus prior resolver matrix:**44 passed,1 warning in1.25s**.
  Added date-before same/previous line,date-after,inline,issuer order,two consecutive
  records,same-name/different-issuer,cross-boundary rejection,single-date,keywords,
  explicit range,Present,missing evidence,multiple dates,identity ambiguity,unique
  name without issuer,normalization,no-op/idempotence,field preservation,one mocked
  provider call and PII-free diagnostics.
- Focused certificate/date/source-consistency/canonical/extraction/repair/diagnostics:
  **176 passed,1 warning in2.38s**,exit0.
- Offline accepted-artifact audit:**95/95 validate,0 payload changes,0 new audit
  items**. Existing valid certificate layouts and the previously verified experience
  source conflict remain unchanged.
- Full backend on guarded `gjob_db_test` through `TEST_DATABASE_URL`:
  **901 passed,3 warnings in204.98s (0:03:24)**,exit0. Existing google-genai,
  Starlette/httpx and HTTP422 deprecation warnings only. Automated tests made zero
  Qwen/Gemini/BGE calls and did not access DEV DB.
- Frontend was not changed and was not rerun;public API/error compatibility is
  unchanged.

## Optional Live Verification

After all automated tests passed,exactly one nonpersistent workflow used the current
production Qwen factory on CV `a08a8a7d-8d28-44fa-845c-2ed00d82f02d`. Source metadata
and extraction-row counts were read under `SET TRANSACTION READ ONLY`;the persistence
service/API was not invoked.

| Observation | Result |
|---|---|
|Primary Qwen generations|1;one transport attempt|
|Completion|done=true,done_reason=stop;no timeout/context failure|
|Prompt/output tokens|3702 /2602|
|Provider duration|79.8485s|
|Resolver result|`SOURCE_DATE_UNMATCHED`|
|Safe detail|`DATE_OUTSIDE_RECORD_BOUNDARY` at `certificates[0]`|
|Safe matcher counts|name1,issuer0,candidate spans0,boundary rejections1|
|Canonical validation|not reached for unresolved payload|
|Correction/repair|not run;0 second model calls|
|Total workflow duration|91.5021s|
|Public HTTP result|N/A;nonpersistent service workflow|
|DEV extraction rows|2 before /2 after;0 writes|

The new diagnostics prove the remaining source representation has more than one
certificate anchor in the same flattened logical line,with no local issuer anchor
available to establish a unique record boundary. Per hard stop,the matcher rejected
the span before collecting a date. No global/nearest-date fallback,second live retry,
timeout/context change or guessed delimiter followed. This is correct fail-closed
behavior,but it is not live extraction success.

The temporary operator script was removed. No raw CV/provider payload,DEV record,
upload,cache,benchmark or canonical artifact was created,modified or deleted.

## Final Status

**CERTIFICATE SOURCE ALIGNMENT HARDENING — VERIFIED at contract level.** Date-before,
date-after,inline,issuer-order,certificate-local boundary,ambiguity,idempotence and
safe diagnostics are regression-tested without weakening any extraction invariant.
The one live CV remains safely blocked because its flattened same-line multi-anchor
layout lacks a deterministic record delimiter/issuer boundary. Supporting that exact
layout would require separately proven delimiter evidence;it must not be approximated
with global or nearest-date assignment under this task.

# Graceful Omission for Unverified Optional Certificate Dates

## Problem

Under previous strict reconciliation, when certificate identity was verified in source text but optional date fields (`issue_date`, `expiration_date`) could not be source-verified due to document layout anomalies (e.g. `DATE_OUTSIDE_RECORD_BOUNDARY` caused by PDF text flattening multiple certificate anchors into a single logical line without local delimiters), the resolver raised `SOURCE_DATE_UNMATCHED`. This in turn raised `CVExtractionCorrectionError` -> `AI_CORRECTION_FAILED` -> HTTP 502, causing the entire CV extraction to fail solely because an optional date on a valid certificate could not be independently grounded.

## Policy

1. **Factual Grounding Safety**: Unverified dates returned by the provider (Qwen) are NEVER trusted or promoted into canonical fact. No guessing, positional date-swapping, or hallucinated dates.
2. **Optional Date Graceful Omission**: Both `issue_date` and `expiration_date` are optional (`CVDate | None = None`) in canonical `CVCertificateItem`. When certificate identity is accepted and grounded, but one or both optional date fields are unmatched or ambiguous in source text, the unverified field(s) are set to `None`.
3. **Preserve Valid Records**: The certificate record itself is NEVER dropped or filtered out. Its name, organization, credential URLs, and other fields are preserved intact.
4. **Canonical Validation Authoritative**: After field omission, the object undergoes standard canonical Pydantic model validation. Chronology validators (`issue_date <= expiration_date`) remain 100% strict and authoritative.
5. **No AI Retries**: Zero additional model calls, zero patch repair calls, and zero prompt mutations for unverified optional dates.

## Field-Level Omission

Resolution is field-level rather than record-level:
- **Verified issue + Unmatched expiration**: `issue_date` is retained with source-verified value; `expiration_date` becomes `None`.
- **Unmatched issue + Verified expiration**: `issue_date` becomes `None`; `expiration_date` is retained with source-verified value.
- **Both unmatched**: Both become `None`; certificate remains.
- **Ambiguous optional date**: If identity is uniquely matched but local date mapping is ambiguous (e.g. multiple distinct candidate dates without differentiating labels), the ambiguous optional date field is omitted (`None`), avoiding extraction failure while preventing hallucination.
- **Pre-existing valid certificates**: Completely untouched (exact no-op, fully idempotent).

## Strict Cases

Strict fail-closed behavior is strictly preserved for:
- **`SOURCE_DATA_CONFLICT`**: When source text contains verified contradictory chronology (e.g. `issued 2025 expires 2022`), it remains a hard error; conflicts are never silently erased.
- **Unmatched Certificate Identity**: When certificate name has zero anchors in source text (`NO_NAME_ANCHOR`), it remains a hard failure (`SOURCE_DATE_UNMATCHED`). Omission is never used to mask hallucinated records.
- **Ambiguous Identity**: When certificate identity matches multiple anchors without unique issuer resolution (`IDENTITY_NOT_UNIQUE`), it remains a hard failure (`SOURCE_DATE_AMBIGUOUS`).
- **Unsupported Date Patterns**: Patterns such as issued "Present" remain hard failures (`UNSUPPORTED_DATE_PATTERN`).
- **Experience Dates**: Chronology and grounding for `experiences.start_date` and `experiences.end_date` remain completely strict and out-of-scope.

## Diagnostics

Safe, non-PII diagnostics have been added to track omissions:
- `certificate_date_omitted_count`: Total number of optional certificate date fields omitted.
- `issue_date_omitted_count`: Number of unverified/ambiguous `issue_date` fields omitted.
- `expiration_date_omitted_count`: Number of unverified/ambiguous `expiration_date` fields omitted.
- Typed audit reasons: `SOURCE_DATE_UNMATCHED_OMITTED` and `SOURCE_DATE_AMBIGUOUS_OMITTED`.
- Detailed reasons: `DATE_OUTSIDE_RECORD_BOUNDARY`, `NO_LOCAL_DATE_EVIDENCE`, `MULTIPLE_LOCAL_DATE_MAPPINGS`.
- Zero PII leakage: Diagnostics contain only counts, codes, and span hashes; never names, issuers, actual dates, or raw CV prose.

## Tests

1. **Certificate Source Alignment & Resolver Matrix**: **56 passed, 1 warning in 0.27s**
   - Verified single date kept while other omitted (both directions)
   - Verified both dates omitted when unverified
   - Verified ambiguous dates omitted field-level
   - Verified 3-certificate mixed matrix (cert 0 issue omitted, cert 1 expiration omitted, cert 2 fully verified)
   - Verified `SOURCE_DATA_CONFLICT` and unmatched identity remain strict failures
   - Verified idempotence and no-op on valid certificates
   - Verified service extraction succeeds with 0 retries and safe diagnostics
2. **Focused Regression Suite (12 test suites, 195 items)**: **195 passed in 1.38s**
   - Certificate source alignment, reconciliation, consistency, partial dates, JSON repair, sparse wire contract, experience alignment, diagnostics, patch repair integration, extraction deadline, budget hardening.
3. **CV Structured Extraction Suite**: **20 passed in 0.16s**

## 95-Artifact Regression

Offline regression check over the 95 frozen canonical artifacts in `evaluation/data/derived/ranking_canonical_cvs.jsonl`:
- **Total CVs**: 95 / 95 validated.
- **Total Certificates**: 105 / 105 validated.
- **Certificate Changes**: Exactly 0 payload modifications.
- **Idempotence**: 100% stable; already-valid certificates remain untouched.
- `evaluation/tests/test_ranking_canonical.py`: **13 passed in 1.30s**.

## Optional Live Verification

Exactly ONE live verification was performed on the real CV `a08a8a7d-8d28-44fa-845c-2ed00d82f02d` (file `24913648.pdf`, 7,011 characters) that previously failed with `SOURCE_DATE_UNMATCHED: DATE_OUTSIDE_RECORD_BOUNDARY`:
- **Read-only DB Check**: Initial extractions count = 4; final extractions count = 4; exactly 0 DEV DB writes.
- **Primary Qwen Calls**: Exactly 1 call (79.5s provider call, 91.20s total elapsed).
- **Secondary / Correction Calls**: 0 correction calls, 0 patch repair calls (`attempted: False`).
- **Resolver Outcome**: `status = resolved`.
- **Graceful Omission**: All 3 certificates (`CompTIA A+`, `CompTIA Security+`, `STI Certified Help Desk Professional`) were retained with `name` preserved, while unverified dates outside the flattened record boundary were gracefully omitted (`issue_date = None`, `expiration_date = None`).
- **Diagnostics**: `certificate_date_omitted_count = 6`, `issue_date_omitted_count = 3`, `expiration_date_omitted_count = 3`, `detail_reason = DATE_OUTSIDE_RECORD_BOUNDARY`.
- **Canonical Validation**: Succeeded.
- **Result**: Extraction succeeded completely instead of failing with 502!

## Full Backend Regression

Full pytest regression against guarded `gjob_db_test` via `TEST_DATABASE_URL`:
- **Result**: **913 passed, 3 warnings in 118.19s (0:01:58)**.
- **Failures**: 0.
- Zero AI model calls in automated tests; DEV DB untouched.

## Final Status

**GRACEFUL OMISSION FOR UNVERIFIED OPTIONAL CERTIFICATE DATES — VERIFIED.**
The extraction pipeline now safely handles unverified optional certificate dates without sacrificing factual grounding or failing valid CV extractions.

## Frontend Partial-Date Confirmation Contract

### Root Cause / Contract

2026-10-11 (Asia/Saigon). The backend already accepts professional dates as an
exact date,PartialDate or OpenEndedDate. The frontend incorrectly declared those
fields as strings and bound persisted objects to native date inputs. React therefore
coerced them to `[object Object]`;submission then called string-only normalization
and threw locally before Axios. The generic error mapper mislabeled that local
conversion failure as a server connection error. No backend contract defect was
found and no backend source or schema was changed.

Added the frontend CVDateValue union and one adapter boundary for editor display,
display formatting,strict parsing and payload normalization. Professional date
editors accept YYYY,YYYY-MM or YYYY-MM-DD and retain OpenEndedDate as `current`.
Year/month precision is never invented as January1/day1. Invalid values are blocked
before POST with an inline field error;local conversion errors are not classified
as network failures. Date of birth remains the existing exact native date control.
The incumbent layout,sections and confirmation endpoint are unchanged.

### Automated Verification

- Focused date/extraction contract:14 passed,0 failed.
- Complete current frontend suite:32 passed,0 failed in5.20s.
- TypeScript build:PASS;Vite production build:PASS,2043 modules.
- Full ESLint:PASS;git diff --check:PASS with existing line-ending warnings.
- Impeccable changed-target detector:0 findings after the accessible delete-control
  color adjustment. No redesign,new dependency or generated asset.
- Coverage includes all four partial-date precisions,open-ended dates,invalid
  calendar dates,lossless untouched round-trip,SSR without object coercion,exact
  confirmation URL/payload and local-versus-network error taxonomy.

### Actual Browser Confirmation

Used the existing authenticated localhost session and exactly CV
549f31bf-6143-469a-a26d-acca54773045. After reload,the live form had12 professional
text date controls,0 `[object Object]` values and only1 native date input(the exact
date-of-birth field). Visible year-only values such as2022/2026 rendered directly;
browser warning/error log was empty.

Clicked `Lưu thông tin CV` exactly once. The existing POST route
`/api/v1/candidate/cvs/{cv_id}/extractions/{extraction_id}/confirm` uses its default
HTTP200 contract;the live client entered its success branch and displayed
`Thông tin CV đã được cập nhật`. A real page reload retained the same confirmed
state and success timestamp;browser warning/error log remained empty.

Read-only post-check:latest extraction remains
cf7796a7-7b26-40ac-8f8d-0d5326014699,status SUCCEEDED,confirmed=true. All persisted
structured CV fields exactly equal the confirmed extraction payload. No new
extraction row or retry was created. Ranking canonical/cache identity remained
2204da01d61dfaab0e13e288505d87f44ecbc93110053c00dc662f4958d559be and status
ranked before/after;the confirmation background task therefore returned from the
compatible cache before provider creation.0 Gemini,0 Qwen,0 BGE calls and no junk
record. The single confirmation is the user-authorized real CV update,not test data.

Changed frontend files:src/types/cv.ts,new src/utils/cvDate.ts,
src/components/cv/ai/cvReviewDraft.ts,CVAIReviewForm.tsx,CVDocumentView.tsx,
src/utils/apiError.ts,new tests/cv-partial-date.test.mjs,and repaired portable/current
assertions in tests/cv-extraction-contract.test.mjs. Existing unrelated worktree
changes were preserved.

**FINAL: PASS — CV PARTIAL-DATE CONFIRMATION VERIFIED IN THE REAL BROWSER.**
One save,HTTP200 route contract,success UI,persisted payload and reload state verified;
no partial-date coercion,no fake dates,no AI call and no extraction retry.
