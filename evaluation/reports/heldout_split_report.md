# Grouped heldout split report

Input SHA-256: 28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8
Seed: 42
Grouping: typed CV/JD connected components; no component broken.

```json
{
  "component_count": 162,
  "component_size_distribution": {
    "1": 129,
    "2": 19,
    "5": 3,
    "3": 6,
    "4": 5
  },
  "largest_component": 5,
  "top10": [
    {
      "component_id": "component_0d0ccaf6173e7ebd",
      "pairs": 5
    },
    {
      "component_id": "component_16a58d4675a93288",
      "pairs": 5
    },
    {
      "component_id": "component_ae0d9851a8661f65",
      "pairs": 5
    },
    {
      "component_id": "component_2ee0acd99dbeedc1",
      "pairs": 4
    },
    {
      "component_id": "component_372e6b87a128a5f8",
      "pairs": 4
    },
    {
      "component_id": "component_5b4b78902c94a3ec",
      "pairs": 4
    },
    {
      "component_id": "component_99e6bef2fa03c0e9",
      "pairs": 4
    },
    {
      "component_id": "component_bcf836228153aa13",
      "pairs": 4
    },
    {
      "component_id": "component_18ba871ecdb02550",
      "pairs": 3
    },
    {
      "component_id": "component_211ba8de6fa4d9e6",
      "pairs": 3
    }
  ],
  "calibration": {
    "pairs": 132,
    "positive": 70,
    "negative": 62,
    "candidate_groups": {
      "EASY_NEGATIVE_CANDIDATE": 18,
      "HARD_NEGATIVE_CANDIDATE": 60,
      "POSITIVE_CANDIDATE": 54
    },
    "hard_human_negative": 30,
    "easy_human_negative": 18,
    "unique_cvs": 114,
    "unique_jobs": 92
  },
  "test": {
    "pairs": 88,
    "positive": 46,
    "negative": 42,
    "candidate_groups": {
      "POSITIVE_CANDIDATE": 36,
      "HARD_NEGATIVE_CANDIDATE": 40,
      "EASY_NEGATIVE_CANDIDATE": 12
    },
    "hard_human_negative": 22,
    "easy_human_negative": 12,
    "unique_cvs": 88,
    "unique_jobs": 88
  },
  "leakage": {
    "cv_id": 0,
    "job_id": 0,
    "pair_id": 0
  },
  "calibration_fraction": 0.6,
  "objective": 76
}
```

Manifest SHA-256: 8e2119a04aaa434b5d4a0feee19fb860feb06ab33a97b01b8d6422fa56da3bcf

Counts/labels/groups were used for stratification only; no scores or outcomes used.
This is a retrospective partition; baseline IDF is frozen and transductive. See HELDOUT_PROTOCOL.md.
