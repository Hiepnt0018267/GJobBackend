# Task 15B — Job Recommendation Evaluation

## Objective

Separate mechanics correctness, real Semantic-v1/BGE-M3 quality, production-visible quality, and signal coverage without changing Task 15A production behavior.

## Frozen Production Contract

Task 15A remains cache-only, candidate-only, full-pool ranked before pagination, cosine descending with `created_at DESC` then UUID DESC tie-break. No production source file was changed by Task 15B.

## Evaluation Layers

Deterministic vectors are mechanics-only evidence. Semantic and production-visible metrics below use the same frozen real BGE-M3 vectors. Controlled missingness is clearly labeled diagnostic and is not presented as an observed provider failure.

## Dataset Version

`job-recommendation-v1`: 10 synthetic candidates, 32 jobs, 290 fully labeled eligible pairs.

## Dataset Freeze & Hashes

The candidate/job/label files were completed and validated before embedding. SHA-256: `{"candidates.jsonl": "94d9bfca9c26502840910ec59af8148dcf44825b1d33c7603a36c4fcad864c5d", "jobs.jsonl": "9e8f1843c51add5f8b5412d4170940810656fc15cf47c743a087a27b06fb2d89", "labels.csv": "dfb553c8c933d71b0c0d5225cc448bdc6964913565af238616dadb02fdea4bcd"}`. Hashes matched again after embedding.

## Relevance Rubric

0 irrelevant; 1 weak/peripheral; 2 plausible/moderate; 3 strong. Binary P/Recall/MRR relevance is grade >=2 and is evaluation-only, never a production threshold.

## Candidate Archetypes

Python/FastAPI, Java/Spring, React, full-stack, data analyst, data engineer, ML/AI, QA automation, DevOps/cloud, and sparse mobile.

## Job Archetypes

Thirty approved exact, adjacent, wrong-stack, wrong-role, sparse-valid and noisy jobs plus two explicitly ineligible status fixtures. The sparse JD retains the schema-required non-empty description.

## Hard Negatives

All six required shared-keyword/wrong-role families are explicitly labeled 0 and never derived from model scores.

## Mechanics Evaluation

Status: `verified` — MECHANICS ONLY. Checks: `{"fewer_than_k_precision_undefined": true, "missing_partition_last": true, "no_relevant_mrr_undefined": true, "no_relevant_recall_undefined": true, "perfect_precision_at_1": true, "reverse_first_relevant_rank": true, "shuffle_invariant": true, "tie_break_exact": true}`.

## Real BGE Semantic Evaluation

