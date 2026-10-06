# Task 14B.5 Phase B — Fresh Independent Final Validation

## 1. Status

**PASS: validation, ground-truth/state freeze, one fixed-threshold evaluation and full
regression. Final algorithm assessment: mixed/inconclusive.** No automatic production
switch, hybrid or post-fresh tuning. Independence refers to this project's old
identities/fitted corpus/threshold calibration, not a new external data source or a
claim about absence from BGE-M3 pretraining.

## 2. Fresh Ground Truth

- Exact path: `C:\DATN\GJobBackend\evaluation\data\derived\fresh_test_pairs_labeled.csv`.
- Validator PASS: **70/70**, **38 human positives / 32 negatives**.
- SHA-256: `1d9820ef3439aca231ed79233b59370b2b849306d55af154db6ca81a018805e9`.
- Every label/reason matches an explicit REVIEWED progress record with timestamp.
- All70 had optional Qwen assistance; those suggestions were not automatically saved
  as human decisions. User confirmed completion before Phase B. Single-reviewer and
  LLM-assisted anchoring risks remain; this is not independently adjudicated truth.
- Seed hash: `9c2d506c45c9fc7386d53627de09b5c12a51404d51f5852a40405af0a4eedca3`.
- Sampling: 28 positive candidates / 32 hard candidates / 10 easy candidates. These
  are not human labels. Source previews and evaluation scores were absent during review.
- Labels were frozen before any fresh scoring; no label/reason was subsequently edited.

## 3. Independence Checks

70 unique CVs, 70 unique JDs, 70 unique valid pair IDs. No duplicate/reused fresh identity.
Old220 overlap: CV=0, JD=0, pair=0. Historical pilot/draft overlap: CV=0, JD=0, pair=0.
Exclusion scope conservatively covers244 prior CV IDs /303 JD IDs, not just202/180
in old220. Exact CV content and normalized duplicate JD content were also excluded.
No old labels or model scores were generation features.

Phase A initially detected one JD exposed in the historical pilot in an unlabeled
draft and replaced that unreviewed draft before opening final fresh review. No labels
or model scores existed for that discarded draft. Final seed was deterministic in
an independent process; no duplicate version folders were left behind.

## 4. Frozen Algorithms

Semantic: existing `SemanticMatchingService.match()` and `cosine_similarity()`, BGE-M3,
raw cosine dot(CV,JD)/(norm(CV)*norm(JD)). Same raw-source text formatter and frozen
model digest/context request profile as old benchmark: num_ctx8192, num_batch8192,
truncate=false. No extraction, Qwen/Gemini scoring, silent truncation or fallback.
140 unique source embeddings were computed,0 cache hits /140 misses.

Baseline: unchanged `baseline-v1-offline-lexical`, not production structured-skill
coverage engine. Score=`0.7 * TF-IDF lexical cosine + 0.3 * title-token coverage`;
TF=`1+ln(count)`; IDF=`ln((1+N)/(1+df))+1`. Original tokenizer, normalization, title
logic, formula, weights and core file remain unchanged. The external fitted-state
adapter binds this same scorer to development-only vocabulary/IDF; see section6.
No previous semantic/baseline/heldout artifact was overwritten.

## 5. Frozen Thresholds

Read unchanged from `evaluation/results/heldout/calibrated_thresholds.json`:

- Semantic: **0.5867267674262028**.
- Lexical: **0.24733698756646583**.
- Original artifact SHA-256:
  `5d552274da24d355c1c9eb631377ace6d31fe059b2a3477434d9ae8644e746f8`.

Prediction semantics remain score >= threshold. No fresh threshold sweep, best-F1
search, calibration, weight optimization or threshold replacement was run.

## 6. Baseline IDF Audit

The old offline runner fits IDF on the evaluated corpus. Running it directly on
fresh70 would have refitted IDF using fresh documents and would not satisfy the
independence requirement. That path was not used.

Instead, before fresh scoring, reconstructed the state from exactly the original
**382 development documents:202 CVs +180 JDs**, with verified old source hashes and
the unchanged constructor. This state reproduced **all220 original baseline scores
exactly**. No fresh text or label participated in IDF fitting or vocabulary creation.

- Fitted-state version: `baseline-v1-development-state-v1`.
- Inference binding: `fixed-development-vocabulary-transform-v1`.
- Vocabulary size:16478.
- State SHA-256: `7b1405dc50bf26e96517b2ff2fdda65e8a1dddab1e7069e6ac44863ce8dbb25d`.
- Private state: `evaluation/cache/fresh-test/baseline_development_state.json`.

Fresh documents are transformed using those fixed IDFs. Out-of-vocabulary terms are
ignored in TF-IDF vectors; literal title coverage still uses all original normalized
CV/title tokens. Empty vectors retain the original score's zero-component behavior.
This OOV/inference protocol was documented and frozen before scoring, never chosen
from fresh performance. It is an explicit fitted-state/configuration extension, not
a core scorer rewrite. Original development scores remain identical. Fresh corpus
statistics never modify IDF. Unknown-word distribution can still affect performance.

