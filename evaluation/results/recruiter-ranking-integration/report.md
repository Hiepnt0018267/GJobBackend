# Task 14C.3 Recruiter Applicant Ranking Policy & Integration

## 1. Status

**PASS integration/regression.** AI sorting is opt-in, cache-only, globally ordered
before pagination, with stable snapshot traversal. Full pytest: **680 passed,
3 warnings in112.16s (0:01:52)**, exit0. No deployment or live model call.

## 2. Objective

Optional recruiter decision-support ordering on existing applicant endpoints.
Preserve business eligibility, default behavior, human review and applicant visibility.

## 3. Evidence from Task 14C.2

P@1=0.70; P@3=0.6333; MRR=0.825; NDCG@10=0.8069.
**USEFUL BUT INCONSISTENT:** three of ten jobs had grade0 at Top1; four grade2
candidates were below Top5. Evidence was not rerun or edited here.

## 4. Frozen Production Policy

AI ordering opt-in; default unchanged; no threshold, suitability classification,
auto-hide/reject/shortlist/hire/review/notification. Recruiter makes final decisions.
Missing similarity never means a poor candidate.

## 5. Existing Recruiter Applicant Flow

Read router/service/repository/schemas/tests, application rules, CV/extraction and
recruiter-job lifecycle, readiness repositories, canonical mappers/fingerprints,
embedding factory/profile, pairwise persistence, storage/config and test guard first.
Default SQL order is **created_at DESC,id DESC**. Existing detail, file/photo access
and explicit business actions remain unchanged. Plan was announced before implementation.

## 6. Business-Valid Applicant Definition

Existing owner-scoped Job/Application join and optional status/job/normalized-search
filters define the full logical set. Search retains existing display-field semantics.
No AI eligibility filter or new implicit status exclusion. Matching uses the CV
attached to the application, not the candidate's subsequently selected default CV.

## 7. Authorization

Role dependency and owner filtering precede AI work. Job-specific AI requests use
existing job ownership/404 semantics first. Global list contains only owned jobs.
Snapshot owner binding and repeated current owner/filter queries prevent cross-owner
traversal. Unauthorized-job API test asserts404 and zero ranking/cache/provider work.

## 8. API Sort Contract

Existing GET /api/v1/recruiters/applications and
GET /api/v1/recruiters/jobs/{job_id}/applications accept sort=newest(default) or
**sort=ai_match**. Invalid enum returns422. ai_top_n>=1 and ranking_snapshot are
AI-only; using them with default sort returns422. No parallel list endpoint.

## 9. Production Canonical Matching Input

Exact production mappers. Batched readiness mirrors MatchingInputService: Builder
directly; uploaded confirmed representation copied onto CV authoritative; otherwise
newest successful structured result, ignoring later failures. No usable representation
is UNAVAILABLE, not extraction. Invalid schema/mapping is ERROR, not exclusion.
JD includes production taxonomy projection; recruiter matching does not require
candidate-facing APPROVED status. No eval input/cache or raw-text adapter.

Verified valid canonical source-chronology conflicts receive no ranking penalty;
dates/warnings are not semantic features (synthetic regression). Unverified serialized
conflict flags cannot bypass existing proof/schema requirements. No source fabricated.

## 10. BGE-M3 Profile

Same production factory: Ollama,bge-m3,ctx8192,batch4096,truncate=false,1024 dimensions,
unchanged raw cosine. No truncation/chunking/model/vector transformation.
RANKING_MODEL_DIGEST deployment pin defaults to verified
7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab.
Precompute verifies local tags before/after generation. List performs no network model
discovery; compatible cache identity is bound to the configured deployment pin.

## 11. Precompute Architecture

One-entity best-effort BackgroundTasks after successful CV create/update, uploaded
extraction success/confirmation, and recruiter job create/update. Each owns a fresh
session, builds canonical input, closes DB session before provider work, and precomputes
one entity. No business writes, extraction, application fan-out or distributed queue.
At most one embed request per task at existing timeout; cache hit makes no request.
Failures cannot undo committed lifecycle operations. Old unchanged entities are not
automatically backfilled by GET; operator can invoke the one-entity precompute service.

## 12. Embedding Cache / Invalidation

