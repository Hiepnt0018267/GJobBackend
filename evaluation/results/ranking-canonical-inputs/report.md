# Task 14C.1.5 Canonical Ranking Input Preparation

## FINAL STATUS: PASS — READY FOR TASK14C.2

**95/95 canonical CVs,10/10 JDs,100/100 ready pairs,105/105 privacy audit PASS.**
Canonical CV/JD/manifest artifacts are frozen. Exactly1 source-backed chronology
conflict is retained as non-fatal SOURCE_DATA_CONFLICT;the source/date order is
preserved,not corrected,and excluded from chronology-derived use. Existing94
successful payloads unchanged.0 new model calls;no scoring/ranking/DEV DB writes.
Full regression642 passed,3 warnings in105.40s. See Final Source Data Conflict Policy.

## Historical Task 14C.1.10 Status

**BLOCKED / NOT PASS:94/95 CV,10/10 JD,99/100 ready.**
Deterministic composite one-to-one alignment resolved18442517 and24964303 with
0 model calls.70750649 aligns uniquely,but the source range for experiences[7]
itself contradicts chronology at month precision. A provider-only reversal cannot
be proven,so dates were not swapped. All92 original accepted payloads and private
responses remain intact. No freeze/scoring. See alignment completion below.

## Historical Private Payload Recovery Status

**BLOCKED / NOT PASS:92/95 CV,10/10 JD,97/100 ready.**
Authorized reconstruction used exactly3/3 generations,one per CV,no correction or
HTTP retry. All3 raw structured responses are now durably retained in private
checkpoints BEFORE schema validation. The lost-payload prerequisite is resolved,
but deterministic source alignment/chronology still rejects these three CVs.
Hard stop honored; no freeze or scoring. See Private Payload Reconstruction below.

## Historical Task 14C.1.9 Status

**BLOCKED BEFORE IMPLEMENTATION: required structured payloads are missing.**
Coverage remains92/95 CV,10/10 JD,97/100 pairs;0 new model calls. All three raw
sources contain date expressions, but neither active checkpoints nor inspected
history retains their structured_result/canonical_input. The prior observer rejected
responses before checkpoint payload storage. An ambiguity resolver cannot reconstruct
missing experiences. See Final Source-Grounded Date Evidence Completion below.
This is an input-retention prerequisite failure, NOT a claim of absent source dates
or insufficient partial-date representation. No canonical freeze or READY statement.

## Historical Final Date Recovery Status

**BLOCKED / NOT PASS: 92/95 CVs, 10/10 JDs, 97/100 ready pairs.**
The authorized partial-date strategy used 10/12 new generations and recovered
three of six CVs. Three reached their two-generation per-CV hard stop; no further
model calls are authorized. Ground truth unchanged; canonical artifacts NOT frozen.
See Final Date Recovery Strategy below. Earlier sections are historical evidence,
not the current coverage/readiness state.

## Historical Task 14C.1.8 Status

**BLOCKED / NOT PASS: 89/95 CVs, 10/10 JDs, 93/100 ready pairs.**
The Final Recovery Attempt below supersedes the historical 71-CV status. Eighteen
of the 24 failures recovered; six date-schema failures persist after the bounded
final correction pass. No complete freeze or READY statement is justified.

## Resume Status

**BLOCKED / PARTIAL — NOT PASS.** All95 unique CV sources were processed through
production extraction/canonical v3. Initial71success/24failed; one bounded retry of
all24 failed items left the same71success/24failed. No sources/pairs were dropped.
JD10/10; manifest72/100ready,28not ready. Acceptance95/95CV and100/100pairs is not met.
No completed canonical freeze and no Task14C.2 scoring authorization.

This report supersedes the earlier partial8-CV run; the initial v2 checkpoint history
remains in private hash-named backups. The user-interrupted chat did not restart the
running batch: it completed95 records in the background and was audited before retry.

## Canonical Version

**matching-canonical-v3-explicit-identity-contract.**
Production mapper functions:
app.services.matching_input_mapper.build_cv_matching_input/build_job_matching_input.
Production CVStructuredExtractionService.extract_from_text and existing shared
Gemini/Ollama name contract used; configured provider ollama/modelqwen3:8b.

Shared sanitizer and identity-overlap auditor are used unchanged. No Task14B raw
adapter, evaluation-only text redaction, prompt tweak, output repair, source slicing,
model fallback, threshold or ranking rule. Every active record has source ID/ref/
hash, canonical version/profile hash and status; accepted records have canonical_input,
canonical_sha256 and the exact production canonical_fingerprint. CVs have explicit
provider/model provenance and identity audit marker. Invalid outputs are not persisted.

Only evaluation wrapper metadata was extended during this resume to record explicit
version/fingerprint/provider fields and verify them on reuse; its fingerprint source
file is included in the preparation profile. Production code was not modified.

## Checkpoint Migration

Initial audit:0VALID_V3,8STALE_PRE_V3 (3old successes+5old failures),87PENDING.
All8 old records were source/hash-verified and invalidated; all3 old successes were
re-extracted and now are accepted v3 results. The10 old JD drafts were regenerated
deterministically through the same production mapper under the current profile.

Byte-identical old backups in evaluation/cache/ranking-canonical-history:
ranking_canonical_cvs-54c153dc676ed8ba28911019547a3203ee0e6733026c32f8dfaf0996872d4eb0.jsonl;
ranking_canonical_jds-51cecd039d9a5fbebd8946c71105a76d8c8c61cc2e0565cda2875ef1dc561d94.jsonl.
First95-record failed checkpoint/summary also backed up before retry.
Backups are audit-only, never Task14C.2 inputs. No successful current-profile CV
was regenerated: all71 complete records remained equal before/after retry.

Final active audit:71VALID_V3,24FAILED,0PENDING,0STALE. Failed records are not
classified as valid merely because their version string saysv3.

## CV Processing

95 unique records, not100 independent CV calls. Source resolution/ref/hash checks pass.
Initial model workflows95:8stale reprocessed+87new. Compatible v3 reuse at start0.
Retry workflows24; compatible successes reused71; retry successes0.

| Final failure category | CV count | Stage/evidence |
|---|---:|---|
|SCHEMA_VALIDATION_FAILED|16|Production extraction/Pydantic validation|
|PROVIDER_UNAVAILABLE|6|Underlying AITimeoutError, existing90-second bound|
|AMBIGUOUS_IDENTITY_OVERLAP|2|Known full_name value overlaps semantic text|

The16 schema failures comprise9 chronological-date validator failures,6 blank
optional-text validator failures and1 invalid date parsing case. These diagnoses
use safe error type/location and inspected existing validators, not raw response
values: e.g. experiences[index] date-order check, field_of_study/description blank
check, experiences[7].end_date date_from_datetime_parsing. No dates swapped, blank
fields patched or invalid item removed to force success.

All24 failures reproduced on the one retry. Future additional identical retries
are not justified without addressing the underlying production/source issue.

## JD Processing

10/10 accepted canonical v3 JDs. Source refs/hashes, version/profile, production
fingerprint and deterministic mapper reconstruction pass. No Qwen JD extraction.

Source-backed title/description retained. Selected skills_desc/separate requirements
absent: no guessed skills/taxonomy/seniority. Unavailable optional fields remain null;
technical fixture APPROVED/vacancies1 is not real approval/vacancy evidence and is
excluded from semantic text. Currency source-backed or documented fixture fallback.
No production job/account/CV records created.

## Privacy Audit

Accepted CVs71/71: schema/UUID/source/profile/hash/fingerprint, exact mapper replay,
shared supported-contact audit and original successful identity audit marker pass.
JD10/10: shared contact audit and mapper replay pass.

Two failures:80527194 and99561379; both replayed full_name overlap. This is an
ambiguous identity/extraction collision, not proof of actual personal-name leakage.
No value/raw CV/name was printed. No aggressive NER, arbitrary role deletion or
privacy-check waiver. These two remain unready until source-only adjudication/shared
pipeline resolution. **Privacy acceptance for all95CVs is NOT achieved.**

Dedicated personal_info fields are structurally excluded from semantic sections;
persisted evaluation personal_info/location metadata minimized without changing
production semantic_text. Contact auditor is conservative, not universal PII/fairness
certification. Names duplicated in free professional prose may require adjudication.

## Pair Manifest

evaluation/data/derived/ranking_canonical_pair_manifest.csv:
exactly100 original unique case/pair/CV/JD identities;72ready=true/28ready=false.
All rows retained. CV reuse explains why71 successful CVs correspond to72 ready pairs.
No relevance grades/reasons, semantic scores or ranks are present in canonical artifacts.
Manifest joins only actual accepted current-profile records, not stale backups.

