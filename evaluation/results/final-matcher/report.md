# Task 14B.7 Final Matcher Selection

## 1. Status

**PASS for decision/policy delivery. Decision C: select Semantic-v1 as the primary
ranking matcher; select no binary matcher. Production integration is pending Task
14B.8, not performed here.** This is a defensible product/engineering choice, not a
claim of statistical superiority, validated production Top-K quality or autonomous
recruitment readiness.

One decision JSON: `evaluation/results/final-matcher-selection.json`. This is the only
Markdown report created for this task. No algorithm, label, fitted state, threshold,
previous result, runtime code or frontend behavior was changed.

## 2. Objective

Choose a practical matching policy from existing evidence, without another experiment.
The primary product question is recruiter review prioritization within one job's
applications, not automatic suitable/unsuitable classification. Candidate job
recommendations are a possible later use case, not an existing production feature.

Plan after source review: inspect actual authorization, score fields, ordering and
pagination; weigh FP/FN, ranking and operational costs; choose one matcher and define
threshold, score, coverage, error and explanation semantics; create only JSON/report;
run offline regression and read-only integrity checks; hand integration to 14B.8.

## 3. Evidence Reviewed

Reviewed stored reports, metrics, predictions and paired outcomes from semantic-v1,
baseline-v1, heldout, fresh-test and hybrid-v1. Read calibrated_thresholds.json,
hybrid_config.json, lexical implementation and development-only IDF binding/state.
All result JSONs in those five folders were readable; original predictions contained
220 semantic, 220 lexical and 70 fresh rows; hybrid predictions contained 88/70 rows.
Frozen hashes/unique IDs were verified without model calls or scoring reruns.

Source reviewed: `app/routers/matches.py`, `app/services/cv_job_match_service.py`,
`semantic_matching_service.py`, `baseline_matching_engine.py`, `matching_input_service.py`,
`matching_input_mapper.py`, `app/schemas/matching.py`, pair-result repository, embedding
factory/provider, recruiter application router/repository and jobs ordering. Frontend
review included MatchResultPanel, RecruiterApplicationMatchPanel, matchingService,
RecruiterApplicationsPage and JobListPage. No source path/behavior was inferred from
evaluation code alone.

| Evidence | Semantic-v1 | Offline lexical baseline |
|---|---:|---:|
| Old 220 default 0.5 TP/TN/FP/FN | 115/9/95/1 | 0/104/0/116 |
| Old 220 pooled ROC-AUC / AP | 0.777188 / 0.779317 | 0.834466 / 0.819943 |
| 88 calibrated TP/TN/FP/FN | 39/20/22/7 | 39/28/14/7 |
| 88 Recall / F1 | 0.847826 / 0.728972 | 0.847826 / 0.787879 |
| 88 pooled ROC-AUC / AP | 0.761387 / 0.784297 | 0.819876 / 0.826252 |
| Fresh 70 TP/TN/FP/FN | 33/19/13/5 | 31/20/12/7 |
| Fresh Precision / Recall | 0.717391 / 0.868421 | 0.720930 / 0.815789 |
| Fresh F1 / Accuracy | 0.785714 / 0.742857 | 0.765432 / 0.728571 |
| Fresh Specificity / Balanced Accuracy | 0.593750 / 0.731086 | 0.625000 / 0.720395 |
| Fresh ROC-AUC / AP | 0.840461 / 0.829989 | 0.816612 / 0.848977 |
| Fresh hard-negative FP | 6/14 | 6/14 |
| Fresh hard-group ROC-AUC / AP | 0.809524 / 0.817624 | 0.682540 / 0.772989 |

Do not pool these evaluations as independent replications. The 88-pair split is
retrospective development evidence; old lexical IDF was transductive. Fresh 70 had
zero old project identity/content overlap and development-only IDF, but came from the
same archives and one Qwen-assisted human reviewer. It is now consumed, not a new
test of this decision. Paired fresh F1 difference (lexical minus semantic) 95% CI
[-0.140802, 0.095191] crosses zero. Fresh semantic-only correct=12, lexical-only=11,
both correct=40, both wrong=7. No overall statistical winner is established.

