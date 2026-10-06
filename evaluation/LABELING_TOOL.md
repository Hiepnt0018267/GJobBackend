# Local AI-assisted human labeling

## Task 14B.5 fresh blind review (Phase A only)

```powershell
venv\Scripts\python.exe -m evaluation.labeling_app --input evaluation/data/derived/fresh_test_pairs_seed.csv --data-dir "C:\DATN\Datasets" --output evaluation/data/derived/fresh_test_pairs_labeled.csv --port 8503
```

Open http://127.0.0.1:8503. Review all fresh pairs from 0/N to N/N, then Validate &
Export. Fresh input automatically selects the existing store's fresh profile:
historical identities/content are forbidden, progress/output namespaces differ,
and a progress fingerprint binds the exact seed hash. No old progress is imported.
Sampling category values are blanked in API payloads; no model matching scores,
predictions, thresholds or sampling score are supplied. Raw CV/JD evidence is read
only from source at review time. Qwen is optional and receives only the rubric and
source evidence; it never confirms human labels or overwrites human decisions.
The human must explicitly choose 0/1 with a non-empty reason for every pair.
Fresh export also verifies no reused old CV/JD/pair, correct source row/ID and no
old/fresh duplicate text. Generic human validator is reused, not weakened.

STOP after labeling/export and tell the agent it is complete. Phase A does not score
fresh pairs or select thresholds. Phase B must first resolve the development-only
lexical IDF state, freeze human output and reuse the existing heldout thresholds.

## Historical benchmark review

Run from the backend root with its existing virtual environment. FastAPI, Uvicorn,
HTTPX and Pydantic are already installed; no extra dependency is needed.

Make sure Ollama is running and `qwen3:8b` is installed:

```powershell
ollama pull qwen3:8b
ollama list
venv\Scripts\python.exe -m evaluation.labeling_app --input evaluation/data/derived/evaluation_pairs_benchmark_seed.csv --data-dir "C:\DATN\Datasets" --output evaluation/data/derived/evaluation_pairs_labeled.csv --model qwen3:8b --base-url http://localhost:11434
```

Open http://127.0.0.1:8501. The app always binds to loopback. The Ollama base URL
must also be loopback. It does not use the production application, APIs or database.

The new benchmark seed has separate progress: `evaluation_labeling_progress_benchmark_seed.csv`.
Selected historical decisions are already reviewed; new pairs are unreviewed. The
old 400-pair draft/progress remain unchanged and archived. All historical reviewed
pairs, including excluded ones, remain in `evaluation_pairs_pilot_reviewed.csv`.
Do not pass the old 400-pair progress file to the new seed. When `--progress` is omitted,
each input filename resolves to its own sibling `evaluation_labeling_progress_<dataset>.csv`.
The app requires `--input` and prints the resolved input/progress paths and counts
at startup. Embedded human decisions are loaded before progress; unreviewed cache
rows cannot erase them. Subsequent explicit human reviews in the same dataset's
progress take precedence so editing/resume continues to work.
To resume the historical 400-pair dataset, explicitly pass both
`--input evaluation/data/derived/evaluation_pairs_draft.csv` and
`--progress evaluation/data/derived/evaluation_labeling_progress.csv`.
Existing `evaluation_labeling_progress_hard.csv` is not automatically imported;
if you have reviewed additional benchmark pairs in that file, explicitly pass it
with `--progress` to resume that work. Unrelated pair IDs are rejected, never imported.
If an old server is still running on 8501, stop that server yourself or launch this
command with `--port 8502`, then open http://127.0.0.1:8502.

Read the full CV and JD side by side. Click **Tạo gợi ý Qwen** if useful. AI receives
the labeling rubric plus full CV text, JD title and description. It receives neither
category nor sampling metadata nor previous human decisions. Its JSON schema is:

```json
{"suggested_label": 0, "reason": "Short evidence-based professional fit explanation."}
```

Requests use `/api/chat`, `stream=false`, `think=false`, `temperature=0`, structured
JSON and a 16384-token context. Large input context saturation is surfaced as an
error, so the reviewer can label manually. AI requests run only on an explicit click;
cached suggestions survive reopening. Regeneration never changes human decisions.

Choose **0 — NOT MATCH** or **1 — MATCH**, write your own non-empty reason, and click
**Save & Next**. Every completed decision is flushed to disk and atomically replaces
the selected progress file (`evaluation_labeling_progress_benchmark_seed.csv` for the new seed).
AI suggestions are saved
separately in the same progress file, with model and timestamps. It contains source
IDs and review metadata, not raw CV/JD text. Reopening resumes at the first unreviewed
pair. Unsaved edits are protected by a navigation warning. Skip leaves the current
unreviewed pair without a final decision.

Use All / Unreviewed / Reviewed / AI-human disagreement / Label 0 / Label 1 filters
and pair-number navigation. Prior reviewed pairs can be edited and saved again.

**Validate & Export Final Dataset** requires every pair to have an explicit human
decision and reason. It invokes the existing validator with the external source
dataset, checks references and non-empty raw text, and only then atomically writes
`evaluation/data/derived/evaluation_pairs_labeled.csv`. The labeled CSV preserves
draft fields for validator compatibility; text-preview columns are blank. Source-aware
validation checks the actual CV/JD text instead. AI fields never enter this output.

Validate again to produce the final benchmark input:

```powershell
venv\Scripts\python.exe -m evaluation.validate_labels --input evaluation/data/derived/evaluation_pairs_labeled.csv --data-dir "C:\DATN\Datasets" --output evaluation/data/derived/evaluation_pairs_final.csv
venv\Scripts\python.exe -m pytest evaluation/tests -q
```

Progress and labeled CSVs are covered by existing gitignore rules. Avoid writing
personal/contact details into human or AI reasons. Follow `LABELING_GUIDE.md`; AI
suggestions, sampling types and sampling scores are never evaluation ground truth.
This tool does not generate benchmark metrics. Run semantic-v1 evaluation only after
the human labels have passed validation.