## Frozen Hashes

Ground truth remains frozen. Canonical outputs below are **PARTIAL CHECKPOINT hashes,
NOT completed frozen Task14C.2 inputs**. summary.json frozen=false/statusBLOCKED.

| Artifact under C:/DATN/GJobBackend/evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|2c64cd9483c470246a3c374f96cf5bd936fd0a46fca1be77bab7aac98e3bad44|
|ranking_canonical_jds.jsonl|dc7a942503daeec44b566f8b8c79afc2eccafdc65bbcfdb5c8d68ed2f71063c7|
|ranking_canonical_pair_manifest.csv|fdc98da55fe7cc8c7c46a83f2339f8ddecbb71b814b35df6040b77f7f3df7f3f|

Loader replay verifies all accepted CV canonical models/fingerprints against stored
professional structured data and all JD mappings against the same raw source.
Deterministically reconstructed manifest equals the stored100-row manifest.
No Qwen rerun was used for deterministic replay. No incomplete artifact called frozen.

## Provider Usage

119 local Qwen extraction workflows:95initial+24retry;95unique CV identities.
No re-call for any of the71 valid v3 artifacts. Old stale3successes were necessarily
reprocessed, not reused. Actual HTTP-level inner retry/attempt counts were not
instrumented; production bounded retry policy unchanged, no claim of zeroHTTP retries.

Observed execution: initial5027.284s,
retry1489.741s,
total6517.024s. These are CLI preparation runtimes,
including loading/validation; not pure inference-only metrics.
Provider per-item metrics remain in checkpoint when a response envelope was available.
stream=false,think=false,temp0,num_ctx8192,timeout90. No context/timeout increase,
silent truncation or automatic provider fallback.

Retry used an in-memory observer subclass that calls the original production service
unchanged and logs only exception categories/whitelisted field locations. Mapping
observer calls original mapper wrapper unchanged, reporting overlap field names only.
No mutated prompt/schema/output, labels or JD in CV calls; no permanent diagnostic
source module or raw-response dump created.

## Tests

- Final evaluation regression: **138 passed,2 warnings in6.77s**, exit0.
- Final extraction/shared providers/privacy/identity/canonical/semantic/embedding:
  **208 passed,1 warning in1.69s**, exit0, --noconftest.
- Source/hash/model/profile/version/fingerprint/schema/mapper/privacy replay of accepted
  records:PASS. Original71 accepted records unchanged on retry:PASS.
- Manifest100rows/72ready, no duplicate/unrelated source/pair; no lock remains.
- Existing warnings: google-genai UnionGenericAlias and Starlette/httpx deprecations.
- Automated tests use synthetic/mocked providers; no liveQwen in pytest or DEV DB.
- Full pytest not rerun: no shared production code changed during this resume.
  Task14C.1.7 full result599passed remains historical regression evidence, not95/95
  live extraction success.

## Ground Truth Integrity

Before/after exact required SHA:
a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d.
No labels/reasons/neutral pool positions/source refs/raw source edited. Source archives
remain Resume.csv816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d
and job_postings.csvd782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f.
Ground truth is read for identity/integrity validation only, never supplied to Qwen,
canonical mapping, diagnostics or output repair. No label-aware correction.

## DB Safety

No DEV connection/session/SQL/write, migration, production account/job/CV/application
or frontend change. Imports initialize model/engine definitions only, no DB connection.
No real dataset BGE-M3 vectors, Semantic-v1 scores/cosine, ranks, Precision@K/Recall@K/
MRR/NDCG, baseline/hybrid run or new threshold. No cloud/Gemini scoring/extraction.

## Cleanup

Both preparation processes completed and removed their task locks. User-interrupted
tool wait did not justify killing/restarting the nearly complete first batch.
All95 CV records,10 JD records,100manifest rows and private audit backups preserved.
No raw source, successful result, human label or old benchmark/cache deleted.
Synthetic fixtures cleaned up normally; no temporary raw-data copies or lingering
task batch. Only this SAME Task14C.1.5 Markdown report updated; no extra Markdown.

## Task 14C.2 Handoff

**BLOCKED — NOT READY FOR TASK14C.2 SEMANTIC-V1 RANKING SCORING.**
No requirement lowered to manufacture95/95. Preserve71 valid v3 CVs/10JDs.
Next justified scope: shared structured-response compatibility/source diagnosis for
chronological/partial dates and blank nullable text, bounded runtime review for six
timeouts, and source-only adjudication of two full_name overlaps. Do not silently
repair evaluation-only output, extend timeouts unboundedly or delete professional text.

After an authorized resolution, reuse still-compatible successful items, retry only
unready items; if production extraction contract/profile changes, use explicit
source-verified backup/invalidation rather than blindly reusing old results.
Freeze all three artifacts only at95CVsuccess/10JDsuccess/100pairsready and privacyPASS.

Commands run:
```powershell
venv\Scripts\python.exe -X utf8 -u -m evaluation.prepare_ranking_canonical --data-dir C:/DATN/Datasets --invalidate-incompatible-checkpoints --retry-failed
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest --noconftest tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
git diff --check
```
One bounded24-item retry through the same prep.run(--retry-failed) was launched inline
with safe observers; source-backed checkpoint backups, metadata/hash/replay audits
also ran. No scoring command, direct output correction or DEV cleanup command.

**Final status: BLOCKED after complete95-source processing and bounded24-item retry.
71/95CV,10/10JD,72/100pairs.**

## Final Recovery Attempt

### Initial Remaining Failures

24 failures: schema 16, timeout 6, full_name overlap 2. A source-scoped private
inventory is recorded in failures.json, including source hashes, safe field/type
diagnostics and character-based token estimates (not tokenizer counts).

### Root Cause Analysis

Schema diagnostics: nine chronological date-order failures, six blank nullable-text
failures, one date parsing failure. No object-to-string/list coercion was needed.
Timeouts were previously diagnosed as AITimeoutError at the 90-second budget.
All six recover at the bounded 180-second setting; this supports runtime-budget
insufficiency, not proof of cold start or GPU contention. Precise earlier timeout
durations and HTTP attempts were not captured. Existing context guard remains on.

The overlap rejection used substring collision, not evidence that personal_info
entered the mapper. Identity-free mapper replay supplies the structural check.
This does not establish that arbitrary names in professional prose are absent.

### Shared Fixes Applied

Nullable whitespace-only primitives normalize to None in shared CV schemas;
mandatory text, date parsing, chronology and extra-field validation remain strict.
No unknown object coercion, fabricated date, item deletion or manual JSON edit.
The shared extraction service allows one correction generation using the SAME
source and StructuredCVExtractionResult schema. Safe feedback includes trusted
field names/indices and error types only, never raw values/messages. Provider
failures do not trigger schema correction. A correction-only mode performs one
generation for the final pass. Existing provider retry/context policy is unchanged.

Settings accepts a maximum of 180 seconds; default remains 90, local LLM setting
is 180. The provider bounds each generation, including its inner retries. Two
schema generations can therefore take roughly 360 seconds. Frontend extraction
timeout remains 120 seconds: interactive HTTP flow compatibility is a known gap,
not claimed fixed here; no frontend changes were authorized or made.

Shared structural audit compares full and identity-free mapper text; it preserves
independently present professional phrases rather than deleting name collisions.
Contact sanitizer/mapper feature selection are unchanged. Version remains
matching-canonical-v3-explicit-identity-contract: valid successful structured and
canonical payloads are unchanged, only invalid absent text/runtime/orchestration
and audit provenance are affected. Explicit source-verified profile migration
records origin_profile_sha256 and validates fingerprints/mapper replay on reuse.

A draft regex-driven date-null schema was reviewed and removed BEFORE any live
use. Recognized partial dates cannot prove the absence of complete date evidence;
forcing null would change the requested schema. Only this task-owned draft module
and its draft test were removed; no dataset/checkpoint was deleted.

### Schema Recovery Results

10/16 recovered. Six remain after initial recovery and one final correction pass:

| CV ID | Earlier safe diagnostic | Why not accepted |
|---|---|---|
|18442517|educations date chronology|Strict start/end ordering failed|
|24964303|experiences[7].end_date parsing|Provider date was not accepted by date parsing|
|27152464|experiences[2] chronology|Strict start/end ordering failed|
|30304575|experiences[5] chronology|Strict start/end ordering failed|
|36517781|experiences[3] chronology|Strict start/end ordering failed|
|70750649|experiences[7] chronology|Strict start/end ordering failed|

