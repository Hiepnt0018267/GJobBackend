# Task 15A — Job Recommendation Foundation

## Source Review

Implemented on 2026-10-11 after reviewing the candidate/CV models and repositories,
uploaded-CV confirmation rules, canonical matching builders and fingerprints, public
job filters, application uniqueness/reapply behavior, Semantic-v1, the BGE-M3 file
cache, recruiter ranking snapshots and candidate authorization conventions.

The domain currently has four job statuses: `PENDING`, `APPROVED`, `REJECTED`, and
`CLOSED`; and six application statuses: `SUBMITTED`, `REVIEWING`, `SHORTLISTED`,
`REJECTED`, `HIRED`, and `WITHDRAWN`. There is no expired/archived/deleted job state
to invent. A unique `(candidate_id, job_id)` application constraint means even a
rejected or withdrawn application cannot currently be submitted again.

The read-only development inventory used for capacity planning contained 9 jobs,
all 9 approved, 21 candidates, 33 CVs, and only 3 default CVs. No DEV row was
created, updated, or deleted during implementation or verification.

## CV Selection Policy

One deterministic policy is frozen:

1. An explicit `cv_id` is used only when it belongs to the authenticated candidate.
   Missing and foreign IDs both return ownership-safe 404. If that explicit CV is
   not canonical-ready, it remains the selected CV and returns an unavailable/error
   signal; the service never silently substitutes another CV.
2. Without `cv_id`, candidate CVs are considered in existing default-first order,
   then `updated_at DESC`, then `id DESC`. The first non-empty canonical-ready CV is
   selected. This normally selects the valid default CV and provides a deterministic
   fallback when the default is empty or an uploaded extraction is not usable.
3. Builder CVs use validated persisted structured fields. Uploaded CVs reuse the
   existing rule: candidate-confirmed persisted fields are authoritative; otherwise
   the latest successful structured extraction may be used. Draft/unusable uploads
   are not selected. No valid CV produces `candidate_signal_status=unavailable`.

The final UUID tie-break was added to the existing CV list ordering so equal update
timestamps cannot make fallback selection nondeterministic.

## Provider Boundary

Recommendation does not read or use `AI_PROVIDER`, does not call Gemini/Qwen or
`/api/chat`, and changes no extraction configuration. It reuses the existing Task 14
`RankingCache`, whose runtime identity is the frozen `EMBEDDING_PROVIDER=ollama`,
`EMBEDDING_MODEL=bge-m3`, context/batch profile, pinned model digest, canonical
version, and `semantic-v1` engine. No provider/model/profile setting changed.

## Candidate Signal Contract

Scoring reuses `CanonicalCVMatchingInput.semantic_text` exactly. Included professional
signals are career objective, normalized skills, experience role/description,
education degree/field/description, project name/role/description, certificate name,
and languages. Existing fingerprint inputs also bind normalized CV skills and project
technologies.

Excluded from semantic text and reasons are name, email, phone, date of birth, photo,
address/location, URLs, gender/demographics, contact identifiers and user/CV IDs.
No explicit candidate preference model exists, so location, work mode and employment
type are request filters only, not inferred preferences or personalized features.
Candidate/CV IDs are authorization and snapshot identity only.

## Eligible Job Pool

The recommendation pool reuses the same filter builder as public job search. It
contains all matching `APPROVED` jobs and excludes `PENDING`, `REJECTED`, and `CLOSED`.
The supported filters are search/keyword, location, employment type, experience
level, industry, experience requirement, level, work mode, salary type/range and
normalized exact skill. Normal public browsing remains independent and unchanged.

There is no pre-ranking result cap. The repository fetches the complete filtered
eligible pool, eager-loads taxonomy skills in a bounded second query, and only then
ranks and paginates.

## Applied Job Policy

Any existing `JobApplication` excludes the job. Exact status policy:

| Status | Recommendation eligibility | Reason |
|---|---|---|
| `SUBMITTED` | Excluded | Active application |
| `REVIEWING` | Excluded | Active application |
| `SHORTLISTED` | Excluded | Active application |
| `HIRED` | Excluded | Terminal successful application |
| `REJECTED` | Excluded | Current unique constraint prevents reapply |
| `WITHDRAWN` | Excluded | Current unique constraint prevents reapply |

