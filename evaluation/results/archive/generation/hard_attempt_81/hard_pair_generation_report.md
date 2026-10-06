# Hard pair generation report

## Root cause of the old set

The old sampler narrowed jobs to 140 before retrieval, treated moderate generic overlap as hard, allowed arbitrary fallback jobs, and grouped titles by sorted first token.

## Summary

```json
{
  "seed": 42,
  "target": 220,
  "total_pairs": 81,
  "quota_shortfall": {
    "POSITIVE_CANDIDATE": 60,
    "HARD_NEGATIVE_CANDIDATE": 79,
    "EASY_NEGATIVE_CANDIDATE": 0
  },
  "candidate_type_counts": {
    "POSITIVE_CANDIDATE": 30,
    "HARD_NEGATIVE_CANDIDATE": 21,
    "EASY_NEGATIVE_CANDIDATE": 30
  },
  "old_total": 400,
  "old_reviewed": 78,
  "old_selected": 10,
  "new_generated": 71,
  "final_reviewed": 10,
  "selection_status_counts": {
    "PILOT_ONLY": 68,
    "INCLUDED_MAIN_BENCHMARK": 10,
    "ARCHIVE_REDUNDANT": 240,
    "ARCHIVE_TRIVIAL": 80,
    "ARCHIVE_NEAR_DUPLICATE": 2
  },
  "unique_cvs": 51,
  "unique_jobs": 74,
  "max_pairs_per_cv": 4,
  "max_pairs_per_jd": 3,
  "category_distribution": {
    "HEALTHCARE": 1,
    "CONSULTANT": 6,
    "FITNESS": 2,
    "APPAREL": 1,
    "ACCOUNTANT": 10,
    "AUTOMOBILE": 5,
    "BANKING": 2,
    "BUSINESS-DEVELOPMENT": 1,
    "AVIATION": 4,
    "ADVOCATE": 6,
    "ENGINEERING": 1,
    "CONSTRUCTION": 4,
    "CHEF": 3,
    "DIGITAL-MEDIA": 1,
    "FINANCE": 4,
    "PUBLIC-RELATIONS": 2,
    "INFORMATION-TECHNOLOGY": 4,
    "SALES": 3,
    "AGRICULTURE": 1,
    "BPO": 6,
    "TEACHER": 1,
    "ARTS": 3,
    "HR": 5,
    "DESIGNER": 5
  },
  "domain_distribution": {
    "education": 8,
    "accounting": 19,
    "hospitality": 3,
    "finance": 5,
    "engineering": 1,
    "software": 14,
    "marketing": 2,
    "operations": 3,
    "sales": 2,
    "healthcare": 5,
    "legal": 5,
    "unknown": 5,
    "science": 1,
    "hr": 5,
    "support": 1,
    "design": 2
  },
  "title_family_coverage": {
    "teaching": 4,
    "mobile": 2,
    "sales": 2,
    "credit": 2,
    "unknown": 36,
    "accounting": 13,
    "data": 3,
    "infrastructure": 6,
    "marketing": 2,
    "laboratory": 3,
    "frontend": 3,
    "investment": 2,
    "backend": 1,
    "clinical": 2
  },
  "industry_coverage": {
    "67": 4,
    "68": 7,
    "69": 4,
    "27": 4,
    "34": 2,
    "6": 10,
    "31": 2,
    "44": 5,
    "7": 1,
    "96": 9,
    "41": 2,
    "54": 1,
    "80": 2,
    "48": 5,
    "51": 2,
    "12": 2,
    "76": 1,
    "9": 3,
    "1": 2,
    "70": 1,
    "121": 2,
    "43": 2,
    "46": 1,
    "92": 3,
    "47": 3,
    "104": 5,
    "37": 1,
    "14": 2,
    "75": 2,
    "52": 1,
    "3": 1,
    "91": 1,
    "50": 1,
    "139": 1,
    "126": 1,
    "127": 1,
    "98": 1,
    "10": 1,
    "32": 1,
    "118": 1,
    "4": 1
  },
  "duplicate_pairs": 0,
  "near_duplicate_jds_excluded": 159,
  "hardness": {
    "POSITIVE_CANDIDATE": {
      "count": 30,
      "median_lexical_overlap": 0.17490050000000001,
      "median_title_overlap": 1.0,
      "same_domain_rate": 1.0
    },
    "HARD_NEGATIVE_CANDIDATE": {
      "count": 21,
      "median_lexical_overlap": 0.129522,
      "median_title_overlap": 0.477515,
      "same_domain_rate": 1.0
    },
    "EASY_NEGATIVE_CANDIDATE": {
      "count": 30,
      "median_lexical_overlap": 0.057855500000000004,
      "median_title_overlap": 0.0,
      "same_domain_rate": 0.0
    }
  },
  "old_hardness": {
    "POSITIVE_CANDIDATE": {
      "count": 160,
      "median_lexical_overlap": 0.0467205,
      "median_title_overlap": 0.08808099999999999,
      "same_domain_rate": 0.13125
    },
    "HARD_NEGATIVE_CANDIDATE": {
      "count": 160,
      "median_lexical_overlap": 0.036552,
      "median_title_overlap": 0.0,
      "same_domain_rate": 0.0625
    },
    "EASY_NEGATIVE_CANDIDATE": {
      "count": 80,
      "median_lexical_overlap": 0.017274499999999998,
      "median_title_overlap": 0.0,
      "same_domain_rate": 0.025
    }
  },
  "limitations": [
    "Candidate types are not ground truth.",
    "Role/specialization vocabularies are lexical cues, not formal taxonomies.",
    "Seniority from CV introduction can be missing or ambiguous.",
    "No skill_abr semantics are invented."
  ],
  "archive_files": [
    "evaluation\\data\\archive\\evaluation_pairs_draft_old_400.csv",
    "evaluation\\data\\archive\\evaluation_labeling_progress_old.csv"
  ],
  "sha256": "adb98b634e050f957fbaaa3c4a03df86ece8b8eaed94b0784bf4cb56ac5432f8"
}
```