These paths are earlier observed diagnostics, not asserted exact final-response
paths: the final pass persisted safe SCHEMA_VALIDATION_FAILED categories only.
Source-only inspection found partial month/year evidence and no recognized complete
date patterns in these six; regex absence is NOT proof of missing full dates.
The unchanged strict pipeline cannot accept the generated inconsistent/invalid
dates. This is not proof that recovery is universally impossible or requires an
architectural rewrite. Any further attempt needs an explicitly revised recovery
budget/strategy; changing date precision representation requires a separately
specified shared contract. Silent exclusion would bias the fixed ranking pool.

### Timeout Recovery Results

6/6 recovered with bounded timeout 180, context 8192, sequential extraction,
think=false, temperature 0, no truncation or cloud/model fallback.

### Privacy Overlap Results

2/2 recovered (80527194 and 99561379) with structural identity independence and
supported-contact audit. Classification: substring audit false positive concerning
identity-field inclusion; this is not a source-based declaration that the values
are definitely professions or definitely not real names. No professional text
was deleted. No broad free-prose identity/fairness certification is claimed.

### Model Usage

Initial recovery: 24 unique failed CV workflows, 18 successes, 6 failures.
Final correction: six workflows/six generations, zero additional successes.
Total this task: 30 workflows on 24 unique CVs; no calls for the original 71 valid
CVs, no JD calls. First-pass generation counters were not persisted; exact total
generations/HTTP attempts are unavailable, not invented. Generation bounds:
30–54 overall, maximum three generations per affected CV across these two passes.
Provider HTTP retries remain independently bounded. No extra live retry on resume.
Final correction CLI runtime: 324.490251 seconds; first recovery runtime was not
retained in the final summary. Earlier 119 workflows/6517.024 seconds belong to
the historical preparation, not this recovery. No Qwen suitability scoring.

### Checkpoint Reuse

Original 71 accepted CVs reused, zero invalidated/re-extracted. Exact equality of
source hashes, structured_result, canonical_input, canonical SHA and fingerprint
verified against the hash-named original backup. Profile/provenance envelopes
were explicitly migrated and backed up. The 18 new successes were reused in the
final pass. All ten JD mappings replay identically from raw sources.

### Final CV Coverage

89/95 success; six failed, zero pending. No source replacement or discarded section.

### Final JD Coverage

10/10 success, source/profile/canonical hash/fingerprint and mapper replay pass.

### Final Privacy Audit

99 accepted entities (89 CV + 10 JD) pass supported-contact and applicable
structural checks. Full 105/105 acceptance is NOT achieved: six CVs lack accepted
canonical outputs. Minimized checkpoints cannot re-prove the original identity
fields, so initial structural audit markers and replay evidence are distinguished.

### Pair Manifest

100 original unique rows retained, 93 ready / 7 unready. Deterministic manifest
reconstruction equals the stored file. Every ready row resolves accepted CV/JD
artifacts. No score/rank/relevance features enter preparation.

### Frozen Hashes

Only ground truth is frozen. Canonical hashes below describe PARTIAL checkpoints:

| File under evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|54eeaae1db86bbd3050646277e2465a2f74f42a8f87b90b6ee33b6b035723a81|
|ranking_canonical_jds.jsonl|7526d079155f208fef624823bb43a2d2944ccad4be5af98d070fb6ebd83a4151|
|ranking_canonical_pair_manifest.csv|b472728d664670d0afbd7f088cb307ee040925e7903a089ec29dbf21e5e7b1fb|

Summary remains frozen=false. The final service cleanup removed unreachable code;
stored extraction-profile hashes describe the actual generating code, not falsely
rewritten as a new freeze. Read-only audit used that recorded profile and replayed
the current identical mapper/schema semantics. Future resume must explicitly
verify profile compatibility rather than bypass its guard.

### Tests

Evaluation: **138 passed, 2 warnings in 6.99s**. Pure extraction/provider/recovery/
privacy/input/semantic/embedding: **215 passed, 1 warning in 1.76s**; exit 0 both.
Full pytest: **606 passed, 3 warnings in 138.24s (0:02:18)**, exit 0, on the existing
guarded gjob_db_test. Warnings are existing google-genai UnionGenericAlias,
Starlette/httpx TestClient and deprecated HTTP_422_UNPROCESSABLE_ENTITY.
Synthetic tests cover blank
nullable/mandatory rejection, dates not swapped/coerced, same-schema correction,
bounded final correction, provider-error separation and structural identity audit.
Real source/ref/hash/fingerprint/mapper/manifest replay PASS with sockets disabled.
No automated test called a live model. git diff --check passed (line-ending warnings).

### Ground Truth Integrity

Required ground-truth hash unchanged. Raw Resume.csv and job_postings.csv hashes
match historical values; labels/reasons and identities remain byte-identical.

### DB Safety

Preparation/replay did not connect to DEV or create/delete DB records. Full pytest
uses existing guarded gjob_db_test via transient TEST_DATABASE_URL; credentials
stay in memory and captured output is redacted. No new DB/config or migration.
No BGE-M3 calls, real semantic scoring, ranks or ranking metrics.

### Cleanup

No preparation process or task lock remains. Valid/failed checkpoints and private
history remain. Only the unsafe unexecuted task-owned date-schema draft was removed;
all human data, raw sources and old benchmark artifacts remain. This SAME Markdown
report was updated; failures.json remains a safe machine audit, not raw output.

### Task 14C.2 Handoff

**BLOCKED — NOT READY FOR TASK 14C.2 SEMANTIC-V1 RANKING SCORING.**
95/95 and 100/100 acceptance are not met. Preserve the 89 successes; do not score
93 ready pairs as a replacement benchmark, waive validation, force ready=true or
repeat identical recovery indefinitely. A revised shared date-recovery strategy
and explicit bounded budget are needed before another live attempt.

### Exact Recovery / Verification Commands

