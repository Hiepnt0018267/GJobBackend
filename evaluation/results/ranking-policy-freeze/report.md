# Task 14C.6 Final Ranking Policy Freeze

## 1. Status

**PASS policy freeze/consistency/regression after a narrow overflow guard fix.**
Final full pytest: **734passed,3warnings in167.15s (0:02:47)**,exit0.
Policy version: recruiter-ranking-policy-v1. This is approval of a constrained
decision-support scope, not deployment,autonomous hiring or fairness certification.

## 2. Objective

Close Task14C by synthesizing existing evidence and freezing actual recruiter ranking
behavior. No new experiment,benchmark,label,model/provider/config/frontend change.
Plan: review four evidence streams/source; define invariants; bind JSON freeze to
source/evidence hashes; behavioral regression/full guarded tests; close14C.

## 3. Evidence Reviewed

### 14C.2 Ranking Quality

Measured100pairs/10jobs/95CVs with105canonical embeddings. P@1=.70,P@3=.633333,
MRR=.825,NDCG@10=.806903. Three jobs have grade0Top1;four grade2 belowTop5.
USEFUL BUT INCONSISTENT. Small constructed/single-reviewer benchmark,not production
prevalence or independent deployment/fairness certification. No metric rerun here.

### 14C.3 Production Integration

Existing endpoints with explicit ai_match;default preserved;cache-only list;full set
beforeN/pages;owner/input-bound snapshot;missing/null visible;no automatic decisions.
Full680tests historical. Policy decision: preserve these safeguards,not broaden scope.

### 14C.4 Fairness Audit

Direct structured identity/contact/photo/DOB excluded from semantic features/ties.
Prose/proxy and ranked-first availability risks remain. Reliable governed protected
labels absent;disparity NOT MEASURED;occupation cohorts are not protected groups.
Audit PASS WITH LIMITATIONS,full697historical. Do not claim the model is fair.

### 14C.5 Robustness Audit

21/22BGErequests,20successful unique vectors,one explicit overflow;no retry/tuning.
GenericJD reverses illustrative three-slot order;proxy/noise score shifts remain.
Keyword repetition decreased scores in one reference,not universal immunity.
Malformed cache/snapshot and duplicate boundary guards fixed with regressions.
PASS WITH LIMITATIONS,full727historical. No experiments repeated here.

All four reports read in full and cross-checked against current router,repository,
service,status/schema,canonical/semantic/fingerprint/provider/profile/cache/precompute
code and existing tests. Report conclusions and policy judgments are not conflated.

## 4. Final Production Decision

**APPROVED FOR OPTIONAL RECRUITER-SIDE RANKING DECISION SUPPORT.**
Semantic-v1 is NOT approved for eligibility,automatic rejection/shortlisting/hiring,
candidate suppression or calibrated suitability classification. This freeze approves
the existing backend policy;no production rollout/restart/UI implementation occurred.

## 5. Activation Policy

sort=ai_match is explicit opt-in on existing recruiter applicant GET endpoints.
Reason: useful but inconsistent,only10benchmark jobs,unmeasured demographic disparity,
proxy/noise sensitivity and intentional human control. No implicit AI default.

## 6. Default Ordering

sort=newest remains default: application.created_at DESC,application.id DESC.
WithoutAI,no canonical/vector/ranking/provider work required. Invalid enum follows422.
Defaults/source/service/API regressions agree;no default/order code edited this task.

## 7. Result Count Policy

No explicit AI count means ALL business-valid filtered applicants are logically
accessible. AI changes order only;page_size is transport,not TopK. No arbitrary3/5/10
default. OfflineK cutoffs remain evaluation-only. Every candidate can be opened/reviewed.

## 8. Explicit N Policy

ai_top_n=N>=1:filter full set,globally rank,then take firstN or all if fewer;no padding.
Unranked remainder is included when needed. total/total_pages describe that explicitly
requested logical subset. N/page-size/filter changes start a new traversal,not eligibility.

## 9. Pagination / Snapshot Policy

