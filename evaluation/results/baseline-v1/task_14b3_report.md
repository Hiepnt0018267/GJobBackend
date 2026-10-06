# Task 14B.3 Baseline-v1 Benchmark Report

## 1. Executive Summary

Final acceptance: **PASS**. All 220 pairs were scored successfully, focused tests
passed, and full regression passed: **450 passed, 3 warnings in 114.79s (0:01:54)**,
exit code 0. The existing test database was reused without creating a new config or DB.
PASS refers to evaluation integrity and regression, not a claim of strong default
baseline performance or production readiness.

Reference: `baseline-v1-offline-lexical`, frozen 0.7 TF-IDF lexical cosine + 0.3 title
coverage. It is not the existing production structured-skill engine. Default 0.5
predicts every pair negative: precision undefined, recall/F1=0, ROC-AUC=0.834466,
AP=0.819943, hard-negative FP=0/52. Zero FP here is **not** strong matching quality.

## 2. Source Review

Inspected production baseline_matching_engine.py, matching_input_mapper.py,
models/skill.py, baseline/matching/semantic/embedding tests, evaluation validators,
metrics, semantic runner and all semantic artifact schemas/metrics. Source headers
confirmed Resume_str and title/description/skills_desc; job_skills has 35 opaque
skill_abr values, no trustworthy dictionary.

Production `BaselineMatchingEngine.match` measures exact structured-skill coverage
with weight 1 and two-decimal score 0–100; no JD skills gives a controlled error.
There is no title/lexical/seniority component in that existing engine. The raw corpus
does not contain matching structured CV/JD skills, so using it for all 220 pairs would
require inventing an adapter's skill meanings. Production code remains untouched.

Reused the human validator, atomic CSV writer, classification/ranking/group/threshold
metric policy; existing semantic artifacts were read and preserved, never rerun.

## 3. Implementation Plan

Added baseline_lexical.py, run_baseline_benchmark.py, tests/test_baseline_benchmark.py,
BASELINE_V1_FROZEN.md. Modified benchmark_metrics.py only to support a score-field
parameter (semantic defaults unchanged) and shared threshold exploration; README updated.
Created seven baseline artifacts and three comparison artifacts plus this task report.

Deviation: explicit separate offline reference identifier, rather than pretending the
raw-text reference measures production's structured-skill baseline. No skill dictionary,
seniority parser or extra signal was invented. Weights/default were frozen before run.

## 4. Ground Truth

- Input: evaluation/data/derived/evaluation_pairs_labeled.csv.
- SHA-256: `28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8`.
- Validation PASS: 220/220, human positive=116, human negative=104.
- Sampling groups: 90 positive candidates / 100 hard candidates / 30 easy candidates.
- label and label_reason are the only ground truth; input was not modified.

## 5. Baseline-v1 Definition

Unicode NFKC/casefold, email/URL span removal, deterministic punctuation-aware tokens,
frozen local generic English stopwords. No stemming, synonym mapping or semantic model.
Title feature: literal normalized JD title-token coverage in CV tokens. Full-document
lexical feature: TF-IDF cosine over the raw CV and JD title/description/skills_desc.
CV Category, labels/reasons, candidate type, sampling score, semantic score, salary,
location and company metadata never enter scoring. No dedicated skill/seniority signal.
Stopwords are local source constants; their SHA is in metrics.json. No skill vocabulary.

## 6. Exact Formula

`baseline_score = 0.7 * lexical_TFIDF_cosine + 0.3 * title_token_coverage`.
TF=`1+ln(term_count)`; IDF=`ln((1+N)/(1+document_frequency))+1`.
IDF is fitted on unique referenced CV/JD entities (202+180), without labels or semantic
predictions. Title coverage=`|JD-title tokens intersect CV tokens| / |JD-title tokens|`.
Empty title/vectors give 0; score is bounded [0,1]. Sorted accumulation is deterministic.
Lexical cosine is a traditional IR statistic, not BGE-M3 or any learned embedding.

## 7. Default Threshold