Persisted vocabulary keys are SHA-256 token identifiers, not raw words/names; the
state stays in the private gitignored cache. No raw CV/JD text or vocabulary string
dump is stored in results. Public freeze metadata records only hashes/provenance.

## 7. Semantic Result

TP33, TN19, FP13, FN5. Precision0.717391; recall0.868421; F1=0.785714;
accuracy0.742857; specificity0.593750; balanced accuracy0.731086;
ROC-AUC0.840461; non-interpolated AP0.829989.

## 8. Baseline Result

TP31, TN20, FP12, FN7. Precision0.720930; recall0.815789; F1=0.765432;
accuracy0.728571; specificity0.625000; balanced accuracy0.720395;
ROC-AUC0.816612; non-interpolated AP0.848977.

## 9. Main Comparison

| Metric | Semantic-v1 | Frozen lexical reference |
|---|---:|---:|
| TP | 33 | 31 |
| TN | 19 | 20 |
| FP | 13 | 12 |
| FN | 5 | 7 |
| Precision | 0.717391 | 0.720930 |
| Recall | 0.868421 | 0.815789 |
| F1 | 0.785714 | 0.765432 |
| Accuracy | 0.742857 | 0.728571 |
| Specificity | 0.593750 | 0.625000 |
| Balanced accuracy | 0.731086 | 0.720395 |
| ROC-AUC | 0.840461 | 0.816612 |
| AP | 0.829989 | 0.848977 |

Both scored the same70 confirmed fresh pairs using frozen thresholds. No test
selection/calibration rerun occurred. Semantic improves recall/F1/ROC-AUC point
estimates; lexical slightly improves precision/specificity/AP. Continuous ranking
and binary operating points are distinct, not probabilities of hiring suitability.

## 10. Hard Negative Comparison

32 hard candidates:18 human positives /14 negatives.

| Metric | Semantic | Lexical |
|---|---:|---:|
| TP/TN/FP/FN | 14/8/6/4 | 14/8/6/4 |
| FP / human negatives | 6/14 | 6/14 |
| Hard-negative FPR | 0.428571 | 0.428571 |
| Hard-positive recall | 0.777778 | 0.777778 |
| F1 | 0.736842 | 0.736842 |
| ROC-AUC | 0.809524 | 0.682540 |
| AP | 0.817624 | 0.772989 |

Both FP=2, semantic-only FP=4, baseline-only FP=4: identical counts are not identical
errors. Semantic has stronger hard-group ranking, but neither removes hard FP well.
Easy candidates:10 human negatives,1 FP each (10%). Positive candidates:28 rows,
20 positives /8 negatives; semantic TP19/TN2/FP6/FN1 vs lexical17/3/5/3.
Full subgroup score distributions/precision/recall are in metrics.json.

## 11. Error Overlap

BOTH_CORRECT=40; BOTH_WRONG=7; SEMANTIC_ONLY_CORRECT=12; BASELINE_ONLY_CORRECT=11.
The algorithms have complementary disagreements, but this is not a evaluated hybrid
and does not justify an automatic fallback or production combination.

Inspected the highest-score five FP and lowest-score five FN per method. Semantic FP
examples include `pair_72dde13f4246a3cab408`, `pair_72d8ee03bcf82506ba2f`,
`pair_ebe823b9e2d8fef6e748`, `pair_17569905915cbe8a488d`,
`pair_e86b9ed3361d0b54d8a2`; lexical examples include
`pair_ebe823b9e2d8fef6e748`, `pair_72d8ee03bcf82506ba2f`,
`pair_00db28a15bd25c46b529`, `pair_ee388d88e4e675bc175e`,
`pair_c8b5d5243d39b3914727`. Existing human reasons often cite specific responsibilities,
seniority or required stack missing despite broad domain/word similarity.

Semantic FN examples: `pair_cd407f43fc70dc465e65`, `pair_ada5bd82c6b391cc37e2`,
`pair_15ec358fa6c3fb8d0f28`, `pair_26ac0e230570cd8447b2`,
`pair_009a08b5d0ce172ddd4f`. Lexical FN examples: `pair_d093a818513cc26563a6`,
`pair_cd407f43fc70dc465e65`, `pair_b88d23d8b5593a11ff4a`,
`pair_86ba628aaca9ac1a51dc`, `pair_050a2769a7ba855596fd`.
Reasons describe transferable/related experience, which literal terms or a fixed
cutoff can miss. These post-score observations did not become new annotations/rules.

## 12. Statistical Uncertainty

1000 paired row bootstrap resamples, seed42, frozen thresholds throughout.
All metrics had1000 valid samples. Fresh identities are unique across all70 pairs;
single-reviewer/domain dependence and difficulty-biased sampling still remain.

