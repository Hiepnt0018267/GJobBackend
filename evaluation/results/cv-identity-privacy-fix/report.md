# Task 14C.1.7 Shared CV Identity Extraction / Matching Privacy Fix

## 1. Status

**PASS for this narrowly scoped identity-contract fix and regression.** Two affected
CVs pass the new production extraction/canonical audit. Full pytest599 passed.
No 95-CV batch, scoring or canonical-dataset freeze was performed.

## 2. Objective

Separate identity extraction from professional matching content. Do not infer a
person's name from a role/heading and do not delete useful prose merely because
an LLM placed the same string in full_name. Shared production/evaluation behavior,
no raw-data mutation, name recovery hack or aggressive free-text NER.

## 3. Original Blocker

Task14C.1.5 had3 successful CVs,5 failed,87 pending;10 JDs and3/100 pairs ready.
The wrapper's known-value equality check rejected full_name/professional-text
collisions as SENSITIVE_VALUE_IN_SEMANTIC_TEXT. That code did not establish whether
the string was a real identity. Production mapper already excluded personal_info
from semantic sections; the name could be duplicated in proper professional fields.

## 4. Diagnostic Method

Source-read-first: CV/extraction schemas, shared prompt, structured extraction
service, Ollama parsing/schema validation, Gemini schema/prompt wiring, mapper,
sanitizer, fingerprints, checkpoint wrapper and tests. No JD/relevance/rank/score
entered diagnostics. Two selected failing IDs10704573/10969918; source text stayed
in memory. Four pre-fix CV-only workflows across those same two samples checked
overlap, safe token shapes, source/professional section evidence; no real names,
raw prompts/output or CV excerpts were printed/persisted.

Plan before implementation: clarify explicit-name contract at shared prompt/schema;
preserve mapper's structural professional allowlist; share overlap auditor with
non-PII semantics; version extraction/canonical profile; safely invalidate incompatible
checkpoints on explicit upgrade; synthetic regression/full test DB suite; two-item
live recheck only. No changes selected from ranking results.

## 5. Root Cause Findings

Unique diagnosed CV classifications: TYPE A confirmed0; TYPE B1; TYPE C1; TYPE D0
in this identity diagnostic sample. Other schema/provider failures were not diagnosed
or repaired by this task.

-10704573: TYPE B, professional business-director heading misclassified as full_name.
  Source starts with a business-director role heading; output safe lexical structure
  is director/business role prose, and overlap occurs in experiences. No explicit
  source name label. This is not evidence the mapper concatenated a name field.
-10969918: TYPE C before fix. A single-word value overlaps experience content; no
  explicit name label. It was not confidently classified as a real name or profession.
  No uncertain string was deleted. New-contract recheck sets name null and retains
  professional sections; that is a post-fix observation, not retroactive proof of B.

Diagnostic classifiers/token masks were inspection-only, not production heuristics.
No ID/category-specific extraction or privacy rule was implemented.

## 6. Extraction Contract Findings

CVPersonalInfo.full_name was nullable/255-character text with trim validation, but
no semantic field description. Prompt had general no-inference/null instructions,
not explicit personal-name-versus-role/heading/company guidance. Pydantic validates
structure, not whether a string genuinely names a person. Both providers consume
the shared prompt and schema. No JSON shape/JSONB or unrelated section changed.

## 7. Canonical Mapper Findings

build_cv_matching_input builds semantic_text from an explicit professional allowlist:
objective, skills, experience position/description, education degree/field/description,
project name/role/description, certificates and languages. It does not serialize
personal_info wholesale, include full_name, or fall back to full_name as objective.
The fix does not remove capitalized company/university/project/technology names.

## 8. Final Identity Matching Policy

full_name NEVER participates as a semantic feature. Email,phone,address,DOB,avatar,
LinkedIn/GitHub/portfolio URLs in personal_info are display/profile-only at this
semantic boundary. Address still supplies canonical location metadata in production,
not embedding text; evaluation minimizes persisted metadata separately with exact
semantic-equivalence assertions. No address/geography matching feature added.

Values duplicated in professional prose are not automatically classified as PII.
The shared overlap auditor reports field names only; uncertain collisions fail closed
for preparation/adjudication without text deletion. This is not universal free-prose
name detection. Structural exclusion is tested through identity-perturbation invariance.

## 9. Extraction Fix