```powershell
venv\Scripts\python.exe -X utf8 -u -m evaluation.prepare_ranking_canonical --data-dir C:/DATN/Datasets --reuse-verified-v3 --retry-failed
venv\Scripts\python.exe -X utf8 -u -m evaluation.prepare_ranking_canonical --data-dir C:/DATN/Datasets --reuse-verified-v3 --retry-failed --final-schema-correction
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest --noconftest tests/test_cv_recovery.py tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Recovery commands above ran before the interrupted turn and were audited, not
rerun here. Full pytest ran in a child process after validate_test_database_url,
with existing Docker credentials and template target resolved in memory; no
password/connection string appears here. Read-only process checks, source/schema
inspection and network-disabled mapper/hash replay were also run. No SQL cleanup,
scoring, new model call or annotation export occurred on this resume.

## Final Date Recovery Strategy

### Shared Date Contract

Implemented **cv-date-precision-v1** in app/schemas/partial_date.py. Professional
education/experience/project/certificate date fields in both CV and canonical
schemas accept a legacy full ISO date OR a strict PartialDate object containing
year/month/day/precision. Year precision forbids month/day; month precision requires
month and forbids day; day precision requires a real calendar date. Optional
components remain null, not fabricated. Full ISO dates still serialize exactly as
before. Exact year, YYYY-MM, MM/YYYY and English month/year input strings normalize
losslessly to partial objects; unknown/invalid values stay invalid, not coerced
to null. Present/Current uses existing is_current=true with absent end_date; the
word Present is not converted into a calendar date. Personal DOB remains the
existing separate full-date optional field, outside professional matching dates.

Shared Gemini/Ollama extraction instructions and correction prompt now preserve
source precision, permit partial dates, prohibit date swapping/fabricated precision
and retain factual items. No evaluation-only structured-output repair or raw-text
fallback. Existing JSONB sections can store these values; no migration necessary.
This expands date JSON values for new partial-date outputs; existing full-date
API values are unchanged. Frontend rendering of new objects is outside this task
and not certified by backend regression.

### Chronology Semantics

An internal validation interval represents each value: year spans its calendar
year, month spans its actual calendar month, day is exact. Interval endpoints are
never persisted as extracted dates. Reject only earliest(start) > latest(end).
Overlapping/mixed-precision intervals are potentially valid, not guessed ordering.
Invalid calendars and inconsistent precision remain rejected; no date swapping,
forced-null recovery or section deletion.

### Version / Fingerprint Decision

Extraction/profile contract version bumped to cv-date-precision-v1 and included in
the preparation profile together with the new source file hash. Canonical semantic
version remains **matching-canonical-v3-explicit-identity-contract**: professional
semantic_text construction and actual fingerprint signals do not consume dates.
Synthetic date-only perturbation proves unchanged text/fingerprint. No embedding
cache claimed compatible merely from a version label; exact fingerprint/schema/
source/mapper replay was performed. No scorer or embedding provider changed.

### Existing 89 CV Compatibility

All89 accepted CVs revalidated before live calls and replayed afterward. Their
structured_result, canonical_input, source hash, canonical hash and matching
fingerprint are exactly equal to the pre-date-strategy checkpoint. Zero calls
for these89; zero successful-item invalidations/re-extractions. Explicit profile
migration records the originating profile and retains hash-named byte-identical
backups; old generating provenance is not falsely relabeled as new extraction.
All10 JD canonical payloads/fingerprints replay identically; only profile envelopes
were migrated, not source content or matching features.

### Six-CV Recovery / Exact Budget

Sequential production extraction, same CV-only source/schema, stream=false,
think=false, temperature0, num_ctx8192, timeout<=180 per generation, existing context
guard. HTTP retries were disabled on the task's provider instance so every counted
generation corresponds to exactly one HTTP request. Production factory defaults
were not changed. An instrumented observer asserted at most2 calls/CV and12 total.
Correction uses the shared service and safe validation feedback, not human dates,
JD/relevance/rank/score. Counts are persisted in failures.json.partial_date_recovery.

| CV ID | Primary | Correction | Final result |
|---|---:|---:|---|
|18442517|1|1|FAILED: source-date evidence check, experiences[0].end_date|
|24964303|1|1|FAILED: source-date evidence check, experiences[0/1/2].end_date|
|27152464|1|1|SUCCEEDED;11 supported partial dates|
|30304575|1|0|SUCCEEDED;18 supported partial dates|
|36517781|1|0|SUCCEEDED;14 supported partial dates|
|70750649|1|1|FAILED: source-date evidence check, experiences[0].end_date|

**6 primary +4 correction =10/12 new Qwen generations /10 HTTP requests.**
No third generation, no hidden HTTP retry, no duplicate batch, no cloud fallback.
Preparation runtime585.032720s; observer lifetime585.072022s. Provider metadata
is preserved where a response was available. No timeout/context increase.

### Source-Compatible Precision / Remaining Blockers

Before accepting each of these six responses, a read-only quality observer checked
every generated professional date against positive matching source evidence for
its precision (year token, month/year or complete day forms). It also required
partial information to remain represented, not all dates null. It never mutated
model output or inferred missing components. This is additional admission validation,
not an alternative extractor/mapper or a regex absence-driven null schema.

The three successes retain43 partial values, all passing this evidence check,
strict schema/interval chronology, production mapping and privacy checks.
It is a conservative document-level pattern check, NOT comprehensive date-language
recognition or proof that every date is attached to the correct employment item.
No universal source-fidelity/LLM quality certification is claimed.

Remaining exact final failures:

- 18442517: first response failed educations[0] chronology; correction passed the
  provider schema but experiences[0].end_date lacked accepted precision evidence.
- 24964303: both responses failed source evidence for experiences[0/1/2].end_date.
- 70750649: first response failed experiences[7] chronology; correction passed the
  provider schema but experiences[0].end_date lacked accepted precision evidence.

Final end-date errors are the observer's source_date_precision_not_supported,
wrapped as safe validation failures; generic checkpoint code remains
SCHEMA_VALIDATION_FAILED. This is distinct from the old date parser rejecting a
valid partial representation. The new contract CAN represent partial dates and
worked for three CVs; these last failures do not establish representational
insufficiency. They indicate unresolved generation/source-evidence fidelity OR
an unsupported evidence notation in the conservative audit. Invalid responses
were not persisted, so the exact offending values/notations cannot be retrospectively
adjudicated from the safe field-only inventory. No claim of proven fabrication.
Budget is exhausted PER ITEM even though total10<12: the unused2 slots do not
authorize a third call for any failed CV. STOP; no further retry was launched.

### Final Coverage / Privacy / Manifest

CV92/95; JD10/10; manifest100 original rows, **97 ready /3 unready**. No duplicate,
replacement, silent exclusion or manually forced ready flag. Accepted102 entities
(92CV+10JD) pass shared supported-contact audits and mapper/fingerprint replay.
Structural identity exclusion is validated at extraction time; minimized historical
records retain their audit markers and exact payload replay. Full105/105 privacy
acceptance is unavailable because three CVs have no accepted canonical output.
Deterministic manifest reconstruction equals the stored file. No score or rank.

### Hashes / Freeze State

Ground truth alone remains frozen. Canonical hashes are PARTIAL CHECKPOINT hashes:

| File under C:/DATN/GJobBackend/evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|428e14ab95f826633bfd875a38e245c7e0bb31931c9b03804154380947f65c5e|
|ranking_canonical_jds.jsonl|3fd03833224a08035248cc6c55f1adfb376605c67041be1f926ea9eb39c6e8bd|
|ranking_canonical_pair_manifest.csv|e659d24451fbd839083662e95f2e36f2358a0eceebf6d192ffd16b8a58455781|

summary.json frozen=false, statusBLOCKED, ready_for_task_14c2=false. Current stored
profile matches current source code; hashes were verified after the batch. No
partial artifact is described as a completed freeze.

### Tests / Review

Before live calls:232 passed,1 warning in1.77s; evaluation138 passed,2 warnings
in6.79s. **Full pytest623 passed,3 warnings in105.29s (0:01:45), exit0**, existing
guarded gjob_db_test only. Full suite passed BEFORE the batch; production code was
not edited afterward. Final focused232 passed,1 warning in1.81s; final evaluation
138 passed,2 warnings in6.52s, exit0. Tests cover partial string/object precision,
invalid precision/calendars, intervals, current flag, full-date serialization,
mixed/overlapping/definitely reversed dates, no forced null/swapping and invariant
canonical text/fingerprints. All tests mock providers; no live pytest model call.
Warnings are existing google-genai, Starlette/httpx and deprecated422 notices.
Final real replay with sockets disabled verifies source/schema/hash/profile,
92 canonical CVs/10 JDs, all89 unchanged success payloads and exact100-row manifest.

### Safety / Cleanup / Commands

Ground truth and source archive hashes unchanged. No DEV session/SQL/write, new DB,
config file, migration, frontend edit, cloud call, embeddings, cosine, rank or
Precision@K/Recall@K/MRR/NDCG. Full pytest used existing TEST_DATABASE_URL guard
and in-memory/redacted credentials, never DEV fallback. No raw CV/provider output,
personal name/contact value or fabricated replacement date in reports/diagnostics.
Batch finished and removed its lock. Private checkpoint backups and valid successes
remain; no data deleted. Only this SAME report.md updated; machine audits retained.

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_partial_dates.py tests/test_cv_recovery.py tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

The live inline instrumented runner invokes prep.run with --reuse-verified-v3,
--retry-failed, data-dir C:/DATN/Datasets, standard shared correction policy and
the explicit observer/call gates described above. It is not a plain CLI run with
default hidden HTTP retries. No permanent diagnostic script or extra Markdown.
Read-only process/source/profile/hash/privacy/mapper audits also ran.

### Final Handoff

**BLOCKED / NOT PASS — NOT READY FOR TASK14C.2.**
Shared partial-date compatibility and regression pass; three source-evidence
failures remain after their hard stop. Preserve92 valid CVs/10 JDs and the fixed
100-pair dataset. Do not score a reduced pool or silently relax evidence checks.
No further live attempt under this budget. Source-only evidence-policy adjudication
must be explicitly resolved before any revised strategy or new budget.

## Final Source-Grounded Date Evidence Completion

### Initial State

92/95 CV,10/10 JD,97/100 ready. Existing contract cv-date-precision-v1;
canonical matching-canonical-v3-explicit-identity-contract. All prior budgets closed.

### Remaining CVs

18442517,24964303,70750649. Their current FAILED records contain source ref/hash,
provider/model/profile, safe error code and generation metrics, but NO structured
result or canonical input. The same is true in every matching historical record.

### Source Review / Missing Prerequisite

Read partial_date.py, CV/structured/canonical schema wiring, chronology helper,
extraction correction/validation flow, prepare_cvs/checkpoint loader, canonical
mapper/profile/fingerprint, source loader and earlier report/audit. The evidence
observer in the previous task was inline, not a durable production resolver. It
rejected validated payloads before prepare_cvs received them. prepare_cvs persists
structured_result only on success; failure branches save diagnostics/metrics only.
Consequently those rejected responses were lost when the batch process exited.
This is an artifact-retention gap in the previous implementation, not user labeling
failure, and cannot be repaired by retroactively adding metadata.

Read-only search covered active JSONL, all canonical history JSONL and backend
JSON/JSONL artifacts including private/ignored paths (permission-restricted reads
were retried with approval). Matching JSON files contain only summaries/failure
audit. No reusable structured payload was located for any of the three CVs.
The provider-response values were deliberately not persisted in the prior task;
field paths alone do not supply roles, companies, descriptions or date alignment.
No current preparation batch remains. No database lookup was attempted.

Document-wide safe source diagnostics (pattern counts, not role attribution):

| CV ID | Year tokens | Month/year patterns | Current-like markers | Structured payload |
|---|---:|---:|---:|---|
|18442517|18|15|13|absent|
|24964303|17|15|4|absent|
|70750649|21|19|1|absent|

All sources/ref/hash checks pass. These counts establish date expressions exist;
they do NOT assign any expression to a particular experience or prove that every
Current marker denotes employment. No raw dates, professional excerpts or PII
were printed/persisted. Source hashes remain in existing checkpoint envelopes.

### Evidence Resolver Design / Plan

Conditional plan, NOT implemented: recover existing structured payloads with exact
source/provenance; resolve evidence in local role/company/source-span context;
distinguish verified year/month/day, open-ended, source-backed ambiguous precision
and genuinely absent dates; never assign global unrelated year matches; validate
chronology on defensible intervals; keep metadata out of semantic_text; replay92
successes; synthetic resolver/regression tests; full guarded pytest if shared code
changes; process3 without model calls; freeze only at95/10/100 and105 audits.

The prerequisite fails before code: there are no structured experience records
to provide the local anchors or values for that resolver. Constructing whole CV
sections anew from raw text would be a different extraction strategy, not date
evidence completion over existing payloads. No manual JSON rebuilding, raw-text
fallback, empty-section substitution or model call was assumed authorized.
Implementing an unused prototype would not satisfy the requested completion.

### Ambiguous Precision Policy

Requested source-backed ambiguity is legitimate and must differ from null. It
must attach to an existing structured date/experience and locally defensible
evidence. Missing entire structured payload is NOT ambiguous date precision.
An ambiguity flag cannot replace company/role/responsibility/experience records.
No new enum/schema/contract was introduced before resolving that input requirement.

### Chronology Semantics

Current interval-based partial chronology remains unchanged and tested. Future
ambiguity may broaden only locally defensible date intervals; Present/Current
must be open-ended, never today's date. This task did not fabricate interval
values, swap dates, force null or weaken impossible-order rejection.

### Existing 92 Compatibility

All92 accepted CVs and10 JDs replay under the unchanged current schema/profile,
source refs/hashes, mapper, fingerprint and supported-contact audits. Stored
canonical payloads and all four dataset/artifact hashes remain unchanged.
No re-extraction, invalidation, profile migration or production file edit this turn.

### Final 3 Results

| CV ID | Source evidence status | Why ambiguity cannot finish this item |
|---|---|---|
|18442517|source/date expressions available|No structured experiences or extracted values retained|
|24964303|source/date expressions available|No structured experiences or extracted values retained|
|70750649|source/date expressions available|No structured experiences or extracted values retained|

Task section21 presumes existing structured extraction payloads; that assumption
does not match disk state. This is NOT the section33 no-date-evidence blocker:
sources do contain dates. The actual independent prerequisite is missing structured
input. No claim is made that the source or proposed ambiguity contract is incapable
of representing the CV. Successful completion requires source-matched payload
backups supplied/restored, or explicit authority for a different reconstruction
workflow. No additional model authority is inferred.

### Final Coverage / Privacy Audit

92/95 CV,10/10 JD; all100 original manifest rows retained,97 ready/3 unready.
Accepted102 entities replay privacy/canonical checks; no new105/105 claim.
No fabricated empty CV, guessed dates or manual ready flag. Freeze remains false.

### Frozen Hashes

Ground truth frozen and unchanged; canonical hashes still PARTIAL checkpoints:

| File under evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|428e14ab95f826633bfd875a38e245c7e0bb31931c9b03804154380947f65c5e|
|ranking_canonical_jds.jsonl|3fd03833224a08035248cc6c55f1adfb376605c67041be1f926ea9eb39c6e8bd|
|ranking_canonical_pair_manifest.csv|e659d24451fbd839083662e95f2e36f2358a0eceebf6d192ffd16b8a58455781|

### Tests

Existing focused date/extraction/providers/identity/privacy/canonical/input/semantic/
embedding tests: **232 passed,1 warning in2.39s**, exit0. Evaluation tests:
**138 passed,2 warnings in10.87s**, exit0. No new resolver tests or implementation
are claimed. Network-disabled real mapper/source/profile/hash/privacy/manifest
replay PASS. Full pytest not rerun: no shared production code changed; historical
623 passed/3 warnings/105.29s is prior-task evidence, not a new full result.

Commands: the same focused/evaluation pytest commands in the preceding section;
read-only rg filename search (including --no-ignore); safe JSON key/status and
source pattern-count inspection; network-disabled canonical replay; git diff --check.
No provider/API/SQL/DB command, scoring, ranking, new config or migration.

### Model Usage / Cleanup

**0 new generations,0 new model requests.** Unused prior budget slots were not
consumed. No Qwen/Gemini/BGE calls, no DEV DB, no raw diagnostics or deletion.
Only this SAME report and safe machine audit updated; all canonical/ground-truth/
source/checkpoint/cache artifacts preserved. No temporary extraction process/lock.

### Final 14C.1.5 Status

**BLOCKED — NOT READY FOR TASK14C.2.** Need the three source-matched structured
payloads before deterministic evidence completion can proceed under zero-model-call
constraints. Restore/provide those private backups; do not counterfeit completion.

## Private Payload Reconstruction

### Authorization / Source Review / Plan

New user authority permits exactly one local Qwen generation for each unresolved
CV18442517/24964303/70750649; previous budgets remain closed. Reviewed provider
request/parse/validation ordering, extraction retries, source loader, date schemas,
canonical/profile/checkpoint handling and private cache ignore rules before edits.
Plan:durable opt-in pre-validation raw sink; disable HTTP/schema corrections for
this batch; shared deterministic local date resolver; mock tests/full guarded
regression; replay92 successes; sequential3 generations; retain rejected responses;
accept only complete schema/chronology/source/mapping/privacy passes; final audit
before freeze. No relevance/JD/ranking input or semantic scoring.

### Pre-Validation Private Retention

app/ai/ollama_provider.py exposes an opt-in structured_response_observer. After
an envelope with structured content/metrics is parsed, it invokes the sink BEFORE
context/content/JSON/Pydantic acceptance. The untouched message content is passed
to the sink, never logged. Without the observer(default),production does not store
raw responses. Observer persistence failures are not silently ignored.

evaluation/recovery_checkpoint.py uses atomic replace/fsync through existing writer.
Each private file records cv_id,source refs/hash/file hashes,provider/model,
generating profile,timestamps,generation metadata,validation result/diagnostic and
raw_structured_response. A durable GENERATION_STARTED record is written before
calling the provider. Existing files forbid starting a second generation; duplicate
response capture is rejected. Raw content remains even after domain/recovery failure.
This is a private recovery/debug artifact,not a successful canonical result.

Exact private directory:
C:/DATN/GJobBackend/evaluation/cache/ranking-payload-recovery-v1

Files:cv_18442517.json,cv_24964303.json,cv_70750649.json. All3 contain raw responses
and generation metadata; all are gitignored via existing evaluation/cache rule.
No raw PII/provider content appears in this report or public/frozen artifacts.
No files were deleted. Raw files are sensitive and must not be published.

### Shared Deterministic Evidence / Contracts

app/services/cv_date_evidence.py resolves a unique nearby date range against an
exact normalized record anchor plus a secondary company/degree/role anchor. It
uses local context with bounded gaps,not arbitrary global year lookup. Ranges
support year,month/year,textual month/year,full ISO dates and Present/Current/Now/
Till date. Source-backed Current becomes explicit OpenEndedDate(state=current),
not today's date or null. Empty objects are invalid; Current must be explicit.

A single local year matching the extracted value can retain year-only ambiguity
without inventing month/day. Ambiguous values validate on a conservative year
interval; interval endpoints remain internal. Missing/contradictory alignments
fail rather than assigning unrelated dates. Original raw JSON is never edited;
the resolver creates a copy and changes only date/current metadata from defensible
local source tokens. It never removes professional items or swaps dates.

Date contract:cv-date-precision-v2-source-evidence.
Evidence contract:cv-local-date-range-evidence-v1.
Canonical semantic version stays matching-canonical-v3-explicit-identity-contract:
dates/ambiguity metadata do not enter semantic_text or matching fingerprints.
Existing92 structured/canonical payloads and fingerprints replay identically;
only source-verified profile envelopes were migrated with private history backups.
No re-extraction or model call for those92 or for the10 JDs.

### Exact Model Budget / Results

max_schema_retries=0 on the existing shared extraction service; original default
one correction remains unchanged for other callers. Task provider HTTP retries=0.
Sequential CV-only qwen3:8b,stream=false,think=false,temperature0,num_ctx8192,
timeout<=180,current context guard,no truncation/cloud fallback. Each source was
passed through the production extraction prompt/provider contract once. A schema
failure reads the retained private payload for deterministic recovery,not a second
generation. Schema-valid responses also undergo source evidence/mapping checks.

| CV ID | Generations | Raw retained | Primary schema | Deterministic result |
|---|---:|---|---|---|
|18442517|1|yes|FAILED|local-range alignment unresolved|
|24964303|1|yes|PASS|multiple plausible local ranges/record alignment unresolved|
|70750649|1|yes|FAILED|experiences[7] definite interval-order violation after grounding|

**3/3 new generations,3 HTTP requests,0 corrections,0 HTTP retries.**
Runtime195.670473s. All provider response payloads remain available; no fourth
call or second per-CV call. Safe counts/results are in failures.json under
raw_payload_reconstruction. No model was asked to score/recommend/rank.

### Precise Deterministic Work Still Missing / Hard Stop

- 18442517:experiences[2] and[3] each have one exact role-anchor occurrence and
  an adjacent range(gap1),but the secondary company string does not match the
  resolver's local window. A justified alias/anchor-provenance policy is missing;
  this is not proof the dates are absent. No arbitrary bypass was applied.
- 24964303:experiences[0/1/2] share repeated role anchors(four occurrences);three
  ranges at gap3 also match the company context. Current resolver cannot assign
  those ranges uniquely to the respective records. Education[0] has no accepted
  nearby range. Needs stronger local record/source-span/description alignment,
  not global year matching or guessed range assignment.
- 70750649:the resolver selects a local source range for experiences[7] with month
  precision at both ends; earliest(start)>latest(end),verified by read-only interval
  diagnosis. Needs adjudication of source-range association and,if correct,an
  explicit source inconsistency policy. Marking known contradictory months merely
  ambiguous or swapping them would hide a definite contradiction and is forbidden.

The provider payload-retention problem is fixed. The resolver is deliberately
conservative and incomplete for these source shapes; it is not claimed universal
date extraction. Per user hard stop,no additional model requests or speculative
recovery rounds were launched. Payloads now allow further authorized deterministic
work without another model call. No JSON was manually repaired,no date forced
null,no section/CV removed,no source or human decision changed.

### Final Integrity / Coverage / Freeze

92/95 CV success,10/10 JD,97/100 ready,3 unready;all100 original pairs remain.
All92 prior successful structured_result/canonical_input/source hash/canonical
hash/fingerprint values equal the pre-reconstruction backup. Current profile
matches current code. Source/ref/hash/schema/mapper/privacy checks and exact
manifest reconstruction pass for accepted data; raw_structured_response is absent
from accepted canonical JSONL. Supported-contact/structural audit scope covers
102 accepted entities;105/105 cannot be claimed while3 outputs are unaccepted.

Freeze was explicitly deferred until final audits;summary remains BLOCKED,
frozen=false,ready_for_task_14c2=false. No partial artifact called frozen.

| File under evaluation/data/derived | Current SHA-256 |
|---|---|
|ranking_pairs_labeled.csv(frozen,unchanged)|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl(partial checkpoint)|98575217311e95c8ece4a94ad0383640e833cd0fe519885e06c09d3830e7f448|
|ranking_canonical_jds.jsonl(partial checkpoint)|0cf0a8bc2bd894a03511fb5714476fa9e8ce68a4dfc84657e582599a879f0b2b|
|ranking_canonical_pair_manifest.csv(not frozen)|e659d24451fbd839083662e95f2e36f2358a0eceebf6d192ffd16b8a58455781|

### Tests / Code Review

New synthetic tests verify raw persistence before failed Pydantic chronology,
exactly one generation with corrections disabled,deterministic recovery from private
payload without a provider call,private/public separation,duplicate-generation
guard,local date precision/open-ended/ambiguity,unrelated dates and multiple-range
rejection. Review tightened Current so{} cannot infer open-ended status.

Final full pytest:**631 passed,3 warnings in106.14s(0:01:46),exit0**,existing guarded
gjob_db_test only. Earlier full run631/148.61s was followed by final regression
after explicit-Current review. Final focused:**240 passed,1 warning in1.86s**.
Final evaluation:**138 passed,2 warnings in6.82s**,exit0. All pytest providers
mocked;no live model in automated tests. Existing google-genai/Starlette/httpx/
deprecated422 warnings only. Source/profile/hash/privacy/mapper/manifest replay
with sockets disabled PASS. An initial replay used host default encoding and failed
to read UTF-8;explicit UTF-8 rerun passed without data/code changes.

### Safety / Cleanup / Exact Commands

No DEV DB/session/SQL/write,migration,frontend change,BGE-M3 request,cosine,
rank,Precision@K/Recall@K/MRR/NDCG or ground-truth/source edit. Full suite used
existing TEST_DATABASE_URL guard,credentials in memory and redacted output,no
new DB/config/OS environment or DEV fallback. Only this SAME report.md updated;
private checkpoint utility/shared code/tests and machine audits were added as
described. Private raw checkpoints and hash-named history intentionally retained.
Batch exited;no task lock or preparation process remains. No data deleted.

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_private_date_recovery.py tests/test_partial_dates.py tests/test_cv_recovery.py tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git check-ignore evaluation/cache/ranking-payload-recovery-v1/cv_18442517.json evaluation/cache/ranking-payload-recovery-v1/cv_24964303.json evaluation/cache/ranking-payload-recovery-v1/cv_70750649.json
git diff --check
```