The SQL exclusion is status-independent and therefore stays aligned with the actual
database reapply rule. Tests cover every enum member.

## Cache-Only Architecture

The GET path calls only `RankingCache.vector(kind, canonical)`. It never calls
`precompute`, the embedding factory, `/api/embed`, a lifecycle hook or a backfill.
Vectors remain private per-entity JSON artifacts under the existing production
ranking-cache root. First-page work performs at most one candidate cache read plus
one cache read per eligible job when the candidate vector is usable. Subsequent
snapshot pages perform zero vector reads. Candidate-unavailable requests also skip
all job-vector reads.

Cache misses never receive score zero. No DEV cache or DB backfill was run. Existing
lifecycle precompute remains the separate mechanism for future cache readiness.

## Cache Identity

Vector identity is unchanged Task 14 identity: entity kind, canonical fingerprint,
canonical semantic-text SHA-256, canonical version, Semantic-v1 engine, full BGE-M3
profile fingerprint and pinned model digest. Editing a canonical CV/JD therefore
selects a different cache artifact; records are not relabeled.

Recommendation policy version is `candidate-job-recommendation-v1`. Snapshot identity
adds authenticated candidate ID, requested/selected CV ID and canonical identity,
automatic-selection CV roster/state, normalized filters, page size, runtime identity,
eligibility-policy version, and the complete eligible job pool with timestamps and
canonical identities. Page number is deliberately excluded.

## Ranking

All eligible jobs in the requested pool are processed before pagination. Cached
candidate and job vectors use the unchanged Semantic-v1 cosine implementation.
Ranked rows sort by raw cosine descending. Equal scores preserve repository order:
`created_at DESC`, then job UUID `DESC`. Pending/unavailable/error rows follow the
ranked partition in that same stable non-sensitive order. A sequential rank is
assigned only to ranked rows.

There is no suitability threshold, score transform, probability, percentage or
local reranking. Even a negative cached cosine remains eligible and ranked. The raw
internal score exists only inside the private ten-minute snapshot and is not in the
candidate response.

## Snapshot Binding

The existing opaque 32-hex Task 14 snapshot store and 600-second TTL are reused.
Page 2+ requires `ranking_snapshot`; ranking occurs once on page 1. Loading validates
the binding and the complete stored traversal: exact membership, no duplicates,
finite score/rank invariants, deterministic ordering, candidate signal consistency
and freshly grounded reasons.

Candidate, CV selection/fingerprint, normalized filters, page size, runtime profile,
policy and job-pool changes reject the old token with 409. A token cannot cross
candidates. Snapshot availability is intentionally frozen during traversal, so a
cache becoming ready does not silently reorder page 2; a fresh page-1 request creates
a fresh view.

## Pool Complexity

Current inspected size is 9 jobs, so scoring is about `9 × 1024 = 9,216` cosine
dimensions. For `J` eligible jobs and 1024-dimensional vectors, first-page score work
is `O(J × 1024)`, snapshot rows/canonical job objects are `O(J)`, and DB job loading
uses a base query plus one select-in taxonomy query rather than N+1 queries.

The file cache has no bulk-read API, so a usable candidate signal causes `1 + J`
private file reads, but never `J` DB queries or provider calls. Only the candidate
vector and current job vector need coexist during scoring (roughly tens of KiB as
decoded Python floats); canonical job data and snapshot rows scale with `J`. At a
hypothetical 10,000-job pool this exact approach implies about 10.24 million vector
components and 10,001 small file reads. Product growth to that scale needs an explicit
retrieval/index stage in a later task; 15A does not silently approximate with “first
100 jobs.” No future pool-size estimate exists in source, so none is fabricated.

## Missing Signal Policy

- Candidate canonical signal absent/empty: selected signal is `unavailable`; every
  eligible job remains visible as unavailable, and no job vector is read.
- Candidate cache miss: signal and rows are `pending`; no provider/backfill runs.
- Job cache miss: that job is `pending` and remains after ranked rows.
- Empty canonical job: `unavailable` and remains visible.
- Corrupt cache/canonical/cosine failure: `error` and remains visible.

Missing signal is never interpreted as a poor match or a zero score.

## Recommendation Reasons

