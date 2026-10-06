# Task 14B.4 Grouped Held-out Evaluation Report

## 1. Executive Summary

**PASS for the frozen retrospective grouped calibration/test protocol and regression.**
This does not certify a new blind, external or fully inductive test, nor production
readiness. Original algorithms/scores/human decisions remain unchanged.

132 calibration / 88 test pairs; CV/JD/pair overlap all zero. Semantic threshold
0.5867267674262028; lexical threshold 0.24733698756646583, selected on calibration
only, persisted before the single test evaluation. Test F1: semantic 0.728972,
lexical 0.787879; test AP: 0.784297 / 0.826252. Hard-negative FP: 13/22 versus 7/22.
Assessment: **mixed / inconclusive for final production selection**. Lexical has better
pooled point metrics, semantic stronger hard-group ranking/recall; paired F1 bootstrap
interval includes zero. Full pytest: **459 passed, 3 warnings in 184.47s**, exit 0.

## 2. Source Review

Reviewed human CSV schema; semantic/baseline runners, original metrics/predictions/
threshold sweeps/reports; benchmark_metrics.py; baseline_lexical.py; validator; existing
baseline/semantic/canonical-input/BGE-M3 tests; test-DB guard and established execution
mechanism. Semantic uses existing BGE-M3 cosine; the offline lexical reference uses
fixed TF-IDF/title coverage. Production's structured-skill baseline is a different
engine and is not measured here. Existing score provenance/IDs/labels/reasons were
validated before reuse. No provider recomputation was needed.

## 3. Implementation Plan

Added heldout_protocol.py, run_heldout_evaluation.py, tests/test_heldout_protocol.py and
HELDOUT_PROTOCOL.md; README updated. No production matcher, old scoring runner, old
algorithm, shared metric implementation or original artifact was modified for this task.
Artifacts: split CSVs/manifest/report, calibration sweeps/freeze/metrics, one-time test
marker, test scores/metrics/paired errors/FP/FN/comparison and this report.

Design: deterministic component partition by count-only stratification; calibration
selection with exact rational tie keys; exclusive-write freeze followed by file-reading
test phase without optimizer; paired bootstrap with fixed thresholds. No deviation
from identity isolation; explicitly disclose retrospective and transductive limitations.

## 4. Ground Truth Integrity

Input: evaluation/data/derived/evaluation_pairs_labeled.csv.
SHA-256: `28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8`.
Validator PASS 220/220: 116 human positives, 104 negatives. Original label/reason bytes
unchanged. Split CSVs omit reasons; error CSV reasons are copied only from the original.
Sampling categories 90/100/30 are analysis groups, never ground truth or scoring inputs.

## 5. Connected Component Audit

202 unique CVs, 180 unique JDs; 162 bipartite connected components.
Size distribution: 129 components of 1 pair, 19 of 2, 6 of 3, 5 of 4, 3 of 5.
Largest=5 pairs. Top10 sizes: 5,5,5,4,4,4,4,4,3,3; exact component IDs are in the split
manifest/report. No giant component; no component was broken or removed.

## 6. Split Design

Seed42; typed CV/job nodes; stable component hash from sorted pair IDs. Target60/40,
actual132/88=60%/40%. Greedy largest-component-first initialization plus strictly
decreasing count-loss flips/swaps; seeded hash tie order. The count objective targets
row count, positives, candidate groups, hard human negatives and easy human negatives.
No scores, model predictions or test outcomes enter split selection. No seed/split
search based on performance was run.

The resulting test set consists entirely of 88 singleton components (88 unique CVs,
88 unique JDs); all multi-pair components are in calibration. This reflects the fixed
component-size-first strategy, not a post-result resplit. It can introduce structural
selection bias and must be considered when generalizing. Stratification is approximate;
the local search is not claimed globally optimal.

## 7. Leakage Verification

Shared CV=0, shared JD=0, shared pair=0. Combined IDs exactly equal the original 220
IDs, each once. Whole-component membership and original labels/references are checked
again when phases resume. Manifest SHA-256:
`8e2119a04aaa434b5d4a0feee19fb860feb06ab33a97b01b8d6422fa56da3bcf`.

## 8. Calibration Set

132 pairs: 70 positives / 62 negatives; 114 unique CVs / 92 unique JDs.
Candidates: 54 positive, 60 hard, 18 easy. Hard: 30 human positives / 30 negatives.
Easy: 18 human negatives. Labels/groups are used for stratification, not scoring.

## 9. Test Set

88 pairs: 46 positives / 42 negatives; 88 unique CVs / 88 unique JDs.
Candidates: 36 positive, 40 hard, 12 easy. Hard: 18 positives / 22 negatives.
Positive candidates: 28 positives / 8 negatives. Easy: 12 negatives.

