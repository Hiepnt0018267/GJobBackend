# Dataset audit

> Statistics only; no resume or job-description text is included.

## Resume.csv

- Rows: 2484
- Unique IDs: 2484
- Eligible: 2483
- Missing text: 1
- Duplicate text groups: 2
- Text length: `{'min': 688, 'median': 5543.0, 'p90': 8618.400000000001, 'p95': 10264.7, 'max': 35217}`

## job_postings.csv

- Rows: 15886
- Unique job IDs: 15886
- Eligible: 15833
- Missing title: 0
- Missing description: 1
- Duplicate description groups: 782
- Near-duplicate candidates: 847
- Description length: `{'min': 6, 'median': 3396.0, 'p90': 6484.0, 'p95': 7477.0, 'max': 20347}`

## Join coverage

| Relation | Covered | Total | Percent |
|---|---:|---:|---:|
| job_to_skills | 15249 | 15886 | 95.99% |
| job_to_industry | 15572 | 15886 | 98.02% |
| job_to_company | 15470 | 15886 | 97.38% |
| company_to_industry | 5953 | 6063 | 98.19% |
| jobs_with_title_and_description | 15885 | 15886 | 99.99% |
| jobs_with_title_description_and_skill_signal | 15248 | 15886 | 95.98% |

## Limitations

- job skill abbreviations have no code dictionary in the supplied files and remain opaque grouping metadata
- near-duplicate JD detection is a deterministic normalized-text candidate check, not semantic deduplication
- no CV-to-JD ground-truth labels exist in the raw inputs