95% F1 intervals: semantic[0.682353,0.877563], lexical[0.656250,0.857143].
Paired F1 delta (lexical-minus-semantic): **[-0.140802,0.095191]**, includes0.
Precision/recall/ROC-AUC/AP intervals are in bootstrap.json. These intervals are
conditional on the fixed thresholds/state and do not measure production prevalence
or dataset selection uncertainty. SciPy is not installed; no dependency was added
solely for McNemar. Paired correctness counts are reported instead.

## 13. Final Algorithm Assessment

**mixed/inconclusive**. Semantic's point F1/recall/ROC-AUC and hard ranking are stronger;
lexical has marginally better precision/specificity and pooled AP. Hard classification
FP counts are equal; the paired F1 interval crosses0 and discordant correctness is
12 versus11. No statistically established overall winner is supported by70 pairs.

This fresh set removes old project identity/content reuse and fresh-IDF fitting,
addressing major limitations of the earlier retrospective split. It remains a small,
single-reviewer, Qwen-assisted, difficulty-focused sample from the same source archives,
not an external adjudicated dataset. Frozen inference state/OOV policy is explicitly
documented; it is not proof that either method is ready for autonomous recruitment
decisions. Neither production threshold nor algorithm was switched.

## 14. Recommended Next Step

Expand genuinely new labels with independent human adjudication, representative role
coverage and preregistered operating-point requirements. A separately versioned
Task14B.6 hybrid experiment may be worth evaluating given disagreements and hard
ranking differences; do not infer its performance from these counts or implement it
in this task. Preserve this fresh result rather than retuning against it.

## 15. Tests

- Phase A independent-process generation reproduced seed bytes exactly; latest Phase A
  full suite:477 passed,3 warnings in137.85s.
- Phase B evaluation tests: **89 passed,1 warning in5.89s**.
- Full Phase B pytest: **481 passed,3 warnings in166.12s (0:02:46)**, exit0.
- New synthetic tests verify dev-state equivalence, no constructor/fitting on fresh
  transform, OOV handling, no threshold optimizer and core file immutability.
- Full tests use existing isolated gjob_db_test with transient TEST_DATABASE_URL and
  secret-redacted output. No new DB/config file or fallback to DEV.
- Warnings are existing google-genai UnionGenericAlias, Starlette/httpx TestClient,
  and deprecated HTTP_422_UNPROCESSABLE_ENTITY in the salary-range test.

## 16. Privacy

No raw CV/JD, personal contact data or raw vocabulary strings in result artifacts.
Source text is read in memory and sent only to local BGE-M3 embedding, never cloud
LLM scoring. Optional Qwen-assisted human labeling happened before freeze; no
Qwen/Gemini call was made by Phase B. Allowed human reasons stay in private ignored
error CSVs; narratives use anonymous pair IDs and professional patterns only.
The real embedding/fitting-state cache is private/gitignored, not a public artifact.

## 17. DB Safety

Offline validation/state reconstruction/scoring used no GJob DB or production API.
Full integration pytest used only the existing guarded test DB and normal fixture
setup/teardown. No DEV record creation/deletion, migration file, frontend change,
CV extraction change, recruiter ranking change or hybrid.

## 18. Cleanup

Validator/state tests use disposable synthetic/temp fixtures. Phase A reconstruction
staging was removed; the initial unreviewed draft was replaced before labeling.
Real freeze artifacts,140 embedding vectors and development-only state remain for
traceability; they are not disposable test caches. No real human labels or prior
evaluation artifacts were deleted. Protected hashes were checked after scoring.

## 19. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_fresh_final --phase freeze --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_fresh_final --phase evaluate --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -m pytest -q
git diff --check -- evaluation
```

Full pytest was launched in a child process with the existing guarded test URL resolved
in memory from Docker credentials/template target; no URL/password is reproduced here.
Additional read-only commands validated progress/overlaps/hashes and inspected saved
metrics/error examples. No fresh scoring or evaluation rerun, threshold sweep or tuning.

Results: fresh_ground_truth_frozen.json, evaluation_started.json, metrics.json,
predictions.csv, error_overlap.csv, four FP/FN CSVs, bootstrap.json and this report.
State is in evaluation/cache/fresh-test/baseline_development_state.json; old reports,
labels, algorithms and calibrated_thresholds.json remain unchanged.

## 20. Final Status

**PASS for Task14B.5 Phase B execution integrity and regression.** Final scientific
assessment: **mixed/inconclusive**. Fresh truth was fully human-confirmed, frozen before
one evaluation, with zero historical identity overlap. No fresh IDF fit, label change,
algorithm rewrite, threshold tuning, hybrid or DEV write occurred. Keep frozen files
unchanged; any genuine annotation correction requires a documented new dataset version.