app/schemas/cv.py: add full_name description requiring only explicitly supplied
candidate personal name; prohibit inference from role/heading/company/summary and
anonymized placeholders; absent/unclear name=null. Same nullable field/validation.
app/ai/cv_extraction_prompt.py: equivalent shared instructions, including PROFILE,
RESUME,CURRICULUM VITAE/company/name/location placeholder examples. Keep factual
professional data in proper existing sections; never copy full_name into matching
fields. Applies equally to Gemini and Ollama. No model-specific prompt/fallback.
No deterministic name detector or broad new post-processing was introduced.

## 10. Canonical Mapping Fix

No behavioral role/identity deletion needed: existing structural allowlist was correct.
Added explicit mapper comment documenting no personal_info serialization/recovery.
Tests show genuine name exclusion, misclassified role preservation through existing
professional fields, identity-only empty semantic text and unchanged input objects.
No full_name-to-objective/experience recovery logic exists.

## 11. Shared Sanitizer Relationship

Existing contact sanitizer stays defense-in-depth, with unchanged contact rules.
Added app.services.matching_text_privacy.find_cv_identity_overlaps(text,personal_info):
pure, safe field-name-only diagnostics, no redaction/NER/name-validity inference.
Evaluation uses this shared auditor instead of its own equality-loop implementation.
Ambiguous collision now yields AMBIGUOUS_IDENTITY_OVERLAP, not a claim of proven PII.
Preparation still refuses such unresolved results; privacy was not waived to pass.

## 12. Canonical Version / Fingerprint

Previous: matching-canonical-v2-contact-sanitized.
New: **matching-canonical-v3-explicit-identity-contract**.
Version conservatively reflects future extraction contract/schema-description changes,
even though the professional-field mapper allowlist itself remains unchanged.
CV/job fingerprints already include this shared constant. Wrapper profile records
version and source hashes, including prompt/schema/sanitizer. Semantic engine remains
semantic-v1, BGE-M3/cosine/ranking/threshold/result-count policy unchanged.

## 13. Cache Safety

Versioned production fingerprints cannot reuse v2 cached match results for v3.
Old rows/embeddings/results are not edited/deleted. No live match request in this task.
Wrapper rejects mismatched profile by default, including old extracted results that
were structurally valid but used the old name contract. No historical14B artifacts
rerun/rewritten; they are not v3 evidence.

## 14. Task14C.1.5 Checkpoint Impact

All3 old successful CVs have incompatible profile fingerprints: **3/3 require fresh
extraction** under v3. They remain byte-identical on disk as historical checkpoint
evidence, not accepted v3 successes. The10 old JD records also require deterministic
profile regeneration, not Qwen. No old artifact was casually erased to save work.

Added --invalidate-incompatible-checkpoints to the existing preparation CLI. It
verifies same source/ref/hash, rejects duplicate/unrelated rows, skips incompatible
items rather than accepting them, preserves byte-identical private backups under
evaluation/cache/ranking-canonical-history before output replacement. Compatible
current-profile items continue to be schema/hash/mapper-validated and reused.
Frozen inputs refuse invalidation. This upgrade flag was NOT executed in this task;
the next resume invokes it explicitly, without manual record editing.

## 15. Synthetic Tests

New tests cover explicit-name/no-name/heading shared schema/prompt wiring; six major
structured section preservation; real-name exclusion and identity perturbation;
misclassified role retained only via professional fields; no identity-only fallback;
artificial identity injection audit; malformed-output validation; source-scoped
checkpoint invalidation/current-profile reuse/duplicate detection.
Mock tests prove contract wiring, NOT that an LLM can never hallucinate.

- Focused extraction/shared Gemini-Ollama/privacy/mapper/semantic/embedding:
  **208 passed,1 warning in1.75s**, exit0.
- Evaluation: **138 passed,2 warnings in6.50s**, exit0.
- Existing contact sanitizer/numeric preservation/version regression still passes.

## 16. Real Diagnostic Recheck

Two further production Qwen workflows after tests, CV-only/no labels:

| CV ID | Name | Canonical/privacy | Skills/experience/education | Latency | Prompt/output tokens |
|---|---|---|---|---|---|
|10704573|null|PASS|14/14/1|60.941s|3890/2289|
|10969918|null|PASS|5/4/1|30.565s|3142/1144|

Both semantic texts nonempty, preserve professional positions from experiences,
have no known identity overlap or supported contact issues. Professional section
counts match corresponding pre-fix observations. No manual output correction or
name recovery. Context8192; ratios0.474854/0.383545; think=false,temp0; no truncation.
Source-only JD contact regression remains10/10 PASS under v3. Samples were not
inserted into old checkpoint/DEV DB; full dataset preparation remains separate.

