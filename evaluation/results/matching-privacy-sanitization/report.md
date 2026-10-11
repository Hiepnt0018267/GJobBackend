# Task 14C.1.6 Shared Matching Text Privacy Sanitization

## 1. Status

**PASS.** Shared production/evaluation sanitizer, focused regression, full pytest
and real 10-JD privacy audit pass. Canonical v2 is wired in the working tree, not a
deployment/commit claim. No canonical batch/scoring was started in this task.

## 2. Objective

Neutralize supported contact identifiers only in the matching representation,
consistently in production and evaluation. Preserve raw records, extraction
persistence, human labels, scoring formulas, provider/model and ranking policy.

## 3. Original Blocker

The production mapper copied contact emails from two JD descriptions into
semantic_text. Task14C.1.5 correctly stopped with 8/10 accepted JDs and no completed
CV extraction. An evaluation-only scrubber would not resolve production fidelity.
This task fixes the shared boundary, not individual source rows or benchmark cases.

## 4. Source Review

Inspected matching_input_mapper.py, matching_input_service.py, matching schemas,
matching_fingerprint.py, cv_job_match_service.py freshness checks,
semantic_matching_service.py, Ollama embedding provider, extraction schema/service,
Task14C.1.5 report/wrapper/tests, existing text/document utilities, and test DB guard,
conftest/compose/template. No reusable contact sanitizer existed in the inspected
production utilities. Generic document whitespace normalization is not contact removal.

Plan before code: add one pure shared sanitizer and safe category-only auditor;
apply after canonical section construction; choose [CONTACT] replacement; version
representation and fingerprints; reuse production mapper/auditor in evaluation;
test numeric/URL false positives and all CV representation paths; rerun real JD audit;
run full guarded pytest; keep old artifacts and defer 95-CV extraction/scoring.

## 5. Shared Pipeline Location

app.services.matching_text_privacy.sanitize_matching_text(text) is the shared pure
function. find_matching_text_privacy_issues(text) reports categories only, never
identifier values. matching_input_mapper._semantic_text calls sanitizer once after
joining the existing canonical sections. Both build_cv_matching_input and
build_job_matching_input use this boundary before any embedding request.

## 6. Sanitization Policy

Deterministic replacement constant: [CONTACT]. Supported email syntax includes
mixed case, plus tags, subdomains, mailto and punctuation. Phones support common
grouped local/international formats, country-prefix numbers and recognizable VN
0-prefix numbers; labeled Phone/Tel/Mobile/Hotline/Điện thoại/SĐT are supported.
Digit-count bounds are 9–15. Numeric metadata labeled certificate/license/ID,
salary, quantity, model/version, serial/invoice/order is preserved conservatively.

Contact URLs: LinkedIn /in/ profiles; Facebook/Instagram, Telegram t.me, WhatsApp
wa.me, Zalo zalo.me; exact /contact, /contact-me, /about-me paths; URLs explicitly
labeled LinkedIn/Portfolio/Personal website/Contact page or supported Vietnamese
equivalents. Ordinary technical URLs are not removed merely for being URLs, and
phone-shaped numeric URL paths/query parameters are protected from phone detection.
Paired direct contact labels become the same token. Ordinary 'contact customers'
or an unpaired 'Phone support' label stays unchanged.

No generic number stripping, occupation rules, job IDs, labels or model results
influence rules. No whitespace cleanup of the original non-contact text is added;
the existing mapper normalization remains authoritative. Neutral tokens preserve
surrounding word boundaries. Function is idempotent and handles None/empty as ''.

## 7. Canonical Versioning

MATCHING_CANONICAL_VERSION = matching-canonical-v2-contact-sanitized.
This versions the representation, not the cosine engine. Semantic-v1 remains
semantic-v1; its service/formula file remains byte-identical. Canonical schemas/API
fields are unchanged. Version is included in evaluation preparation profile/source
hashes and both production matching fingerprints. No DB version field or migration.

## 8. CV Integration

