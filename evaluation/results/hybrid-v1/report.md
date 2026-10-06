# Task 14B.6 Hybrid-v1 Offline Experiment Report

## 1. Status

**PASS protocol/regression; research assessment: HYBRID-V1 SACRIFICES TOO MUCH RECALL
at the frozen operating point.** No requirement that fusion wins was imposed. Alpha0.50,
threshold0.4962121212121212, recall-floor0.80; fallback=false. Calibration Recall0.80,
Specificity0.774194, FP14;88 development holdout Recall0.695652, Specificity0.785714,
FP9. FP falls but the intended useful-recall level does not generalize. No retuning.
Full pytest: **495 passed,3 warnings in107.98s (0:01:47)**, exit0.

## 2. Source Review

Inspected existing semantic service/cosine, semantic/baseline runners and artifacts,
lexical TF-IDF/title scorer, fixed development-only IDF binding/state, grouped split,
frozen thresholds, shared metrics/bootstrap and synthetic regression tests. Source
schemas/provenance/IDs/hashes matched. Reused component predictions, metrics, grouped
partition validation, error extraction and exclusive/hash utilities. No provider call,
component rescoring, IDF fit or production code change.

Motivation is lower recruiter-facing false positives while preserving recall, not
highest F1. Previously observed complementary errors justify exploring a small family,
not assuming that fusion will improve quality. Both datasets were already consumed.

## 3. Evaluation Protocol

Frozen HYBRID_V1_PROTOCOL.md before real calibration. Fit ECDF and select one of
three weights/thresholds on132 only; exclusively persist hybrid_config; evaluate88
once; only then evaluate70 once as a consumed post-hoc diagnostic. All phase markers
prevent silent overwriting/rerun tuning. Same metric/tie conventions and original
component thresholds are retained. Primary objective/policy never changed after outcomes.

## 4. Data Usage Boundaries

- 220 labeled pairs are repeatedly inspected **development data**, not new validation.
-132 calibration:70 human positives/62 negatives; normalization/parameter selection only.
-88:46 positives/42 negatives; **retrospective development holdout**, not independent.
-70:38 positives/32 negatives; component results were previously seen and motivated
  fusion research; **POST-HOC CONSUMED FRESH-SET DIAGNOSTIC — NOT INDEPENDENT HYBRID VALIDATION**.
-88/70 never entered alpha/threshold selection or normalization fit. No split/seed
  search or fresh best-threshold analysis. Labels/reasons/pair membership unchanged.

## 5. Frozen Component Algorithms

Semantic-v1: unchanged BGE-M3 raw cosine from SemanticMatchingService.match() and
cosine_similarity(), same original raw-source preprocessing. Lexical reference:
unchanged baseline-v1-offline-lexical,0.7 TF-IDF cosine+0.3 title coverage, original
TF/IDF/tokenizer/weights. This is not production's structured-skill coverage engine.
Both keep original Task14B.4 thresholds: semantic0.5867267674262028,
lexical0.24733698756646583. Source/score/human artifact hashes verified throughout.

## 6. Normalization

Right-inclusive empirical CDF fitted separately to the132 calibration component
scores: F_cal(x)=count(calibration scores<=x)/132. Duplicates count multiplicity;
below min maps0; at/above max maps1; observed min maps its tied frequency/132.
Unseen scores use only this stored reference. Percentiles are ranks, not probabilities.
Monotone step mapping can create ties/saturation and change ranking relative to raw
scores. No heldout/fresh score-distribution fitting or alternative normalization search.

The same frozen development-only lexical IDF state from Task14B.5 was verified, SHA
`7b1405dc50bf26e96517b2ff2fdda65e8a1dddab1e7069e6ac44863ce8dbb25d`.
It was not refitted here. Old220 scores exactly correspond to that development state;
70 scores already used fixed-vocabulary inference with documented OOV handling.

## 7. Candidate Hybrid Configurations