## 4. Product Matching Use Cases

**Current product:** recruiter explicitly requests matching for one submitted CV on
an application detail page. POST `/api/v1/recruiters/applications/{application_id}/match`
is scoped to recruiter-owned jobs and the submitted CV. The backend also exposes POST
`/api/v1/candidate/jobs/{job_id}/match` for a candidate-owned CV/approved job, but the
current frontend has no candidate match panel/service call. No candidate recommendation
endpoint or score-sorted application list was found.

Recruiter application lists currently use created_at DESC, id DESC, with status/search/
job filters. Matching does not make application-status transitions. There is no
production binary threshold, unified match_score field or matching Top-K policy.

**Selected target:** A, recruiter ranking with manual review; optional existing
user-selected status/search filters remain, not a score suitability gate. Recruiter
decides review/shortlist/reject/hire. Ranking is scoped to one fixed job, not a global
ordering of candidates across unrelated jobs. Candidate recommendations remain a
separately authorized future feature. Do not restore candidate-side matching UI merely
because a backend pair endpoint exists.

## 5. Semantic-v1 Assessment

BGE-M3 raw cosine already has a provider-neutral service and authorization-aware pair
orchestration. Fresh point estimates favor semantic recall/F1/ROC-AUC and hard-group
ranking. Avoiding lexical-only exclusion is aligned with human review prioritization;
related wording/transferable experience is a plausible advantage, not a proven guarantee.

Specificity is weaker, pooled AP is not uniformly better, and development FP can be
high. Semantic score does not verify mandatory qualifications. It depends on embedding
inference/model availability and versioned freshness. Choosing it for ranking does not
make its historical binary threshold a safe rejection policy.

## 6. Baseline-v1 Assessment

The benchmark reference is `baseline-v1-offline-lexical`: 0.7 TF-IDF cosine + 0.3
literal title-token coverage. It is deterministic and inexpensive, with better pooled
development metrics and slightly better fresh precision/specificity/AP. This is serious
counterevidence to any claim that semantic universally ranks better.

Fresh recall is lower; lexical overlap and fixed-vocabulary OOV behavior can miss
related wording. The frozen development state uses 382 documents, vocabulary 16478;
SHA-256 `7b1405dc50bf26e96517b2ff2fdda65e8a1dddab1e7069e6ac44863ce8dbb25d`.
It was read/verified, not fitted or transformed on new input in this task.

Production `BaselineMatchingEngine` is DIFFERENT: exact normalized structured-skill
coverage, weight 1, 0-100, with skills/project-technology evidence and controlled
insufficient-signal status. Its version string is also baseline-v1, but it is not
the lexical benchmark. Do not transfer lexical metrics/thresholds to that engine or
silently substitute it as the selected primary matcher.

## 7. Hybrid-v1 Assessment

**NOT SELECTED FOR PRODUCTION.** Preserve code/config/artifacts for thesis evidence.
Frozen alpha=0.50, threshold=0.4962121212121212, recall floor=0.80, fallback=false.
88 result: TP32/TN33/FP9/FN14; Recall0.695652 versus0.847826 for both components.
FP reduction introduces seven additional FN compared with each component; intended
recall did not generalize. Higher 70 diagnostic F1 does not rescue this failure and
is not independent hybrid validation. No Hybrid-v2, guard, fusion or retuning here.

## 8. False Positive vs False Negative Trade-off

Chosen product assumption: **showing additional candidates for human review is less
harmful than automatically hiding a potentially good applicant.** Recruiter time is
valuable, but a reviewable FP and irreversible score-based exclusion have different
costs. Fresh semantic retained two additional positives at the cost of one additional
FP versus lexical; hard-negative FP remained equal. This supports a cautious workflow
choice, not a precise economic cost model or measured production prevalence.