Live inline instrumented runner called existing prep.run with --reuse-verified-v3,
--retry-failed,data-dir C:/DATN/Datasets;service corrections and provider HTTP
retries explicitly disabled;observer persisted raw first;deterministic resolver
ran on retained response. Final read-only source/alignment/interval/profile/hash/
process audits made0 additional model calls. No durable diagnostic script or
extra Markdown report. No SQL cleanup command.

### Final Status

**BLOCKED / NOT PASS — NOT READY FOR TASK14C.2.**
3/3 reconstruction budget consumed and closed;raw payloads are safely retained.
Three deterministic alignment/chronology failures remain. Do not freeze incomplete
inputs,score a reduced dataset,guess range assignments or waive definite chronology.

## Deterministic Experience-to-Source Alignment Completion

### Initial State

92/95 CV,10/10 JD,97/100 ready;three private payloads present. All model budgets
closed. Source-read-first inspected actual record/range/role occurrence counts,
schema/chronology,existing grounding,mapper/privacy,fingerprints and private cache.
Only safe indexes,offsets,counts and evidence metrics were output;no raw source
text,company/person name,contact or provider response was printed.

Plan before implementation:generic composite local evidence and ordered one-to-one
assignment;company normalization without exact-secondary veto;repeated-role global
assignment;source-proven date correction only;replay92;synthetic tests before
real recovery;network-disabled processing;full isolated test regression;freeze
only at95/10/100 and105 audits. No per-CV production branch or weight tuning.

