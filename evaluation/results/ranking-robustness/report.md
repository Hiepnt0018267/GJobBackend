# Task 14C.5 Ranking Robustness / Edge Cases

## 1. Status

**PASS WITH LIMITATIONS after minimal correctness fixes; not a robustness guarantee.**
Synthetic semantic sensitivity measured with21/22 authorized BGE requests.
Cache-shape/snapshot-integrity/duplicate-boundary bugs reproduced BEFORE fixes and
regressed afterward. No model/cosine/threshold/sort-policy tuning. Full pytest:
**727 passed,3 warnings in202.97s (0:03:22)**,exit0. Proxy/noise/generic-JD and
persistent-PENDING risks remain, not declared fixed.

## 2. Objective

Stress the current frozen Semantic-v1 representation/provider/formula and recruiter
cache/status/order/pagination controls. Distinguish semantic sensitivity from clear
integration correctness bugs. No new benchmark competition, relevance labels,
fairness conclusion or Task14C.6 policy decision.

## 3. Frozen Production Configuration

sort=ai_match opt-in; default created_at DESC,id DESC unchanged. Semantic-v1/BGE-M3,
ctx8192,batch4096,truncate=false,raw cosine; no score threshold/hide/reject/shortlist/
hire/notification. Canonical matching-canonical-v3-explicit-identity-contract.
Profile fingerprint bcfd85c8e892993fa3111882be45f8beb92a610d191edb4455abb2aed0a908cc.
Model digest7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab,
verified before/after. Actual runner c8192,b4096,ub4096,np1 verified against loaded
model path. No override,context/batch increase,truncation,model/server/OS/env change.

## 4. Test Strategy

Reviewed ranking/cache/precompute/readiness/routers/repository/schema/canonical/
privacy/semantic/provider/profile/fingerprint and 14C.3/14C.4 tests; retained14C.2
USEFUL BUT INCONSISTENT evidence (P1=.70,P3=.6333,MRR=.825,NDCG10=.8069).
Plan and fixed recipe/flags/budget persisted before live requests.
Reference backend CV/JD plus fixed frontend-transfer and gardening controls.
Each CV variant replaces only the reference slot; controls stay constant. JD
variants score the same three reference CVs. Exact ties retain fixed default
application slot order reference,transfer,unrelated. No outcome-driven case search.

Frozen diagnostic-only flags: |Δcosine|>=.05 or |Δrank|>=2; near-gap<=.00001 excluding
exact ties. Arbitrary descriptive thresholds, NOT production eligibility policy.
Keyword1x/5x/20x,proxy20x,one duplicated experience. Tokenizer-only binary search
chooses long<=3950 total tokens and deliberate overflow>=4250 before affected
vectors/results; model scores never influence fixture construction.
Maximum22 sequential embed requests,no retries/cloud/Qwen/Gemini. Unexpected
provider/profile/digest/tokenizer error stops; one expected overflow rejection allowed.
Started marker refuses rerun; successful private vectors prevent redundant inference.
Only synthetic data; no frozen real-case perturbation/relabeling. Operational failures
use mocks, not deliberate outage of the shared Ollama server.

## 5. Synthetic Case Inventory

22 counted canonical identities:17CV fixtures including identity duplicate and
overflow;5JDs.21 unique embedding texts (identity duplicate shares input).
Classes covered: short/long/sparse/keyword/proxy-location/school/employer/language/
noise/duplicate CV;short/long/noisy/generic JD;exact/near ties;missing/stale/legacy/
provider/precompute states;pending completion/new arrival/snapshot corruption;
identity invariance;0/1/100/all-pending/all-tied pools;shared CV across jobs;API invalid
parameters/authorization/filter/N. Machine inventory/scores/findings/protocol are
consolidated in robustness_metrics.json; no raw CV/JD dump or extra Markdown/CSV.

## 6. Input Length Robustness

Native SAME loaded BGE /tokenize(add_special=true),not chars/4 or an unrelated tokenizer.
ReferenceCV74tokens;shortCV7;sparseCV18. Very-longCV3928tokens/19384characters and
JD3919tokens/19286characters accepted with full unchanged text. Native tokenizer
construction is counted separately from embeddings; exact token-ID lists never saved.
One explicit overflowCV4271tokens/21082characters (>4096,<8192) rejected by
EmbeddingInputTooLongError; no vector accepted/cached for it. No repeat/increased cap.
Production precompute mock confirms ERROR/null and applicant remains visible.
truncate=false request/code path and explicit overflow refusal support no intentional
silent truncation; no claim of an independently decoded encoder-content audit.