Existing pairwise rows store scalars/baseline evidence, not vectors or model digest.
Minimal private filesystem cache avoids new DB tables/migrations and eval-cache reuse.
Default root .cache/recruiter-ranking is ignored, not exposed by file/static routes.
Identity includes canonical version/fingerprint, exact semantic-text SHA, shared
profile fingerprint(ctx/batch/truncate/model/provider), model digest and semantic engine.
Change means miss; reuse validates identity, dimension and finite/nonzero vector.
Atomic replacement prevents partial reads; exclusive identity leases suppress duplicate
concurrent lifecycle generations. Crash leases are not automatically stolen.

## 13. Ranking Algorithm

Filter full set first; cached vectors per unique CV/JD; unchanged production cosine;
RANKED first, score DESC; unranked afterward. Only then explicitN/page slice.
No threshold, normalization or status write. Global endpoint compares each application
against its own JD; cross-job cosines are not calibrated suitability measures.

## 14. Tie-Break Policy

Stable sort preserves created_at DESC,id DESC inside exact-score ties and throughout
the non-ranked group. No sensitive/display attribute tie-break. Negative and actual
zero similarities remain valid ranked values, not hidden.

## 15. Ranking Status Semantics

ranked: compatible vectors/finite cosine available.
pending: canonical input exists, current embedding absent.
unavailable: usable canonical representation absent or semantic text empty.
error: schema/mapping/cache/provider failure or inconsistent CV ownership.
These states are distinct from unchanged application business status.

## 16. Missing AI Signal Policy

All remain visible in default fallback order. Non-ranked ai_rank and score are null,
never fake0. Snapshot retains its availability view when precompute completes;
new page1 traversal observes the new signal.

## 17. Default Full-List Policy

No default TopK. Seventeen valid applicants remain17 logically even with page_size5.
Transport paging does not define eligibility or logical count.

## 18. Explicit Result Limit Policy

ai_top_n=N ranks all first, then takes firstN (including visible unranked remainder
if needed). Fewer thanN returns all; no padding. total/total_pages describe this
explicitly requested truncated logical set, not an implicit AI threshold.

## 19. Pagination Semantics

Global sort before slice. Default pages retain existing offset behavior. AI page1
returns ranking_snapshot; page>1 requires token and unchanged page_size/filters/N.
Missing token on later AI pages returns422. Changing sort starts a new traversal.

## 20. Pagination Stability / Snapshot Policy

Random opaque server-side ten-minute snapshot contains IDs/order/ranks/states/scalars,
no source text. Binding hashes owner, filters,N,page_size, application membership/status/
default order, canonical identities and runtime. Availability-only completion preserves
same snapshot order. Changed membership/status/CV/JD/profile, missing/expired snapshot
returns409 with restart guidance, not silent duplicate/skip. Storage failure returns503
with default-sort guidance instead of pretending to guarantee stability. Shared private
storage across deployment workers is required.

## 21. API Response Changes

Additive item fields: ai_rank,ranking_status,semantic_match_score. Additive list field:
ranking_snapshot. Default non-AI fields null. Existing authorized display fields and
human actions retained. No vectors, semantic/raw text or provider internals exposed.

## 22. Raw Score / UI Interpretation Policy

**Raw cosine != percentage/probability.** 0.73 is not73% suitable. Prefer rank/state,
raw scalar hidden by default; optional label 'similarity score'. Decision support only.

## 23. Provider Failure Behavior

List calls no provider. Compatible existing cache remains usable during outage;
failed lifecycle attempt stores safeERROR metadata; cold miss staysPENDING. Applicants
remain visible and statuses unchanged. No cloud fallback or ranking extraction retry.

## 24. Performance / N+1

Default paginated path unchanged. AI eager-loads candidate/job/CV/template, selectin-
loads JD taxonomy, batches uploaded extraction history. No per-applicant DB query.
API regression asserts at most8 SQL queries for17 candidates, including auth/query
work. Warm cost: unique cache reads,Ncosines,O(NlogN) sort. Snapshot continuation
validates current identity without vector lookups/reordering. Full sets are materialized;
no load-test guarantee or arbitrary hidden cap. Logs contain aggregate states/counts/
runtime only, not PII/text/vectors. No cache-hit telemetry count is claimed.

## 25. Privacy

Production professional-field allowlist/shared contact sanitizer exclude intentional
direct identity/contact/photo features. Authorized display fields remain for human
review. Private cache stores hashes/vectors/IDs/metadata, never raw semantic/source text.
OS service-account permissions and non-public root are deployment requirements.
Structural exclusion does not certify arbitrary free-prose PII or fairness.

## 26. Human Review