Ranking still creates exposure risk: low-ranked good candidates may receive less
attention. Therefore preserve access to every application, explicit unranked/coverage
counts, pagination and the ordinary recency view. Do not equate ranking-only policy
with guaranteed full recall or fair exposure.

## 9. Ranking vs Binary Classification

Ranking orders relative similarity for one fixed job/CV context. Binary classification
requires a defensible suitability cutoff and validated operating requirements. Select
ranking only. No automatic suitable/unsuitable badge, rejection, hire or shortlist.
Top-K is a display budget, not a positive/negative decision. Pooled pair ROC-AUC/AP
suggest useful signal, but do not validate per-JD NDCG, Recall@K or Precision@K.
Those were not calculated or invented for this task.

## 10. Operational Considerations

Reuse SemanticMatchingService and CVJobMatchService, not a second scoring stack.
Current service embeds both canonical texts on a cache miss. Pair results are cached
by CV/JD fingerprints, engine versions, provider/model configuration and dimensions;
there is no reusable entity-level vector cache. Semantic failure returns unavailable
with independent structured-skill evidence; it does not silently switch matcher.

Historical offline runtime (220): lexical2.557915s; semantic initial77.075s/cache
replay9.922s. These are aggregate offline runs, NOT comparable per-request production
latency/SLA or measured current GPU load. Backend embedding default timeout30s;
frontend pair-match timeout45s. Avoid unbounded synchronous ranking inference/model
swap load; 14B.8 must assess bounded computation/coverage and cache reuse explicitly.

Important integration gaps: benchmark raw-source-normalized text differs from
production canonical structured fields; extraction quality was not evaluated. Offline
requests used num_ctx8192/num_batch8192/truncate=false after production's default
request failed on long raw texts. Production sends truncate=false but not those options.
Do not claim benchmark performance transfers unchanged; verify/document representation
and runtime-profile compatibility before rollout, without silently changing preprocessing.

## 11. Final Matcher Decision

**Decision C. Semantic-v1 is selected as GJob's primary ranking matcher, not as a
calibrated probability classifier. No binary matcher is selected.** Selection status:
engineering_policy_selected_integration_pending. Evidence remains mixed; the choice
balances human review, fresh recall/hard ranking, existing service reuse and operational
costs. Baseline's AP advantage is acknowledged rather than explained away.

The decision JSON is documentation, not an active application configuration. Nothing
imports it into production in this task. No feature has been rolled out.

## 12. Production Role

Primary semantic ranking signal for applications to a recruiter-owned job, presented
as decision support. Human status transitions remain authoritative. Structured-skill
evidence can remain an independent diagnostic panel, never a second primary score,
fusion gate or lexical-baseline stand-in. Search, apply and CV handling remain usable
when matching fails/is processing/not ready.

## 13. Threshold Policy

No hard score threshold or display cutoff for primary ranking. Do not hide/reject low
scores, treat missing/stale scores as zero, or use 0.5 as a default suitability gate.
Historical semantic0.5867267674262028 and lexical0.24733698756646583 remain evaluation
operating points only, read from unchanged heldout/calibrated_thresholds.json (SHA-256
`5d552274da24d355c1c9eb631377ace6d31fe059b2a3477434d9ae8644e746f8`).
No binary flow was found that requires promotion of either threshold. If such a flow
is requested later, its explicit policy must reuse a frozen threshold or undergo a
separate approved validation; do not silently calibrate on consumed data.

## 14. Top-K / Ranking Policy

No existing matching K was found. Reuse existing pagination as the display budget:
recruiter UI10, backend application default20, permitted1-100. A page of ten is not
a validated optimal K and does not mean ten suitable candidates. Rank the complete
authorized, job-scoped, user-filtered scored pool BEFORE pagination by full-precision
semantic score DESC, then application created_at DESC, id DESC. Never score/sort only
the current recency page and call it global Top-K. Keep remaining pages accessible.