Exactly `H=alpha*S_percentile+(1-alpha)*B_percentile`, alpha0.25,0.50,0.75.
No nonlinear stacking, learned model, guard, bonus, occupation rule or extra alpha.
Integer percentile ranks are combined over common4N before final float division,
algebraically the same weights; this avoids splitting mathematical ties by ulp drift.
This numerical policy was specified/tested before calibration, not added post-result.

## 8. Recruiter-facing Objective

Recall floor exactly0.80 is a product-oriented choice, not a universal statistical
standard. Within floor-eligible calibration configurations, optimize Specificity to
reduce FP. F1 remains secondary. Calibration feasibility does not guarantee heldout
Recall>=0.80, so recall generalization and additional FN are reported prominently.

## 9. Calibration Selection

Exact count-derived Recall>=4/5 filter. Eligible selection order: highest Specificity,
lower FP, higher F1, Precision, Recall, threshold, alpha closest0.50. Exact fractions
compare rates/F1. Complete ties retain first candidate in fixed alpha order.
Thresholds: observed hybrid scores, adjacent midpoints,0,1,nextafter(max,+infinity);
prediction rule H>=threshold. No coarse-grid-only search.

Fallback only if no eligible configuration: highest Recall, Specificity, lower FP,
F1, Precision, threshold, closest alpha0.50. It is implemented/tested and explicitly
false here. With valid positives and endpoint0, an all-positive configuration always
meets the floor, though specificity could be useless; feasibility alone proves little.
No recall-floor reduction or alternative objective was used.

## 10. Frozen Hybrid-v1

- Algorithm/version:hybrid-v1; ECDF fit scope:Task14B.4 calibration only.
- Alpha=**0.50**; baseline weight=**0.50**.
- Threshold=**0.4962121212121212**; recall floor=**0.80**.
- Fallback=false; frozen=true; calibration count132.
- Config SHA-256:
  `ad05275ae64f96fee03378cea50f5ee12f894d9774a7ce2d53a217ece4f7b976`.
- Original components, calibration/split/protocol and development IDF hashes recorded.

Normalization, policy, alpha, threshold and floor were not modified after88 or70.

## 11. Calibration Results

| Alpha | Thresholds searched | Best eligible threshold | TP/TN/FP/FN | Recall | Specificity | Precision | F1 | Hard FP |
|---|---:|---:|---|---:|---:|---:|---:|---:|
|0.25|240|0.48863636363636365|56/48/14/14|0.80|0.774194|0.80|0.80|5|
|**0.50 selected**|220|0.4962121212121212|56/48/14/14|0.80|0.774194|0.80|0.80|7|
|0.75|238|0.4185606060606061|58/41/21/12|0.828571|0.661290|0.734177|0.778523|11|

All three had floor-eligible configurations. Alpha0.25 and0.50 tie on primary/count/
F1/precision/recall criteria; higher threshold selects0.50 before the closest-alpha
tie-break. Alpha0.25 has lower calibration hard FP, but hard FP was not in the frozen
tie policy; it was not retrospectively substituted. Full sweeps—including rejected
configurations with eligible=false—are preserved in JSON and three private CSVs.

## 12. Calibration FP/Recall Trade-off

| Method | FP | FN | Precision | Recall | Specificity | F1 |
|---|---:|---:|---:|---:|---:|---:|
|Semantic-v1|29|8|0.681319|0.885714|0.532258|0.770186|
|Lexical|20|5|0.764706|0.928571|0.677419|0.838710|
|Hybrid|14|14|0.80|0.80|0.774194|0.80|

Hybrid vs semantic:FP−15, FN+6, Recall−0.085714, Specificity+0.241935.
Vs lexical:FP−6, FN+9, Recall−0.128571, Specificity+0.096774.
Components retain old max-F1-selected thresholds as required; hybrid uses a different
recall-floor objective. These are operating-point cost/benefit comparisons, not
matched-objective controls that isolate gains attributable to fusion alone.

## 13. 88-Pair Development Holdout