### Private Payload Recovery Inputs

Reused evaluation/cache/ranking-payload-recovery-v1/cv_18442517.json,
cv_24964303.json,cv_70750649.json. Each raw response and its generating provenance
remain byte-identical throughout this task. Source refs,source hash and source
archive hashes were checked before recovery. No provider instance/request was
used;socket construction and provider creation were explicitly disabled.
Recovery provenance references raw-content SHA-256 and private-checkpoint SHA-256,
not a copied response. Raw files stay private/gitignored and were not overwritten.

### Shared Alignment Design

Added app/services/cv_experience_alignment.py,reused by shared date grounding.
Rule/version:**cv-composite-monotonic-alignment-v1**. Evidence contract:
**cv-local-date-range-evidence-v2-composite**. Date contract remains
cv-date-precision-v2-source-evidence. Canonical semantic version remains
matching-canonical-v3-explicit-identity-contract;no semantic_text/fingerprint
construction change. Dates/provenance do not enter matching text.

Candidates are local role/date-range headers. Roles use normalized token phrases
with punctuation/whitespace tolerance;company token coverage strips only legal
suffixes(ltd/limited/inc/incorporated/llc/corp/corporation/co),not arbitrary company
meaning. Source body spans end at neighboring experience headers;recognized
Education/certification/project boundaries prevent cross-section date capture.
No document-wide year assignment to work items. Offset provenance refers to
casefolded/whitespace-normalized source coordinates,not original raw byte offsets.