## 7. Sparse / Generic Input Behavior

ShortCV cosine.545208 and sparseCV.651272 versus reference.927614; both finite/rankable,
move1→2 in three-slot pool. They lose professional detail, so this is not a causal
length-only effect or proof of poor suitability. Generic JD reverses reference order;
no new human gold labels or automatic rejection imposed.

## 8. Keyword Stuffing

Reference.927614;1x=.925884,5x=.911572,20x=.893049.
Scores decrease monotonically; deltas-.001730,-.016042,-.034565; rank stays1.
No material flag under the predefined.05/2 rule. This reference starts at rank1,
so a rank-gain ceiling applies. No stuffing advantage observed HERE, not proof of
universal resistance or an irrelevant-stuffed-CV ranking study. No anti-keyword penalty.

## 9. Duplicate Content Sensitivity

Duplicated experience adds no new facts:cosine.926213,Δ-.001401,rank1 unchanged.
No material flag. Dedicated skill normalization still deduplicates names; experiment
duplicates actual experience narrative, not merely already-deduplicated skill fields.
No deduplication/model mitigation added after results.

## 10. Proxy-Heavy Text Sensitivity

Repeated public school/employer names and location/language mentions were placed
in allowed synthetic prose,not identity metadata. They reduce score by.0643..0859;
all preserve reference rank1. Four MATERIAL_SCORE_SHIFT/PROXY_TEXT_SENSITIVITY flags.
These manipulate both prominence and redundant narrative density; they do not
isolate prestige/geography causally or establish protected-class discrimination.
No real candidate PII/demographic inference or automatic proxy stripping.

| CV case | Total tokens | Cosine | Δcosine | Rank before → after | Diagnostic flags |
|---|---:|---:|---:|---|---|
| REFERENCE_CV | 74 | 0.927614 | 0.000000 | 1 → 1 | none |
| VERY_SHORT_CV | 7 | 0.545208 | -0.382406 | 1 → 2 | MATERIAL_SCORE_SHIFT |
| SPARSE_CV | 18 | 0.651272 | -0.276342 | 1 → 2 | MATERIAL_SCORE_SHIFT |
| KEYWORD_STUFFED_1X | 82 | 0.925884 | -0.001730 | 1 → 1 | none |
| KEYWORD_STUFFED_5X | 114 | 0.911572 | -0.016042 | 1 → 1 | none |
| KEYWORD_STUFFED_20X | 234 | 0.893049 | -0.034565 | 1 → 1 | none |
| DUPLICATED_SECTION_CV | 114 | 0.926213 | -0.001401 | 1 → 1 | none |
| LOCATION_HEAVY_CV | 134 | 0.853609 | -0.074004 | 1 → 1 | MATERIAL_SCORE_SHIFT, PROXY_TEXT_SENSITIVITY |
| SCHOOL_PRESTIGE_HEAVY_CV | 154 | 0.841695 | -0.085919 | 1 → 1 | MATERIAL_SCORE_SHIFT, PROXY_TEXT_SENSITIVITY |
| EMPLOYER_PRESTIGE_HEAVY_CV | 114 | 0.859112 | -0.068502 | 1 → 1 | MATERIAL_SCORE_SHIFT, PROXY_TEXT_SENSITIVITY |
| LANGUAGE_HEAVY_CV | 154 | 0.863318 | -0.064296 | 1 → 1 | MATERIAL_SCORE_SHIFT, PROXY_TEXT_SENSITIVITY |
| NOISY_CV | 414 | 0.830928 | -0.096686 | 1 → 1 | MATERIAL_SCORE_SHIFT, NOISE_SENSITIVITY |
| IDENTITY_VARIANT | 74 | 0.927614 | 0.000000 | 1 → 1 | none |
| VERY_LONG_CV | 3928 | 0.728939 | -0.198675 | 1 → 1 | MATERIAL_SCORE_SHIFT |

## 11. Noise Robustness