0.5 was frozen before the real run as the midpoint of the normalized score range.
It was **not** picked using labels and is not production calibration. Real scores range
0.023449–0.482687, so this default is inappropriate on this corpus. It was not changed
after seeing that outcome. Further algorithm/default changes require a new version/task.

## 8. Benchmark Execution

```powershell
venv\Scripts\python.exe -u -m evaluation.run_baseline_benchmark --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir C:/DATN/Datasets --output-dir evaluation/results/baseline-v1
```

Scored 220/220, no skips/limit. Runtime 2.557915 seconds. No network/provider/DB calls.
An independent repeat reproduced every score exactly and kept human label/reason intact.

## 9. Main Metrics

| Metric | Frozen default result |
|---|---:|
| TP | 0 |
| TN | 104 |
| FP | 0 |
| FN | 116 |
| Precision | undefined (no predicted positives) |
| Recall | 0 |
| F1 | 0 |
| Accuracy | 0.472727 |
| Specificity | 1 |
| ROC-AUC | 0.834466 |
| PR-AUC / non-interpolated AP | 0.819943 |

Positive mean/median: 0.353141 / 0.384185; negative mean/median: 0.209952 / 0.214872.
Percentiles and balanced accuracy/MCC are in metrics.json; undefined values remain null.

## 10. Threshold Analysis

Default=0.5. Exploratory best=0.24733698756646583; TP=104, TN=70, FP=34, FN=12;
precision=0.753623, recall=0.896552, F1=0.818898, accuracy=0.790909,
specificity=0.673077. Grid [0,1] at 0.05 increments plus observed-score boundaries,
same metric/tie policy as semantic. Highest threshold breaks equal-F1 ties.

**This is an in-sample exploratory threshold estimate, not a held-out production
calibration.** It does not replace the frozen default or change production.

## 11. Candidate Group Analysis

| Sampling group | Count | Human + / - | Default TP/TN/FP/FN | Accuracy |
|---|---:|---|---|---:|
| POSITIVE_CANDIDATE | 90 | 68 / 22 | 0 / 22 / 0 / 68 | 0.244444 |
| HARD_NEGATIVE_CANDIDATE | 100 | 48 / 52 | 0 / 52 / 0 / 48 | 0.52 |
| EASY_NEGATIVE_CANDIDATE | 30 | 0 / 30 | 0 / 30 / 0 / 0 | 1 |

Full precision/recall/F1, mean/median and distribution metrics are in metrics.json.
Group labels are sampling categories, not ground truth.

## 12. Hard Negative Analysis

Default: 0/52 human negatives are FP, but all 48 human positives in the hard group are
FN. Thus this cannot establish superior hard-case discrimination.
At both methods' exploratory best thresholds: baseline hard FP=16/52 (30.77%),
hard recall=39/48 (81.25%); semantic hard FP=35/52 (67.31%), recall=45/48 (93.75%).
Ranking within the whole hard group favors semantic slightly on ROC-AUC
(0.762821 vs 0.751603), and more on AP (0.773228 vs 0.690948).

## 13. False Positives

Default FP=0; there are no top-five default FP/hard-failure examples to inspect.
As explicitly exploratory diagnostics, inspected the top five best-threshold FP and
top five best-threshold hard-group FP; IDs/scores are listed in comparison report.
Human reasons cite specific missing role experience, accounting software/compliance,
networking tools or teaching duties despite broad occupational word overlap.
No labels, tokens, weights or special-case rules were changed after inspection.

## 14. False Negatives

Default FN=116. Inspected the five lowest-scoring human positives:
`pair_f323eaeb937b92906e0e`, `pair_9a44efc39a230519f808`,
`pair_72f973dc7aa568fe0cde`, `pair_420e1a29b5a003da0766`,
`pair_ded4c6cc998e2d8b1878`. Human reasons describe recruiting, fitness management,
electrical maintenance and transferable sales/customer-service experience. Literal
title/document overlap can miss related role wording. Default threshold also rejects
even the highest-scoring positives. No source data or human judgments were changed.

## 15. Semantic-v1 vs Baseline-v1

