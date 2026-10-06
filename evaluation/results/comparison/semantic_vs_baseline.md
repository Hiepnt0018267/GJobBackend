# Semantic-v1 vs Baseline-v1

## Post-run interpretation and sanity review

The frozen lexical default predicts **all 220 negative**, so its 0 FP and 100%
specificity are degenerate rejection, not evidence of a superior recruitment classifier.
Precision is undefined; recall/F1 are zero. Default error-overlap counts largely
reflect opposite constant/permissive operating points, not proven hybrid complementarity.

Pooled lexical ROC-AUC/AP (0.834466/0.819943) exceed semantic (0.777188/0.779317)
on this sample. At each method's own exploratory best F1, lexical F1=0.818898,
precision=0.753623, recall=0.896552, FP=34, FN=12; semantic F1=0.755396,
precision=0.648148, recall=0.905172, FP=57, FN=11. Both choices are IN-SAMPLE.

On the 52 human-negative hard cases, best-threshold lexical FP=16 (30.77%) versus
semantic FP=35 (67.31%), with hard-positive recall 81.25% versus 93.75%.
However ranking **within the hard group** favors semantic: ROC-AUC 0.762821 versus
0.751603, AP 0.773228 versus 0.690948. Lexical best-threshold easy FP=0/30 versus
semantic 4/30. Pooled ranking gains must not hide this mixed hard-case result.

Neither frozen default is sufficiently validated for deployment. Use held-out,
CV/JD-grouped calibration/testing data before selecting an operating point or winner.
This offline reference is distinct from production's structured skill matcher.

### Inspected examples (no label changes)

There are no default baseline FP or default hard-negative failures. To examine
failure patterns, these explicitly **exploratory** cases were inspected instead:

- Five highest-scoring exploratory FP: `pair_d188d5d01d5f2451a71d` (0.458720),
  `pair_9ea8229393e5607fe5f2` (0.450397), `pair_08e59d39b40e7d9a60bb` (0.426330),
  `pair_bef85c51805986b7fd9e` (0.416185), `pair_47390f706386a24597b7` (0.413747).
- Five exploratory hard failures: `pair_9ea8229393e5607fe5f2`,
  `pair_47390f706386a24597b7`, `pair_5cf46717e4c3ae2c5251`,
  `pair_ecff6917d440c479dbb6`, `pair_e2b74a7195efd0293b7c`.
- Five lowest-score default FN: `pair_f323eaeb937b92906e0e`,
  `pair_9a44efc39a230519f808`, `pair_72f973dc7aa568fe0cde`,
  `pair_420e1a29b5a003da0766`, `pair_ded4c6cc998e2d8b1878`.
- Five semantic-only-correct default cases: `pair_04265b56be13601792a5`,
  `pair_04be82e7b02372bc30f5`, `pair_0679e3f11adf0eb92d83`,
  `pair_06e6916b7738ae51ab37`, `pair_07064fae21cb21e66e8c`.
- Five baseline-only-correct default cases: `pair_07cbddd5debb210cad77`,
  `pair_08e59d39b40e7d9a60bb`, `pair_0b43ce019c2e6293ca29`,
  `pair_0f1ea871fb169fccf78c`, `pair_16628dc76c06a34b9a40`.

Human explanations after scoring suggest broad occupational word overlap can conceal
missing required duties/tools/compliance; literal lexical overlap can miss transferable
experience/related titles. Those explanations are not new annotations and never enter
features or weights. No post-hoc tuning was performed.

## 1. Evaluation Setup

Same input hash, all 220 source-linked human decisions; same metric/tie/threshold-exploration policy. Candidate groups are not labels.

## 2. Algorithms

Semantic: existing BGE-M3 raw-text cosine. Baseline: frozen offline TF-IDF/title reference, not production structured-skill coverage.

## 3. Default Threshold Comparison

| Metric | Semantic-v1 | Offline lexical baseline |
|---|---:|---:|
| threshold | 0.5 | 0.5 |
| TP | 115 | 0 |
| TN | 9 | 104 |
| FP | 95 | 0 |
| FN | 1 | 116 |
| precision | 0.5476190476190477 | None |
| recall | 0.9913793103448276 | 0.0 |
| f1 | 0.7055214723926381 | 0.0 |
| accuracy | 0.5636363636363636 | 0.4727272727272727 |
| specificity | 0.08653846153846154 | 1.0 |
| roc_auc | 0.7771883289124668 | 0.8344661803713528 |
| average_precision | 0.7793172421704532 | 0.8199429081710353 |
| Hard-negative FP | 52 | 0 |
| Easy-negative FP | 21 | 0 |

## 4. Best Exploratory F1 Comparison

BOTH IN-SAMPLE EXPLORATORY; no production calibration or cherry-picking default versus best.
| Metric | Semantic-v1 | Offline lexical baseline |
|---|---:|---:|
| threshold | 0.575883997681205 | 0.24733698756646583 |
| TP | 105 | 104 |
| TN | 47 | 70 |
| FP | 57 | 34 |
| FN | 11 | 12 |
| precision | 0.6481481481481481 | 0.7536231884057971 |
| recall | 0.9051724137931034 | 0.896551724137931 |
| f1 | 0.7553956834532374 | 0.8188976377952756 |
| accuracy | 0.6909090909090909 | 0.7909090909090909 |
| specificity | 0.4519230769230769 | 0.6730769230769231 |
| roc_auc | 0.7771883289124668 | 0.8344661803713528 |
| average_precision | 0.7793172421704532 | 0.8199429081710353 |

## 5. Hard Negative Comparison

{
  "human_negatives": 52,
  "semantic_fp": 52,
  "baseline_fp": 0,
  "both_fp": 0,
  "semantic_only_fp": 52,
  "baseline_only_fp": 0
}

## 6. Easy Negative Comparison

HARD_NEGATIVE_CANDIDATE: semantic FP=52, baseline FP=0; FPR=1.0 / 0.0.
EASY_NEGATIVE_CANDIDATE: semantic FP=21, baseline FP=0; FPR=0.7 / 0.0.

## 7. False Positive Comparison

Semantic=95; baseline=0.

## 8. False Negative Comparison

Semantic=1; baseline=116.

## 9. Error Overlap

{
  "BOTH_WRONG": 1,
  "BOTH_CORRECT": 9,
  "SEMANTIC_ONLY_CORRECT": 115,
  "BASELINE_ONLY_CORRECT": 95
}

## 10. Ranking Quality

ROC-AUC=0.7771883289124668 / 0.8344661803713528; AP=0.7793172421704532 / 0.8199429081710353.

## 11. Tradeoffs

Lower FP alone is not superiority: compare recall/FN, F1, specificity and ranking together. Different score scales make threshold 0.5 uncalibrated for both.

## 12. Which method appears stronger?

See measured metrics and post-run review. Do not force a winner from accuracy alone; no held-out validation supports final deployment selection.

## 13. Recommended Next Step

Reserve held-out, CV/JD-grouped calibration/testing data and evaluate chosen operating points. No hybrid or production switch is implemented.
