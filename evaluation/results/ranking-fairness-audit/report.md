# Task 14C.4 Fairness & Sensitive Attribute Audit

## 1. Status

**PASS WITH LIMITATIONS for the audit, not a fairness certification.**
No intentional structured name/contact/photo/DOB input or sensitive tie-break found.
Professional prose/proxy and access-to-ranking risks remain. Reliable governed
protected-group outcome labels are absent; disparity is NOT MEASURABLE FROM CURRENT
DATA. Final full regression: **697 passed,3 warnings**, exit0.

## 2. Objective

Audit direct-field exclusion, indirect leakage/proxies, production controls and
source-backed cohorts without model tuning, demographic inference or policy rewrite.
No real ranking/embedding/extraction was rerun.

## 3. Production Ranking Policy Reviewed

Read applicant router/service/repository/schema, ranking/cache/precompute/readiness,
canonical mappers/fingerprints/privacy, semantic/cosine/provider/profile, lifecycle
hooks, existing identity/ranking tests and Task14C.2 artifacts. Announced taxonomy
and audit plan before scanning. sort=ai_match remains explicit; newest is default.
No threshold, auto-hide/reject/shortlist/hire/review/notification. All business-valid
applicants remain accessible by default; missing scores remain null. Explicit caller
ai_top_n and existing search/status filters are business requests, not AI eligibility.

## 4. Sensitive Attribute Taxonomy

Direct identity/contact: full name,email,phone,home/street address,photo,account/CV IDs.
Potentially protected/sensitive: gender/sex,age/DOB,race/ethnicity,religion,disability,
nationality/citizenship,marital status,sexual orientation,political affiliation.
Proxy-like: education/employer/organization names,locations,country references,
languages/proficiency,employment gaps,career dates/graduation year. Proxy-like does
not mean prohibited. Classifications below: A job-relevant; B potentially relevant
and fairness-sensitive; C unnecessary/high-risk direct identity; D absent as an
intentional semantic feature. No field was removed or new attribute inferred.

## 5. Direct Attribute Exclusion Audit

CV.personal_info full_name/email/phone/address/avatar/DOB/profile URLs never enters
the professional section allowlist. Address supplies location metadata, not semantic
text or fingerprint. Managed photo key/account/candidate/CV IDs are not embedding
features. IDs remain necessary authorization/cache/result references.
JD location/company/account metadata is not directly concatenated into semantic
text. Synthetic perturbations preserve CV/JD semantic text and fingerprints.

Production schema explicitly permits DOB for CV/profile display; it is excluded from
matching and is not approved/used as an age cohort. No first-class gender/race/etc
matching input exists. Synthetic extra ORM protected/photo fields are ignored by the
mapper, not transformed into features. Explicit name extraction contract remains
unchanged: personal name only when clear, no role/heading/company inference.
Professional role text is not deleted merely because it resembles a name.

**Boundary:** structural exclusion is not universal free-prose exclusion. A name,
address or protected statement already in an allowed description can survive.
Supported contact patterns yielded0 residuals in95CV/10JD frozen canonical texts,
but that auditor is not a general name/address/protected-attribute detector.

## 6. Canonical Feature Inventory

CV semantic sections: objective,skill names,experience position/description,
education degree/field/description,project name/role/description,certificate names,
language names/proficiency. Frozen nonempty canonical fields: objective82,skills92,
experience94,education94,projects1,certificates32,languages13 of95CVs.
These field counts are not section quality or causal ranking-importance scores.

JD sections: title,description,requirements,skills,industry,level,experience requirement.
Separate employer/school/certificate-issuer names,structured career dates,gaps,
CV/DOB/location metadata are not deliberately selected semantic sections. They may
appear inside descriptions/project/certificate text. No explicit language weighting;
whole text is embedded. Learned sensitivity/importance remains unmeasured.

## 7. Tie-Break Audit

SQL starts created_at DESC,id DESC; stable score-DESC sort retains this order for
exact ties. No name,age,gender,location,photo or demographic tie-break.
Synthetic name/contact/avatar changes keep equal-score order; changing default
ordering time changes order as documented. Stable chronology is not proof of
socially neutral effects; digital access/application timing may still correlate
with background. No such correlation was inferred or measured here.

