# Task 14C.2 Semantic-v1 Ranking Evaluation

## 1. Status

**PASS execution/integrity/regression. Research assessment:USEFUL BUT INCONSISTENT.**
All100 pairs scored and fully ranked across10 jobs with unchanged production
Semantic-v1 and frozen canonical inputs. Shared physical-batch fix passed sanity
and105-input exact-token guard. No post-result tuning,threshold/hide/reject rule,
baseline/hybrid competition or automatic production integration.

Key results:P@1=0.700000,P@3=0.633333,MRR=0.825000,NDCG@10=0.806903.
7/10 jobs have a relevant Top1,3 do not;4 grade2 candidates remain belowTop5.
Small constructed benchmark does not establish autonomous recruitment suitability.

## 2. Objective

Answer:when a recruiter has multiple valid applicants for one job,does production
Semantic-v1 put more relevant applicants above less relevant ones? Plan/source
review preceded scoring:verify4 frozen hashes/source/profile/privacy;load exact
canonical models;cache105 embeddings;production match on label-free identities;
freeze scores then full ranks;join grades;fixed macro metrics/error/job bootstrap/
random sanity;stored-score replay;one report. No algorithm optimization.

Inspected production semantic/cosine,embedding provider/factory/settings/profile,
persistence-cache freshness,canonical loader/mapper/fingerprints/source-conflict
policy,old semantic runner/cache utilities,metric/distribution/atomic writers.
Reused safe utilities,NOT Task14B raw-text adapter/context-only offline provider.

## 3. Frozen Inputs

All paths below relative to C:/DATN/GJobBackend;hashes verified before/after live
scoring and final replay. Original human grades/reasons,pools and canonical inputs
unchanged. Canonical-v3/source-verified nonfatal chronology metadata intact.

| Path | SHA-256 |
|---|---|
| evaluation\data\derived\ranking_canonical_cvs.jsonl | 0a7da44fde0cde5f0ff45259093bb7f194cbc40bea502bf02c50bfe66682f615 |
| evaluation\data\derived\ranking_canonical_jds.jsonl | 9da55f0731adf98c1c7aefe7072759effc04816f6568ddee9caef9f1e14fedc1 |
| evaluation\data\derived\ranking_canonical_pair_manifest.csv | cd715793e5ba37272d7cd1b82847f58e78879b1aaaf2577efab1c520f1ae92b9 |
| evaluation\data\derived\ranking_pairs_labeled.csv | a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d |

## 4. Coverage Verification

100 unique pairs,10 cases/jobs,10 candidates/case,95 unique CVs,10 JDs.
Manifest100/100 ready;source refs/hash/profile/Pydantic/mapper/fingerprints/privacy
replayed;no duplicate CV in pool,no missing ref,no dropped pool. All100 finite
scores/ranks;each job ranks1..10 exactly. Human grades0=54,1=32,2=14.
Every pool has grade0 and grade>=1;6/10 have no grade2 and remain in all primary
metrics. One source chronology conflict is not eligibility/ranking evidence.

## 5. Semantic-v1 Configuration

Exact production SemanticMatchingService.match() receives full canonical models
and a cache implementing the same EmbeddingProvider contract. It calls embed_many
for ordered CV/JD text and existing cosine_similarity;raw cosine
dot(CV,JD)/(norm(CV)*norm(JD)). No score transform/calibration/probability,
threshold,bonus,weight/rank optimization,pooling or client vector normalization.

Semantic core unchanged:
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.
BGE modelbge-m3(Ollama responsebge-m3),1024 dimensions,Ollama0.34.2.
Digest7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab.
Canonical versionmatching-canonical-v3-explicit-identity-contract.

Production/evaluation use SAME get_embedding_provider factory. Shared profile
full-input-context-batch-v2:ctx8192,batch4096,truncatefalse,vector_postprocessingnone.
Fingerprintbcfd85c8e892993fa3111882be45f8beb92a610d191edb4455abb2aed0a908cc.
New profile/provider code hash/request identity frozen before scoring;no model/
text/cosine/metric changes. Existing server/provider normalization unchanged.

## 6. Embedding / Cache Usage

