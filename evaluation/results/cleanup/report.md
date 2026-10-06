# Evaluation Cleanup Report

## 1. Status

**PASS. Archived21 historical files in6 directories; deleted0 files.**
Reusable tooling, tests, ground truth, final evidence/decisions and reproducibility
caches remain. Only this new Markdown report and two additive .gitignore rules were
created/edited; no production or Python source change.

## 2. Files Reviewed

Inventoried all705 files under evaluation before cleanup:651 non-bytecode KEEP files,
33 regenerable bytecode KEEP files,21 ARCHIVE files,0 DELETE. Reviewed source imports/
references, CLI defaults, tests, documentation, CSV/JSON provenance, frozen manifests,
root .gitignore/.pytest_cache, evaluation README and root README/scripts references.
Classification and SHA-256 checks completed before moves; no filename-only deletion.

| Path/category | Action | Reason |
|---|---|---|
| evaluation/*.py, labeling_ui.html, guides/protocols, tests | KEEP | Reusable annotation, validation, generation, metrics, reproduction |
| derived/evaluation_pairs_labeled.csv, fresh_test_pairs_labeled.csv | KEEP | Final human ground truth |
| derived/calibration_pairs.csv, test_pairs.csv | KEEP | Frozen partition |
| derived/evaluation_pairs_draft.csv, evaluation_pairs_pilot_reviewed.csv | KEEP | Fresh historical exclusion dependencies and frozen hashes |
| derived/current seeds, progress, dataset.json and hard draft | KEEP | Review/reproduction provenance or documented CLI defaults |
| data/archive/existing old400 draft/progress | KEEP | Historical audit originals |
| derived/hard_attempt_81, hard_v2, hard_verified | ARCHIVE | Superseded generation snapshots |
| reports/hard_attempt_81, hard_v2, hard_verified | ARCHIVE | Corresponding historical diagnostics |
| reports/root, results/final evidence, final matcher decision | KEEP | Referenced/frozen thesis and decision evidence |
| cache/semantic-v1, cache/fresh-test | KEEP | Embeddings and frozen development IDF needed for reproducibility |
| Bytecode and root pytest cache | KEEP | Already ignored; removal/regeneration would not improve clarity |

## 3. KEEP

All22 top-level evaluation Python modules, labeling HTML, validators, three pair
generators, metrics/runners, heldout/fresh helpers and evaluation tests remain in their
original locations for Task14C/reproduction. No generator was removed or moved.
All semantic/baseline/heldout/fresh/hybrid/comparison/final-matcher results remain.

Historical multiple Markdown reports were not aggressively deleted. Some are
referenced/frozen; the new one-report rule is not applied retroactively to erase them.
Progress files were not presumed redundant just because an export exists.

All651 retained non-bytecode files are byte-identical. Sorted path/hash aggregate:
`407d15d54bc37bc117ecddb1c2d399d54382de9283bcb24943ce3cff0823c2b2`.
Bytecode is excluded because tests/imports can regenerate it.

## 4. ARCHIVED

Exactly21 files moved; each individual SHA-256 verified before and after. Absolute
source/destination paths were validated inside the backend evaluation root, destinations
had to be absent, source directories could not be reparse points. No overwrite.

| Original path | Destination |
|---|---|
| `evaluation/data/derived/hard_attempt_81/evaluation_labeling_progress_hard.csv` | `evaluation/data/archive/generation/hard_attempt_81/evaluation_labeling_progress_hard.csv` |
| `evaluation/data/derived/hard_attempt_81/evaluation_pairs_benchmark_seed.csv` | `evaluation/data/archive/generation/hard_attempt_81/evaluation_pairs_benchmark_seed.csv` |
| `evaluation/data/derived/hard_attempt_81/evaluation_pairs_hard_draft.csv` | `evaluation/data/archive/generation/hard_attempt_81/evaluation_pairs_hard_draft.csv` |
| `evaluation/data/derived/hard_attempt_81/evaluation_pairs_pilot_reviewed.csv` | `evaluation/data/archive/generation/hard_attempt_81/evaluation_pairs_pilot_reviewed.csv` |
| `evaluation/data/derived/hard_v2/evaluation_labeling_progress_hard.csv` | `evaluation/data/archive/generation/hard_v2/evaluation_labeling_progress_hard.csv` |
| `evaluation/data/derived/hard_v2/evaluation_pairs_benchmark_seed.csv` | `evaluation/data/archive/generation/hard_v2/evaluation_pairs_benchmark_seed.csv` |
| `evaluation/data/derived/hard_v2/evaluation_pairs_hard_draft.csv` | `evaluation/data/archive/generation/hard_v2/evaluation_pairs_hard_draft.csv` |
| `evaluation/data/derived/hard_v2/evaluation_pairs_pilot_reviewed.csv` | `evaluation/data/archive/generation/hard_v2/evaluation_pairs_pilot_reviewed.csv` |
| `evaluation/data/derived/hard_verified/evaluation_labeling_progress_hard.csv` | `evaluation/data/archive/generation/hard_verified/evaluation_labeling_progress_hard.csv` |
| `evaluation/data/derived/hard_verified/evaluation_pairs_benchmark_seed.csv` | `evaluation/data/archive/generation/hard_verified/evaluation_pairs_benchmark_seed.csv` |
| `evaluation/data/derived/hard_verified/evaluation_pairs_hard_draft.csv` | `evaluation/data/archive/generation/hard_verified/evaluation_pairs_hard_draft.csv` |
| `evaluation/data/derived/hard_verified/evaluation_pairs_pilot_reviewed.csv` | `evaluation/data/archive/generation/hard_verified/evaluation_pairs_pilot_reviewed.csv` |
| `evaluation/reports/hard_attempt_81/hard_pair_distribution.json` | `evaluation/results/archive/generation/hard_attempt_81/hard_pair_distribution.json` |
| `evaluation/reports/hard_attempt_81/hard_pair_generation_report.md` | `evaluation/results/archive/generation/hard_attempt_81/hard_pair_generation_report.md` |
| `evaluation/reports/hard_attempt_81/old_pair_selection_report.csv` | `evaluation/results/archive/generation/hard_attempt_81/old_pair_selection_report.csv` |
| `evaluation/reports/hard_v2/hard_pair_distribution.json` | `evaluation/results/archive/generation/hard_v2/hard_pair_distribution.json` |
| `evaluation/reports/hard_v2/hard_pair_generation_report.md` | `evaluation/results/archive/generation/hard_v2/hard_pair_generation_report.md` |
| `evaluation/reports/hard_v2/old_pair_selection_report.csv` | `evaluation/results/archive/generation/hard_v2/old_pair_selection_report.csv` |
| `evaluation/reports/hard_verified/hard_pair_distribution.json` | `evaluation/results/archive/generation/hard_verified/hard_pair_distribution.json` |
| `evaluation/reports/hard_verified/hard_pair_generation_report.md` | `evaluation/results/archive/generation/hard_verified/hard_pair_generation_report.md` |
| `evaluation/reports/hard_verified/old_pair_selection_report.csv` | `evaluation/results/archive/generation/hard_verified/old_pair_selection_report.csv` |

All files remain recoverable by moving back to the listed original paths after
confirming those locations are free. Data snapshots are under data/archive/generation;
historical diagnostics are under results/archive/generation.

Hash checks confirmed identical root/hard_v2/hard_verified seed/draft/progress copies
and repeated pilot/selection files. These were archived, not deleted, to preserve
provenance. The81 trial also contains distinct history. No runtime Python/test
dependency on these six historical directories was found. One retained historical
report mentions the original81 locations; this table supplies the relocation map
without rewriting immutable history. Frozen manifest entries were not changed.

## 5. DELETED

**None. DELETE=0.** No scratch artifact was proved disposable enough to remove.
No human label, progress, cache, benchmark, report or external raw dataset was deleted.
No deletion recovery is needed; all archived content remains on disk.

## 6. Labeling Tool Status

KEPT labeling_app, labeling_ui.html, labeling_ai/store and fresh labeling helpers.
Current220/70 seeds/progress/exports remain together at original paths.
Input-authoritative progress scoping and human decisions are unchanged.
Fresh progress/dataset identity JSON participate in freeze provenance. Legacy
draft/progress copies remain because older documented CLI defaults reference them.
No labeling server or live AI suggestion was invoked.

## 7. Validator Status

KEPT validate_labels and fresh overlap/source/export utilities. In particular,
fresh_test_protocol.exclusion_files reads sibling historical draft/pilot files.
Moving root copies would reduce exclusions or break frozen hashes, so they stay.
Tests enforcing label0/1, reasons, duplicates, references and exports remain.

## 8. Benchmark Artifact Status

All final result folders and final-matcher-selection.json/report are byte-identical.
No runner, threshold search, scoring, IDF fit, phase marker reset or provider rerun.
Import smoke passed for22 modules; hybrid config and fresh protected-hash manifests
still verify. These are dependency checks, not a new benchmark execution.

## 9. Ground Truth Integrity

Paths below remain unchanged under evaluation/data/derived:

| File | SHA-256 |
|---|---|
| evaluation_pairs_labeled.csv | 28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8 |
| fresh_test_pairs_labeled.csv | 1d9820ef3439aca231ed79233b59370b2b849306d55af154db6ca81a018805e9 |
| calibration_pairs.csv | 8f1957b958a8b7fc686053b8fd4dbc4fa330a47ce1cbfc3afb872cb7ef05776d |
| test_pairs.csv | e26b5715d0a1a4589616cc23d930ceef89d91e3af79beaf346c7ceaf02743e11 |

Original220/70 labels,132/88 split, progress and final decisions were neither normalized,
exported, moved nor edited.

## 10. Gitignore Changes

Added only `.env.test` and `evaluation/data/archive/**/*.csv`.
Existing derived/labels/archive CSV, recursive result CSV, embedding/pytest cache and
bytecode exclusions preserved, including unrelated preexisting worktree edits.
Nested archives contain private data; git check-ignore confirmed data archive CSV,
result archive CSV and .env.test protection. Final JSON/Markdown not blanket-ignored.
No secret values/passwords read or printed.

## 11. Tests

- Evaluation tests: **103 passed,1 warning in5.46s**, exit0.
- Import smoke: **22 modules**, connections forbidden; fresh/hybrid freeze verification PASS.
- Integrity audit: **651 KEEP files unchanged,21 ARCHIVE files hash-identical,DELETE=0**.
- git diff --check: exit0; only existing LF/CRLF conversion warnings.
- One cleanup Markdown report; no new source/test module.
- Full pytest not required/rerun: no Python code paths/imports changed, per task scope.

Existing test warning: Starlette/httpx TestClient deprecation. Tests use synthetic/temp
fixtures with normal teardown. Commands: `venv\Scripts\python.exe -m pytest evaluation/tests -q`,
read-only Python import/hash audits, `git check-ignore`, `git diff --check`.
Archive used native PowerShell Move-Item with validated literal paths and hash preflight.

## 12. DB / Provider Safety

No DEV/test DB access, API call, migration, production/frontend edit or live provider
call. Import smoke blocked network connections. No Qwen/Gemini/Ollama/new embeddings.
No raw external datasets moved/copied/deleted. Only paths/hashes and aggregate metadata
appear in this report, no raw CV/JD/contact text. Unrelated worktree changes preserved.

## 13. Remaining Technical Debt

Root historical draft/pilot/progress files remain necessary for CLI/frozen audit
compatibility; further consolidation needs an explicit provenance migration, not
silent cleanup. Historical reports may mention former paths; use section4's map.
Multiple older reports remain where valuable/referenced/frozen.

Caches consume space but are reproducibility state. Existing bytecode/pytest caches
are harmless ignored local files. Current generators should use new output directories,
not overwrite labeled/frozen inputs. Private archived CSVs must not be published.

Folder guide: derived=canonical/freeze-dependent inputs; data/archive=historical inputs/
trials; reports=root audit/generation/split evidence; results=final experiments/decisions;
results/archive=historical diagnostics; cache=private reproduction state.

## 14. Final Status

**PASS.** Six historical directories archived,21 files preserved,zero deletion.
Ground truth/final evidence/tooling intact; tests/import/freeze/hash checks pass.
No production/DB/provider behavior changed. Only one new cleanup report created.

