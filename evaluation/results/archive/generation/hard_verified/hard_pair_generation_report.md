# Hard pair generation report

## Root cause of the old set

The old sampler narrowed jobs to 140 before retrieval, treated moderate generic overlap as hard, allowed arbitrary fallback jobs, and grouped titles by sorted first token.

## Summary

```json
{
  "seed": 42,
  "target": 220,
  "total_pairs": 220,
  "quota_shortfall": {
    "POSITIVE_CANDIDATE": 0,
    "HARD_NEGATIVE_CANDIDATE": 0,
    "EASY_NEGATIVE_CANDIDATE": 0
  },
  "candidate_type_counts": {
    "POSITIVE_CANDIDATE": 90,
    "HARD_NEGATIVE_CANDIDATE": 100,
    "EASY_NEGATIVE_CANDIDATE": 30
  },
  "old_total": 400,
  "old_reviewed": 78,
  "old_unreviewed": 322,
  "old_selected": 11,
  "new_generated": 209,
  "new_candidate_type_counts": {
    "POSITIVE_CANDIDATE": 89,
    "HARD_NEGATIVE_CANDIDATE": 100,
    "EASY_NEGATIVE_CANDIDATE": 20
  },
  "final_reviewed": 10,
  "final_unreviewed": 210,
  "selection_status_counts": {
    "PILOT_ONLY": 68,
    "INCLUDED_MAIN_BENCHMARK": 11,
    "ARCHIVE_REDUNDANT": 150,
    "ARCHIVE_TRIVIAL": 169,
    "ARCHIVE_NEAR_DUPLICATE": 2
  },
  "unique_cvs": 202,
  "unique_jobs": 180,
  "max_pairs_per_cv": 3,
  "max_pairs_per_jd": 4,
  "category_distribution": {
    "BANKING": 12,
    "FITNESS": 8,
    "ACCOUNTANT": 9,
    "SALES": 8,
    "ARTS": 9,
    "DESIGNER": 10,
    "AUTOMOBILE": 7,
    "ENGINEERING": 9,
    "CONSULTANT": 11,
    "CONSTRUCTION": 15,
    "CHEF": 7,
    "APPAREL": 8,
    "TEACHER": 7,
    "ADVOCATE": 13,
    "BPO": 7,
    "HR": 7,
    "PUBLIC-RELATIONS": 10,
    "FINANCE": 7,
    "INFORMATION-TECHNOLOGY": 10,
    "BUSINESS-DEVELOPMENT": 14,
    "DIGITAL-MEDIA": 8,
    "AVIATION": 8,
    "HEALTHCARE": 9,
    "AGRICULTURE": 7
  },
  "domain_distribution": {
    "marketing": 24,
    "finance": 21,
    "design": 9,
    "operations": 8,
    "sales": 30,
    "accounting": 19,
    "software": 19,
    "hospitality": 12,
    "healthcare": 12,
    "support": 5,
    "education": 14,
    "engineering": 9,
    "hr": 22,
    "unknown": 7,
    "legal": 3,
    "science": 1,
    "fitness": 1,
    "construction": 3,
    "aviation": 1
  },
  "title_family_coverage": {
    "unknown": 75,
    "credit": 10,
    "marketing": 18,
    "infrastructure": 22,
    "investment": 10,
    "backend": 2,
    "data": 11,
    "clinical": 17,
    "sales": 17,
    "accounting": 9,
    "laboratory": 5,
    "mobile": 4,
    "recruiting": 10,
    "teaching": 6,
    "electrical": 3,
    "frontend": 1
  },
  "industry_coverage": {
    "43": 18,
    "41": 14,
    "80": 9,
    "100": 9,
    "96": 15,
    "87": 1,
    "4": 13,
    "6": 19,
    "92": 5,
    "44": 4,
    "104": 8,
    "124": 2,
    "14": 16,
    "42": 3,
    "31": 12,
    "3231": 1,
    "98": 3,
    "27": 12,
    "34": 6,
    "116": 2,
    "112": 4,
    "145": 1,
    "137": 3,
    "47": 5,
    "17": 4,
    "70": 1,
    "97": 1,
    "9": 1,
    "45": 4,
    "46": 2,
    "106": 1,
    "75": 7,
    "8": 3,
    "32": 6,
    "15": 5,
    "69": 5,
    "3222": 1,
    "12": 3,
    "76": 1,
    "3": 1,
    "7": 1,
    "88": 1,
    "83": 1,
    "3224": 1,
    "48": 3,
    "67": 3,
    "118": 4,
    "135": 2,
    "68": 4,
    "78": 1,
    "1": 2,
    "52": 1,
    "71": 1,
    "99": 2,
    "139": 2,
    "23": 1,
    "1359": 1,
    "86": 2,
    "147": 1,
    "54": 4,
    "55": 3,
    "133": 2,
    "25": 1,
    "93": 1,
    "117": 4,
    "19": 2,
    "20": 1,
    "26": 1,
    "90": 1,
    "95": 1,
    "56": 1,
    "59": 1,
    "16": 1,
    "84": 1
  },
  "duplicate_pairs": 0,
  "near_duplicate_jds_excluded": 159,
  "hardness": {
    "POSITIVE_CANDIDATE": {
      "count": 90,
      "median_lexical_overlap": 0.118864,
      "median_title_overlap": 1.0,
      "same_domain_rate": 1.0
    },
    "HARD_NEGATIVE_CANDIDATE": {
      "count": 100,
      "median_lexical_overlap": 0.099544,
      "median_title_overlap": 0.6093375000000001,
      "same_domain_rate": 1.0
    },
    "EASY_NEGATIVE_CANDIDATE": {
      "count": 30,
      "median_lexical_overlap": 0.037812,
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
    "No skill_abr semantics are invented.",
    "TOO_TRIVIAL/ARCHIVE_TRIVIAL means insufficient mining evidence, not a human judgment of irrelevance.",
    "Hardness diagnostics verify lexical separation only, not benchmark accuracy."
  ],
  "archive_files": [
    "evaluation\\data\\archive\\evaluation_pairs_draft_old_400.csv",
    "evaluation\\data\\archive\\evaluation_labeling_progress_old.csv"
  ],
  "sha256": "248f170be40249ba1626bf5ab2dea56ca921fd67b734fdbc9b38229cd74c69a4"
}
```