## 8. Fallback Ordering Audit

RANKED precedes all PENDING/UNAVAILABLE/ERROR; the latter group retains default
created_at DESC,id DESC. No photo/profile-completeness/name demographic fallback.
Identity-only changes leave fallback order/scores unchanged. Missing score and rank
remain null; no silent exclusion. Existing name/email search can intentionally
change the filtered pool; invariance tests concern fixed business-valid membership,
not different caller searches.

## 9. Ranking Availability Audit

Canonical-ready but cold/incompatible cache -> PENDING; missing usable representation/
empty text -> UNAVAILABLE; schema/mapping/cache/provider failure -> ERROR.
Builder maps directly. Uploaded confirmation is authoritative; otherwise newest
successful extraction is used, ignoring later failures. Uploaded with no successful
representation is unavailable even if arbitrary CV JSON fields look populated.
Synthetic source-path guard demonstrates Builder PENDING versus Uploaded UNAVAILABLE
without any model call. This is a technical mechanism, not a demographic finding.

Current offline corpus has95 raw Resume_str-derived CVs and all100 frozen pairs
scored. It does NOT contain real production Builder/Uploaded/PDF/DOCX/legacy cohorts
or list availability/duration telemetry. No production access rates are invented.

## 10. Protected Attribute Data Availability

Ground-truth/prediction columns are case/job/CV/pair/provenance/relevance/rank/score,
not governed protected-group labels. Resume.csv columns: ID,Resume_str,Resume_html,
Category. Category is an occupation label, not gender/race/age/nationality.
Free-prose cue presence is not a reliable candidate group label. Canonical artifacts
minimize personal metadata; raw-text mentions are not approved demographic metadata.
No label recovery from names,photos,dates,languages,locations or LLM was attempted.

Source-backed operational inventory: Category95CVs; one offline source origin95CVs;
selected JD formatted_experience_level5/10,location10/10,formatted_work_type10/10.
These JD fields are job metadata, not candidate attributes; no candidate cohort
inferred from them. Production source_type/MIME/readiness schemas exist, but observed
production rates/sample history do not exist in the authorized benchmark. Full
machine-readable field/source/protected/usable/sample-count/purpose inventory is in
audit_summary.json.

## 11. Protected-Group Disparity Analysis

**NOT MEASURABLE FROM CURRENT DATA.** Protected-group outcome disparity could not
be measured from the current benchmark because reliable source-backed protected
attribute labels are absent. No demographic classifier,synthetic-real label,
face inference,LLM guess or age-from-graduation calculation. Do not substitute
operational occupation groups for protected classes or interpret missing results
as zero disparity.

## 12. Operational Cohort Analysis

Join original Resume.csv.Category by exact selected CV identity/source row under
verified archive SHA. Reuse existing100 scores/ranks only; no rescoring or relabeling.
All23 categories retained:13 have pair-row n<5,10 have n5..9; none reaches10.
Guards use candidate-job opportunity rows: n<5 descriptive only,n<10 high uncertainty;
all remain descriptive regardless of n. Also report unique CVs and jobs: repeated
CVs mean row n is not independent sample size. PUBLIC-RELATIONS has5 rows but only4
CVs and remains especially small. Five CVs recur across jobs.

Table counts are TopK candidate opportunities, not qualification-adjusted fairness
rates. JSON rates divide counts by cohort candidate-job rows; rank fractions use
(rank-1)/(pool_size-1). No cross-job cosine mean or probability comparison.
All pools have10 candidates, but job/grade mix differs markedly; no causal attribution,
significance test or protected-group discrimination claim.