## 10. Frozen Algorithms

Semantic: unchanged SemanticMatchingService.match()/cosine_similarity(), BGE-M3,
raw dot(CV,JD)/(norm(CV)*norm(JD)), score [-1,1]; original offline embedding context
settings remain as documented in Task14B.2. No provider or embedding call here.

Baseline: unchanged `baseline-v1-offline-lexical`, 0.7 TF-IDF lexical cosine + 0.3
title-token coverage, score [0,1], fixed NFKC/casefold/static stopwords. TF=1+ln(count),
IDF=ln((1+N)/(1+df))+1 fitted previously on the whole raw corpus. No refit, skill
dictionary, seniority inference, weight or preprocessing change. All original score
artifacts and implementation/freeze hashes were verified before/after this protocol.

## 11. Threshold Selection Policy

Both algorithms maximize calibration F1, then higher precision, lower FP, higher
threshold. F1/precision tie comparisons use exact count-derived fractions. Candidates
are calibration observed scores, adjacent midpoints, range endpoints and nextafter
calibration maximum toward positive infinity. Prediction semantics: score >= threshold.
No test/global score boundaries or old exploratory best thresholds were supplied.
The selector's only data argument is calibration rows.

## 12. Calibrated Thresholds

| Algorithm | Threshold | Calibration precision | Recall | F1 | TP/TN/FP/FN |
|---|---:|---:|---:|---:|---|
| Semantic-v1 | 0.5867267674262028 | 0.681319 | 0.885714 | 0.770186 | 62/33/29/8 |
| Lexical reference | 0.24733698756646583 | 0.764706 | 0.928571 | 0.838710 | 65/42/20/5 |

Calibration ROC-AUC/AP: semantic 0.786866/0.778080; lexical 0.841244/0.817610.
Lexical threshold happens to equal the earlier global exploratory optimum; it was
independently selected from calibration-only boundaries under the frozen policy.
Exclusive-write freeze SHA-256:
`5d552274da24d355c1c9eb631377ace6d31fe059b2a3477434d9ae8644e746f8`.
Persisted freeze timestamp precedes the one-time test-start marker. Calibration
results are not final test estimates. Threshold JSON was not rewritten after test.

## 13. Held-out Test Main Results

| Metric | Semantic | Lexical reference |
|---|---:|---:|
| TP | 39 | 39 |
| TN | 20 | 28 |
| FP | 22 | 14 |
| FN | 7 | 7 |
| Precision | 0.639344 | 0.735849 |
| Recall | 0.847826 | 0.847826 |
| F1 | 0.728972 | 0.787879 |
| Accuracy | 0.670455 | 0.761364 |
| Specificity | 0.476190 | 0.666667 |
| Balanced accuracy | 0.662008 | 0.757246 |
| ROC-AUC | 0.761387 | 0.819876 |
| PR-AUC / non-interpolated AP | 0.784297 | 0.826252 |

These use the same 88 test pairs and calibration-frozen thresholds. No test threshold
sweep/optimization or final-test rerun was performed. Undefined subgroup metrics are
null, not fabricated zeros.

## 14. Hard Negative Test Results

40 hard candidates, 18 human positives / 22 negatives.

| Metric | Semantic | Lexical reference |
|---|---:|---:|
| TP/TN/FP/FN | 14/9/13/4 | 12/15/7/6 |
| FP / human negatives | 13/22 | 7/22 |
| Hard-negative FPR | 0.590909 | 0.318182 |
| Hard-positive recall | 0.777778 | 0.666667 |
| ROC-AUC | 0.699495 | 0.661616 |
| AP | 0.725130 | 0.631189 |

Both FP=5, semantic-only FP=8, baseline-only FP=2. Lexical reduces FP but loses more
hard positives. Semantic has stronger hard-group ranking despite worse calibrated FP.

## 15. Easy Negative Test Results

12 easy human negatives. Semantic FP=2/12 (16.67%), mean score=0.524286.
Lexical FP=0/12, mean score=0.088802. ROC-AUC/AP are undefined for this one-class group.
Perfect easy-group rejection must not conceal hard-case weaknesses.

## 16. Positive Candidate Test Results

36 candidates: 28 human positives / 8 negatives. Semantic precision=0.781250,
recall=0.892857, F1=0.833333; lexical precision=0.794118, recall=0.964286,
F1=0.870968. TP/TN/FP/FN: 25/1/7/3 versus 27/1/7/1.
Mean/median scores: semantic 0.630550/0.625103; lexical 0.356150/0.338158.
Distributions/percentiles and ranking results are in test_metrics.json.

