# GJob matching evaluation foundation

Offline tooling for auditing external CV/JD corpora and preparing a human-labeled
evaluation set. It does not call an LLM, run a benchmark, change matching engines,
use the application database, or expose data through an API.

## Requirements and inputs

Python's standard library is sufficient. The `--data-dir` may contain nested folders;
the tools locate the nine expected CSV filenames by basename. Paths are never
hardcoded. See `PROVENANCE.md` before sharing any artifact.

Eligibility defaults are centralized in `EvaluationConfig`: CV text ≥ 200 characters,
JD description ≥ 100 characters, 120 sampled CVs, 140 sampled JDs, 400 pairs, seed
42, and at most four pairs per CV or JD. Missing salary/location never excludes a JD.

## Commands

Run from the backend repository root:

```powershell
python -m evaluation.audit --data-dir "C:\path\to\Datasets"
python -m evaluation.generate_pairs --data-dir "C:\path\to\Datasets" --seed 42
python -m evaluation.validate_labels --input "evaluation/data/labels/evaluation_pairs_labeled.csv" --data-dir "C:\path\to\Datasets"
python -m pytest evaluation/tests -q
```

Audit writes JSON and Markdown statistics to `evaluation/reports/`. Generation writes
an unlabeled local draft and a distribution report. Copy the draft into
`evaluation/data/labels/`, review it using `LABELING_GUIDE.md`, then validate it.

## Pairing design

The generator first performs deterministic, diversity-aware sampling by CV category
and title token. It indexes only the small JD sample, retrieves bounded token-overlap
pools, and emits positive, hard-negative and easy-negative *candidates*. There is no
full raw CV×JD cross join. Job semantic review text follows current canonical signals:
title, description, skill description and experience level. It excludes salary,
location, company prestige, benefits and contacts.

`skill_abr` has no supplied dictionary. Codes are retained as opaque metadata and no
meaning is invented. `cv_skills_hint` contains lexical intersections for reviewer
navigation, not structured skill extraction. Pair type and score must never be used
as final labels.

## Reproducibility and leakage

Stable SHA-256 ordering plus the CLI seed makes output deterministic for identical
inputs and configuration. The loader removes repeated IDs and exact duplicate texts,
the generator forbids duplicate pairs and caps reuse, and the audit reports exact and
normalized JD duplicate candidates. Future train/dev/test splits must group by CV or
JD identity; never randomly split pairs that share the same source entity.

## Local human labeling assistant

Task 14B.1.1 adds a separate localhost review app with optional Ollama Qwen suggestions.
See [LABELING_TOOL.md](LABELING_TOOL.md) for launch, autosave, resume and export commands.
Human decisions are required for every final label; the dataset-generation commands
above remain independent of this assistant.

## Harder benchmark seed and historical pilot

The legacy `generate_pairs` command remains available for provenance. For the new
benchmark, use the separate offline generator:

```powershell
venv\Scripts\python.exe -m evaluation.generate_hard_pairs --data-dir "C:\DATN\Datasets" --seed 42
```

It archives the old draft and progress byte-for-byte **before** generating artifacts.
Existing archives are reused only when identical; changed sources get a hash-suffixed
archive. All reviewed pairs are preserved in `evaluation_pairs_pilot_reviewed.csv`.
Only content-qualified old pairs enter `evaluation_pairs_benchmark_seed.csv`, with
their original human labels, reasons, status and timestamps. Exclusions are documented
for every old pair in `evaluation/reports/old_pair_selection_report.csv`.

Targets are 90 positive, 100 hard-negative and 30 easy-negative **candidates**, including
the selected old pairs. No candidate type is a ground-truth label. New pairs remain
unreviewed. At most four pairs share a CV or JD; normalized duplicate descriptions are
excluded. The miner indexes the full eligible JD corpus, extends legacy CV coverage
with a deterministic 300-CV category sample, and retrieves bounded candidate pools.
It does not score a full CV-by-JD Cartesian product.

