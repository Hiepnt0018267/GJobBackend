# Task 14C.1 Ranking Dataset Setup

## 1. Status

**Phase A and Phase B PASS. Human labeling/export complete; final ground truth
validated and frozen. READY FOR TASK14C.2.** Sections2–11 retain Phase A history;
sections12–15 record Phase B validation, quality audit and final frozen SHA.

Generated 10 jobs × 10 candidates = 100 relevance judgments, 95 unique CVs, 9 role
families. Initial review was0/100; it is now100/100 with exported/frozen human labels.
No Semantic scoring/ranking metric was run in either phase.
Visual browser QA is unavailable and is explicitly not claimed as passed.

## 2. Source Review

Confirmed final-matcher-selection.json/report: semantic-v1 is the recruiter ranking
signal, not a probability/binary classifier. Candidate recommendations are out of
scope (Task15). Inspected old220/fresh70 schemas, frozen calibration/test partitions,
stored semantic/fresh/heldout predictions and existing metric/hash utilities.
Existing pair scores are available, but were never generation or review inputs.

Reviewed SemanticMatchingService/cosine, matching_input mapper/readiness and offline
embedding cache behavior: raw-source evaluation differs from canonical production
inputs. These are unchanged. Reviewed common.py, generators, hard_mining professional
cues, validator, labeling_app/store/HTML, source locator and atomic CSV writer.

Raw Resume.csv and job_postings.csv are located uniquely beneath C:/DATN/Datasets by
basename, not assumed nested paths. Source row references and source-file SHA-256
are recorded/validated. No raw source copy was made. The generation manifest contains
their hashes and old-input hashes, without raw CV/JD or contact data.

Plan before coding: audit candidates/job; build dedicated fixed-seed pools with
content-only gates; review all new graded judgments independently; minimally extend
the existing local annotation app; bind progress to seed/source identity; validate
source coverage, grades and pool quality; tests/reproduction; then stop for human
annotation. No new annotation framework, binary-label mapping or model call.

## 3. Existing Pair Dataset Ranking Audit

| Dataset | Pairs | Jobs | CVs | Mean candidates/job | Median | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| evaluation_pairs_labeled.csv | 220 | 180 | 202 | 1.222222 | 1 | 4 |
| fresh_test_pairs_labeled.csv | 70 | 70 | 70 | 1 | 1 | 1 |

| Dataset | 1 candidate | 2 | 3–4 | 5–9 | 10+ | ≥2 | ≥3 | ≥5 | ≥10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Old220 | 155 | 16 | 9 | 0 | 0 | 25 | 9 | 0 | 0 |
| Fresh70 | 70 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Combined290 pairs contain250 jobs and still maximum4 candidates/job. Consequently
none is a useful ≥6-candidate ranking query. No arbitrary regrouping of unrelated
pair rows, fake per-job benchmark or ranking claim was made.

## 4. Ranking Dataset Design

Unit: one fixed JD with ten distinct CVs. Pool query IDs are rank_job_ plus a stable
SHA-derived identifier of job/source identity/seed42; pair IDs reuse make_pair_id.
Within-case positions are deterministic neutral hash order, not professional strength
or algorithm rank. Ten job queries are selected round-robin across professional role
families, with seeded hashing within each family.

Model-independent content strata per pool: 3 role-aligned candidates, 3 related/
transferable candidates, 3 specialization challenges, 1 cross-domain sanity candidate.
Gates use existing professional cue vocabularies/family/specialty and literal shared
professional-term counts (≥5 aligned, ≥3 related/challenge, ≤1 sanity). Known differing
specialties support the challenge stratum. These are NOT relevance labels, guarantees
of suitability or baseline-v1 scores. No embedding, scorer, threshold or AI rating
participates. Quotas are not relaxed silently if no adequate pool exists.

Candidate reuse is bounded at two jobs; actual95 distinct CVs across100 pairs means
five reused CVs. Exact normalized CV duplicates and near-normalized JD duplicates
are excluded within the available pool. Old220/fresh70/historical draft/pilot source
identities are excluded, so all selected rows are source_status=NEW. No old label1
was mapped to grade2. Existing raw archives may still contain incidental equivalent
content under other identities: this is a same-archive foundation, NOT a claim of a
fully fresh external or independently validated ranking test.

No sensitive attribute is extracted as metadata or used as a selection feature.
Role cues and shared professional vocabulary are transparent sampling heuristics,
not a fairness guarantee. Real relevance diversity is unknown until human review.
Pool groups are hidden during annotation. No salary, location, prestige or contact
feature is added. There are no production applications/records behind these pools.