Global ordering before pages. AI page1 creates opaque ten-minute ranking_snapshot;
later pages require token,same owner/filters/page_size/N and compatible identities.
Availability-only changes retain old order/status view;fresh page1 can observe completion.
Membership/status/canonical/profile/filter changes,expired/missing/corrupt snapshot:
409 restart page1. Missing later-page token:422. Stable storage unavailable:503,offer
default sort. Whole manifest checks count,unique owned IDs,state/nullability,finite
scores,ranks/order before slice. No silent mixed ordering,duplicate or skipped traversal.

## 10. Applicant Eligibility Policy

Existing owner/application join and job/status/normalized-search business rules only.
Score does not determine validity,status or eligibility. Existing search may use
authorized name/email/display fields;that is a caller filter,not an embedding feature.
Role/owned-job checks precede AI. Duplicate application input fails409,not silent drop.

## 11. Ranking Status Policy

Exact production names:
ranked:compatible validated vectors and finite raw cosine available.
pending:canonical data ready,current compatible vector absent/not yet prepared.
unavailable:usable canonical input absent or semantic text empty.
error:canonical/cache/provider/computation/CV ownership-consistency failure.
These are availability states,not suitability labels or application business status.

## 12. Missing AI Signal Policy

Missing != low similarity. Non-ranked semantic_match_score and ai_rank staynull,
never fake0. Applicants remain visible with explicit state. Actual zero/negative
cosines remain ranked values. No threshold,classifier or status mutation.

## 13. Ordering / Tie-Break

Ranked first,raw cosine DESC at full precision. Exact ties preserve default
created_at DESC,id DESC. Non-ranked group follows in that same default order.
No name,gender,DOB,photo,address/contact demographic tie-break. Chronology/stability
is not proof of socially neutral effects. Backend does not sort on rounded UI values.

## 14. Embedding Profile Freeze

Semantic-v1,ollama/bge-m3,context8192,batch4096,truncate=false,1024dimensions,
vector_postprocessing=none. Version full-input-context-batch-v2;fingerprint
bcfd85c8e892993fa3111882be45f8beb92a610d191edb4455abb2aed0a908cc.
Digest pin7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab.
Canonical matching-canonical-v3-explicit-identity-contract;unchanged production cosine.
Physicalubatch4096 was observed in14C.2/14C.5;not rediscovered/live-called in14C.6.
No silent slicing/chunking,truncation or batch8192 upgrade. Overflow fails explicitly,
becomes safe non-ranked state and remains accessible. Capacity bounds are not suitability
thresholds. Model/profile/canonical changes require deliberate re-evaluation/cache identity.

## 15. Cache Safety

Production vector cache binds canonical version/fingerprint,textSHA,model digest,
provider/model/profile(ctx/batch/truncate) and semantic engine. No incompatible cache
relabeling/evaluation-cache reuse. Malformed payload/status/identity or wrong/nonfinite/
zero vectors are non-rankedERROR;stale identity is miss/PENDING. Valid vectors remain
private,never response payload. Atomic writes/exclusive leases retained. Duplicate and
whole-snapshot14C.5guards retained. Private disk trust is not cryptographic authenticity
of semantically wrong but numerically valid vectors;service-account permissions required.

## 16. Precompute / Cold Cache

One-entity best-effort post-commit hooks for CV create/update,uploaded extraction
success/confirmation,and recruiterJDcreate/update. Current production mapper/readiness:
application-attached CV,Builder directly;uploaded confirmed copy authoritative,
otherwise newest successful extraction. No raw adapter or extraction from recruiter GET.
Owned task session closes before provider work;at most oneembed/task;unchanged cache hit
zero requests. List live embedding/extraction budget isZERO,not an unbounded cold loop.
No durable queue/backfill/deadline introduced. Lost tasks/crash leases need verified
operator or lifecycle recovery;old unchanged entities may staypending indefinitely.

## 17. Provider Failure

Compatible cached signals remain usable without provider discovery from list. Cold
miss stayspending;failedprecompute records safeerror. No removal/rejection/business
status mutation. Pin verification before/after precompute;model replacement requires
deliberate pin/profile review. List cannot truthfully detect live outage without a
provider request,so a cold miss is not mislabeled as measured outage. No cloud fallback.