Builder CV, candidate-confirmed uploaded CV and latest successful structured
extraction all pass through build_cv_matching_input. Tests exercise each path.
Names/email/phone/photo/DOB/address in personal_info still are not selected semantic
fields; contact identifiers appearing in objective/experience prose are now sanitized.
Structured fields and location metadata are not rewritten. Free-prose names or
demographic facts are outside this contact-only policy; no broad NER scrubber added.

## 9. JD Integration

Title, description, requirements, skills and other existing semantic sections are
constructed exactly as before, then sanitized together. Raw description/requirements
and canonical structured fields remain intact. No company/title/industry/skill or
responsibility rule was changed. Source-only reproduction of the real two failures
confirms emails are absent from final matching text.

## 10. Evaluation Integration

prepare_ranking_canonical.py still directly calls both production mapper functions.
Its contact assertion now delegates to the shared category auditor; no duplicated
email regex or evaluation-only transformation remains. Existing personal-value
admission checks are audits, not an alternate text formatter or demographic scrubber.
Profile records the canonical version and sanitizer file hash.

Added --refresh-jd-drafts for explicit next-task upgrade of the incomplete v1 drafts.
It refuses a frozen summary or any CV checkpoint, verifies original JD source
provenance and rebuilds the unfrozen JDs through the new mapper. Normal startup does
not refresh drafts automatically. This flag was NOT executed here; old checkpoints,
summary, manifest and blocker report remain historical evidence.

## 11. Cache / Embedding Implications

Production CVJobMatchService compares fingerprint_cv/job with stored fingerprints
before serving cached results. Fingerprints include exact semantic_text, matching
skills/project technologies, and now canonical_version. Thus changed text invalidates
old results, and even unchanged text cannot collide across v1/v2 representations.
Existing cached DB records are not edited/deleted. Cache misses recompute on normal
future matching requests; whole-match cache invalidation can also recompute the
unchanged baseline component. No baseline formula change is implied.

OllamaEmbeddingProvider has no local reusable embedding cache; it sends the supplied
texts directly. Historical offline caches/artifacts remain untouched and must not be
used as canonical-v2 evidence. Evaluation canonical profile includes version/code
hashes; future scoring must verify the frozen new inputs and their text identities.

## 12. Privacy Audit

Read-only audit of the same 10 selected JDs: **10/10 PASS** for supported contact
patterns after the production mapper. Raw supported-contact issues: email in two
JDs (3693046701 and 3699410505); none in the other eight. No final issues detected;
all ten outputs idempotent. No real source excerpts/contacts were copied to tests
or this report. This is a supported-pattern audit, not a general PII/fairness proof.

## 13. False-positive Preservation Tests

Preserved Python 3.12, .NET 8, AWS EC2, ISO 27001, 5 years, 20%, 3-person team,
HTTP 200, REST API, CCNA, IELTS 7.0, 2024-2026, full dates, salary 20-30 million,
long salary amounts, certificate IDs/quantities resembling phone numbers and
technical URLs including numeric paths/query parameters. Non-contact mapper
output matches an identity-sanitizer control exactly. Input fixture objects remain
unchanged. No result-dependent tuning or real ranking metric was used.

## 14. Tests

- Final focused sanitizer/input/semantic/embedding: **133 passed in 0.99s**, exit 0.
- Final evaluation regression: **138 passed, 2 warnings in 5.90s**, exit 0.
- Synthetic tests cover email categories, phone formats, URLs, idempotence,
  determinism, empty input, punctuation/adjacent career numbers, technical/numeric
  preservation, all three CV production entry paths, raw immutability, shared
  evaluation JD mapping and versioned cache identity.
- Earlier full suite: 578 passed, 3 warnings in102.52s; final verification below
  supersedes this intermediate run after additional false-positive regression cases.

## 15. Full Pytest

Final full pytest: **585 passed, 3 warnings in 103.00s (0:01:42)**, exit 0.
Warnings are existing google-genai UnionGenericAlias, Starlette/httpx TestClient and
HTTP_422_UNPROCESSABLE_ENTITY deprecations. No failing tests.
Only existing gjob_db_test is targeted via the repository's
TEST_DATABASE_URL guard and child-process environment. No new DB/config, OS-wide
setting or guard bypass. URL/password are never printed. Existing Docker credentials
and the existing test-template target are resolved in memory if a test URL is absent;
the guard verifies separation from DEV and actual database identity before fixtures.