Every application stays openable; existing review/shortlist/reject/hire remain explicit
recruiter actions. Sorting does not disable actions, change eligibility or notify anyone.

## 27. Tests

Focused synthetic: **17 passed,1 warning in1.45s**. Covers descending/ties/negative/
zero/full17/topN/mixed states, global paging, pending completion without duplicate/skip,
snapshot owner/member/status/source/profile changes, cache reuse/change/corruption/
outage, batched readiness, valid source-conflict canonical, one-entity hooks and session
closure. API regression covers real owner/default/filters/global order/four pages/N,
zero extraction/provider, bounded SQL and unchanged statuses. Offline evaluation:
**149 passed,2 warnings in5.72s**. Providers mocked; caches synthetic/temp only.
Initial new fixture failed by duplicating candidate/job applications; fixed to17 distinct
candidates. Enum serialization warning corrected, not suppressed. Final full suite
includes all latest tests and production changes.

## 28. Full Pytest

**680 passed,3 warnings in112.16s (0:01:52),exit0.** Existing guarded gjob_db_test only,
DEV/test URL guard/current_database check and normal migration fixtures. Credentials
in child memory/redacted output. No live provider. Warnings: existing google-genai,
Starlette/httpx TestClient and deprecatedHTTP422 notice. No schema migration added.

## 29. Manual Sanity

No separate live/DEV sanity needed: synthetic TestClient scenario verifies default/AI/
pending/four-page traversal. No deployment or real applicant extraction was invoked.

## 30. DB Safety / Cleanup

No DEV connection/write, new DB/config, migration, frontend edit or benchmark rerun.
New API test removes only its unique synthetic applications/jobs/CVs/principals in
correct FK order. Three principals from initial failed fixture were verified and removed
from guarded test DB; no real records touched. Temp caches teardown normally. No
production cache generated. Existing unrelated worktree changes preserved.

Frozen hashes unchanged:
ground a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d;
CV 0a7da44fde0cde5f0ff45259093bb7f194cbc40bea502bf02c50bfe66682f615;
JD 9da55f0731adf98c1c7aefe7072759effc04816f6568ddee9caef9f1e14fedc1;
manifest cd715793e5ba37272d7cd1b82847f58e78879b1aaaf2577efab1c520f1ae92b9.
Semantic core 0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf unchanged.

## 31. Known Limitations

Useful but inconsistent;10-job benchmark; opt-in; fairness not evaluated; robustness
pending. Availability depends on precompute/cache. BackgroundTasks is best-effort,
not durable/retrying queue; old entities need lifecycle update/controlled precompute.
Private cache must be shared between deployment workers; no multi-host certification.
Model identity is a deliberate deployment pin, not live discovery on every list.
Expired snapshots removed on access; periodic dedicated-cache retention is operator
responsibility. Crash leases require verified cleanup. Full sets use proportional
memory/disk, without production throughput measurements. Serialized conflict metadata
still requires existing proof-aware validation, not an unchecked chronology bypass.
No live cache warmup or client/proxy timeout behavior during background work measured.

## 32. Frontend Handoff

Small future UI: default existing sort plus explicit AI match. Show rank and ranked/
pending/unavailable/error; raw score hidden, no '% suitable'. Keep all applicants and
human actions. Store snapshot for pages with same filters/page_size/N; clear on sort/
filter changes, restart on409, offer default on503. AI result count distinct from page
size. No frontend implemented here.

## 33. Task 14C.4 Handoff

Audit sensitive/free-prose attributes, group behavior, missingness and ranked-first
availability bias. Structural exclusion is not a fairness conclusion. Do not make AI
default or add thresholds without separate authority.

## 34. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_applicant_ranking.py -q --tb=short
venv\Scripts\python.exe -m pytest tests/test_recruiter_applications.py tests/test_applicant_ranking.py -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

DB commands launched in guarded child environment with existing Docker/test credentials
resolved only in memory. Additional read-only source/git/hash/ignore reviews and exact
task-owned synthetic fixture cleanup. No live BGE/Qwen/Gemini or benchmark runner.

## 35. Final Status

**PASS Task14C.3 backend integration/regression.** Default preserved, AI optional,
cache-first/read-only, full global ordering with stable snapshots and visible missing
signals. One new Markdown report only. Not a deployment/fairness/perfect-ranking claim.

**READY FOR TASK 14C.4 FAIRNESS & SENSITIVE ATTRIBUTE AUDIT**