## 18. Score Exposure Policy

Existing backend raw cosine field remains permitted for technical/API use. Prefer
ai_rank/ranking_status on recruiter UI;raw scalar hidden by default recommendation.
If shown,label'similarity score',not match/fit percentage or success/suitability
probability. **0.73 !=73% suitable.** No calibrated classifier or cross-job probability
comparison. API shape unchanged;frontend implementation remains a separate task.

## 19. Human Review / No Auto-Decision

Mandatory recruiter human review/final decision. Ranking never auto-hide/reject,
shortlist/hire,markreviewed,change application status or notify a decision. Existing
explicit human actions remain available. There is NO suitability threshold/config:
score<X→hide/reject and score>=X→suitable are prohibited. No automatic eligibility.

## 20. Privacy / Sensitive Attribute Safeguards

Shared production canonical professional allowlist/contact sanitizer;direct
personal_info/account/photo/DOB fields not intended semantic features. IDs needed
for authorization/cache/result routing are not embedded. No semantic text/vectors
in ranking response/logs. Existing authorized display/search identity fields remain,
with possible human-review bias. Free-prose names/addresses/protected statements can
survive finite sanitizer rules;no universal PII/NER guarantee or new stripping policy.
Valid source chronology warnings are metadata,not scoring signals;unverified flags
cannot bypass existing proof-aware schema rules. No demographic inference allowed.

## 21. Fairness Limitations

Protected-group disparity NOT MEASURED;reliable governed labels absent. Direct exclusion
!=fairness. Occupation/source/readiness cohorts are not protected classes. Proxy effects
and ranked-first exposure risks remain. Do not claim 'Semantic-v1 is fair',infer groups
from names/photos/languages/locations or calculate age from graduation evidence.

## 22. Robustness Limitations

Proxy/location/school/employer/language-heavy and noisy prose alters scores. Generic
JD can concentrate/reverse useful ordering;short/sparse data has limited signal.
Keyword non-improvement in one reference is not immunity. No causal proxy attribution,
population robustness or new calibration claim. No heuristic compensation/penalty
or model tuning in this freeze. Correctness guards fixed in14C.5 remain,not reopened.

## 23. Known Operational Limitations

Persistentpending/legacycoldcache/heldlease can reduce practical visibility because
ranked rows precede all others. Not solved by keeping applicants accessible. Snapshot
status view maylag completion up to10minutes. BackgroundTasks best-effort,not durable
retry/SLA/backfill. Private shared worker storage/retention/operator recovery and model
deployment pin are required. Full sets use proportional memory/disk;no production
load guarantee. Cross-job list cosines are not calibrated suitability comparisons.

## 24. Monitoring Recommendations

Future safe metadata:state counts/source-cohort availability,pending age/backfill backlog,
AI usage/latency,cache hits/misses,provider failures,invalid cache/snapshot/duplicate
incidents and recruiter complaints/usefulness. Existing logger records aggregate
counts/runtime;cache-hit and pending-duration telemetry is NOT claimed implemented.
No rawCV/JD/semantictext,vectors,PII or demographic guesses in logs. No new monitoring
infrastructure here. Metrics/backfill require separately scoped future work.

## 25. Future Re-Evaluation Triggers

Larger independent ranking pools;governed protected-group data;recruiter behavior
study/complaints;high/prolongedpending;integrity/provider incidents;material proxy/
robustness failures;model/digest/profile/canonical changes. Reopen only with explicit
future roadmap/evidence or genuine correctness blocker,not another optimistic tuning loop.

## 26. Frozen Policy Version

**recruiter-ranking-policy-v1**,normative policy.json,not a new runtime loader/config
or embedding/canonical version. Bindings:18current source files,7prior evidence files,
4ground/canonical inputs. Exact policySHA:
391f72429c98d598aa086cb6e0ccbc70ce9041d726c28c946f56ea8651182862.
Behavior is already implemented;new policy tests guard contracts,not source formatting.
Future revisions must explicitly version/review policy and relevant compatibility.

## 27. Regression / Policy Checks