## Candidate examples (not ground truth)

### POSITIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 29915354 / marketing | 3699087542: Videographer / marketing | 0.119512 |  |
| 17584743 / marketing | 3693045289: Marketing Coordinator / marketing | 0.118445 |  |
| 54308684 / sales | 3691794313: Sales & Customer Support Specialist / sales | 0.10747 |  |
| 20748929 / sales | 3694122503: Sr Customer Success Manager, Strategic Account Services / sales | 0.105197 |  |
| 11183737 / hospitality | 3699085616: Front of the House Manager / hospitality | 0.110765 |  |

### HARD_NEGATIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 98379112 / finance | 3697390594: Financial Services Manager / finance | 0.154183 | specialization_difference |
| 13014900 / design | 3694101268: Designer / Intern / design | 0.137687 | specialization_difference |
| 34304175 / operations | 3698002100: Data Center Logistics Associate L3 / operations | 0.08638 | specialization_difference |
| 35554162 / accounting | 3700504344: Accounting Manager / accounting | 0.102046 | specialization_difference |
| 12374933 / software | 3701315753: Information Technology Engineer / software | 0.104078 | specialization_difference |
| 20356750 / finance | 3693048957: Acquisitions/Investment Associate – Industrial and Outdoor Storage (IOS) / finance | 0.141942 | specialization_difference |
| 26790545 / design | 3693056244: UX/UI Designer - Data Intelligence / design | 0.153004 | specialization_difference |
| 27903191 / marketing | 3487275706: Director of Sales & Marketing / marketing | 0.082422 | specialization_difference |
| 10830646 / education | 3697386941: Instructor (Math & Science) / education | 0.101899 | specialization_difference |
| 25867805 / accounting | 3693071651: Accountant (Bilingual Chinese) / accounting | 0.110366 | specialization_difference |

### EASY_NEGATIVE_CANDIDATE

| CV ID / family | JD / family | Lexical | Mismatch cues |
|---|---|---:|---|
| 12413512 / education | 3693058261: Member Service Specialist (Jacksonville) / support | 0.037296 |  |
| 34544955 / construction | 3697353823: Lead/Senior Tech - CA / sales | 0.039475 |  |
| 14176254 / healthcare | 3697356797: Support Coordinator- Adult Services / unknown | 0.039789 |  |
| 23577836 / healthcare | 3693057078: CV Underwriting Assistant / finance | 0.038103 | specialization_difference |
| 12695537 / science | 3693597703: Senior Associate, Paid Media / marketing | 0.031113 | specialization_difference |