Disclose total application count, fresh scored count and unranked count/status. Not
ready, failed or stale rows remain visible through an explicit unranked section and
ordinary full list. Partial coverage must not masquerade as a complete ranking.
If ranking cannot be computed, use the existing recency view with an unavailable
notice, not a silent score substitution. The global cross-job list stays recency-first.

Candidate recommendations, IF explicitly authorized in 14B.8/later, can use the same
semantic matcher to rank eligible approved/open jobs for one selected owned CV, no
hard score cutoff, with ordinary search/apply intact. Reuse existing jobs UI9/backend
default10/max100 pagination as a proposed display budget; nine is not a tested
recommendation K. No CV/provider readiness becomes a gate to browsing or applying.
Candidate recommendation API/UI remains disabled until that separate rollout decision.

## 15. Score Interpretation

Use `semantic.result.semantic_similarity`, raw cosine [-1,1]. Higher means greater
semantic content similarity, not probability of suitability/hiring/acceptance,
guaranteed qualification, human assessment or a percentile. Sort full precision;
round only the display. Prefer "Điểm tương đồng ngữ nghĩa", not "Phù hợp 87%".
Current MatchResultPanel already shows raw cosine with [-1,1]/not-hiring-probability
copy; retain that honest interpretation. No ECDF or percentage transformation.

Do not generate reasons from cosine alone. Existing strengths/gaps come from exact
structured-skill evidence and must be labeled independently. "Not found in CV data"
does not prove a skill is absent; extraction may miss it. Keep score/version/model,
freshness/status and computation time traceable; missing is not zero.

## 16. Baseline-v1 Future Role

Retain offline lexical implementation, fixed IDF state and artifacts as evaluation
reference/regression/diagnostic. No automatic fallback or future guard is implemented
or approved here. Preserve production structured-skill evidence separately; it is
neither the benchmark lexical scorer nor a probability classifier.

## 17. Hybrid-v1 Future Role

Retain frozen research artifacts; not selected, deployed, deleted or reopened. Future
fusion would require a separately authorized/versioned experiment and untouched
evaluation data, not edits to the existing results to create a winner.

## 18. Known Risks

Small, difficulty-focused, single-reviewer/LLM-assisted same-archive data; statistical
uncertainty; repeated development exposure and consumed70; raw/canonical representation
gap; finite context; model-tag drift; extraction omissions; provider latency/model swap;
ranking exposure bias; no representative per-job large candidate pool/Top-K quality;
unvalidated production prevalence/calibration. Semantic is not uniformly superior to
lexical and can rank occupationally similar but unqualified applicants highly.

These risks justify human review, full-list access, explicit unavailable states and
integration verification. They do not justify inventing stricter filters or claiming
autonomous hiring quality. No new fairness/performance guarantee is asserted.

## 19. Task 14B.8 Requirements

Integration handoff (NOT implemented here):

1. Reuse SemanticMatchingService, CVJobMatchService and MatchingInputService authorization,
   submitted-CV ownership and uploaded-CV precedence (builder, confirmed, latest usable
   success). Preserve prior usable success, apply independence and existing domain errors.
2. Extend the recruiter job-scoped application flow with explicit match-score ordering;
   preserve global recency lists, ownership/status/search filters and human transitions.
3. Rank the complete authorized filtered pool before pagination, stable tie-breaks;
   expose total/scored/unranked coverage and access to every application. Do not silently
   cap computation and label an incomplete pool global Top-K.
4. Reuse raw semantic score response fields and add only justified list metadata for
   status/version/model/freshness. Keep null/stale distinct from zero and cosine separate
   from structured coverage. No binary gate, probability percentage or fake explanation.
5. Reuse fresh pair-result cache; assess bounded inference and per-entity cache only if
   justified. Any new cache identity must cover canonical text, engine/preprocessing,
   provider/model identity, dimensions and request profile; no stale cross-model reuse.