Frozen generic score(before real3 evaluation):
6*role_coverage +2*company_coverage +3*responsibility_coverage +date_compatibility.
Each component is integer0..1000. Role coverage requires>=750 and penalizes
seniority/title-token differences. Company mismatch requires responsibility
coverage>=400;nontrivial descriptions also require>=400. Date compatibility is
weak supporting evidence,not authority overriding stronger role/context evidence.
These are alignment evidence points,NOT Semantic-v1 scores/probabilities/ranking.

Dynamic programming maximizes total evidence with increasing source offsets and
one-to-one span use. It respects document order rather than sorting dates,so a
reverse-chronological source layout is supported. Missing eligible ordered
assignment fails;it never assigns one range twice or greedily consumes nearest.
Two distinct optimal date outcomes are retained to detect ambiguity;many equivalent
paths cannot hide a third tied path with different dates. Tied different dates
fail. Equivalent-date ties may use deterministic source-offset tie-break with an
explicit status,not fabricated confidence. No algorithm selection based on labels.

This shared helper is reusable in production but remains an explicit source-grounded
post-failure recovery operation,not a newly enabled automatic mutation of every
successful production extraction. Existing production schemas/mappers validate
every recovered result. Non-experience educational date evidence retains the shared
local resolver;unique institution/local-year evidence supports explicit year
ambiguity when degree formatting differs. No absent/invalid value is forced null.

### CV 18442517 Resolution

PASS. Eight experiences map one-to-one to eight ordered source ranges. At indexes2/3,
company component0 is compensated by exact role coverage1000,responsibility
coverage1000 and date compatibility1000,with unique ordered assignment. No blind
company-veto removal or fuzzy arbitrary company assignment. Other records have
company1000. Educational local-year ambiguity validates without fabricated month/day.
All professional fields/items preserved;production mapping/privacy passes.

### CV 24964303 Resolution

PASS. Nine experiences map to nine distinct ranges. Repeated-role indexes0/1/2
are handled by the global one-to-one/document-order assignment and their distinct
responsibility spans,not first/nearest-range reuse. All chosen role/company/
responsibility/date components1000;ordered assignment unique. Education dates
validate via locally supported institution/year ambiguity where precision is not
day/month-proven. No source global-year lookup,record deletion or provider call.

### CV 70750649 Resolution

NOT PASS. All8 experiences have a unique ordered composite assignment. The remaining
domain failure is **experiences[7]**,not unresolved role/company ambiguity.
Chosen normalized source span[7595,7913],range[7612,7630],candidate7. Role/company/
responsibility/date compatibility all1000(total12000). Both source endpoints have
month precision;earliest(start)>latest(end),so ordering is definitely impossible.
Grounding reproduces the source contradiction rather than correcting it.

| Candidate | Normalized range offsets | Eligibility for experience7 | Why insufficient |
|---|---|---|---|
|0|1040–1058|false|role evidence below admission floor|
|1|2875–2893|false|role evidence below admission floor|
|2|4244–4262|false|role evidence below admission floor|
|3|5091–5109|false|role evidence below admission floor|
|4|5446–5464|false|role evidence below admission floor|
|5|6647–6665|false|role evidence below admission floor|
|6|7187–7205|false|role evidence below admission floor|
|7|7612–7630|true|source-backed month/month range violates chronology|

No alternative eligible range proves an earlier-to-later source order. This is NOT
the allowed provider-reversed/source-correct case. Swapping,weakening known month
precision into ambiguity or assigning a different role's range would manufacture
certainty. Current evidence cannot establish a chronology-safe canonical record.
More alignment scoring/model calls cannot adjudicate a contradictory source range.
No fundamental extraction-architecture rewrite is needed to diagnose this;completion
requires authoritative source adjudication or a separately authorized explicit
source-conflict representation/policy. Neither was assumed. Source/labels unchanged.

### Recovery Provenance

Accepted new CV envelopes include source hash,private raw-content/checkpoint hashes,
recovery rule/evidence version,timestamp,affected item indexes,normalized spans/
range offsets,component metrics,status and validation result. Correction category:
source_grounded_date_metadata. Raw provider payloads remain the immutable original;
recovered structured data is a separate representation. Failed70750649 retains
safe contradiction provenance with SOURCE_CHRONOLOGY_CONTRADICTION. No raw PII.

### Existing 92 Compatibility

All92 original structured/canonical payloads,canonical hashes,matching fingerprints
and source hashes equal the pre-task snapshot. Zero re-extractions/invalidations.
Profile migration explicit with hash-named backups. Final safety review hardened
third-tie detection and description evidence;replay confirms all94 current successful
payloads are unchanged and two new source-grounded outcomes reproduce exactly.
Current stored profile matches current source. No stale canonical fingerprint used.

### Final CV Coverage

**94/95 SUCCEEDED**,1 FAILED(70750649),0 pending. All95 identities retained.

### Final JD Coverage

**10/10**. Schema/source/fingerprint/privacy and mapper replay pass. No recomputation
of canonical payload or model use;only verified profile metadata migration.

### Final Privacy Audit

Supported-contact/structural checks pass for104 accepted entities(94CV+10JD).
Full105/105 is NOT achieved because one CV has no domain-valid accepted output.
This is not a universal arbitrary-prose PII/fairness certification. No raw response
key/content copied into canonical artifacts;personal_info minimized as before.

### Pair Manifest

100 original unique pairs retained,**99 ready/1 unready**. Every ready row resolves
accepted CV/JD;deterministic reconstruction equals stored manifest. No excluded
pool,manual ready flag,label modification,score or rank. Frozen=false.

### Frozen Hashes

Ground truth alone remains frozen. Current canonical hashes are PARTIAL checkpoints:

| File under evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|e9ce4ad9061d71ff551050c419ef542d80368de02f93ca370ea9b84196435c8f|
|ranking_canonical_jds.jsonl|3ccedb61e1fa3375f65ae0748a9aad57d30d8abdc4e7eaea8ca159ef043f77ee|
|ranking_canonical_pair_manifest.csv|23db667e7b6d7df556abdc3c08da3b89565ed49cc27707fae1e70db857a9c777|

### Tests

Synthetic-first alignment/private/date tests32 passed,1 warning in1.32s after fixing
a synthetic Education-boundary collision and preserving existing safe no-range
ambiguity. New tests cover aliases,role/company variations,one-to-one ranges,
reverse-chronological document ordering,partial/current dates,equivalent vs distinct
date ties(including a third alternative),Education isolation and source-proven swap
versus source contradiction. No model call in tests.

Final focused247 passed,1 warning in1.65s;evaluation138 passed,2 warnings in9.43s,
exit0. Earlier full638 passed,3 warnings in160.36s;final full after safety review:
**638 passed,3 warnings in106.73s(0:01:46),exit0**. Existing isolated gjob_db_test only,
TEST_DATABASE_URL guard,credentials in memory/redacted,no DEV fallback/new config.
Warnings are existing google-genai,Starlette/httpx and deprecated422 notices.

### Model Usage / Safety / Cleanup

**0 new Qwen/Gemini/BGE calls**. Real recovery/replay forbids socket/provider use.
No CV extraction invocation,new model generation,cloud call,DEV DB/session/SQL,
migration,frontend change,semantic score,cosine,rank or Precision@K/Recall@K/MRR/NDCG.
Source archives and frozen human ground truth remain byte-identical. Private
payloads/checkpoints/history intentionally retained;no deletion or raw diagnostic.
Only this SAME Markdown report updated;safe machine provenance added to existing
failures.json and canonical envelopes. No preparation process/lock left behind.

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_experience_alignment.py tests/test_private_date_recovery.py tests/test_partial_dates.py tests/test_cv_recovery.py tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Inline deterministic runner imports shared ground_structured_dates/production
schemas/mappers,loads private JSON+source refs/hash,blocks sockets and provider
construction,preserves originals,validates and checkpoints two successes,rebuilds
manifest/summary. Read-only candidate/interval/hash/privacy replay also ran. No
scoring command,SQL cleanup or additional Markdown file.

### Final Status

**BLOCKED / NOT PASS — NOT READY FOR TASK14C.2.**
Two remaining alignment cases resolved safely;the final source chronology conflict
cannot be normalized under current authorization. Preserve94 accepted CVs,10 JDs,
all100 pairs and immutable private responses. Do not manufacture95/95 or freeze99/100.