## 5. Relevance Rubric

- **0 — NOT RELEVANT:** substantial role mismatch or no evidence of core capability.
- **1 — PARTIALLY / PLAUSIBLY RELEVANT:** meaningful relevant/transferable capability,
  but important responsibilities or requirements remain unsupported.
- **2 — STRONGLY RELEVANT:** substantial evidence of fit to role, responsibilities,
  skills and core requirements. Not a recommendation to hire.

Human reason is mandatory, based on professional evidence. Ignore salary, company
prestige, protected attributes and personal/contact details. No AI ground truth.
Review each CV/JD independently; avoid inferring grade from pool composition.
Binary relevance ≥1 versus ==2, gains and metric/K policy are deferred to14C.2.

## 6. Blind Labeling Controls

Ranking mode is human-only: no AI suggestion buttons or provider calls. Payload/UI
exclude semantic/baseline/hybrid score, sampling type, prediction and model rank.
Reviewer sees one CV, persistent corresponding JD, rubric and that pair's own saved
judgment; no other candidates' grades or complete ranking is displayed. Plain seeded
position is explicitly labeled neutral order. Raw source text is fetched locally
for reading; incidental personal text is not converted to ranking metadata.

Progress rows contain seed SHA, source identity, pair ID, human grade/reason/status/
timestamp. Seed/source hash mismatch, unrelated/duplicate progress rows or old
labeling filenames are rejected. Startup never rewrites progress. Thread + exclusive
local process file lock guards cooperating writers; stale sessions and new freeze
artifacts block mutations. A leftover lock after process termination blocks safely;
inspect the exact process/lock rather than guess-deleting it.

Validation rejects invalid/blank grades/reasons, pair/CV duplicates, inconsistent
job/case grouping, missing/blank sources, changed refs/title and noncontiguous neutral
positions. Minimum pool6 is enforced. Labeled all-same/no-relevant/no-negative pools
are flagged, never silently removed. Export requires full REVIEWED coverage, retains
human data and writes a hash/quality summary with frozen=true only then. Another
session cannot overwrite the exported CSV after freeze. Corrections require a new
dataset version. Interrupted export is visible and blocks further mutation.

## 7. Generated Seed

- Path: evaluation/data/derived/ranking_pairs_seed.csv.
- Jobs/cases: **10**; judgments: **100**; candidates per job: min/mean/median/max=10.
- Unique CVs: **95**; maximum reuse: **2**; role families: **9**.
- Seed: **42**; relevance_grade/relevance_reason blank on every row.
- SHA-256: `12054002ad8bfd48c834ff9d0fce281d631ecd9032f2d139d158b7c90be2930a`.
- Phase A provenance: evaluation/results/ranking-dataset/seed_manifest.json.
- Schema: ranking_case_id, job_id, cv_id, pair_id, pool_position_seed, source_status,
  candidate_source_ref, job_source_ref, job_title, relevance_grade, relevance_reason.

No raw CV/JD previews are duplicated in the seed; full text is loaded from source refs
for annotation. Seed CSV is private under existing gitignore rules. Manifest includes
source/code/input hashes, sampling audit and rubric, not a final ground-truth summary.
Independent-process replay into a disposable directory reproduced seed bytes exactly;
that replay directory was removed. No outcome-conditioned regeneration occurred.

## 8. Labeling App

Run from C:/DATN/GJobBackend:

```powershell
venv\Scripts\python.exe -X utf8 -u -m evaluation.labeling_app --input evaluation/data/derived/ranking_pairs_seed.csv --data-dir C:/DATN/Datasets --port 8503
```

URL: **http://127.0.0.1:8503/**. A hidden local server is running for handoff (task
process PID11868 at report time). No public exposure or production API is added.
Initial progress verified through read-only HTTP: **0/100 reviewed,100 remaining**.

Select a job; read one CV/JD; select0/1/2; enter reason; Save & Next. Switching jobs
prompts for unsaved work and restores the correct dropdown if fetching fails. Resume
loads the first unreviewed pair. Export is disabled until coverage is complete and
requires explicit confirmation. Result paths, only after user decisions:

- evaluation/data/derived/ranking_labeling_progress.csv.
- evaluation/data/derived/ranking_pairs_labeled.csv.
- evaluation/results/ranking-dataset/dataset_summary.json.

Server logs live in the task-owned local TEMP/gjob-ranking-ui-15257fbd0ff14d7386e683fc107130cd
while the server remains active. They are operational handoff logs, not dataset caches.
No real decision POST was made for smoke tests. Keep the original raw sources unchanged.

## 9. Tests