**95 CV+10 JD=105 unique texts/vectors;0 hits/105 misses in NEW profile.**
105 successful embedding calls,including blocker sanity ONCE reused from memory.
Every vector validated finite,nonzero,1024-dimensional;model/provider metadata
consistent. No duplicate calls for the5 CV identities reused across jobs.
Runtime69.487782s includes identity/preload/exact-token gate and100 cached pair
scores,not random-simulation/report time. No rerun embedding for replay.

Private cache:evaluation/cache/ranking-semantic-v1-ctx8192-batch4096-v2.
Keys bind model/digest/provider/version/shared profile/fingerprint,request options,
canonical fingerprint/version,text SHA,core hashes. No plaintext source in cache.
Old4096 cache21 vectors and8192-only cache0 vectors retained,NOT relabeled/reused.
Raw structured diagnostic checkpoints stay private,not ranking artifacts.

Private protocol.json freezes original metric POLICY,hashes,embedding identity and
evaluation code hashes. scores.json freezes100 label-free scores. Its presence
allows score/rank replay without new embeddings. Public outputs refuse silent
overwrite. Restart/resume must retain compatible model/profile/text/fingerprints.
Backend process needs reload/restart for shared config;no OS/server setting changed.

## 7. Frozen Evaluation Policy

Original14C.2 POLICY verified byte-equivalent as data against the original protocol;
only authorized embedding capacity/profile changed.

- Primary relevant=human grade>=1;P/R K=1,3,5.
- NDCG grades0/1/2,gain2^grade-1,discountlog2(rank+1),K=1,3,5,10.
- RR first relevant rank in FULL list;MRR macro across10 jobs.
- Sort ALL10 by raw scoreDESC,pair_idASC;no jitter/label-sensitive tie-break.
- Macro query means,not pooled candidate micro averages.
- Undefined zero-relevant denominators explicit;real primary pools all positive.
- Strict grade2 secondary only;zero-grade2 queries undefined,not zero-averaged.
- Bootstrap1000 JOB resamples,seed42;random sanity10000 within-job shuffles,seed42.
- Error predicates fixed before outcomes;deep inversion=grade0 at least3 ranks
  above at least2 grade1 items. No predicate/metric change after results.

Scoring API accepts exactly case/job/CV/pair IDs plus canonical models. Human grade/
reason absent;grades joined ONLY after complete stored scores/full ranks. Source
chronology conflict metadata not text/score input. No raw CV/JD adapter.

## 8. Production Result Count Policy

No explicit recruiter limit:return FULL ranked valid applicant list.
Explicit requestedN:rank all,then take firstN(or all when fewer available).
Eligibility is business/application validity,never score threshold.
No auto-hide/reject/suitable classification;recruiter final decision-maker.
K1/3/5/10 are OFFLINE EVALUATION CUT-OFFS ONLY,not production limits.
No endpoint/recruiter API/frontend integration in this task.

## 9. Main Ranking Metrics

Macro means by10 jobs,full precision in metrics.json;display rounded6 decimals.

| Metric | Result |
|---|---:|
| precision@1 | 0.700000 |
| precision@3 | 0.633333 |
| precision@5 | 0.580000 |
| recall@1 | 0.130278 |
| recall@3 | 0.497500 |
| recall@5 | 0.684722 |
| mrr | 0.825000 |
| ndcg@1 | 0.700000 |
| ndcg@3 | 0.674420 |
| ndcg@5 | 0.696074 |
| ndcg@10 | 0.806903 |

P@1 is relevance-under-this-rubric,NOT probability of candidate/job suitability.
Macro recall differs from pooled candidate recall;no post-hoc threshold.

## 10. Top-K Grade Composition

Counts over10 jobs;rates are proportions of10/30/50 slots.

| Cutoff | Grade0 count(rate) | Grade1 count(rate) | Grade2 count(rate) |
|---|---:|---:|---:|
| Top-1 | 3 (0.300000) | 4 (0.400000) | 3 (0.300000) |
| Top-3 | 11 (0.366667) | 13 (0.433333) | 6 (0.200000) |
| Top-5 | 21 (0.420000) | 19 (0.380000) | 10 (0.200000) |

Top1 relevant7/10,strong grade2 atTop1=3/10. Top3 has11 grade0/30(36.67%);
Top5 has21 grade0/50(42%).17 of46 relevant candidates are belowTop5.
These observations do NOT authorize hiding the lower half of applicants.

## 11. Full-List Ranking Quality