| Source Category | Pair rows / unique CVs | Jobs | Mean rank | Top1 / Top3 / Top5 counts | Grades 0/1/2 |
|---|---:|---:|---:|---:|---:|
| ACCOUNTANT | 8 / 7 | 5 | 4.750 | 1 / 2 / 6 | 5/0/3 |
| ADVOCATE | 6 / 6 | 5 | 4.833 | 0 / 2 / 5 | 3/2/1 |
| AGRICULTURE | 2 / 2 | 2 | 5.500 | 1 / 1 / 1 | 1/1/0 |
| APPAREL | 3 / 3 | 3 | 6.000 | 0 / 0 / 1 | 0/2/1 |
| ARTS | 4 / 4 | 4 | 5.500 | 1 / 1 / 1 | 2/2/0 |
| AUTOMOBILE | 1 / 1 | 1 | 5.000 | 0 / 0 / 1 | 1/0/0 |
| AVIATION | 3 / 3 | 2 | 5.000 | 0 / 0 / 2 | 1/2/0 |
| BANKING | 2 / 2 | 2 | 5.500 | 0 / 1 / 1 | 2/0/0 |
| BUSINESS-DEVELOPMENT | 9 / 9 | 6 | 6.222 | 0 / 2 / 3 | 7/0/2 |
| CHEF | 2 / 2 | 2 | 8.500 | 0 / 0 / 0 | 1/1/0 |
| CONSTRUCTION | 1 / 1 | 1 | 5.000 | 0 / 0 / 1 | 0/1/0 |
| CONSULTANT | 8 / 8 | 5 | 5.625 | 0 / 3 / 3 | 2/6/0 |
| DESIGNER | 1 / 1 | 1 | 2.000 | 0 / 1 / 1 | 0/1/0 |
| DIGITAL-MEDIA | 6 / 6 | 5 | 6.500 | 1 / 1 / 2 | 4/2/0 |
| ENGINEERING | 6 / 6 | 4 | 2.167 | 2 / 5 / 6 | 3/1/2 |
| FINANCE | 3 / 3 | 3 | 6.667 | 0 / 1 / 1 | 2/0/1 |
| FITNESS | 4 / 4 | 3 | 6.500 | 1 / 1 / 1 | 4/0/0 |
| HEALTHCARE | 4 / 4 | 3 | 3.250 | 0 / 2 / 4 | 2/2/0 |
| HR | 5 / 5 | 4 | 6.200 | 0 / 0 / 2 | 3/2/0 |
| INFORMATION-TECHNOLOGY | 9 / 7 | 6 | 6.556 | 1 / 2 / 2 | 7/2/0 |
| PUBLIC-RELATIONS | 5 / 4 | 4 | 4.800 | 1 / 2 / 3 | 1/3/1 |
| SALES | 6 / 5 | 4 | 5.333 | 1 / 3 / 3 | 1/2/3 |
| TEACHER | 2 / 2 | 2 | 9.500 | 0 / 0 / 0 | 2/0/0 |

Totals:100 rows,95CVs,10jobs; Top1/3/5 counts reconcile to10/30/50.
Example descriptive contrast: ENGINEERING6rows,Top3=5/6 versus
INFORMATION-TECHNOLOGY9rows,Top3=2/9. Grade/job mixtures differ; this is NOT evidence
of demographic discrimination or isolated occupational bias. Coverage is offline
scored_count; production ranked/pending/unavailable/error rates stay null, never0.

## 13. Proxy Risk Review

| Category | Classification / intentional semantic selection | Remaining risk |
|---|---|---|
| Skills/tasks/professional titles | A; selected | Role fit, extraction/model coverage still imperfect |
| Languages/proficiency | B; selected,13CVs | Nationality/ethnicity proxy possible; no inference or measured weighting |
| Candidate/JD structured location | D in text; metadata may exist | B if geography enters descriptions; onsite relevance/context dependent |
| Career dates/graduation/gaps | D as structured features; prose may retain them | B age/career-stage proxy; never compute age |
| Employer/school names | D as dedicated fields; prose overlap | B prestige/socioeconomic proxy; do not indiscriminately strip |
| Organization/project/certificate names | B; some name fields selected | Credentials/tasks useful but identity/prestige references possible |
| Name/contact/photo/DOB | C if used; intentionally excluded | Prose copies not universally detected |
| Pronouns/protected self-descriptions | B/C context-dependent; no dedicated field | Prose survival can expose sensitive cues; no candidate classification |