| Metric | Semantic-v1 | Lexical | Hybrid-v1 |
|---|---:|---:|---:|
|TP|39|39|32|
|TN|20|28|33|
|FP|22|14|9|
|FN|7|7|14|
|Precision|0.639344|0.735849|0.780488|
|Recall|0.847826|0.847826|0.695652|
|F1|0.728972|0.787879|0.735632|
|Accuracy|0.670455|0.761364|0.738636|
|Specificity|0.476190|0.666667|0.785714|
|Balanced Accuracy|0.662008|0.757246|0.740683|
|ROC-AUC|0.761387|0.819876|0.830228|
|AP|0.784297|0.826252|0.846344|
|Hard-negative FP|13/22|7/22|4/22|
|Easy-negative FP|2/12|0/12|0/12|

Same88 pairs, frozen thresholds. This is consumed development holdout evidence, not
new independent validation. Neither alternative alpha was evaluated on88/70.

## 14. Heldout FP/Recall Trade-off

FP decreased by13 versus semantic and5 versus lexical. Specificity increased by
0.309524 and0.119048. But Recall dropped0.152174 relative to both, introducing7
additional FN each. Of46 suitable candidates, hybrid misses14 (30.43%), not7.
Recall=**0.695652**, below0.80 by0.104348 and down0.104348 from calibration0.80.
The floor did **not** generalize. Lower FP therefore comes at too large a recall cost
for the stated operating objective. No threshold/alpha/floor change was made to fix it.

## 15. Hard Negative Results

40 hard candidates:18 human positives/22 negatives.

| Method | TP/TN/FP/FN | FPR | Hard-positive Recall | ROC-AUC | AP |
|---|---|---:|---:|---:|---:|
|Semantic|14/9/13/4|0.590909|0.777778|0.699495|0.725130|
|Lexical|12/15/7/6|0.318182|0.666667|0.661616|0.631189|
|Hybrid|11/18/4/7|0.181818|0.611111|0.714646|0.729538|

Hybrid removes9 hard FP versus semantic and3 versus lexical, but misses3/1 more
hard positives. Hard-negative score mean/median, subgroup distributions and selected
percentiles are retained in heldout_metrics.json. Easy rejection is not the sole
explanation of the FP improvement; nevertheless hard recall is also weak.

## 16. Ranking Results

Hybrid pooled ROC-AUC/AP point estimates exceed both components on88; hard ranking
is competitive/slightly above semantic here. This does not rescue low binary recall:
ranking and shortlist cutoffs are separate. ECDF step ties/saturation are disclosed.

|88 score|Positive mean/median|Negative mean/median|Positive p5/p95|Negative p5/p95|
|---|---|---|---|---|
|Semantic percentile|0.585804/0.553030|0.337843/0.333333|0.181818/0.958333|0.031061/0.726894|
|Lexical percentile|0.620883/0.583333|0.325036/0.287879|0.206439/0.939394|0.053788/0.733333|
|Hybrid|0.603343/0.611742|0.331439/0.316288|0.249053/0.882576|0.049242/0.672159|

All percentiles/distributions are in the saved metrics, not recalculated for selection.

## 17. Positive Recall

Overall Recall:semantic/lexical0.847826, hybrid0.695652. Hard positives:14/18,12/18,
11/18. Positive-candidate positives:semantic25/28,lexical27/28,hybrid21/28.
Hybrid introduces4 extra positive-candidate FN versus semantic and6 versus lexical.
Improved precision is not achieved without substantial suitable-candidate loss.

## 18. Error Complementarity

88 component buckets:53 BOTH_COMPONENTS_CORRECT,15 BOTH_COMPONENTS_WRONG,
6 SEMANTIC_ONLY_CORRECT,14 BASELINE_ONLY_CORRECT. These use original frozen component
thresholds, not0.5 defaults. Paired errors:hybrid correct/semantic wrong13; reverse7.
Hybrid correct/lexical wrong6; reverse8. Complementarity is not automatically recovery.

## 19. Hybrid Recovery

|88 component bucket|Count|Hybrid correct|Hybrid wrong|
|---|---:|---:|---:|
|Both correct|53|49|4|
|Both wrong|15|3|12|
|Semantic-only correct|6|3|3|
|Lexical-only correct|14|10|4|