NDCG@10=0.806903;54 graded inversions(lower grade above higher grade) across pools.
11 grade0-above-grade2 pair inversions;9 deep-list inversion comparison events.
All10 applicants retained per query,including17 relevant belowTop5.
Strong candidates belowTop5:4(rank6,7,6,10);8 grade2 candidates belowTop3.

NDCG's ideal grade-sorted ordering is an upper-bound metric reference,NOT a
production algorithm. Binary ideal attainable P@3 varies by relevant prevalence:
jobs with only1 relevant can achieve at most1/3. Per-job P variation must be read
with pool composition/recall/NDCG,not blamed entirely on model quality.

## 12. Per-Job Results

All10 candidates included. Counts n/rel/g2 shown;no raw source/PII.
Full details,strict diagnostics/grade distributions/inversions in metrics.json.

| ranking_case_id | job_id | candidate_count | relevant_count | grade2_count | precision@1 | precision@3 | precision@5 | recall@1 | recall@3 | recall@5 | first_relevant_rank | reciprocal_rank | ndcg@1 | ndcg@3 | ndcg@5 | ndcg@10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rank_job_030b49989e9b03838e88 | 3693065853 | 10 | 1 | 0 | 0.000000 | 0.333333 | 0.200000 | 0.000000 | 1.000000 | 1.000000 | 2 | 0.500000 | 0.000000 | 0.630930 | 0.630930 | 0.630930 |
| rank_job_047e1ee49c4462d5f0cf | 3693589224 | 10 | 3 | 0 | 1.000000 | 0.666667 | 0.400000 | 0.333333 | 0.666667 | 0.666667 | 1 | 1.000000 | 1.000000 | 0.703918 | 0.703918 | 0.860344 |
| rank_job_7616538cc926787a2a85 | 3693046701 | 10 | 6 | 4 | 1.000000 | 1.000000 | 1.000000 | 0.166667 | 0.500000 | 0.833333 | 1 | 1.000000 | 1.000000 | 0.802612 | 0.939523 | 0.942079 |
| rank_job_86256e7f060ccec6b807 | 3693045435 | 10 | 8 | 0 | 1.000000 | 1.000000 | 1.000000 | 0.125000 | 0.375000 | 0.625000 | 1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| rank_job_89fd797f815313096a1d | 3701321399 | 10 | 6 | 0 | 1.000000 | 1.000000 | 0.800000 | 0.166667 | 0.500000 | 0.666667 | 1 | 1.000000 | 1.000000 | 1.000000 | 0.853932 | 0.970544 |
| rank_job_a860f9c853a4d145a149 | 3697399507 | 10 | 9 | 5 | 1.000000 | 1.000000 | 1.000000 | 0.111111 | 0.333333 | 0.555556 | 1 | 1.000000 | 1.000000 | 0.802612 | 0.769872 | 0.932730 |
| rank_job_ba1101c8423ea2bdc5c7 | 3699411457 | 10 | 2 | 1 | 0.000000 | 0.000000 | 0.200000 | 0.000000 | 0.000000 | 0.500000 | 4 | 0.250000 | 0.000000 | 0.000000 | 0.355840 | 0.453943 |
| rank_job_bfeea8a8b8995516cb3e | 3699410505 | 10 | 1 | 0 | 0.000000 | 0.333333 | 0.200000 | 0.000000 | 1.000000 | 1.000000 | 2 | 0.500000 | 0.000000 | 0.630930 | 0.630930 | 0.630930 |
| rank_job_c6ab53cbebb914bc5cb7 | 3699421616 | 10 | 5 | 4 | 1.000000 | 0.666667 | 0.600000 | 0.200000 | 0.400000 | 0.600000 | 1 | 1.000000 | 1.000000 | 0.703918 | 0.605433 | 0.845261 |
| rank_job_d16e63af2f39a31b166d | 3693050905 | 10 | 5 | 0 | 1.000000 | 0.333333 | 0.400000 | 0.200000 | 0.200000 | 0.400000 | 1 | 1.000000 | 1.000000 | 0.469279 | 0.470365 | 0.802269 |

Weakest job3699411457:first relevantrank4,P@3/R@3=0,NDCG@10=0.453943.
Job3693045435:NDCG@10=1.0,all8 relevant before negatives. Other jobs vary
substantially. Job3693050905 has first relevant at1 but R@3=0.20,R@5=0.40;
one correct Top1 does not establish useful full shortlist ordering.

## 13. Ranking Errors

