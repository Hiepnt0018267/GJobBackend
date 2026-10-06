# Frozen Hybrid-v1 experiment protocol

Frozen before real calibration/evaluation. Reuse immutable component scores only.
No source text/LLM/provider call, component algorithm change, IDF refit or production
integration. Baseline is the offline lexical reference, not the structured skill engine.

## Allowed family and normalization

For component calibration scores fit right-inclusive ECDF:
`F_cal(x) = count(calibration scores <= x) / 132`. Store sorted calibration samples.
Duplicates count multiplicity; below calibration min maps0, at/above max maps1;
observed min maps its tied count/132. Unseen values use only the calibration reference.
No extrapolation, fresh/heldout fit or alternative normalization search. Percentiles
are relative ranks, not calibrated probabilities; unseen-score ties/saturation can
affect ranking.

`hybrid = alpha * semantic_percentile + (1-alpha) * baseline_percentile`.
Exactly alpha0.25,0.50,0.75. No bonus, gate, nonlinear model or added occupation rule.
Fusion combines integer ECDF ranks over a common denominator4N before the final float
division, algebraically the same weights. This prevents floating ulp differences from
splitting mathematically equal weighted percentile scores during threshold selection.

## Operating selection

On132 calibration only: thresholds are observed hybrid scores, adjacent midpoints,
0,1 and nextafter(max,+infinity); predict score >= threshold. Exact count-derived
Recall >=4/5 filters eligible configs. Max Specificity, then lower FP, higher F1,
Precision, Recall, threshold, alpha closest0.50. Exact F1/rate fractions compare ties;
complete ties retain first candidate in fixed alpha order. Preserve/reveal all sweeps,
including rejected candidates. No post-result extra weights/policies.

If none eligible: highest Recall, Specificity, lower FP, F1, Precision, threshold,
alpha closest0.50; record fallback true, never lower floor. With valid positives and
all-positive endpoint0, a floor-eligible candidate necessarily exists, though its
specificity may be useless. Fallback is retained/tested for restricted synthetic cases.

## Data sequence

132 tune/normalize -> persist exclusive hybrid_config ->88 consumed retrospective
development holdout once ->70 consumed fresh post-hoc diagnostic once. Phase70 is
blocked until phase88 results exist. Neither evaluation split enters the optimizer.
All original labels/component scores/thresholds/IDF state remain byte-identical.
No test/fresh optimizer or component rescoring is called.

Components retain Task14B.4 max-F1 thresholds per task requirements, not newly
recall-floor calibrated controls. Thus FP/recall comparisons describe operating-point
tradeoffs; they cannot isolate fusion gains from different selection objectives.

## Uncertainty and interpretation

1000 paired row resamples, seed42, fixed config. Metrics/CI for F1, Precision, Recall,
Specificity, ROC-AUC/AP and Hybrid-minus-each-component F1/Specificity/Recall.
Report subgroup hard-negative FP/recall/ranking and component-bucket recovery/breakage.
Do not optimize after evaluation, force a winner or call70 independent Hybrid testing.
No untouched external test; repeated development inspection, limited family, small
single-reviewer/AI-assisted difficulty-focused labels and unknown production prevalence.
Any changed family/policy/floor/normalization becomes a new version/task.