Hybrid preserves3/6 semantic-only successes and recovers10/14 lexical-only successes,
but breaks4 cases both components got right and fixes only3 both got wrong. CSVs
preserve per-pair outcomes without raw source text.

## 20. Statistical Uncertainty

1000 paired bootstrap resamples of88, seed42, fixed ECDF/config/thresholds throughout.
Hybrid95% CI: F1[0.623377,0.829787], Precision[0.651100,0.900000],
Recall[0.550881,0.818182], Specificity[0.650000,0.904762],
ROC-AUC[0.741232,0.907773], AP[0.737050,0.924792].

|Hybrid minus component|F1 CI|Specificity CI|Recall CI|
|---|---|---|---|
|Semantic|[-0.085887,0.093418]|[0.175000,0.448980]|[-0.266667,-0.055556]|
|Lexical|[-0.144139,0.032919]|[0.025625,0.228571]|[-0.275040,-0.040816]|

Conditional intervals support a specificity gain and recall loss, not a clear F1 win.
They exclude calibration-selection/split/development-inspection uncertainty and are
not confirmatory external evidence. All metric intervals/deltas and valid-resample
counts are in bootstrap.json. No heavy dependency/McNemar package was added.

## 21. 70-Pair Post-hoc Diagnostic

**NOT an independent Hybrid-v1 test. POST-HOC CONSUMED FRESH-SET DIAGNOSTIC.**
Only evaluated after config freeze and88 completion. No70 alpha/threshold/ECDF/feature
selection or component scoring/provider call. Original70 scores/state/labels unchanged.

|Metric|Semantic|Lexical|Hybrid|
|---|---:|---:|---:|
|TP/TN/FP/FN|33/19/13/5|31/20/12/7|28/28/4/10|
|Precision|0.717391|0.720930|0.875000|
|Recall|0.868421|0.815789|0.736842|
|F1|0.785714|0.765432|0.800000|
|Accuracy|0.742857|0.728571|0.800000|
|Specificity|0.593750|0.625000|0.875000|
|Balanced Accuracy|0.731086|0.720395|0.805921|
|ROC-AUC|0.840461|0.816612|0.867188|
|AP|0.829989|0.848977|0.864062|
|Hard FP|6/14|6/14|1/14|
|Easy FP|1/10|1/10|0/10|

FP−9/−8 versus semantic/lexical, but FN+5/+3. Recall remains below0.80; a higher F1
here does not establish primary research success or independent validation. Hybrid
hard-positive recall12/18 (0.666667) versus14/18 for both; hard ranking0.801587 AUC,
0.834044 AP.70 recovery:both-correct37/40 (break3), both-wrong fix2/7,
semantic-only preserve8/12, lexical-only recover9/11. Paired hybrid gains11/losses7
against semantic and10/5 against lexical. No adjustment was made after this diagnostic.

## 22. Algorithm Assessment

**HYBRID-V1 SACRIFICES TOO MUCH RECALL** under the frozen recruiter-facing objective.
Specificity/FP and ranking point gains are real observations, but the intended useful
recall level failed on88 and remains below floor in the consumed70 diagnostic.
F1 need not be maximal, but low recall cannot be ignored simply because FP is lower.
Do not call this clearly promising, declare a production winner or cherry-pick70 F1.

## 23. Recommended Task 14B.7 Decision

Recommendation D: do not promote this binary hybrid operating point; it sacrifices
too much recall. Preserve current production configuration (no switch made here).
Investigate future preregistered, matched-objective component controls, larger truly
unseen role-diverse labels and recall-stability requirements. Ranking fusion may merit
separate validation, not deployment from this experiment. Any new policy/family/floor
must become Hybrid-v2/new task, not a modification of these frozen artifacts.

## 24. Tests

- Evaluation/hybrid tests: **103 passed,1 warning in4.39s**.
- Pure baseline/semantic/canonical-input/BGE-M3 regression: **90 passed in1.05s**.
- Full pytest: **495 passed,3 warnings in107.98s (0:01:47)**, exit0.
- Full suite used existing isolated gjob_db_test via transient TEST_DATABASE_URL;
  credentials/URLs redacted, no new DB/config/OS-wide setting or DEV fallback.