Generic soft skills/headings/format artifacts appended to referenceCV:
.830928,Δ-.096686,rank1 unchanged,MATERIAL_SCORE_SHIFT/NOISE_SENSITIVITY.
Noise changes score materially under diagnostic rule but does not change this pool's
winner. No learned noise correction or sanitization policy tweak.

## 12. JD Robustness

| JD case | Total tokens | Reference/transfer/unrelated cosines | Ranks | Spread |
|---|---:|---|---|---:|
| REFERENCE |74|.927614/.707676/.531033|1/2/3|.396581|
| VERY_SHORT |26|.643515/.638197/.526427|1/2/3|.117088|
| GENERIC |41|.522810/.541998/.579485|3/2/1|.056675|
| NOISY |354|.883451/.675035/.498271|1/2/3|.385180|
| VERY_LONG |3919|.668001/.568232/.433480|1/2/3|.234521|

Short/generic concentrate scores; generic swaps best/worst slots by2 positions and
flags MATERIAL_RANK_SHIFT. No measured exact ties or pairs within frozen1e-5 near-gap.
Very-long JD and referenceCV changes flag material score shift; noisyJD deltas
stay below.05. Long CV/JD use repeated generic professional filler, changing content
mix as well as length: not a controlled length-only causal estimate. Unknown live
recruiter usefulness remains; scores are not probabilities/calibrated across JDs.

## 13. Tie / Near-Tie Stability

Mock exact/all-equal scores retain default safe time/ID order and identity invariance.
.700000/.699999/.699998 sorted full-precision DESC; no jitter or rounding tie trick.
Repeated snapshot views preserve order. Equal-content identity variant reuses exact
input/vector and has exactly same reference score,not a second independent model run.

## 14. Ranking Precision / Serialization Stability

Sorting uses raw cosine,not rounded display values. Synthetic JSON round-trip preserves
.7 and.699999 order/N boundary. NaN/nonfinite values never accepted as valid scores.
New snapshot guard checks finite[-1,1] intrinsic cosine domain,not an eligibility
threshold; it rejects corrupt metadata with409 rather than scoring/hiding a candidate.

## 15. Missing Embedding / PENDING

PENDING/UNAVAILABLE/ERROR retain null score/rank and remain visible behind ranked rows
in frozen fallback order. All-pending0/1/100 cases return valid metadata/full set.
Held lease prevents duplicate generation without silently declaring ready; state can
persist until operator/lifecycle work. No duration monitoring or new backfill/retry SLA.

## 16. Legacy / Profile Mismatch

Existing profile/digest tests and injected legacy canonical identity prove stale
vectors not reused; PENDING/null still visible. Missing usable uploaded representation
is UNAVAILABLE,not fake0. Existing canonical source-conflict/identity regressions pass;
no raw-text/extraction fallback or old evaluation vector reuse.

## 17. Provider Failure

Mock failed precompute records ERROR,null; subsequent explicitly invoked bounded
precompute succeeds and unchanged success hits cache with zero redundant requests.
List never invokes provider/extraction; compatible cached signals remain usable.
Lifecycle session/commit-isolation regression retained; no list status/business write.
No artificial shutdown of shared provider or cloud fallback.

## 18. Cache Safety

Pre-fix stress: nonobject vector-cache JSON caused AttributeError; malformed missing
identity was classified PENDING rather than safe corrupt-record ERROR. Added dict/
identity/status guards; invalid records now ERROR/null, mismatch identity stays miss.
No production vector deletion/relabeling or cache namespace/profile tuning.
Synthetic private storage remains trusted for valid but semantically incorrect vectors;
shape/finite validation is not cryptographic authentication of arbitrary disk tampering.

## 19. Invalid Vector Safety

Wrong dimension,zero norm,NaN,Inf,bool components rejected safely; no invalid cosine
or NaN sorting. Existing vector provider validation and unchanged cosine reused.
Actual overflow response yields no hidden partial vector. Model-quality limitations
are separate from invalid-data handling; no numerical formula alteration.

## 20. Pagination / Snapshot Stability

Existing PENDING→RANKED test: same snapshot freezes original order/status; no duplicate/
skip across four pages; fresh snapshot observes new rank. New arrival/status/canonical/
profile changes invalidate old traversal with409; fresh page1 includes updated set.
TTL/binding semantics retained. No page-local sort or silently restarted traversal.