## 17. Full Pytest

**599 passed,3 warnings in103.22s (0:01:43)**, exit0.
Existing isolated gjob_db_test only, through TEST_DATABASE_URL guard/current DB
identity verification and normal fixtures/migrations. No new DB/config/OS-wide
setting or DEV fallback. URL/password only memory child process, output redacted.
Warnings are existing google-genai UnionGenericAlias, Starlette/httpx TestClient,
and deprecated HTTP_422_UNPROCESSABLE_ENTITY. No failed tests or live pytest models.

## 18. Ground Truth / Raw Data Integrity

Ranking ground truth remains byte-identical:
a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d.
Old CV checkpoint remains54c153dc676ed8ba28911019547a3203ee0e6733026c32f8dfaf0996872d4eb0;
JD checkpoint51cecd039d9a5fbebd8946c71105a76d8c8c61cc2e0565cda2875ef1dc561d94.
Resume.csv remains816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d;
job_postings.csv d782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f.
Semantic service unchanged0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.
No human labels, raw sources, uploads, existing extraction DB results or benchmark
artifacts edited. Unrelated existing dirty worktree changes preserved.

## 19. DB / Provider Safety

Migration none; DEV session/connection/write none. Six live local Qwen workflows
total:4 diagnostic +2recheck on two unique CVs. No Gemini/BGE scoring/network cloud,
JD extraction, embeddings, cosine, ranking or metrics. Automated tests fully mocked.
Live sample data only in process memory; reports contain IDs/hashes/counts/safe facts,
not real names/raw CV/prompt/provider payload. No cleanup of DEV data needed.
Synthetic fixtures clean up normally; no full batch/lingering task process started.

## 20. Known Limitations

One pre-fix sample remains Type C, not retrospectively relabeled as proven misclassification.
Prompt/schema descriptions guide the model, not a guarantee of correct identity/section
extraction. No broad free-text NER or universal fairness claim; names copied into
arbitrary professional prose may require source-only adjudication. Overlap audit is
conservative and can flag useful role text when metadata is misclassified. Do not
silently waive it. Other schema/provider failures and finite context/latency remain.
Full95CV quality/privacy validation and100pair freeze are not completed here.

## 21. Task14C.1.5 Resume Handoff

Shared name contract: CVPersonalInfo.full_name description and
CV_EXTRACTION_SYSTEM_INSTRUCTION. Structural mapper:
app.services.matching_input_mapper.build_cv_matching_input (identity excluded).
Shared audit:find_cv_identity_overlaps; contact sanitizer retained.
Version:v3-explicit-identity-contract; version/profile prevents stale cache reuse.
Three old successful CVs must be recomputed, not reused under changed prompt/profile.

Next-task command, NOT executed here:

```powershell
venv\Scripts\python.exe -X utf8 -u -m evaluation.prepare_ranking_canonical --data-dir C:/DATN/Datasets --invalidate-incompatible-checkpoints --retry-failed
```

Back up/invalidate old source-verified v2 checkpoints, process unique95CV/10JD,
preserve future compatible v3 items, confirm privacy and100/100ready, then freeze
new hashes. Do not use --refresh-jd-drafts with an existing CV checkpoint. No scoring
until the complete new canonical artifact freeze is verified.

## 22. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_cv_identity_contract.py tests/test_cv_structured_extraction.py tests/ai tests/test_matching_inputs.py tests/test_matching_text_privacy.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Full suite launched in a guarded secret-redacted child environment using existing
test DB/template/Docker credentials, no secrets reproduced. Inline diagnostic/recheck
programs used production service/factory and CV-only sources for the two IDs;
source-only header/category/count/hash and checkpoint-version audits. Source category
used only for diagnosis, never supplied to provider or production rules. One Markdown
report and optional summary.json; no new diagnostic raw-data copy/cache or deletion.

## 23. Final Status

**PASS — READY TO RESUME TASK14C.1.5 CANONICAL RANKING INPUT PREPARATION.**
Shared explicit-name contract, existing structural exclusion, truthful shared audit,
version/cache/checkpoint safety and two-item recheck verified; full599tests pass.
Not a declaration of95/95CV completion, blanket identity fairness or14C.2 readiness.
Resume/freeze all canonical inputs separately; no ranking/scoring in this task.