Transparent IDF-weighted lexical/title overlap, professional-family cues and explicit
specialization/seniority/technology mismatch cues drive mining. Generic boilerplate
does not drive the professional cue gate. Hard candidates require same-family evidence,
lexical overlap >= 0.07 and a mismatch cue, plus title overlap >= 0.25 or four shared
professional cues. Positive candidates require same-family evidence, lexical overlap
>= 0.10, title overlap >= 0.40 and no detected mismatch. Easy candidates require no
same-family evidence, lexical overlap <= 0.04 and title overlap <= 0.15.
These imperfect lexical rules are sampling diagnostics only. `TOO_TRIVIAL` means a
pair failed the evidence gates; it does not establish that the pair is irrelevant.

Human labels/reasons never affect selection. Reviewed status only prioritizes reuse
of existing work. No matching engine, embedding score, LLM, production code or database
is used. Reports include before/after diagnostics, diversity, reuse limits and 5/10/5
candidate examples. Higher lexical overlap does not itself prove benchmark quality.

The generator refuses to overwrite existing new outputs. For another run, supply fresh
`--output-dir` and `--reports-dir` paths. Do not regenerate over human progress.
See [LABELING_TOOL.md](LABELING_TOOL.md) to review the new seed using separate progress.

## 14B.2 preparation

### Task 14B.6: frozen offline Hybrid-v1 experiment

Read [HYBRID_V1_PROTOCOL.md](HYBRID_V1_PROTOCOL.md) before running. Fit ECDF/reference
scores and select only alpha0.25/0.50/0.75 and a Recall>=0.80 operating point on132
calibration pairs. Freeze before88 development holdout, then70 consumed diagnostic.

```powershell
venv\Scripts\python.exe -m evaluation.run_hybrid_experiment --phase calibrate --data-dir "C:\DATN\Datasets"
venv\Scripts\python.exe -m evaluation.run_hybrid_experiment --phase heldout --data-dir "C:\DATN\Datasets"
venv\Scripts\python.exe -m evaluation.run_hybrid_experiment --phase fresh --data-dir "C:\DATN\Datasets"
```

Outputs default to evaluation/results/hybrid-v1. No provider/scorer/IDF refit, extra
weights or production integration. Exclusive config/phase markers prevent rerun tuning.
Components retain existing max-F1 thresholds; comparisons are operating-point tradeoffs,
not matched-objective fusion-isolation controls. Neither88 nor70 is a new independent
Hybrid test. All calibration sweeps, rejected configurations, recall costs, hard errors,
ranking, recovery and uncertainty are reported. Do not edit the frozen config.

### Task 14B.4: retrospective grouped calibration/test protocol

Read [HELDOUT_PROTOCOL.md](HELDOUT_PROTOCOL.md). No algorithm/provider rerun is needed.

```powershell
venv\Scripts\python.exe -m evaluation.run_heldout_evaluation --phase split --data-dir "C:\DATN\Datasets"
venv\Scripts\python.exe -m evaluation.run_heldout_evaluation --phase calibrate --data-dir "C:\DATN\Datasets"
venv\Scripts\python.exe -m evaluation.run_heldout_evaluation --phase test --data-dir "C:\DATN\Datasets"
```

Default `--phase all` runs those boundaries in order. Whole bipartite graph components
are assigned once with seed42, target60/40; identities/labels/artifact hashes are checked.
Threshold selection sees calibration rows only and uses max F1, precision, lower FP,
higher threshold. Observed boundaries/midpoints/endpoints come from calibration only.
Exclusive-write artifacts protect split, thresholds and a one-time final-test marker.
Never rerun split/calibration/test to seek better outcomes. An interrupted test phase
stops rather than silently overwriting its artifacts; review the interruption first.

Important: earlier full-corpus label analyses and transductive baseline IDF prevent
claiming a brand-new blind/inductive test. This is retrospective grouped threshold
validation on frozen scores; genuinely unseen external labels remain necessary.
Pair bootstrap uses fixed thresholds and may understate shared-entity uncertainty.
New split/result CSVs follow existing private-data gitignore rules; reports use IDs
and aggregates, never raw CV/JD text. Full tests reuse the existing guarded test DB.

### Task 14B.3: frozen offline lexical reference