Pre-fix injected corruption accepted duplicate/unknown IDs/bad rank/state/score, or
non-list body crashed. Whole-snapshot validation now checks count,owned current IDs,
uniqueness,state,nullability,finite score,rank sequence and deterministic ordering
BEFORE page slice; invalid manifests return409. Duplicate service-boundary application
IDs now409 rather than duplicate response. Normal ORM query was not observed yielding
duplicates; this is defensive boundary integrity,not new candidate exclusion.
Valid historical snapshots remain compatible.

## 21. Result Limit / Filter Interaction

Full logical set beforeN/page. Near-tie N boundary remains exact. Pending completion
does not change old N snapshot; fresh snapshot may change TopN. Fewer thanN returns all.
Real guarded API tests verify positive search selecting one applicant before rank,
status/search empty sets,full17/paging/explicitN and unchanged statuses.
Existing endpoint supports status/search/job filters,not a date filter; no fabricated
date-filter test or new API added. Invalid sort,N0/Nnegative,page0,page_size101,bad token
return422 with no AI work. Missing later-page token follows existing422.

## 22. Authorization

Role and owned-job checks precede AI. Unauthorized/nonexistent job returns existing404
without ranking/cache/provider work. Snapshot owner binding tested. No candidate-data
leakage or provider-internal error output. No API permission expansion/new endpoint.

## 23. Performance / Scale

Mock100 applicants:101unique entity vector lookups (100CV+1JD),100 output rows,
linear per-applicant cosine loop plus O(NlogN) sort. SharedCV across two jobs:
oneCV/twoJD lookups,independent cosines1 and0,no pairwise score leakage.
SQL eager/batch loading regression remains<=8queries for17 applicants. New snapshot
guard is O(NlogN),not quadratic. These are instrumentation/code complexity checks,
not a production throughput benchmark; runtime varied with local/testDB conditions.

## 24. Identity Invariance Regression

Changed synthetic name/email/phone/address/photo metadata yields identical canonical
semantic input and fingerprint,not demographic labels. Real experiment identity
variant uses one cache hit,scoreΔ0/rankΔ0. Existing14C.4 guarded tests and mock semantic
invariance retained. No universal claim about sensitive prose or model fairness.

## 25. Findings

| Finding | Severity / status | Evidence | Production impact / next step |
|---|---|---|---|
| R1 malformed cache payload | HIGH,correctness FIXED | pre-fix AttributeError; guarded shape/status now ERROR | safe fallback,retain regression |
| R2 corrupt snapshot | HIGH,correctness FIXED | incomplete/invalid manifests accepted or crashed | whole traversal validation/409,retain regression |
| R3 duplicate boundary row | MEDIUM,defensive FIXED | injected row duplicated output | reject inconsistent input;normal ORM duplication not observed |
| R4 proxy prose density | MEDIUM,NOT TUNED | four shifts-.0643..0859,rank stable | future input-warning/robustness work,not demographic claim |
| R5 generic JD | MEDIUM,NOT TUNED | reference/control order1/2/3→3/2/1 | warn about weak job signal in14C.6 |
| R6 noise/sparse/long mix | MEDIUM,NOT TUNED | score shifts,content/length confounded | limits/interpretation,not calibrated penalties |
| R7 persistent PENDING | MEDIUM,NOT FIXED | best-effort hooks/no backfill/SLA,held-lease simulation | consider monitoring/recoverability later |
| R8 repetition here | LOW,limited observation | keyword scores decrease;duplicateΔ-.0014 | no broad anti-stuffing guarantee |

Pre-fix focused run:10failed/14passed in1.48s. Post-fix regressions pass. Only two
production files changed: ranking_cache.py and applicant_ranking_service.py.
No unsafe HIGH finding silently waived; no semantic sensitivity declared fixed.

## 26. Known Limitations

Single synthetic backend reference and two controls,not real-world prevalence or a
new labeled benchmark. Three-slot rank ceiling/limited distractors; public-organization
prominence not an experimentally validated prestige hierarchy. Long prose includes
repetition/content dilution; no isolated causal effect. No extraction fidelity/live
recruiter behavior study,demographic fairness,score calibration or runtime/model-reload
repeatability certification. One deliberate overflow case. Mocks verify operational
contracts,not all server/hardware failures. PENDING durability/access risks remain.
No benchmark optimism/tuning or reduced-pool replacement of14C.2.