## 17. Error Overlap

BOTH_CORRECT=53; BOTH_WRONG=15; SEMANTIC_ONLY_CORRECT=6; BASELINE_ONLY_CORRECT=14.
These buckets now use calibration-frozen thresholds, not the old 0.5 defaults.
The paired difference favors lexical in point accuracy, but is not a hybrid evaluation
or proof of statistically established superiority.

## 18. False Positives

Inspected five highest-score semantic FP: `pair_80a7790d275311155fad`,
`pair_888c9adbe0624241ef88`, `pair_47f9dcf1003206e5c199`,
`pair_71ba4be999a46cdf8120`, `pair_375d5ac14b353848a646`.
Five highest-score lexical FP: `pair_08e59d39b40e7d9a60bb`,
`pair_47390f706386a24597b7`, `pair_ecff6917d440c479dbb6`,
`pair_5242b21dcd9fda648b86`, `pair_7e78a3f9ca8f10d48104`.
Post-score human reasons often distinguish mandatory licensing/tools/role duties from
broad occupational similarity. These are interpretations of existing reasons, not
new eligibility annotations or scoring rules. No personal details are copied here.

## 19. False Negatives

Inspected five lowest-score semantic FN: `pair_00b86c026205d5d0c274`,
`pair_92b8dfd7b97929652cd5`, `pair_9f46ffffd151d966414e`,
`pair_154f1bddf2a05d77fb7f`, `pair_380cd77c4c4e262ed5b6`.
Five lowest-score lexical FN: `pair_f323eaeb937b92906e0e`,
`pair_9a44efc39a230519f808`, `pair_72f973dc7aa568fe0cde`,
`pair_380cd77c4c4e262ed5b6`, `pair_14c88a1d7de2f53fac2f`.
Human reasons describe related/transferable experience; literal vocabulary can miss
it, while cosine may still fall below a calibrated cutoff. All judgments remain unchanged.

Inspected hard disagreements including `pair_14c88a1d7de2f53fac2f`,
`pair_384c3f15132ff869a960`, `pair_47f9dcf1003206e5c199`,
`pair_4b413e4320c1a7855a5a`, `pair_5242b21dcd9fda648b86`; also five examples each of
semantic-only-correct and baseline-only-correct. The corresponding rows are preserved
in test_error_overlap.csv. No annotation error was corrected in this benchmark.

## 20. Ranking vs Classification

Lexical has higher pooled test ROC-AUC/AP and calibrated precision/F1, with equal
overall recall; semantic has higher hard-group ROC-AUC/AP and hard-positive recall.
Binary operating-point performance and continuous ranking are different questions.
Pooled gains partly include lexical's easy/positive-group behavior. This dataset is
not a representative per-job candidate-ranking pool or production prevalence estimate.

## 21. Statistical Uncertainty

1000 paired row percentile bootstrap resamples of test only, seed42, thresholds fixed;
all metric intervals had 1000 valid samples. No threshold re-selection in bootstrap.
95% F1 intervals: semantic [0.622642,0.816017], lexical [0.687484,0.870393].
Paired F1 delta (lexical-minus-semantic): [-0.025609,0.151141], includes zero.
Precision/recall/ROC-AUC/AP intervals are in test_metrics.json.

Intervals are conditional on this split, frozen models and selected thresholds; they
do not account for calibration/split uncertainty, historical analyst exposure,
transductive IDF or single-reviewer/domain dependence. Test rows have unique identities
here, but label/domain correlations can remain. No significance claim or McNemar test.

## 22. Algorithm Selection Assessment

**Mixed evidence / inconclusive for a final production algorithm choice.** Lexical
looks stronger on pooled point estimates but semantic retains hard-group ranking and
recall advantages. Paired F1 uncertainty overlaps zero. More importantly, this is a
retrospective grouped threshold holdout: all 220 labels were previously globally
analyzed, and frozen lexical IDF included all corpus texts. No new test labels entered
threshold selection, but this is not confirmatory blind or fully inductive evaluation.
Do not declare either method production-ready or switch algorithms from these results.

## 23. Recommended Next Step

Collect genuinely unseen independent CV/JD labels and preregister grouped calibration/
test allocation. A future inductive lexical evaluation should fit IDF only on permitted
training/calibration text under a new clearly identified protocol; do not silently
replace these frozen scores. Consider an explicit ranking-vs-classification operating
policy or separately evaluated hybrid only in a new task. Nothing is implemented here.

## 24. Artifacts