Aggregate finite text cues: CV pronoun terms4/95,sensitive-topic terms7/95,
four-digit-year cues38/95; JD corresponding0/10,3/10,2/10.
Literal normalized employer-name overlap10CVs and school-name overlap6CVs.
Overlap does not prove mapper field injection or prestige effects. Year matches
can be technical/date references, not age evidence. Pronouns/topic words can refer
to clients,job equal-opportunity statements or other people, not applicant identity.
No raw text,offending value,school/employer/person name or demographic label output.

A synthetic professional objective retains a pronoun,home-address phrase and year
while the supported-contact auditor returns no issue. This establishes detector
coverage limits, not a confirmed real-person address leak in the frozen corpus.
Supported emails/phones/contact URLs are sanitized identically in production and
evaluation because both call the exact shared mapper/sanitizer; no alternate filter.

## 14. PENDING / UNAVAILABLE Fairness Risk

**MEDIUM operational visibility risk.** Ranked-first can place a useful unavailable
applicant behind a less useful cached applicant. Visibility retained is not equal
exposure. BackgroundTasks is best-effort, no durable retry/backfill/completion SLA;
cold entries and crash leases can persist indefinitely until lifecycle/operator work.
ERROR timestamp is not a PENDING-duration measurement. No persistence duration or
real cohort rate observed. Snapshots deliberately retain the old status/order up to
10minutes; prevent duplicate/skip but delay new availability until a new traversal.
No policy/architecture change was authorized or implemented in this audit.

## 15. Legacy Data Risk

Pre-14C.3 unchanged CV/JD entities have no automatic vector backfill. Profile/digest/
canonical changes correctly invalidate cache, but create PENDING exposure until
precomputed. Uploaded extraction availability adds another dependency; old invalid
structured data can become ERROR. This mechanism plausibly disadvantages legacy/
source paths, but no observed production disproportion or demographic correlation
is claimed. Scalar pairwise caches are not usable substitutes for the pinned vector
cache. Verified source chronology metadata is not a relevance feature; forged/
unproven flags still cannot bypass schema validation.

## 16. API / Response Audit

AI additions only ai_rank,ranking_status,semantic_match_score and ranking_snapshot.
No protected inference,fairness-adjusted score,demographic group or probability.
Authorized candidate name/email/avatar remain list display fields; detail can expose
existing phone/CV profile metadata for human review. They are not AI inputs/tie-breaks,
but human-review bias remains possible. Snapshot/cache contains private IDs/hashes/
scalars/vectors, not raw canonical text. Raw cosine is not a percentage/probability;
cross-job list cosines are not calibrated comparable suitability probabilities.

## 17. Human Review Safeguards

Opt-in/default regression intact. List/cache ranking does not change application
status or trigger shortlist/reject/hire/notifications. All are accessible by default,
including negative scores and unavailable signals. Caller N truncation is explicit;
default list remains accessible. Existing guarded API test asserts unchanged statuses
and full17 logical applicants. Human control reduces automatic harm, not proof that
human or AI decisions are unbiased.

## 18. Tests

Focused fairness/ranking/identity/privacy: **103 passed,1 warning in1.78s**, exit0.
Includes seven direct-field invariances,CV/JD metadata/photo/DOB exclusion,mock score
identity equality,tie/fallback independence,source-path availability,API absence of
demographic outputs,small/missing cohort guards and prose/contact coverage observations.
No live model needed; mock equality is not a measured BGE counterfactual sensitivity.

Offline regression: **149 passed,2 warnings in5.63s**, exit0.
Final full guarded rerun: **697 passed,3 warnings in113.47s (0:01:53)**, exit0.
This rerun followed all final audit/test additions. A reserved-domain synthetic
email fixture initially failed validation; fixed fixture only, not production schema.
Warnings are existing google-genai,Starlette/httpx and deprecatedHTTP422 notices.

## 19. Data / DB Safety

Audit has0model calls/0DB access. Full tests use existing guarded gjob_db_test only,
TEST_DATABASE_URL validation/current_database check and normal test migrations;
credentials remain in child memory with redacted output. Providers/lifecycle mocked.
No DEV access/write,new database,migration,env/config,frontend or production source
change. Existing new-API fixture cleanup and temp fixtures retained.