## Final Source Data Conflict Policy

### Decision / Source Review / Plan

User explicitly authorizes SOURCE_DATA_CONFLICT as non-fatal ONLY for uniquely
aligned/source-supported chronology that is contradictory in source itself.
Generated contradiction against correct source remains EXTRACTION_CONTRADICTION
and fails. Source/schema/mapper/replay review preceded changes. Plan:trusted
source-consistency context,explicit warning metadata,strict ordinary validation,
safe chronology-consumer boundary,replay94,recover707 only with network blocked,
tests/full isolated regression,final105/100 audit,freeze,stop before scoring.

### Shared Implementation / Normal Validation Remains Strict

app/schemas/source_date_consistency.py defines metadata and an immutable internal
VerifiedSourceConflicts capability binding dates/professional record/metadata.
app/services/cv_source_consistency.py independently re-aligns source,requires a
unique assignment and source-supported components,then validates recovered
StructuredCVExtractionResult with trusted Pydantic context. No CV-ID branch.

CVEExperience date validator still rejects reversed chronology by default.
Client/LLM-supplied warning metadata is NOT a waiver:without source-verification
context(or a previously verified in-process instance)it fails. Changed records
invalidate the binding. A valid source range cannot excuse generated reversed
chronology;the shared grounding path now raises EXTRACTION_CONTRADICTION. This
explicitly supersedes the earlier authorized source-proven-swap experiment.
No global validation guard was disabled and no ordinary chronology rule loosened.

Only verified source-conflict experience records carry date_consistency:
state=SOURCE_DATA_CONFLICT,chronology_usable=false,source-text SHA-256,normalized
range offsets,rule_version. Optional metadata is omitted when absent;all94 existing
structured/canonical payloads remain exactly equal. Canonical mapper passes this
metadata separately,not as matching text. CanonicalExperience.chronology_range
returnsNone for source conflicts;future chronology/duration consumers must use
this admission boundary/respect chronology_usable=false. No chronology-derived
matching/ranking feature was introduced;current matching does not consume dates.

Production-shared helper remains an explicit source-authorized post-failure path,
not an automatic waiver for arbitrary uploaded/builder JSON. Serialized conflicts
require source replay to regain authority. Checkpoint read_records receives source
text,verifies its ref/hash,reconstructs source proof and checks exact stored data
and mapper equivalence. Replay without source authority fails closed.

### CV70750649 / Source Preservation

Only70750649 reprocessed using unchanged raw CV source and private response.
experiences[7] aligns uniquely to normalized source range[7612,7630],span[7595,7913].
Both source endpoints have month precision and reversed chronology. The recovered
representation preserves those exact month-level values/order and marks the
source conflict;no swap,null,date invention,section deletion or source edit.
Original provider response remains byte-identical in its private checkpoint.

The raw provider had day-level dates whereas source proves month precision;
year/month components match. Prior source-grounding projects to the actual source
precision without claiming the raw extra day was verified. The warning applies
to the faithful SOURCE-GROUNDED representation,not a false claim of verified raw
day precision. No fabricated day is retained in the canonical conflict range.

Exactly1 warning recorded. Professional role/company/responsibilities/skills and
descriptions remain available. Warning/date metadata do not enter semantic_text.
Fingerprint version remains matching-canonical-v3-explicit-identity-contract;
only source consistency/validation contract cv-source-date-consistency-v1 was added
to profile/source-code hashes. No embedding/matching cache version bump needed.

### Compatibility / Provenance / Final Audit

All94 prior successful structured_result/canonical_input/source hash/canonical
hash/matching fingerprint values equal the pre-policy snapshot. No re-extraction
or model call for them. Explicit profile migration preserved hash-named history.
10 JDs replay identically. New707 metadata/provenance records source/hash/private
payload hash,recovery rule,index7,warning state,source offsets and validation status.
No raw response copied into public/frozen accepted artifacts. All private payloads
and source/ground-truth files unchanged;no deletion.

Final95/95 CV models and10/10 JD models pass exact source/ref/hash/profile/fingerprint/
mapper replay. Supported-contact and structural identity-exclusion audits PASS:
**105/105**. This is scoped supported-identifier/structural privacy verification,
not universal arbitrary-prose PII/fairness certification. Manifest reconstruction
equals stored100 unique rows;**100/100 ready**,all CV/JD refs resolve. No label/reason/
pool membership modification.105 audit includes the conflict record as professional
matching-valid,not chronology-valid.

### Frozen Official Hashes

All three canonical artifacts frozen only AFTER full tests and complete audits.
summary.json statusPASS,frozen=true,ready_for_task_14c2=true. Official paths/hashes:

| File under C:/DATN/GJobBackend/evaluation/data/derived | SHA-256 |
|---|---|
|ranking_pairs_labeled.csv|a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d|
|ranking_canonical_cvs.jsonl|0a7da44fde0cde5f0ff45259093bb7f194cbc40bea502bf02c50bfe66682f615|
|ranking_canonical_jds.jsonl|9da55f0731adf98c1c7aefe7072759effc04816f6568ddee9caef9f1e14fedc1|
|ranking_canonical_pair_manifest.csv|cd715793e5ba37272d7cd1b82847f58e78879b1aaaf2577efab1c520f1ae92b9|

### Tests / Final Verification

- Policy/date/private/alignment tests:36 passed,1 warning in1.38s.
- Focused extraction/providers/source consistency/alignment/privacy/input/embedding:
  **251 passed,1 warning in1.72s**,exit0.
- Evaluation regression:**138 passed,2 warnings in6.36s**,exit0.
- Final chronology feature-boundary tests:4 passed,1 warning in1.12s.
- **Full pytest:642 passed,3 warnings in105.40s(0:01:45),exit0.** Existing guarded
  gjob_db_test only,TEST_DATABASE_URL resolved in memory/redacted output,no DEV.
- Frozen-loader replay verifies official hashes/current profile/source-conflict
  authority and all95/10 with provider construction,DNS,external connect/sendto
  denied:PASS,"Already frozen;no provider calls."

Tests explicitly cover A source-correct/generated-reversed FAIL,B faithful reversed
source warning without swap/null,C normal valid unchanged,D partial overlap unchanged,
E conflict excluded from chronology accessor/matching signal. Forged warning/context
on changed professional record fails. Historical tests were updated only for the
user's new A-policy semantics,not to conceal unrelated regressions. All pytest
providers mocked;no live provider/DEV DB. Existing google-genai/Starlette/httpx/
deprecated422 warnings only.

The first frozen async harness blocked Windows loop initialization;the next replaced
socket type and triggered a self-pipe type warning. Neither changed artifacts or
called a provider. Final clean harness initializes the local Windows loop first,
retains socket type and forbids provider/DNS/connect/sendto;read-only replay passes
without that error. This is harness handling,not a relaxed network/model guard.

### Safety / Commands / Cleanup

**New model calls0(Qwen/Gemini/BGE).** Recovery used raw source/private payload/
shared deterministic code only,network/provider denied. No DEV session/SQL/write,
migration,frontend change,new test DB/config,cloud fallback,embedding/cosine/semantic
score,rank or Precision@K/Recall@K/MRR/NDCG. Existing semantic matcher/mapper text
policy remains unchanged. No secret/PII/raw source/provider content in report.
Private cache stays gitignored;sourceConflict metadata contains only hashes/offsets.
No task process/lock,temporary raw copy or manual DB cleanup required.

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_source_date_consistency.py tests/test_experience_alignment.py tests/test_private_date_recovery.py tests/test_partial_dates.py tests/test_cv_recovery.py tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Additional inline socket/provider-disabled source replay and recovery used
validate_source_grounded,production schemas/mappers,strict read_records with source
texts;official frozen-loader replay used existing prep.run. Full suite launched in
a guarded secret-redacted child process on existing test DB. No URL/password printed.
No scoring/SQL cleanup/model command. Only this SAME Markdown report updated;
summary.json/failures.json and accepted canonical/provenance outputs finalized.

### Final Status / Handoff

**TASK14C.1.5 FINAL STATUS:PASS.**95/95 CV,10/10 JD,100/100 ready,105/105 audit;
1 source chronology conflict preserved non-fatally and excluded from chronology
interpretation.0 new model calls. Frozen source-consistency replay requires raw
source refs/hashes for the warning record;do not strip warning metadata or interpret
its range as clean duration. No Semantic-v1 scoring was performed.

**READY FOR TASK14C.2 SEMANTIC-V1 RANKING SCORING.**