## 16. Ground Truth / Raw Data Integrity

Ranking ground truth SHA remains
a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d.
Old220/fresh70 ground truth and calibrated thresholds match their previous recorded
SHA values. Resume.csv SHA remains
816a7cd985a9a41e3ce8d1e83cb7e1beb1e854a89c1cf1fd0d75494faaa0559d;
job_postings.csv remains
d782e95f35cbd5f658ad7124021c938f5c8c1656f1c059b6dc9d402d1eaa195f.
Semantic service SHA remains
0c347e9dd24ab68b10e2c95a3eea7d634e40a9c094c07e206aed0e62d1319fdf.
No old14B artifacts, labels, raw sources, uploaded files or extraction results were
rewritten. Old metrics are historical raw/previous-representation evidence, not v2
ranking validation. Existing unrelated dirty-worktree changes were preserved.

## 17. DB / Migration

Migration: none. Canonical text is generated dynamically. No DEV DB access/write,
account/CV/job/application creation or database cache cleanup. Full pytest uses
isolated test DB only, with normal migrations/fixtures/teardown.

## 18. Provider Usage

Zero live Qwen/Gemini/BGE-M3 calls. JD audit uses deterministic source/mapper code;
CV tests use synthetic representations and mocked dependencies. No embeddings,
cosine scores, ranks, thresholds or ranking metrics were calculated.

## 19. Known Limitations

Conservative recognized syntax, not all international phones/obfuscated emails or
all personal website domains. Bare ambiguous numeric IDs without metadata labels
can resemble local phones; arbitrary prose cannot be perfectly disambiguated by
regex. Unsupported social hosts/profile schemes may remain. No general name,
address, demographic or protected-attribute detector. A [CONTACT] token still
signals contact presence; no claim it makes all representations demographically fair.
Existing schema fields may contain personal data outside semantic_text and are not
redacted in production. Extraction quality and ranking performance are not evaluated.
The full canonical dataset and 14C.2 scoring remain separate unfinished tasks.

## 20. Task 14C.1.5 Resume Handoff

Shared API: app.services.matching_text_privacy.sanitize_matching_text.
Version: matching-canonical-v2-contact-sanitized. Mappers:
app.services.matching_input_mapper.build_cv_matching_input/build_job_matching_input.
Versioned production fingerprints prevent old unsanitized match-cache reuse.
Real JD audit:10/10. Use the explicit --refresh-jd-drafts upgrade for the current
unfrozen, CV-empty checkpoint; process unique CVs with production extraction;
canonicalize JDs and verify complete manifest/new hashes before a canonical freeze.

Next-task command, **not run here**:

```powershell
venv\Scripts\python.exe -X utf8 -u -m evaluation.prepare_ranking_canonical --data-dir C:/DATN/Datasets --refresh-jd-drafts
```

Do not run 14C.2 until 95 CVs/10 JDs and 100/100 pairs pass/freeze. This task does
not erase or retrospectively relabel the prior blocked reports as successful.

## 21. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_matching_text_privacy.py tests/test_matching_inputs.py tests/test_semantic_matching.py tests/embeddings -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Full pytest launches through a secret-redacted child environment with the validated
existing TEST_DATABASE_URL; no credential-bearing command is reproduced. Additional
read-only source-only 10-JD privacy/idempotence and SHA audits ran. One protected
historical-file hash read was retried with read-only approval. Synthetic/temp tests
clean up through their fixtures. No real data/checkpoint/embedding cache was deleted,
no lingering batch was started and no source-data cleanup was needed.

## 22. Final Status

**PASS — READY TO RESUME TASK 14C.1.5 CANONICAL INPUT PREPARATION.**
Shared canonical v2 sanitizer and versioned fingerprints are implemented; 10/10 real
JDs pass, full regression passes (585 tests). Ground truth/raw sources unchanged,
no live provider/DEV write/migration/frontend/scoring. Canonical input preparation
must still finish/freeze separately before Task14C.2 can run.