Read-only integrity comparison:146 preexisting production/ranking input/evidence
files byte-identical, including all app Python sources and prior reports. Four
ground/canonical frozen SHA values match Task14C.1.5/14C.2; predictions unchanged:
904d3081a60824f334abb6424281f705a23bd52b184bd1a3dbe25e5c11d63b8c.
Raw source archive hashes verified. No labels/reasons/raw text/cache deleted or edited.
Only new audit helper,synthetic tests,one report and aggregate JSON produced.

## 20. Limitations

10constructed ranking jobs,100pairs,95CVs,limited reuse,single-reviewer judgments.
Source occupation labels are not validated qualifications; unequal job/grade mixtures.
Every cohort<10 opportunity rows; reused CVs introduce dependence. No representative
production prevalence,live recruiter behavior study,availability SLA telemetry or
governed protected labels. Scores uncalibrated. Literal cue scans do not detect all
PII/proxies or attribute cues to an applicant. Absence of direct PII != fairness.
No counterfactual real embeddings,prestige/location/language causal effects,
equal-opportunity/equalized-odds estimate or fairness certification. Operational
cohorts != protected groups. No legal compliance determination was made.

## 21. Findings

| ID | Severity | Evidence-based finding |
|---|---|---|
| F1 | LOW / verified safeguard | Direct structured-field exclusion,non-sensitive explicit ties,opt-in and human controls pass |
| F2 | MEDIUM | Prose retains potential sensitive/proxy cues; contact auditor is not comprehensive NER/address detection |
| F3 | MEDIUM | Ranked-first plus non-durable precompute/no backfill can cause persistent access-to-ranking disadvantage |
| F4 | MEDIUM / evidence gap | Protected-group outcome disparity unmeasured; occupation cohorts cannot substitute |
| F5 | LOW / residual boundary | Authorized identity display/search and chronological ordering can still have social effects |

No HIGH direct-field/tie/photo/automatic-decision violation demonstrated. This is
not a claim that high risks never occur in arbitrary unseen prose or future code.

## 22. Recommendations for 14C.5 / 14C.6

14C.5: separately authorize robustness cases for sparse/long/short CVs,missing skills,
keyword repetition,prose geography/dates,prestige/language-heavy text,source-path/
legacy/cache states,ties and identity-only invariance. Do not tune/select changes
from this audit; no such real model experiments were run here.

14C.6/product follow-up: consider private cohort/state/duration telemetry and a
bounded recoverable precompute/backfill strategy; surface unavailable/pending clearly
and retain default view/all-applicant review. Seek appropriately governed,explicit,
consented protected-group audit data if outcome disparity is required,never infer it.
Review prose PII boundary with shared production/evaluation rules before any removal.
Any mitigation/policy change needs separate authority; no automatic stripping here.

## 23. Exact Commands Run

```powershell
venv\Scripts\python.exe -m pytest --noconftest tests/test_ranking_fairness_guards.py tests/test_applicant_ranking.py tests/test_cv_identity_contract.py tests/test_matching_text_privacy.py -q --tb=short
venv\Scripts\python.exe -m pytest evaluation/tests -q --tb=short
venv\Scripts\python.exe -m pytest -q --tb=short
venv\Scripts\python.exe -X utf8 -m evaluation.audit_ranking_fairness --source C:/DATN/Datasets/archivecv/Resume/Resume.csv
git diff --check
```

Final source-JD inventory additionally invoked the same audit(root,source,job_source)
with C:/DATN/Datasets/archivejd/job_postings.csv and sockets disabled. Full pytest
runs in a guarded child environment,not DEV fallback; exact credentials not recorded.
Read-only source/header/metadata/hash reviews. JSON produced via apply_patch from
validated safe aggregate output; no new CSV/XLSX or spreadsheet workbook authored.

## 24. Final Status

**PASS WITH LIMITATIONS for the audit.** Intentional direct structured-field use
excluded,production controls intact; free-prose/proxy and availability risks remain.
Protected-group disparity cannot be measured from current data. Do not say
'Semantic-v1 is fair'. Relevant/full regressions and unchanged-input checks pass.

**READY FOR TASK 14C.5**

**RANKING ROBUSTNESS / EDGE CASES**