- All evaluation: **125 passed,1 warning in6.84s**, exit0 (22 new ranking cases plus
  existing103). Existing warning: Starlette/httpx TestClient deprecation.
- Pure semantic/baseline/input/embedding regression: **90 passed in0.89s**, exit0.
- New tests cover deterministic/stable pools, source refs, pool size/duplicates/case
  consistency/position, 0/1/2 and reason validation, resume/hash isolation, concurrent
  freeze/write lock, export coverage/preservation, mixed/uniform grade flags, blind
  payload/UI and old progress filename rejection. No real provider/DB calls.
- Independent-process generation replay: exact seed SHA, temporary replay cleaned.
- Live HTTP GET smoke:100 rows,0 reviewed, complete source content, no score leakage.
- Protected integrity:813 preexisting files unchanged except authorized labeling_app
  mode extension. Task14B evidence, labels, model/scorer/migration files unchanged.
- Full integration pytest not run: production code/DB behavior unchanged; old labeling
  tests and relevant pure engines were exercised. No DEV/test DB was accessed.

An initial new test failed on Windows default text encoding, corrected to explicit
UTF-8; final suite passes. Finish reviewer found freeze cross-session and failed-job-
switch state defects; both fixed, tested and independently confirmed resolved by
code review. Browser inventory was empty, so no screenshot/actual browser layout or
assistive-technology approval is claimed. Detector ran in degraded regex mode
(parser modules unavailable), with an inherited flat-type-hierarchy warning; it is
not a clean visual quality verdict. Incumbent blue/slate document layout preserved
under Impeccable's local-extension/craft guidance, no product frontend redesign.

Commands:

```powershell
venv\Scripts\python.exe -u -m evaluation.ranking_dataset --data-dir C:/DATN/Datasets
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -m pytest --noconftest tests/test_baseline_matching.py tests/test_semantic_matching.py tests/test_matching_inputs.py tests/embeddings -q
```

## 10. Privacy / DB Safety

Offline only: no DEV record creation/deletion, DB connection, migration, production
API/frontend edit, candidate recommendation, new model call, embedding generation,
scoring, threshold, bonus rule, Top-K selection or ranking metrics. Existing labeled
220/70 and all14B artifacts remain byte-identical. Synthetic fixtures/temp exports use
pytest cleanup; no synthetic row was inserted into real progress. Only one Markdown
report for14C.1; no dataset_summary.json before human labels complete.

Human review remains authoritative. Sampling heuristics can introduce selection bias;
role-family diversity does not establish demographic fairness. Same English-oriented
archives, small pools and single reviewer remain limitations. Neither graded diversity
nor ranking quality has been established yet. Full fairness analysis is deferred.

## 11. Next User Action

**Phase A user action completed:100 human judgments and Validate & Export.** Use the rubric and
professional evidence; never copy sampling assumptions into grades. If a pool is
ambiguous/poor, document it rather than manufacture label diversity. Phase B must
inspect coverage, flags and grade distribution, validate/freeze final SHA and update
this same report with sections12–15. It must not run ranking metrics.

Task14C.2 handoff, only after frozen ground truth: load ranking_pairs_labeled.csv,
reuse unchanged semantic-v1 to score each CV/JD, order within each job, define binary
relevance/gains/K explicitly, then Precision@K, Recall@K, MRR, NDCG and per-job errors.
No production integration or candidate-side recommendation in14C.1/14C.2.

## 12. Final Ground Truth

**Phase B completed after the user's explicit confirmation of 100/100 human judgments
and Validate & Export. Existing export/freeze artifacts were verified, not overwritten.**

- Exact input: `C:\DATN\GJobBackend\evaluation\data\derived\ranking_pairs_labeled.csv`.
- Rows: **100/100**, ranking cases: **10**, unique jobs: **10**, unique CVs: **95**.
- Grade distribution: **0=54, 1=32, 2=14**.
- Ground-truth SHA-256:
  `a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d`.
- Seed SHA-256:
  `12054002ad8bfd48c834ff9d0fce281d631ecd9032f2d139d158b7c90be2930a`.
- Existing freeze summary: evaluation/results/ranking-dataset/dataset_summary.json;
  frozen=true, ranking_metrics_computed=false.
- Summary SHA-256:
  `9265d0cf1c108149587e48d399f0a4043712198f2ede10af760e5647c205130d`.
- Human progress SHA-256:
  `a94f7faf32eaf8391f125440dcbe89fcdecaab64c920f36f6455c2e9e96f216d`.