No LLM is used. Ranked items receive at most three deterministic `shared_skill`
reasons from exact normalized intersections of canonical job skills with canonical
CV skills and project technologies. Evidence uses the job's display spelling. Reasons
are contextual statements that the skill appears in both inputs; they do not claim
that a skill caused the embedding score, assign a contribution, invent a skill, use
PII or expose raw cosine. Non-ranked items have no reasons.

## Authorization

`GET /api/v1/candidate/jobs/recommendations` requires `CANDIDATE`. Unauthenticated
requests receive 401 and recruiter requests 403. The API never accepts a candidate ID;
it uses the authenticated user. Explicit foreign/missing CVs receive indistinguishable
404. Snapshot binding prevents cross-candidate reuse.

Response items follow the existing flattened `JobResponse` convention and add only
`recommendation_rank`, `recommendation_status`, and bounded `reasons`. Envelope fields
include page metadata, opaque `ranking_snapshot`, selected CV ID, candidate signal
status and state counts. It exposes no vector, score, canonical text, fingerprint,
provider or model.

Safe logs contain only eligible/ranked/pending/unavailable/error counts, candidate
signal status, total ranking duration and snapshot-reuse boolean; no IDs, PII, text,
vectors or provider details.

## Tests

New Task 15A integration tests: **8 passed, 3 warnings in 1.55s**. Coverage includes:

- explicit owned CV, default CV, deterministic valid fallback, no CV, unusable CV,
  foreign CV, canonical fingerprint mutation and CV-switch snapshot rejection;
- every actual job status and all six application statuses;
- all-cache-hit, candidate-unavailable, one and many job-cache misses with provider
  and precompute traps proving zero live/provider calls;
- fixed-vector global ranking before pagination, negative-score retention, all four
  semantic states, stable page concatenation and zero vector rereads on snapshots;
- candidate/filter/profile/pool snapshot binding, grounded bounded reasons, public
  schema privacy, auth and bounded DB query count.

Automated tests used deterministic two-dimensional fixture vectors only at the mocked
cache boundary. No Ollama/Gemini/Qwen request occurred. Pytest was guarded by a child
`TEST_DATABASE_URL` targeting `gjob_db_test`; credentials stayed in memory/redacted.
All synthetic users/CVs/jobs/applications were deleted by test cleanup, and temporary
cache/snapshot artifacts lived under pytest temporary roots.

## Task 14 Regression

Focused Task 15A + public jobs + candidate/recruiter applications + canonical input +
Semantic-v1 + embeddings + ranking metrics: **154 passed, 4 warnings in 24.80s**.
This verifies the shared public filter refactor did not change public listing behavior,
and recruiter Semantic-v1 ranking/cache/snapshot behavior remains intact.

Full backend regression after final implementation: **921 passed, 4 warnings in
118.25s (0:01:58)**. Warnings are existing google-genai, Starlette/httpx and deprecated
HTTP 422 constant warnings. `git diff --check` passes with existing line-ending
conversion warnings only. No frontend file or test changed because Task 15C is out of
scope. No live BGE smoke was justified or performed; deterministic cache-boundary and
full regression evidence are sufficient.

## Limitations

- Existing data requires lifecycle precompute before cache misses become ranked; this
  task intentionally adds no queue, admin backfill or synchronous generation.
- Per-entity JSON file reads and exact full-pool canonicalization are correct at the
  current scale but need an explicit retrieval/vector-index boundary for large pools.
- Skill-overlap reasons are contextual, not explanations of cosine attribution and
  can be empty even for a semantically ranked job.
- No explicit preference profile exists; filters are not silently promoted to learned
  preferences.
- Recommendation quality, fairness, calibrated thresholds and offline P@K/MRR/NDCG
  evidence belong to Task 15B. Frontend behavior belongs to Task 15C.

Recommended Task 15B input is the frozen 15A candidate/CV selection policy, exact
approved-never-applied pool policy, policy/profile/snapshot identity, full ranked and
unranked state contract, and a source-backed labeled candidate-job dataset evaluated
without changing Semantic-v1 or production thresholds.

## Final Status

**TASK 15A — JOB RECOMMENDATION FOUNDATION — VERIFIED.** Candidate authorization,
deterministic CV selection, approved/unapplied full-pool retrieval, cache-only
Semantic-v1 ranking, stable secure snapshots, missing-signal visibility and grounded
reasons are implemented and regression-tested. Zero live model calls, zero DEV DB
writes, zero provider/profile changes, and no Task 15B/15C implementation.