New tests verify approval/noauto flags,null/no-threshold/full-set,.95/.40/.01 visibility,
actual default service path with noAI,current factory/profile/digest/state/version,
before/after statuses and full17/globalN/four-page stable pending completion.
Reuse cache-corruption/duplicate/authorization/snapshot/identity tests rather than
inventing new experiments. policy_checks.json separates source inspection,behavioral
tests and remaining limitations. SHA evidence/source/input consistency checks PASS.
No threshold/AI-default/hidden-applicant contradiction found. One corruption-safety
gap was reproduced: oversized JSON integers caused OverflowError in cached-vector
validation and snapshot isfinite. Pre-fix5passed/2failed in1.13s. Narrow correction:
cache catches OverflowError; snapshot checks intrinsic[-1,1] before isfinite.
Two new regressions pass. No change to cosine,model,profile,threshold or valid ordering.
Only ranking_cache.py and applicant_ranking_service.py guards changed;source bindings
were updated explicitly before final freeze. No new evaluation subtask/experiment.

## 28. Tests

Focused policy/ranking/robustness/fairness/embedding/semantic:
**140passed,1warning in2.32s**,exit0.
Offline evaluation:**151passed,2warnings in7.15s**,exit0.
Final full guarded: **734passed,3warnings in167.15s (0:02:47)**,exit0,including both
overflow regressions. Existing727-pass14C.5 and initial732-pass run are historical,
not the final result. Warnings are existing google-genai,Starlette/httpx,
deprecatedHTTP422. Providers/lifecycle mocked;synthetic/temp fixtures only.

## 29. DB / Model Safety

ZERO live BGE/Qwen/Gemini or model metadata/tokenizer requests;no benchmark/robustness/
fairness rerun,new pairs,labels,threshold search or comparison. No DEV DB access/write,
new database,env/config,migration,frontend or server change. Only the two named numeric
corruption guards changed production Python;valid API ordering/policy is unchanged.
Full tests existing guarded gjob_db_test via TEST_DATABASE_URL/current_database
validation and normal fixture/migration bootstrap;credentials memory/redacted.
New tests pure synthetic;existing owned API/test cleanup retained,temp snapshots teardown.
Of150preexisting protected production/input/evidence files,148are byte-identical;
only the two documented guard files changed. All prior evidence and four frozen
inputs unchanged;source/policy bindings verified after fixes. No real data/cache/
artifact deleted or overwritten. One new report.md,policy.json,policy_checks.json
and seven synthetic policy tests;unrelated worktree edits preserved.

## 30. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_ranking_policy_freeze.py tests/test_applicant_ranking.py tests/test_ranking_robustness.py tests/test_ranking_fairness_guards.py tests/embeddings tests/test_semantic_matching.py -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
git diff --check
```

Fullpytest launched inside guarded in-memory child environment with existing test/
Docker credentials,not shellURL/password or new settings. Read-only source/report/
JSON/hash/config-name/OpenAPI/service contract reviews. No live-provider command.
Policy/report/checks authored via apply_patch;one new Markdown report only.

## 31. Task 14C Final Conclusion

Optional Semantic-v1 recruiter ranking is approved under this exact policy,not for
autonomous decisions. Semantic remains the selected list signal. Baseline-v1 offline
is reference/evaluation only;Hybrid-v1 not selected. Existing separate structured
pairwise baseline component/API is unchanged and not the offline lexical baseline;
this list-policy freeze neither deploys nor removes it. No competitor switch.

Task14C closes with quality useful but inconsistent,
fairness unestablished,robustness/availability limitations explicit. No more Semantic-v1
tuning planned inside14C;no14C.7/14C.8 for ordinary known limitations. Final regression
and integrity verification PASS. Approval does not mean deployment or removal of
documented limitations.

**TASK 14C — AI CV ↔ JD RECRUITER RANKING: COMPLETE**

## 32. Next Roadmap Handoff

Future authorized roadmap may implement the small recruiterUI handoff or Task15
candidate-side job recommendation,a DIFFERENT objective that does not automatically
inherit this ranking policy. Neither is implemented or started here. No new subtask
invented to delay14C closure.

**READY FOR NEXT ROADMAP TASK**
