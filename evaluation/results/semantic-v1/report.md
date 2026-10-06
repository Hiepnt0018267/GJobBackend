# Semantic-v1 Benchmark

## Verification and interpretation

- Input validation: PASS, 220/220, 116 human positives and 104 human negatives.
- Human input SHA-256 remained unchanged:
  `28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8`.
- Initial complete run: 202 unique CVs, 180 unique JDs, 0 cache hits, 382 misses,
  77.075 seconds. Independent cache replay: 382 hits, 0 misses, 9.922 seconds.
- Replay predictions were byte-identical (SHA-256
  `588a6d0fbfddc4ef6f7088fb354166bdf3662b15ace5774e7d572aadc9eaae46`).
- ROC-AUC was independently verified by pairwise positive/negative comparisons;
  Average Precision was independently verified by ordered positive ranks.
- Every prediction's human label and reason matches the input unchanged.
- Tests: `venv\Scripts\python.exe -m pytest evaluation/tests -q`:
  **50 passed, 1 warning in 2.01s** (existing Starlette/httpx deprecation).
- Regression: `venv\Scripts\python.exe -m pytest --noconftest tests/test_semantic_matching.py tests/embeddings/test_ollama_provider.py tests/embeddings/test_embedding_config.py -q`:
  **63 passed in 0.87s**. `--noconftest` avoids the project's DB-initializing test harness.
- No production scoring/provider/mapper files were edited, no labels were changed,
  no baseline benchmark was run, and no production threshold was changed.
- No application APIs, extraction LLMs, DEV/production database operations or test
  records were used. The cache replay used a disposable directory which was removed.

### Important failures at threshold 0.5

This threshold is an evaluation assumption, not a calibrated production threshold.
It classifies 210/220 pairs as positive: TP=115, TN=9, FP=95, FN=1.
Recall is high (99.14%) but specificity is only 8.65%; this is poor rejection of
unsuitable pairs, not strong overall recruitment matching quality.

The hard group contains 48 human positives and 52 human negatives, despite its sampling
name. All 52 human negatives are false positives (FPR 100%). The easy group has 30
human negatives; 21 are false positives (FPR 70%). Even the easy sanity group performs
poorly at this threshold. Positive/negative score means (0.6361 / 0.5800) overlap.

Post-hoc inspection of the strongest false-positive human explanations suggests
coarse occupational similarity can obscure mandatory role requirements:

- `pair_9ea8229393e5607fe5f2` (0.6994): branch-management/financial-services experience
  versus the reviewer's evidence requirements for Personal Banker duties.
- `pair_424434b0077e9df4675d` (0.6906): the reviewer cites missing managerial/hospitality,
  certification and language requirements.
- `pair_80a7790d275311155fad` (0.6892): medical claims/coding/insurance experience
  versus Medical Director licensing/clinical requirements.
- The sole false negative, `pair_00b86c026205d5d0c274` (0.4923), was judged relevant
  for Director of Communications based on content/campaign experience.

These are interpretations of human reasons after scoring, not new labels or verified
eligibility rules. They did not enter embedding inputs or change semantic-v1.

### Exploratory threshold

The best observed in-sample F1 threshold is 0.575883997681205: F1=0.7554,
precision=0.6481, recall=0.9052, accuracy=0.6909, specificity=0.4519.
This is an in-sample exploratory threshold estimate, not a held-out production
calibration. It still yields 57 FP and 11 FN; it was not applied to production.

### Context diagnostics and commands

Ollama version: 0.34.2; BGE-M3 model metadata reports `bert.context_length=8192`.
The unchanged production embedding request failed with `EmbeddingInputTooLongError`.
An offline request with num_ctx=8192 alone still failed. The same 9733-character CV
passed with num_ctx=8192 and num_batch=8192, returning 1024 dimensions and
prompt_eval_count=2356. No text was truncated. These runtime parameters are recorded
in cache/report identity; this is not an evaluation of production's default context.
Ollama's native embedding endpoint supports request options and `truncate=false`:
[official API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md).

```powershell
venv\Scripts\python.exe -u -m evaluation.run_semantic_benchmark --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir C:/DATN/Datasets --output-dir evaluation/results/semantic-v1 --num-ctx 8192 --num-batch 8192
```

Added code: `evaluation/run_semantic_benchmark.py`, `evaluation/benchmark_metrics.py`,
`evaluation/tests/test_semantic_benchmark.py`. Updated `.gitignore` and
`evaluation/README.md`. Created the seven requested result files; cache vectors and
error CSVs remain gitignored. No migrations or DB cleanup were necessary.