Status: `completed`. Profile fingerprint `bcfd85c8e892993fa3111882be45f8beb92a610d191edb4455abb2aed0a908cc`; model digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`; unique entities 40; total generation `/api/embed` calls 40; calls in the final replay 0; cache hits in the final replay 40; failures 0. Initial generation wall time was 24.87413030001335 seconds; final cache replay was 0.4612493999302387 seconds.

## Semantic Ranked Quality

Conditional on semantic availability.

| Metric | Macro mean | Defined | Undefined |
|---|---:|---:|---:|
| precision_at_1 | 1.000000 | 10 | 0 |
| precision_at_3 | 0.900000 | 10 | 0 |
| precision_at_5 | 0.720000 | 10 | 0 |
| recall_at_3 | 0.537857 | 10 | 0 |
| recall_at_5 | 0.723690 | 10 | 0 |
| mrr | 1.000000 | 10 | 0 |
| ndcg_at_3 | 0.896942 | 10 | 0 |
| ndcg_at_5 | 0.888075 | 10 | 0 |
| ndcg_at_10 | 0.881549 | 10 | 0 |

Actual embedding coverage is 100%, so this actual-availability view is identical to
the conditional semantic view. The separately frozen controlled-missingness diagnostic
does not pretend BGE failed: candidate coverage is 0.9, pair rankability is 0.886207,
and its visible metrics are P@1 1.0, P@3 0.833333, P@5 0.68, Recall@3 0.487857,
Recall@5 0.673690, MRR 1.0, NDCG@3 0.831879, NDCG@5 0.828493, and NDCG@10 0.823862.

## Production Visible Quality

Full eligible universe in frozen Task 15A display order.

| Metric | Macro mean | Defined | Undefined |
|---|---:|---:|---:|
| precision_at_1 | 1.000000 | 10 | 0 |
| precision_at_3 | 0.900000 | 10 | 0 |
| precision_at_5 | 0.720000 | 10 | 0 |
| recall_at_3 | 0.537857 | 10 | 0 |
| recall_at_5 | 0.723690 | 10 | 0 |
| mrr | 1.000000 | 10 | 0 |
| ndcg_at_3 | 0.896942 | 10 | 0 |
| ndcg_at_5 | 0.888075 | 10 | 0 |
| ndcg_at_10 | 0.881549 | 10 | 0 |

## Coverage

`{"actual_embedding_run": {"candidate_signal_coverage": 1.0, "candidates_with_any_missing_signal": 0, "eligible_pairs": 290, "pair_rankability_coverage": 1.0, "pending_or_unavailable_or_error_job_coverage": 0.0, "ranked_job_coverage": 1.0, "ranked_pairs": 290, "request_rankability_coverage": 1.0}, "controlled_missingness_diagnostic": {"candidate_signal_coverage": 0.9, "candidates_with_any_missing_signal": 4, "eligible_pairs": 290, "pair_rankability_coverage": 0.8862068965517241, "pending_or_unavailable_or_error_job_coverage": 0.11379310344827587, "ranked_job_coverage": 0.8862068965517241, "ranked_pairs": 257, "request_rankability_coverage": 0.9}, "job_embedding_coverage": 1.0}`

## Metric Definitions

P@K uses denominator K and is undefined when fewer than K ranked/displayed items exist. Recall denominator is relevant items in the named universe. MRR is reciprocal first relevant rank, zero only when relevant items exist but none are retrieved. NDCG uses gain `2^grade-1`, log2 discount, and is undefined for zero IDCG.

## Bootstrap Confidence Intervals

Candidate-level percentile bootstrap, 1,000 resamples, seed 42. See `results.json` for every point estimate and 95% interval.

| Metric | Semantic 95% CI | Visible 95% CI |
|---|---:|---:|
| precision_at_1 | [1.000000, 1.000000] | [1.000000, 1.000000] |
| precision_at_3 | [0.733333, 1.000000] | [0.733333, 1.000000] |
| precision_at_5 | [0.620000, 0.820000] | [0.620000, 0.820000] |
| recall_at_3 | [0.447500, 0.625854] | [0.447500, 0.625854] |
| recall_at_5 | [0.619851, 0.825854] | [0.619851, 0.825854] |
| mrr | [1.000000, 1.000000] | [1.000000, 1.000000] |
| ndcg_at_3 | [0.827954, 0.964252] | [0.827954, 0.964252] |
| ndcg_at_5 | [0.838361, 0.939323] | [0.838361, 0.939323] |
| ndcg_at_10 | [0.844165, 0.918885] | [0.844165, 0.918885] |

## Random Baseline

Within-candidate random ordering, 10,000 simulations, seed 42. It is a sanity reference, not a production competitor.

| Metric | Semantic random | Visible random |
|---|---:|---:|
| precision_at_1 | 0.181800 | 0.181800 |
| precision_at_3 | 0.181680 | 0.181680 |
| precision_at_5 | 0.181566 | 0.181566 |
| recall_at_3 | 0.102817 | 0.102817 |
| recall_at_5 | 0.171314 | 0.171314 |
| mrr | 0.381676 | 0.381676 |
| ndcg_at_3 | 0.172097 | 0.172097 |
| ndcg_at_5 | 0.202702 | 0.202702 |
| ndcg_at_10 | 0.272890 | 0.272890 |

## Stability

Repeated evaluation from the same isolated cached vectors produced identical ranking IDs, metrics, and tie resolution; ranking order variance is `0`.

## Error Analysis

Machine-readable cases: 2 rows in `ranking_cases.csv`; case counts `{"LOWEST_NDCG_AT_5": 2}`. The sparse mobile profile is the lowest real semantic NDCG@5 case; the controlled candidate-unavailable QA scenario is the lowest controlled visible case. No data, labels, canonical text, ranking policy, or profile was tuned after scores were observed.

## Limitations

Small synthetic single-labeler benchmark; controlled archetypes are not production prevalence. It does not establish deployment readiness, broad statistical significance, calibration, or demographic fairness. Controlled missingness is scenario analysis, not observed BGE failure. CV-selection behavior remains Task 15A regression evidence rather than a semantic-quality variable in this canonical dataset.

## Reproducibility

Inputs, outputs, and isolated cache are separate. Canonical hashes, fixed UUIDs/timestamps, profile/model identity, request counts, seeds and runtimes are recorded in machine-readable artifacts. Tests use no live models; the explicit evaluation command uses only `/api/embed`.

## Regression Tests

Task 15B metric/dataset/ranking tests: **10 passed in 1.13s**. Final focused Task
14/15A/15B regression: **98 passed, 3 warnings in 2.23s**. Final full backend:
**931 passed, 4 warnings in 119.71s (0:01:59)**. Pytest used the existing guarded
`gjob_db_test`; the child process derived `TEST_DATABASE_URL` in memory, and the
repository guard verified it differs from DEV and matches `current_database()`.
Tests made zero live model calls. Warnings are the existing google-genai,
Starlette/httpx, and deprecated HTTP 422 warnings.

## Final Status

**TASK 15B — JOB RECOMMENDATION EVALUATION DATASET & METRICS — VERIFIED.** VERIFIED here means the frozen evaluation protocol completed with compatible real BGE-M3 vectors; it is not an unstated quality threshold or deployment approval.