- data/derived/calibration_pairs.csv; test_pairs.csv.
- reports/heldout_split_manifest.json; heldout_split_report.md.
- results/heldout/calibrated_thresholds.json; calibration_metrics.json.
- semantic-v1_calibration_threshold_sweep.csv; baseline-v1_calibration_threshold_sweep.csv.
- test_evaluation_started.json; test_metrics.json; test_predictions.csv.
- test_error_overlap.csv; semantic_false_positives.csv; semantic_false_negatives.csv.
- baseline_false_positives.csv; baseline_false_negatives.csv; final_comparison.md; this report.
- Code/protocol/tests: heldout_protocol.py, run_heldout_evaluation.py,
  HELDOUT_PROTOCOL.md, tests/test_heldout_protocol.py; README updated.

All paths above are relative to evaluation/. CSV privacy exclusions already cover
new artifacts. No raw text, embedding cache or new dependency was created.

## 25. Automated Tests

- Evaluation/split/calibration/freeze/bootstrap: **67 passed, 1 warning in 4.88s**.
- Pure baseline/semantic/canonical-input/BGE-M3 regression: **90 passed in 1.08s**.
- Full pytest: **459 passed, 3 warnings in 184.47s (0:03:04)**, exit code0.
- Full suite used existing guarded gjob_db_test, with credentials supplied in memory
  to the child process; URLs/passwords were redacted. No new DB/config file.
- Warnings: google-genai UnionGenericAlias, Starlette/httpx TestClient and deprecated
  HTTP_422_UNPROCESSABLE_ENTITY in the existing salary-range test. No failing tests.
- Synthetic infeasible component fixtures stop instead of breaking a component;
  test phase/bootstraps cannot call optimizer; altered partitions/threshold artifacts
  and a second final evaluation are rejected. Synthetic temp fixtures clean themselves.

## 26. Privacy / Security

No provider, production endpoint or application/DB imports in the heldout runner.
Input/source/algorithm/old-artifact/protocol hashes verified across phase boundaries.
Split/test records use source IDs/scores/labels; allowed human reasons stay in gitignored
error CSVs. Narratives omit names/contact data; no secrets/connection URLs logged.
Exclusive creation prevents overwriting frozen split/threshold/result artifacts.

## 27. Database / Migration

DEV/production DB writes: no. New migration files: no. Offline split/calibration/test
used no DB. Full integration regression used only the existing validated test DB and
normal fixture setup/teardown; conftest applied its existing migrations to the test DB.
No production threshold, matcher, API, ranking, extraction pipeline or frontend changed.

## 28. Test Data Cleanup

Synthetic fixture/result roots use TemporaryDirectory cleanup. Validator staging
is disposable. No real CV/job/application/account or uploaded file was created by
this evaluation; no DEV cleanup needed/performed. Original historic drafts/progress
and both benchmark artifact directories remained unchanged. Existing test-suite
fixtures handled isolated test DB data. No new test DB/config or temporary cache.

## 29. Known Limitations

220 total labels, single-reviewer subjectivity, difficulty-focused selection; grouping
reduces effective independent component count; only88 test rows; singleton-only test
partition structural bias; no external validation or representative prevalence; no
hybrid, no extraction evaluation; retrospective label exposure and transductive IDF.
Bootstrap intervals are conditional and do not make this a fresh blind deployment test.

## 30. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -m pytest --noconftest tests/test_baseline_matching.py tests/test_semantic_matching.py tests/test_matching_inputs.py tests/embeddings -q
venv\Scripts\python.exe -u -m evaluation.run_heldout_evaluation --phase split --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -u -m evaluation.run_heldout_evaluation --phase calibrate --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -u -m evaluation.run_heldout_evaluation --phase test --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -m pytest -q
git diff --check -- evaluation
```

Full pytest was launched in a child process using the established TEST_DATABASE_URL
mechanism, resolved only in memory from existing Docker credentials/template target.
Additional read-only commands inspected schemas/component counts, frozen provenance,
persisted results/sanity examples and hashes. No provider rerun or test threshold sweep.
One diagnostic read command had a shell-quoting SyntaxError and was replaced with a
read-only comprehension command; it did not execute any evaluation or alter artifacts.

## 31. Final Status

**PASS: retrospective grouped threshold protocol and full regression completed.**
Zero CV/JD/pair overlap; all220 accounted for; calibration-only thresholds persisted
before one final test evaluation; source/labels/algorithms/scores/thresholds unchanged.
All mandatory reports and paired/FP/FN/group metrics produced; no hybrid/post-test
tuning/production switch. Scientific final assessment remains mixed/inconclusive.
Independent confirmatory validation, not further retuning of this test, is the next step.