ranking_errors.csv contains IDs/ranks/scores/grades and comparison identities,
no source text or human reason dump. Counts are diagnostic EVENTS,not disjoint
candidate/job buckets;pair-comparison errors may repeat one candidate.

| Error predicate | Events |
|---|---:|
| DEEP_LIST_INVERSION | 9 |
| GRADE2_BELOW_TOP3 | 8 |
| GRADE2_BELOW_TOP5 | 4 |
| RELEVANCE_INVERSION | 11 |
| TOP1_IRRELEVANT | 3 |
| TOP3_POLLUTION | 22 |

TOP3_POLLUTION22 comparison rows involve9 distinct grade0 candidates,where relevant
items lie below. It is not the same count as all11 grade0 Top3 slots. Graded54
inversions also include0-vs1/1-vs2,not only RELEVANCE_INVERSION0-vs2.

Representative anonymous observed errors(not new annotations/rules):

| Type | Job | Pair | Rank | Grade | Compared pair | Compared rank |
|---|---|---|---:|---:|---|---:|
| TOP1_IRRELEVANT | 3693065853 | pair_1ebe95187e72bd492328 | 1 | 0 | — | — |
| GRADE2_BELOW_TOP5 | 3697399507 | pair_b6835667bdab04c4c268 | 6 | 2 | — | — |
| RELEVANCE_INVERSION | 3699411457 | pair_00b93ce714e41f326dd2 | 1 | 0 | pair_a30c050f5eda8b9ed42c | 4 |
| DEEP_LIST_INVERSION | 3693050905 | pair_0aabe8c47968c18f590d | 2 | 0 | pair_4f1c0d36324a0a6c0768 | 5 |

Additional strong bottom placement:pair_46a19e3f784029389018 grade2 at rank10,
job3699421616. Comparisons diagnose disagreement with existing human judgments;
no labels revised,role-specific bonus or algorithm tweak added after inspection.

## 14. Score Ties

Exact tie groups0,tied pair comparisons0,jobs affected0,max group size1.
Policy remains scoreDESC/pair_idASC for future ties. No jitter or grade tie-break.

## 15. Per-Job Variance

| Metric | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| ndcg@10 | 0.806903 | 0.852803 | 0.453943 | 1.000000 |
| ndcg@5 | 0.696074 | 0.667424 | 0.355840 | 1.000000 |
| precision@3 | 0.633333 | 0.666667 | 0.000000 | 1.000000 |
| recall@3 | 0.497500 | 0.450000 | 0.000000 | 1.000000 |

P@3 spans0..1,NDCG@10 spans0.453943..1.0. This small sample demonstrates instability
across its jobs,not a population estimate of industry-specific fairness.

## 16. Statistical Uncertainty

1000 bootstrap resamples BY JOB,seed42,frozen scores/ranks/policy.
Percentile95% intervals,not independent-pair bootstrap:

| Metric | Low | High |
|---|---:|---:|
| mrr | 0.625000 | 1.000000 |
| ndcg@10 | 0.693508 | 0.907352 |
| ndcg@5 | 0.572348 | 0.804966 |
| precision@3 | 0.400000 | 0.833333 |
| recall@3 | 0.308312 | 0.694312 |

Wide intervals reflect10 queries. Shared CV reuse may create cross-job dependence;
bootstrap preserves whole pools but does not eliminate that dependence. Intervals
conditional on constructed dataset/single labeling process/frozen profile,not
model-selection uncertainty,production prevalence or external deployment evidence.

## 17. Random Ranking Sanity Baseline

10000 fixed-seed42 within-job permutations,same grades/pool sizes,macro aggregation.
Clearly named random ranking sanity baseline,NOT Baseline-v1 or a trained competitor.

| Metric | Semantic-v1 | Random expectation |
|---|---:|---:|
| precision@1 | 0.700000 | 0.459210 |
| precision@3 | 0.633333 | 0.459747 |
| precision@5 | 0.580000 | 0.460298 |
| recall@1 | 0.130278 | 0.099847 |
| recall@3 | 0.497500 | 0.300517 |
| recall@5 | 0.684722 | 0.500460 |
| mrr | 0.825000 | 0.634937 |
| ndcg@1 | 0.700000 | 0.406403 |
| ndcg@3 | 0.674420 | 0.439540 |
| ndcg@5 | 0.696074 | 0.485297 |
| ndcg@10 | 0.806903 | 0.690110 |