Each exported grade/reason matches its explicitly REVIEWED progress record, with a
valid reviewed_at timestamp. Human judgments remain authoritative. The row ordering,
pair identities, job/CV/case IDs, neutral positions and source references match the
seed exactly; only the two human relevance fields differ from the blank seed.
There was no re-export, translation, normalization, correction or binary-to-grade mapping.

## 13. Pool Quality

All ten original pools remain; min/mean/median/max pool size=10. The flags below use
the rubric's broad relevance (grade>=1), not an implicit final binary metric policy.

| Ranking case | Job ID | Size | Grade0 | Grade1 | Grade2 | Required quality flags |
|---|---|---:|---:|---:|---:|---|
| rank_job_89fd797f815313096a1d | 3701321399 | 10 | 4 | 6 | 0 | None |
| rank_job_c6ab53cbebb914bc5cb7 | 3699421616 | 10 | 5 | 1 | 4 | None |
| rank_job_030b49989e9b03838e88 | 3693065853 | 10 | 9 | 1 | 0 | None |
| rank_job_a860f9c853a4d145a149 | 3697399507 | 10 | 1 | 4 | 5 | None |
| rank_job_ba1101c8423ea2bdc5c7 | 3699411457 | 10 | 8 | 1 | 1 | None |
| rank_job_86256e7f060ccec6b807 | 3693045435 | 10 | 2 | 8 | 0 | None |
| rank_job_d16e63af2f39a31b166d | 3693050905 | 10 | 5 | 5 | 0 | None |
| rank_job_7616538cc926787a2a85 | 3693046701 | 10 | 4 | 2 | 4 | None |
| rank_job_bfeea8a8b8995516cb3e | 3699410505 | 10 | 9 | 1 | 0 | None |
| rank_job_047e1ee49c4462d5f0cf | 3693589224 | 10 | 7 | 3 | 0 | None |

- All-same-grade pools: **0**.
- Pools without any relevant candidate (grade>=1): **0**.
- Pools without any negative candidate (grade0): **0**.
- Undersized pools: **0**.
- Pools with all three grades: **4**; pools with no grade2: **6**.
- Two pools have only one grade1 and nine grade0 candidates.

**Important limitation for14C.2:** if binary relevance is defined as grade==2,
six queries have no binary-positive candidate. Their Recall@K/MRR/ideal-gain handling
must be explicitly specified; do not silently drop these queries, invent positives
or change human labels. Under grade>=1 all queries have at least one relevant candidate.
These observations are dataset sanity checks, not ranking metrics or a K decision.
All pools are retained even where strong relevance is scarce. Single-reviewer,
same-archive, content-mined sampling and reuse limitations from Phase A still apply.

## 14. Validation

Read-only validation PASS, using unchanged ranking_dataset.validate and source loading:

- Exactly100 seed/export/progress rows; all pair IDs unique and deterministic.
- Grades restricted to0/1/2; every human reason non-empty.
- No duplicate CV within a case; each case has one consistent job_id and each job one case.
- Every source CV/JD exists, has non-empty content and correct source row reference/title.
- Neutral pool positions are unique/contiguous; stable case IDs match source hash/seed42.
- Source hashes match generation manifest; seed hash matches progress/freeze identity.
- All100 human grade/reason pairs match progress; no unrelated or missing reviewed rows.
- Per-pool counts, global grade distribution and labeled SHA match the existing summary.
- No extra score/rank columns: export header matches the original ranking FIELDS.

Relevant tests: **125 passed,1 warning in5.89s**, exit0:

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
```

Warning remains the existing Starlette/httpx TestClient deprecation. Tests use
synthetic/temp data with normal cleanup; no real label/progress writes. No runtime
code changed in Phase B, so full DB regression was not required or run.

The audit disabled socket connections. No Semantic scoring/ranking, model/provider
request, embedding generation, Qwen/Gemini call, DEV/test DB access or production
change occurred. No Precision@K, Recall@K, MRR, NDCG or semantic scores/ranks created.
Only this same Markdown report was updated; no new Markdown or freeze JSON was created.

## 15. Frozen Dataset Status

**READY FOR TASK 14C.2**

Final dataset integrity and required pool checks pass; every pool is preserved.
The user's existing export SHA/frozen summary are the final ground-truth reference.
Keep labels, reasons, seed and provenance immutable. Genuine annotation corrections
require a documented new dataset version, not edits to this frozen CSV.

14C.2 must load this frozen100-row input, verify SHA, preregister binary relevance,
graded gains, K and zero-relevant-query policy, and only then score unchanged
Semantic-v1 and evaluate within each job. Report per-job errors and the six
grade2-empty queries transparently. Readiness means dataset/protocol handoff, not
a claim of ranking accuracy, demographic fairness or production deployment.