## Candidate examples (not ground truth)

### POSITIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 18725071 / education | 3693043732: Special Education Teacher / education | 0.174543 |  |
| 18725071 / education | 3693048951: Special Education Teacher → $2500 Sign-on Bonus! / education | 0.181582 |  |
| 16924102 / hospitality | 3693598847: Director of Event Operations / hospitality | 0.185424 |  |
| 35172961 / engineering | 3701321964: Cleanroom Process Technician / engineering | 0.174542 |  |
| 28969385 / accounting | 3694100639: Accounts Payable Specialist / accounting | 0.180829 |  |

### HARD_NEGATIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 28969385 / accounting | 3693071651: Accountant (Bilingual Chinese) / accounting | 0.142495 | specialization_difference |
| 20356750 / finance | 3693048957: Acquisitions/Investment Associate – Industrial and Outdoor Storage (IOS) / finance | 0.141942 | specialization_difference |
| 29051656 / software | 3697381432: Oracle Database Administrator (7121) / software | 0.266005 | specialization_difference |
| 39441617 / software | 3697395824: Network Engineer III / software | 0.153231 | specialization_difference |
| 39441617 / software | 3701323844: IT Infrastructure Engineer / software | 0.129522 | specialization_difference |
| 12413512 / education | 3697386941: Instructor (Math & Science) / education | 0.123878 | specialization_difference |
| 18368613 / sales | 3694105162: Vice President of Sales / sales | 0.128822 | specialization_difference |
| 29051656 / software | 3693046734: Database Developer / software | 0.134082 | specialization_difference |
| 41152404 / software | 3693046079: AEM Developer / software | 0.125142 | specialization_difference |
| 70892619 / education | 3697386941: Instructor (Math & Science) / education | 0.123293 | specialization_difference |

### EASY_NEGATIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 23933031 / support | 3693586403: IT Auditor / accounting | 0.063702 |  |
| 34317538 / design | 3699415350: Proposal Manager - Infrastructure Business Development / operations | 0.06953 |  |
| 24285142 / design | 3693587388: Boutique Manager / sales | 0.035599 |  |
| 29221006 / hr | 3697397763: Assistant Store Manager (ASM) / healthcare | 0.083196 |  |
| 27496514 / legal | 3701158169: Manager, Project Financials / unknown | 0.063621 |  |