Point estimates improve on random for these metrics,especially graded top ordering.
This is a sanity reference,not a paired statistical-superiority test or a validated
production comparison. No post-result selection/tuning or baseline/hybrid scoring.

## 18. Strict Grade-2 Diagnostic

Secondary only,4 contributing queries;6 zero-grade2 queries retained with undefined
strict metrics,NOT averaged as zero. Precision@1=.75,@3=.50,@5=.50;
Recall@1=.175,@3=.35,@5=.775;strict MRR=.8125. These are macro over4 eligible
queries,not all10 and not primary policy. Sparse grade2 coverage limits inference.
Strong ordering is imperfect:8/14 strong candidates belowTop3 and4 belowTop5.

## 19. Interpretation

**USEFUL BUT INCONSISTENT.** Useful candidates often reach the top:7/10 relevant
Top1,MRR.825,better than random point reference. Strong candidates sometimes rank
well(3/4 grade2-bearing jobs have strong Top1),but8 grade2 items fall belowTop3 and
4 belowTop5. Full-list NDCG.807 suggests a helpful ordering signal,not clean
separation:54 graded inversions and17 relevant belowTop5 remain.

Some jobs are much weaker;the worst misses relevance entirely inTop3. Dataset
prevalence constrains attainable precision,so inspect per-job recall/NDCG as well.
Capacity/profile fix enables faithful full-input scoring,NOT proof of stronger
algorithm or quality tuning.

Reasonable to proceed to14C.3 as a HUMAN-IN-THE-LOOP ranking-signal integration
with full-list visibility/no rejection and safeguards,NOT as approval for automatic
hiring filters. Larger genuinely independent per-job pools,additional adjudication,
extraction-fidelity checks and recruiter usability/fairness evidence remain needed.
No implementation or deployment approval beyond this task inferred.

## 20. Limitations

10 jobs,10 candidates/job,95 unique CVs with reuse,single human labeling process,
constructed/content-focused benchmark,6 grade2-empty pools,same external archives,
not representative production prevalence,no live recruiter study,fairness not
evaluated(Task14C.4). Relevance concerns corpus evidence;LLM-produced canonical
representation may omit/distort despite schema validation;extraction quality not
formally benchmarked here. Frozen canonical preparation/privacy is scoped,not
universal free-prose PII/fairness assurance.

One source chronology conflict preserved non-fatally,dates excluded from semantic
ranking. Hardware/runtime-dependent speed;profile/model/provider/digest must remain
compatible. Source-token cap4096 verified for this universe,not arbitrary future CVs;
longer future inputs fail controlled,never silently truncated. No probability
calibration,classification threshold or guaranteed candidate recommendation.

## 21. Task14C.3 Handoff

Use Semantic-v1 continuous score as PRIMARY recruiter ranking SIGNAL only.
No explicit limit:rank all valid applicants and return FULL list.
Explicit callerN:rank all first,then takeN(or fewer when available).
No hard score threshold,auto-hide,reject,suitable label or arbitrary defaultTopK.
Deterministic scoreDESC/stable identifier tie-break;recruiter final decision-maker.
Preserve canonical privacy/source warnings and shared profile/cache freshness.
K in this report is measurement only. API authorization/application validity,
concurrency/failure handling and UX/fairness validation belong to subsequent work.
No recruiter endpoint integration/frontend change performed now.

## 22. Tests

- Pre-live physical profile/embedding/cache/ranking regressions:98 passed,1 warning in1.67s.
- Pre-live evaluation:149 passed,2 warnings in7.45s.
- **Full pytest662 passed,3 warnings in180.56s(0:03:00),exit0**,existing guarded
  gjob_db_test ONLY via TEST_DATABASE_URL;credentials memory/redacted,no DEV fallback.
- Final evaluation149 passed,2 warnings in11.01s.
- Final embedding/admission/ranking/semantic/canonical98 passed,1 warning in1.57s.
- Independent100-label/finite-score/full-rank coverage/stored-score replay PASS;
  manual macroP@3 recomputation PASS. All4 hashes/core unchanged afterward.
- Tests mock providers/use synthetic/temp inputs;no live model in pytest. No real
  private corpus dependency in automated synthetic tests. Existing google-genai/
  Starlette/httpx/deprecated422 warnings only. git diff --check PASS.