- Warnings:existing google-genai UnionGenericAlias, Starlette/httpx TestClient and
  deprecated HTTP_422_UNPROCESSABLE_ENTITY in the salary-range test.
- Synthetic tests cover ECDF bounds/ties, rational-fusion ties, exact weights, unsupported
  alpha rejection, exact floor, specificity policy/fallback, external data non-influence,
  frozen evaluation without optimizer/refit, paired recovery and network/provider absence.

## 25. Privacy / Security

No raw CV/JD, names/contact fields or vocabulary dumps in results. Only IDs/scores/
labels and allowed private error-file human reasons. CSV privacy exclusions unchanged.
Config stores anonymous calibration score samples and hashes, not source text. No
model/LLM/provider/network call in runner; isolated interpreter test checks imports.
All original220/70 labels/components and state/protocol hashes are verified.

## 26. DB Safety

Offline Hybrid selection/evaluation used no GJob DB or production API. Full integration
tests used only the existing guarded test DB and its normal fixtures/migration bootstrap.
No DEV create/delete, new migration file, production matcher/threshold/API/flow/frontend
change. No production integration or automatic fallback/hybrid deployment.

## 27. Cleanup

Synthetic score/CSV/config fixtures use disposable temp roots and clean themselves.
Only requested real experiment artifacts remain. Original220,70, semantic, baseline,
heldout and fresh-test reports/scores were not deleted/overwritten. No temporary cache,
raw-data copy, new model or DEV cleanup was needed.

Artifacts in this folder:hybrid_config.json; calibration_results.json; three complete
alpha sweep CSVs; heldout_started.json; heldout_metrics.json; heldout_predictions.csv;
heldout_error_overlap.csv; heldout_false_positives.csv; heldout_false_negatives.csv;
fresh_diagnostic_started.json; fresh_diagnostic_metrics.json; fresh_diagnostic_predictions.csv;
fresh_diagnostic_error_overlap.csv; bootstrap.json; report.md. New code/protocol/tests:
hybrid_protocol.py,run_hybrid_experiment.py,HYBRID_V1_PROTOCOL.md,test_hybrid_protocol.py;
README updated. Existing component/metric implementations unchanged.

## 28. Known Limitations

Small, single-reviewer/AI-assisted, difficulty-focused datasets;220 and70 consumed;
no untouched external Hybrid-v1 test; repeated development inspection; limited alpha
family; product-chosen0.80 floor; in-sample selection over many threshold boundaries;
ECDF ties/saturation and distribution shift; transductive old development IDF;
component controls chosen under different max-F1 objective; no representative
production prevalence or per-JD large candidate ranking pool; conditional row-bootstrap
uncertainty excludes model-selection/split uncertainty. Failure on88 was not hidden.

## 29. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -m pytest --noconftest tests/test_baseline_matching.py tests/test_semantic_matching.py tests/test_matching_inputs.py tests/embeddings -q
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_hybrid_experiment --phase calibrate --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_hybrid_experiment --phase heldout --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -X utf8 -u -m evaluation.run_hybrid_experiment --phase fresh --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -m pytest -q
git diff --check -- evaluation
```

Full pytest launched in a child process with guarded test URL resolved only in memory
from existing Docker credentials/template target. Additional read-only diagnostics
inspected saved alternatives/groups/CIs/recovery/hashes; a protected-file read blocked
by default sandbox was retried read-only with permission. No scoring/provider rerun,
test threshold search, extra alpha or algorithm change after either evaluation.

## 30. Final Status

**PASS experiment integrity/regression. Negative product-oriented result:** frozen
Hybrid-v1 removes FP but **sacrifices too much Recall** for the specified objective.
The family, normalization, alpha0.50, threshold0.4962121212121212, floor0.80 and policy
remain frozen. No production switch. Preserve this evidence; do not retune consumed
evaluation splits to make the experiment win.