## 27. Recommendations for 14C.6

Carry14C.2 quality,14C.3 integration,14C.4 fairness limits,and all above findings into
FINAL RANKING POLICY FREEZE. Decide explicitly on opt-in/full-list/availability order/
raw-score exposure,warnings and monitoring; do not infer approval for policy changes
from this task. Include weak/genericJD and sparse/noisy/proxy narratives,409 restart
UX,cache integrity/recovery and PENDING/backfill monitoring. No thresholds,feature
stripping,anti-keyword penalties or final product policy chosen here.

## 28. Tests

Before live:60passed,1warning in2.09s (recipe + operational/ranking/fairness mocks).
Final focused including embedding/semantic safety: **135passed,1warning in2.35s**.
Evaluation: **151passed,2warnings in7.30s**.
Full guarded: **727passed,3warnings in202.97s (0:03:22)**,exit0.
Warnings existing google-genai,Starlette/httpx and deprecatedHTTP422.
Initial failures preserved in section25. Automated tests use synthetic/mock providers.
A test-append placement mistake was corrected before execution; no fixture/data loss.
No tests relaxed to accept unsafe cache/snapshot or alter model outcomes.

## 29. Model / DB Safety

21actual /api/embed requests:20successful unique vectors +1explicit overflow failure.
1identity vector cache hit;21attempted cache misses include failure. CLI experiment
runtime52.886117s includes tokenization/profile/loading;not pure inference latency.
Native tokenizer/model metadata requests are NOT embedding calls and were not counted
as generations; exact read-only HTTP total was not instrumented. Budget22,no retries.
Qwen/Gemini0. Synthetic model input only,no realCV/JD/PII or demographic inference.
Separate ignored evaluation/cache/ranking-robustness-v1,not production/14C.2 cache.

Experiment noDB access. Tests existing guarded gjob_db_test only via TEST_DATABASE_URL/
current_database guard,normal migration fixtures,secret-redacted child environment.
No DEV connection/write,newDB/config/env,migration,frontend or OS/server change.
146preexisting protected files byte-identical,including frozen ground/canonical/
14C.2 scores/reports and previous audit reports;only the two named safety-source files
changed. Semantic core unchanged SHA
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.
No label/reason/source/benchmark modifications.

## 30. Cleanup

Synthetic temp cache fixtures clean themselves; new API principal and existing owned
application/CV/job fixtures use scoped FK-safe cleanup on testDB. No DEV records touched.
Retain20private experiment vectors,protocol/started/completed/count inventory/progress
for reproducibility; no raw text in these caches. No live retry/task process remains.
Shared Ollama server/model was not stopped. No real dataset/cache/benchmark deleted.
Only one new Markdown report and consolidated metricsJSON; no extra notes/summaryMD.

## 31. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_ranking_robustness.py -q --tb=short
venv\Scripts\python.exe -m pytest --noconftest evaluation/tests/test_robustness_recipe.py tests/test_ranking_robustness.py tests/test_applicant_ranking.py tests/test_ranking_fairness_guards.py -q --tb=short
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_ranking_robustness --cache-root evaluation/cache/ranking-robustness-v1
venv\Scripts\python.exe -m pytest --noconftest evaluation/tests/test_robustness_recipe.py tests/test_ranking_robustness.py tests/test_applicant_ranking.py tests/test_ranking_fairness_guards.py tests/embeddings tests/test_semantic_matching.py -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Full suite launched in guarded in-memory child environment using existing test/Docker
credentials;no connection string/password recorded. Read-only source/hash/cache-count/
local tags/show/props/numeric runner flag/tokenizer checks also performed by the frozen
runner. ResultsJSON/report authored via apply_patch from saved measurements. No real
benchmark runner,unapproved extra embedding,retry,SQL cleanup outside test fixtures,
new extraction,cloud call or production cache warmup.

## 32. Final Status

**PASS WITH LIMITATIONS.** Safe operational guards/regression verified after minimal
correctness fixes. Proxy/noise/generic-JD sensitivities and persistentPENDING remain
evidence for14C.6,not hidden/tuned away. Production opt-in/no-threshold/human-control
policy preserved. No claim of universally robust or fair ranking.

**READY FOR TASK 14C.6**

**FINAL RANKING POLICY FREEZE**