## 1. Objective

Evaluate existing semantic-v1 against 220 human-reviewed pairs, offline.

## 2. Ground Truth

Only label/label_reason are ground truth. AI suggestions assisted the reviewer; sampling groups are not labels.

## 3. Dataset

Human positives: 116; negatives: 104.

## 4. Semantic-v1 Implementation

Reuses app.services.semantic_matching_service.SemanticMatchingService.match and cosine_similarity unchanged.
Score = dot(CV, JD) / (norm(CV) * norm(JD)), raw range [-1, 1]. No weighted title/skills rules.
Embedding model: bge-m3; adapter: raw-source-normalized-v1.
CV uses original Resume_str with existing normalize_multiline_text. JD uses existing TITLE/DESCRIPTION/SKILLS section helpers and skills_desc.
This isolates matching from extraction. It is not an end-to-end evaluation of production structured-CV preprocessing.
No invented skill-code meanings, structured fields, industry/experience enums, or LLM extraction.

Offline embedding options: num_ctx=8192, num_batch=8192, truncate=false.
The unchanged production request failed on full-text inputs. num_ctx alone still failed; explicit encoder num_batch was required by local Ollama.
These are documented offline full-text runtime settings, not a production configuration change.

## 5. Default Threshold

Evaluation threshold: 0.5. No production classification threshold was found; this is an evaluation assumption.

## 6. Main Results

| Metric | Result |
|---|---:|
| precision | 0.5476190476190477 |
| recall | 0.9913793103448276 |
| f1 | 0.7055214723926381 |
| accuracy | 0.5636363636363636 |
| specificity | 0.08653846153846154 |
| roc_auc | 0.7771883289124668 |
| average_precision | 0.7793172421704532 |
| balanced_accuracy | 0.5389588859416445 |
| mcc | 0.18675513070059435 |

PR-AUC is reported as non-interpolated Average Precision; undefined metrics are null, not fabricated zeros.

## 7. Confusion Matrix

TP=115, TN=9, FP=95, FN=1

## 8. Threshold Analysis

This is an in-sample exploratory threshold estimate, not a held-out production calibration.
Exploratory best F1: {'TP': 105, 'TN': 47, 'FP': 57, 'FN': 11, 'threshold': 0.575883997681205, 'precision': 0.6481481481481481, 'recall': 0.9051724137931034, 'f1': 0.7553956834532374, 'accuracy': 0.6909090909090909, 'specificity': 0.4519230769230769, 'false_positive_rate': 0.5480769230769231, 'balanced_accuracy': 0.6785477453580901, 'mcc': 0.4046304167506211}
Production threshold was not changed.

## 9. Candidate Group Analysis

| Group | Count | Human + / - | FP / FN | F1 | Accuracy |
|---|---:|---|---|---:|---:|
| POSITIVE_CANDIDATE | 90 | 68 / 22 | 22 / 1 | 0.8535031847133758 | 0.7444444444444445 |
| HARD_NEGATIVE_CANDIDATE | 100 | 48 / 52 | 52 / 0 | 0.6486486486486487 | 0.48 |
| EASY_NEGATIVE_CANDIDATE | 30 | 0 / 30 | 21 / 0 | 0.0 | 0.3 |

## 10. Hard Negative Analysis

Hard-group FPR among human negatives: 1.0.
hard_negative_errors.csv lists all hard-group human negatives, highest score first; predictions identify which are false positives.
Easy-group success must not obscure hard-group errors; sampling groups can contain human positives.

## 11. False Positives

Count: 95. See false_positives.csv, highest score first.

## 12. False Negatives

Count: 1. See false_negatives.csv, lowest score first.

## 13. Limitations

220-pair, single-human-reviewer, difficulty-focused sample; not representative production prevalence.
In-sample threshold analysis is not held-out calibration. No baseline comparison. Matching, not extraction, is measured.
Raw-source adapter differs from structured production CV representation and may retain incidental source text.
ROC-AUC/AP evaluate pooled pair ranking, not a representative per-job candidate ranking test.

## 14. Conclusion

Results describe measured semantic-v1 behavior only; no superiority over baseline-v1 is claimed.

## 15. Next Step

Run baseline-v1 against the exact same human-labeled pairs, with a documented deterministic adapter.

## Reproducibility