```powershell
venv\Scripts\python.exe -m evaluation.run_baseline_benchmark --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir "C:\DATN\Datasets" --output-dir evaluation/results/baseline-v1
```

Read [BASELINE_V1_FROZEN.md](BASELINE_V1_FROZEN.md) before running. The existing
production baseline measures structured skill coverage; raw sources cannot support
that engine without fabricating skills. This task's distinct identifier is
`baseline-v1-offline-lexical`: frozen 0.7 TF-IDF lexical cosine + 0.3 title-token
coverage, default evaluation threshold 0.5. No LLM, embeddings, DB or provider imports.
The baseline folder name is a task convention, not a claim that the production skill
engine was measured. No skill_abr mappings or skill/seniority guesses are introduced.

The runner requires the exact frozen 220-pair hash, matching semantic source hashes
and pair/label references. It reads, hashes and preserves all semantic artifacts;
never reruns semantic. Metrics, FP/FN/groups and exploratory thresholds reuse the
shared metric implementation. Comparison outputs default to `evaluation/results/comparison`.
Existing outputs are refused. `--limit` marks a diagnostic run partial and produces
no full head-to-head comparison. Reports contain IDs/metrics; allowed human reasons
stay in gitignored CSVs. No post-run tuning or automatic production algorithm switch.

### Semantic-v1 offline benchmark

```powershell
venv\Scripts\python.exe -m evaluation.run_semantic_benchmark --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir "C:\DATN\Datasets" --output-dir evaluation/results/semantic-v1
```

Validation requires exactly 220 complete human-labeled pairs before any embedding.
The runner reuses `SemanticMatchingService.match` and `cosine_similarity` unchanged,
with the existing Ollama embedding provider (BGE-M3, `/api/embed`, `truncate=false`).
It does not use DB, application APIs, baseline scoring, or LLM extraction.

External raw CVs lack structured production fields: the documented offline adapter
uses original Resume_str normalized by existing whitespace helpers; JD uses title,
description and free-text skills_desc in existing semantic section formatting.
Opaque skill codes and analysis/label fields are excluded. This is a matching-only
raw-source benchmark, not production extraction/preprocessing evaluation.

No production classification threshold exists. Default 0.5 is an explicitly stated
evaluation assumption. A grid over [-1, 1] plus observed score boundaries supports
exploratory threshold analysis; the in-sample optimum is not held-out calibration.
Undefined metrics are null. PR-AUC is non-interpolated Average Precision with ties
grouped, not trapezoidal interpolation. Sampling groups are never ground truth.

Caches are local, keyed by entity ID/content hash, model digest and adapter/core
identity. They contain embeddings, never raw CV/JD text, and are gitignored. Error
CSVs contain human reasons and are also gitignored. Aggregate metrics/report are
shareable subject to provenance policy. Existing result files are never overwritten;
use a fresh output directory for another run. `--limit` is diagnostic only and marks
results partial. Embedding context overflow fails without silently truncating text.

The existing provider request failed on the real corpus with an input-too-long error.
The offline-only request adapter sets `options.num_ctx=8192` (or `--num-ctx`) and
preserves `truncate=false`, reusing production provider response/error validation.
On local Ollama 0.34.2, num_ctx alone still rejected a 2356-token CV. The same text
passed unchanged with encoder `num_batch=8192`; the offline adapter therefore sets
this explicitly too (`--num-batch`). This is encoder capacity, not `--batch-size`,
which controls the number of texts per request.
Ollama `/api/show` confirms BGE-M3 capacity 8192; larger values are rejected. This
does not change production provider code/configuration or the cosine algorithm.
Context configuration is recorded in reports and cache identity. This is a full-text
evaluation configuration, not a claim that current production context is equivalent.

Raw resumes do not provide GJob's structured `CVSkillItem` list. `baseline-v1` uses
normalized structured CV skills/project technologies and structured job skills, so a
curated deterministic adapter or a clearly documented baseline subset will be needed.
`semantic-v1` can consume canonical semantic text more directly. This task does not
choose thresholds or benchmark either engine.