| Metric | Semantic default 0.5 | Lexical default 0.5 |
|---|---:|---:|
| TP | 115 | 0 |
| TN | 9 | 104 |
| FP | 95 | 0 |
| FN | 1 | 116 |
| Precision | 0.547619 | undefined |
| Recall | 0.991379 | 0 |
| F1 | 0.705521 | 0 |
| Accuracy | 0.563636 | 0.472727 |
| Specificity | 0.086538 | 1 |
| ROC-AUC | 0.777188 | 0.834466 |
| AP | 0.779317 | 0.819943 |
| Hard-negative FP | 52 | 0 |
| Easy-negative FP | 21 | 0 |

The same numeric threshold does not calibrate different score distributions. No best
threshold was substituted for one method in this default table.

## 16. Exploratory Best-F1 Comparison

| Metric | Semantic best | Lexical best |
|---|---:|---:|
| Threshold | 0.575883997681205 | 0.24733698756646583 |
| Precision | 0.648148 | 0.753623 |
| Recall | 0.905172 | 0.896552 |
| F1 | 0.755396 | 0.818898 |
| FP | 57 | 34 |
| FN | 11 | 12 |

Both are **IN-SAMPLE EXPLORATORY**, not production results or held-out calibration.
At those thresholds easy FP is semantic 4/30 versus lexical 0/30.

## 17. Error Overlap

Frozen defaults: BOTH_CORRECT=9, BOTH_WRONG=1, SEMANTIC_ONLY_CORRECT=115,
BASELINE_ONLY_CORRECT=95. These counts mostly reflect one method predicting almost
everything positive and the other everything negative; they are not evidence of a
validated complementary hybrid. Inspected five examples in each one-sided bucket.
Hard head-to-head: both FP=0, semantic-only FP=52, baseline-only FP=0.

## 18. Interpretation

Defaults are not both usable: semantic is highly permissive, lexical default is
completely rejecting. Lexical has stronger pooled ROC-AUC/AP and better exploratory
overall F1/precision with slightly lower recall. The hard-group ranking result is
mixed/opposite: semantic has higher hard-group AUC/AP. Perfect easy-negative lexical
results can boost pooled performance and should not conceal hard-case weaknesses.

## 19. Algorithm Selection Assessment

**Mixed evidence; neither default is ready as a validated deployment classifier.**
The raw lexical method is a transparent reference, not a production skill-baseline
measurement. This 220-pair difficulty-focused sample and transductive IDF do not
support a final algorithm-selection conclusion. Do not force a winner from FP or
accuracy alone. No production algorithm switch was made.

## 20. Recommended Next Step

Create held-out calibration/test sets grouped by shared CV/JD identity, preserve
frozen algorithms, and compare realistic operating points including hard-group ranking.
Expand human labels and representative prevalence. A hybrid may be worth a separate
evaluation, but default error overlap alone does not justify implementing it here.

## 21. Automated Tests

- Evaluation tests: **58 passed, 1 warning in 2.74s**.
- Original structured baseline/canonical input/semantic/BGE-M3 regression:
  **90 passed in 0.94s**, using --noconftest to avoid DB setup.
- Full pytest: **450 passed, 3 warnings in 114.79s (0:01:54)**, exit code 0.
- Earlier runs without a test environment were blocked safely. The audit found the
  existing `gjob_db_test` inside the existing PostgreSQL container; a read-only
  `SELECT current_database()` verified the connection before the suite ran.
- TEST_DATABASE_URL was supplied only to the pytest child process, using the existing
  Docker credentials and the existing template's test database name. No new config
  file, DB, OS-wide environment setting or guard bypass was created.
- No tests called live providers. No fallback to DEV DB was attempted.
- Full-suite warnings: google-genai `_UnionGenericAlias` deprecation (Python 3.17),
  Starlette/httpx TestClient deprecation, and deprecated HTTP_422_UNPROCESSABLE_ENTITY
  in `tests/test_jobs.py::test_list_jobs_salary_min_gt_max_422`. None are test failures.

### Historical test mechanism audit