```json
{
  "input": "C:\\DATN\\GJobBackend\\evaluation\\data\\derived\\evaluation_pairs_labeled.csv",
  "input_sha256": "28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8",
  "source_hashes": {
    "Resume.csv": "816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d",
    "job_postings.csv": "d782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f"
  },
  "implementation": "app.services.semantic_matching_service.SemanticMatchingService.match",
  "identity": {
    "model": "bge-m3:latest",
    "digest": "7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab",
    "provider": "ollama",
    "adapter": "raw-source-normalized-v1",
    "core_sha256": "0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf",
    "base_url": "http://localhost:11434",
    "num_ctx": 8192,
    "num_batch": 8192,
    "truncate": false,
    "adapter_sha256": "842c0e187aa7def5f85ae01ba9096bc706d430b245a3b309eb47c2f4bde0ee53"
  },
  "model": "bge-m3",
  "score_range": [
    -1,
    1
  ],
  "threshold": 0.5,
  "threshold_grid": [
    -1.0,
    -0.95,
    -0.9,
    -0.85,
    -0.8,
    -0.75,
    -0.7,
    -0.65,
    -0.6,
    -0.55,
    -0.5,
    -0.45,
    -0.4,
    -0.35,
    -0.3,
    -0.25,
    -0.2,
    -0.15,
    -0.1,
    -0.05,
    0.0,
    0.05,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.43281486749777986,
    0.45,
    0.45735710749186576,
    0.4594491696069742,
    0.4729871972192861,
    0.47910530886977193,
    0.48192904943816345,
    0.4824967301747574,
    0.4911687311002232,
    0.49234342290780964,
    0.4991367781592712,
    0.5,
    0.5046538140913426,
    0.5053805580957865,
    0.5074192635674158,
    0.5094380725043316,
    0.5102306903729071,
    0.5138906922940993,
    0.514033343643461,
    0.5164217314279558,
    0.5168925358693155,
    0.5173834310399343,
    0.5196235421733558,
    0.5198899823700581,
    0.5213596087048936,
    0.5293969652987226,
    0.5304236742205632,
    0.5305938562307524,
    0.5306184100334508,
    0.5343026214617281,
    0.5365962986174662,
    0.5371062860271915,
    0.5450434464885209,
    0.54563708692906,
    0.55,
    0.5508825920965111,
    0.5535764508732416,
    0.5536403638199675,
    0.5537082070893857,
    0.5555436731137411,
    0.5574417106174402,
    0.5613652519450496,
    0.5619435719893916,
    0.5625161179578033,
    0.5626204496581013,
    0.5635388083981683,
    0.5640008165006256,
    0.5650653745149622,
    0.5651910449735379,
    0.5653485210446305,
    0.5668227110598988,
    0.5671052665411567,
    0.5680207110910369,
    0.5687476650372307,
    0.5687644331610687,
    0.569614398968898,
    0.5697558666345317,
    0.571986125664264,
    0.5727500307850931,
    0.5749800784807553,
    0.575778567376408,
    0.575883997681205,
    0.578163648471064,
    0.5822268504280697,
    0.5830859593445233,
    0.5831580799508733,
    0.5832227309268933,
    0.5834823719101341,
    0.5837159126900119,
    0.5848592010591942,
    0.5863325562486924,
    0.5867267674262028,
    0.587568659703164,
    0.5882854590016626,
    0.5888479903368926,
    0.5902308341016713,
    0.5909056993487682,
    0.5911307865831773,
    0.5935128238862744,
    0.5937198020812267,
    0.5944988893730744,
    0.5951666021562863,
    0.5956289894479768,
    0.5973568133787666,
    0.5980056296463645,
    0.5989074376976974,
    0.59971658258156,
    0.5997606275747958,
    0.5999997998208703,
    0.6,
    0.6013681448303972,
    0.6014731366861921,
    0.6024324757720878,
    0.6031380521096247,
    0.6048071388839932,
    0.6048813010382067,
    0.6056602103535415,
    0.6056846704102894,
    0.6058428288315509,
    0.606865273535165,
    0.6069690797239841,
    0.6070073334816485,
    0.6072339671124024,
    0.6083608815433719,
    0.6091320721731017,
    0.6092055052843482,
    0.6094179652128613,
    0.6094716216791619,
    0.6098513857678453,
    0.6101370827645152,
    0.6108718845890577,
    0.6117313771010915,
    0.6118028793796784,
    0.612451964136163,
    0.6151228946137878,
    0.615298458351819,
    0.616039134618331,
    0.6161033223005956,
    0.6161425569209653,
    0.6164133922859732,
    0.617392300945566,
    0.6182359711875922,
    0.6186098286629792,
    0.6195334405908844,
    0.6213183467154639,
    0.6217767527195123,
    0.6218498821506655,
    0.6222238401066917,
    0.6228403566921057,
    0.6229314598543942,
    0.6232549165297139,
    0.6235558022380722,
    0.6235937276335928,
    0.6247862135442088,
    0.6254206143964969,
    0.6267767373745332,
    0.6270601394980428,
    0.627872046287997,
    0.628860130001506,
    0.6291357636700982,
    0.629559563170642,
    0.6295930657077127,
    0.6296900501432495,
    0.6298824975434028,
    0.6309003895989896,
    0.6311334363954303,
    0.6329193820811149,
    0.6332278858859585,
    0.6337663099761832,
    0.6368608436501543,
    0.63690121285264,
    0.6371670126336936,
    0.6381472432686234,
    0.6384425910347278,
    0.6386861991996065,
    0.6392388084564702,
    0.6401356532107441,
    0.6404659930302594,
    0.6413968312143856,
    0.642758970505083,
    0.6438944430054031,
    0.6441770240646449,
    0.6449674426086699,
    0.645407157526829,
    0.6459201128313982,
    0.6464748938900112,
    0.6465816976893504,
    0.6472139090699666,
    0.6478439475480242,
    0.6485884308055414,
    0.65,
    0.6505498694464726,
    0.6517204263211565,
    0.6531224309905765,
    0.654191513460054,
    0.6548664978325663,
    0.6553727832755991,
    0.6554083380101817,
    0.6571994067371629,
    0.6583027198217841,
    0.6585904646835808,
    0.6589144329084479,
    0.6590925825926252,
    0.6602449818916591,
    0.6605076605828248,
    0.6614417552542452,
    0.6653506082192839,
    0.6657924204018592,
    0.6658426338796115,
    0.6674827840589775,
    0.6678922756232747,
    0.6683913229151401,
    0.6694925101810398,
    0.6710641925719592,
    0.6717217958894893,
    0.6730808751557855,
    0.6732585030188512,
    0.6735114917625935,
    0.6751123443582515,
    0.6755052923133154,
    0.6774517095143262,
    0.6807655050596795,
    0.680906438428452,
    0.6821883586401154,
    0.6831591339901464,
    0.6840082354936348,
    0.684120917376374,
    0.6852024133005097,
    0.6853758345646522,
    0.6857293715027731,
    0.689160450035321,
    0.6899160571079002,
    0.6906315195576421,
    0.6927152053029512,
    0.6928455644248391,
    0.6983446792308527,
    0.6994389222388364,
    0.7,
    0.7042908885981141,
    0.7060130025747311,
    0.7213768007197124,
    0.7281100658165947,
    0.7285432564580003,
    0.7357649845281529,
    0.75,
    0.7560300207393359,
    0.7654083740190964,
    0.7654083740190966,
    0.8,
    0.85,
    0.9,
    0.95,
    1.0
  ],
  "git_commit": "82c5840a8a03721c6f10d54628d796ade639f57f",
  "timestamp": "2026-10-05T06:28:54.710114+00:00",
  "command": [
    "C:\\DATN\\GJobBackend\\evaluation\\run_semantic_benchmark.py",
    "--input",
    "evaluation/data/derived/evaluation_pairs_labeled.csv",
    "--data-dir",
    "C:/DATN/Datasets",
    "--output-dir",
    "evaluation/results/semantic-v1",
    "--num-ctx",
    "8192",
    "--num-batch",
    "8192"
  ],
  "partial": false,
  "unique_cvs": 202,
  "unique_jobs": 180
}
```

## Highest-scoring false positives / Lowest-scoring false negatives

| Error | Pair ID | Score | Sampling group |
|---|---|---:|---|
| FP | pair_9ea8229393e5607fe5f2 | 0.6994389222388364 | HARD_NEGATIVE_CANDIDATE |
| FP | pair_424434b0077e9df4675d | 0.6906315195576421 | POSITIVE_CANDIDATE |
| FP | pair_80a7790d275311155fad | 0.689160450035321 | POSITIVE_CANDIDATE |
| FP | pair_d188d5d01d5f2451a71d | 0.6852024133005097 | POSITIVE_CANDIDATE |
| FP | pair_de6a8667e4609151ea3d | 0.6751123443582515 | POSITIVE_CANDIDATE |
| FN | pair_00b86c026205d5d0c274 | 0.49234342290780964 | POSITIVE_CANDIDATE |
