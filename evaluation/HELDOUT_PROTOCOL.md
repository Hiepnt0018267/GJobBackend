# Frozen Task 14B.4 protocol

Frozen before real split/calibration/test. Preserve all original labels/reasons,
semantic/baseline scores and implementation hashes. Reuse predictions without any
provider calls, IDF refit, preprocessing change, hybrid or production switch.

## Grouping and split

Typed bipartite graph: CV nodes and JD nodes; each pair is an edge. Whole connected
components only. Component IDs hash sorted pair IDs. Seed 42, calibration target 60%,
acceptable 55–65%; test remainder. Audit sizes/top10 before publishing a partition.
Stop for a giant component or if this fixed method cannot create a reasonable
two-label partition; never random-row-split or break a component.

Deterministic greedy initialization then strictly decreasing flips/component swaps
on an integer count-only objective: deviations from 3/5 of total row count (weight25),
positive count (weight10), each of three candidate groups (weight1), hard human negatives
(weight1) and easy human negatives (weight1). Seeded hash breaks ties. No scores or
algorithm predictions enter partition optimization. No split/seed search using metrics.

## Calibration

Both algorithms: maximize calibration F1, tie-break by higher precision, lower FP,
higher threshold. Exact rational comparison of count-derived F1/precision. Candidates:
calibration observed scores, adjacent midpoints, score-range endpoints and nextafter
calibration maximum toward +infinity. Prediction semantics are score >= threshold.
Selector accepts calibration rows only; do not use full-corpus/test score boundaries.

Persist thresholds exclusively once with input/calibration/test/manifest/algorithm/score
hashes, seed, timestamp and this policy. Test phase reads that artifact from disk.
After freeze, evaluation never calls the selector. An exclusive test-start marker
prevents accidental repeated final evaluations/retuning. Existing artifacts are never
overwritten; resume only an unfinished phase with unchanged provenance.

## Test interpretation

Same test pairs and frozen thresholds; pooled/groups classification, ROC-AUC/AP, paired
errors and FP/FN. 1000 paired row bootstrap resamples, seed42, fixed thresholds; report
95% percentile intervals and valid-resample counts. Shared entities inside test mean
row intervals can understate uncertainty. No claim of significance from small point
differences, no automatic winner/hybrid or production calibration.

## Critical validity limits

This is **retrospective grouped threshold holdout**, not a previously unseen external
test: all 220 labels have already appeared in global analyses. The frozen lexical
reference's IDF was fitted on all referenced corpus texts, including later test texts.
There is no new test-label use in calibration, but this remains transductive covariate
exposure and is not a strictly inductive deployment evaluation. Refitting IDF would
change frozen scores, so it is not done here. Independent future data is needed for
confirmatory validation. The reference is baseline-v1-offline-lexical, not production's
structured skill matcher. Sampling groups are not ground truth.