No metric/formula/ground truth/production semantic code changed to pass tests.
Shared batch config/profile/request and cache binding are authorized capacity changes.

## 23. Privacy / DB Safety

No Qwen/Gemini calls,no DEV DB session/SQL/write,user/job/CV/application creation,
migration,frontend or production endpoint change. Existing model/engine imports
do not open DEV connections. Full integration tests use isolated guarded test DB.
Local BGE receives only frozen canonical professional semantic_text,not raw source,
names/emails/phones/address/photo fields,labels/reasons or chronology warnings.
No fairness claim. Outputs use anonymous IDs/scores/grades,not raw source/contact
text/reasons. Real vectors/token-count/protocol state remain private/gitignored.

## 24. Cleanup

Synthetic/temp fixtures clean themselves. No DEV test records/files created or
manual cleanup needed. No task process/lock/transient raw copies. Retain new105
private vectors and frozen label-free score/protocol/admission state for replay;
old21/empty legacy caches preserved,not relabeled/deleted. All frozen inputs,
private extraction payloads and previous benchmark evidence unchanged.
Only ONE existing report.md in this output directory updated.
Requested outputs:metrics.json,predictions.csv,ranking_errors.csv,bootstrap.json,
random_baseline.json and this SAME report.md.

## 25. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/embeddings evaluation/tests/test_ranking_metrics.py evaluation/tests/test_token_admission_diagnostics.py tests/test_semantic_matching.py tests/test_matching_inputs.py -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_ranking_semantic --phase all --data-dir C:/DATN/Datasets
git diff --check
```

Full pytest launched in guarded child environment with existing test DB credentials
resolved in memory/redacted. Source/profile/hash/model metadata checks;exact105
tokenization through verified loaded BGE runner;single blocker sanity cached;
actual runner numericflags checked;stored-score-only independent rank/label replay.
No second embedding evaluation,threshold sweep,post-result metric edit or SQL cleanup.

## 26. Final Status

**PASS Task14C.2 execution/integrity and shared capacity fix.**100 scores/ranks,
10 complete queries,unchanged frozen inputs/Semantic-v1,full/focused regression.
Scientific assessment **USEFUL BUT INCONSISTENT**,not autonomous recruitment
readiness or fairness certification. Task14C.3 may proceed as constrained human-
review ranking integration;no code integration/deployment performed here.

## Physical Batch Blocker Resolution

Earlier diagnostic:CV16244633 has2074 content tokens+2 BOS/EOS=2076. Context8192
was honored but physical n_ubatch2048 rejected it;synthetic2048 total passed,2050
failed. This was NOT8192 token overflow. User authorized shared num_batch4096 ONLY.

Added embedding_num_batch(default4096,1024..4096) to shared Settings;factory/provider
sends num_ctx8192,num_batch4096,truncatefalse. Shared profile
full-input-context-batch-v2,fingerprint
bcfd85c8e892993fa3111882be45f8beb92a610d191edb4455abb2aed0a908cc.
Provider/model/digest/version/config/normalization/canonical binding frozen in
new private protocol. Production persisted-match config identity changes with
batch;no migration or manual DB invalidation. Backend must reload config to apply.

Exactly ONE blocker embedding under new profile:PASS,prompt_eval_count2076,
1024 finite/nonzero dimensions. Cached entry1 reused,not requested again.
Verified actual runner:-c8192,-b4096,-ub4096,-np1. Exact loaded-model tokenizer
counted ALL105 full canonical texts before remaining embeddings:
max2365 total,3 inputs>2048,0>4096,0>8192. Entire universe fits authorized profile;
no need/attempt to raise batch8192. No OOM/runtime instability observed.

Old4096 cache21 vectors/ctx8192-only cache0 retained as incompatible historical
state. New ctx8192-batch4096-v2 cache105 vectors generated fresh,0hits/105misses.
No false relabeling or unproved cross-profile reuse. Profiles bound canonical
fingerprints/text hashes,model digest/provider version and request configuration.
All4 canonical/human/manifest hashes unchanged before/after;source chronology
warning not treated specially. Model/vector dimensions/pooling/normalization/
cosine/ranking/relevance/K remain unchanged;no truncate/chunk/raw-text adapter.

**Physical-batch fix PASS.** Shared production/evaluation capacity and runtime
verification passed;original14C.2 protocol resumed once and completed honestly.