6. Verify canonical-input/extraction and embedding context-profile gaps before rollout.
   Do not import the offline runner/provider into production or silently change matcher
   text/model/options. Record actual latency/cold-start/context limitations separately.
7. Handle provider unavailable/not-ready/stale inputs explicitly with retry and ordinary
   recency/unranked access. No lexical/structured-score substitution or automatic rejection.
8. Keep candidate recommendations/match UI absent unless explicitly authorized. If
   approved, scope to owned selected CV and eligible approved/open jobs with ranking/
   pagination only, no browse/apply gate or arbitrary optimized K.
9. Test RBAC/cross-recruiter isolation, ordering BEFORE pagination, ties, coverage,
   partial failure/null/stale/negative cosine, cache invalidation, uploaded-CV precedence,
   no human-status side effects and no apply/browse regression using mocks/synthetic data.
10. Run full pytest through existing guarded TEST_DATABASE_URL and scoped synthetic
    smoke with exact cleanup if authorized; no DEV reset or benchmark/threshold tuning.

## 20. Tests

- Current evaluation regression: **103 passed, 1 warning in 4.50s**, exit0.
- Current pure matching/canonical/embedding regression: **90 passed in 0.95s**, exit0.
- Read-only real artifact audit PASS: JSON parsing, expected CSV counts/unique pair IDs,
  frozen hybrid/source hashes and 220/70 human-label hashes. Audit disabled sockets;
  no score recomputation, optimizer, fitting or provider/DB connection.
- Decision JSON parsed/type-checked against its explicit fields/policy and existing
  thresholds/metrics. Report structure checked for the exact22 sections and output scope.
- No runtime code changed, so no unnecessary test module or full DB suite added. Full
  pytest is optional for this documentation-only task per attachment section26 and
  was NOT rerun; 495 passed/3 warnings in107.98s is the historical14B.6 result, not a
  new14B.7 run. Full guarded regression remains required for14B.8 implementation.
- Existing warning: Starlette/httpx TestClient deprecation. No failing tests.

Commands run (all in backend root, except frontend source inspection):

```powershell
venv\Scripts\python.exe -m pytest evaluation/tests -q
venv\Scripts\python.exe -m pytest --noconftest tests/test_baseline_matching.py tests/test_semantic_matching.py tests/test_matching_inputs.py tests/embeddings -q
git diff --check -- evaluation
```

Additional read-only Python/PowerShell diagnostics parsed aggregate artifacts, checked
decision policy, CSV counts, hashes and source ordering/UI. No benchmark runner command,
Ollama/LLM call, DB command, migration or threshold-search command was executed.

## 21. DB / Privacy / Cleanup

No DEV/test DB connection or data creation/deletion in this task. Pure tests use
--noconftest and evaluation tests use synthetic fixtures/temporary directories, with
their existing cleanup. No live provider called. No raw CV/JD/contact text, credentials,
URLs/passwords or vocabulary dump copied into output; only aggregate evidence.

Before/after integrity audit covers846 preexisting source/test/migration/evaluation
files, excluding pycache and these two new outputs: aggregate tree SHA-256
`5c1744e4bd6ddad31d2b4d198036949c6e4fb3893808cbc08aef71a264b0c55b`.
Original algorithms, labels, thresholds, fitted states and artifacts remain byte-identical.
Unrelated existing worktree changes preserved. Exactly two task files created, one JSON
and one Markdown report; no extra docs/cache/data copies to clean up.

## 22. Final Status

**PASS. Select Semantic-v1 for ranking-first recruiter decision support; select no
binary matcher.** Policy explicit; baseline retained as reference, hybrid not promoted,
all evidence frozen. This is an engineering selection under mixed evidence, not a new
statistical winner or completed deployment. Task14B.8 must implement/verify the bounded,
authorized, transparent ranking workflow. Candidate recommendation rollout remains
separately authorized, and all applications remain accessible to human review.