README's "Running backend tests safely" section documents a dedicated PostgreSQL
target passed through `.env` or process environment. Settings reads `.env`, not
`.env.test.example`. Conftest validates the target before connection, verifies actual
database identity, applies existing Alembic migrations to that test target and
replaces the SQLAlchemy factory/FastAPI dependency with test sessions.

Git commit `9e099b4` (2026-09-14) and current HEAD contain this guard. Earlier snapshot
`a1e7f85` has no conftest and tests import application SessionLocal directly; that
older implicit mechanism is not safe to reuse. Git source alone does not retain the
exact transient environment of every previous successful pytest invocation. Under
the current guard, successful full runs require TEST_DATABASE_URL in their process
environment or loaded `.env`; the current parent process lacked that value.

No pytest.ini, pyproject.toml, setup.cfg, tox.ini, Makefile, pytest wrapper or CI workflow
was found to auto-load the example. Docker compose has one existing PostgreSQL service
on host port 5433, not a separate test service. The test DB already existed in that
server. Reused that standard process-environment mechanism with the existing DB;
no new persistent test configuration was necessary. No URL or password is recorded.

## 22. Privacy / Security

Runner has no app/provider/SQLAlchemy/httpx imports; an isolated interpreter test
blocks sockets and proves those imports do not occur. No raw CV/JD or fitted token
dictionary is persisted. Reports use anonymous source IDs and aggregate metrics;
allowed human reasons remain in existing gitignored CSVs. No secrets or personal
contact details were added to narratives. No new dependencies or endpoints.

## 23. Database / Migration

DEV/production DB write: no. New migration files: no. The offline benchmark created
no account/CV/job/application. Full integration regression used only the validated
existing `gjob_db_test`; its normal conftest applied existing test-schema migrations
and its existing fixtures exercised test records. It never connected to DEV for tests.

## 24. Test Data Cleanup

Real benchmark created only requested offline artifacts. Validation/replay staging
uses disposable temporary directories; no DEV test records/files need deletion.
Original data and all seven semantic artifacts remained byte-identical. Baseline
fixtures/result tests explicitly clean temporary directories; no dataset cache is created
by this baseline. Full-suite fixture setup/teardown ran in the isolated test DB; no
manual DEV cleanup was necessary or performed. No excluded historical pairs or
progress files were touched. No new DB/config file was created for the regression.

## 25. Known Limitations

Only 220 difficulty-focused, single-reviewer pairs; human subjectivity; intentionally
simple English-oriented lexical reference; transductive IDF; incidental raw prose;
no reliable structured skill dictionary; in-sample threshold exploration; no held-out
calibration; extraction quality and production structured baseline not evaluated;
no hybrid; no representative per-job ranking pool. Full integration regression passed;
the measured default baseline weakness and calibration limitations remain unchanged.

## 26. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -m pytest --noconftest tests/test_baseline_matching.py tests/test_semantic_matching.py tests/test_matching_inputs.py tests/embeddings -q
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe -u -m evaluation.run_baseline_benchmark --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir C:/DATN/Datasets --output-dir evaluation/results/baseline-v1
git diff --check -- evaluation
```

Additional read-only Python diagnostics inspected source headers, unique skill_abr
count, SHA-256s, stored-score exploratory groups and sanity examples; an independent
predict replay verified every frozen score/label/reason and semantic artifact hash.
No semantic rerun, Ollama/LLM call or DB cleanup command was used.

For the successful full run, `venv\Scripts\python.exe -m pytest -q` was launched in
a child process after validate_test_database_url passed, with TEST_DATABASE_URL
resolved in memory from the existing Docker service credentials and existing
`.env.test.example` target name. Captured output was redacted before display.
No connection string, credential value or password-bearing command is included here.

## 27. Final Status

**PASS**. Offline benchmark/comparison, reproducibility, focused tests and full
regression are complete. Full result: **450 passed, 3 warnings in 114.79s**, exit 0.
Baseline weakness was reported honestly and no post-hoc tuning was performed.
Ground truth, frozen formula, semantic artifacts and production code were not changed
to make tests pass. No new test config/DB was created; DEV data was not used or changed.
Scientific limitations do not disappear because tests pass: neither default classifier
is a validated production choice; held-out evaluation remains a separate next step.
