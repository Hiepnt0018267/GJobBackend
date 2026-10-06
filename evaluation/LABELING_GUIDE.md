# CV ↔ JD Human Labeling Guide

This guide is for human review of `evaluation_pairs_draft.csv`. The candidate type and
`sampling_score` only help construct a diverse review queue; neither is ground truth.

## Labels

- `1` — Relevant: the CV is meaningfully suitable for the JD when role/job family,
  core skills, responsibilities, experience and truly required qualifications are
  considered together.
- `0` — Not relevant: there is a material role mismatch, missing core capability,
  unrelated background, or a genuinely essential qualification mismatch.
- Unsure: leave `label` blank while resolving uncertainty. `UNSURE` is not a valid
  final label and the validator will reject it.

Always write a concise, evidence-based `label_reason`. `review_notes` is optional.

## Holistic rules

- Experience is one dimension, not a hard formula. Four years against a five-year
  request does not automatically mean label `0`.
- Degree or certification differences matter only when the JD makes them essential.
- Treat lexical overlap as evidence to inspect, not proof of relevance.
- Judge the work itself; do not use salary, location, gender, company popularity,
  benefits or company size as core relevance evidence.
- Do not infer the label from `cv_category`, industry metadata, `pair_type`, skill
  codes or `sampling_score`.

## Workflow

1. Generate the draft with a recorded seed.
2. Read both text previews and use `cv_id`, `job_id`, and source-row columns to locate
   the source record if the preview is insufficient.
3. Fill `label` and `label_reason`; optionally add `review_notes`.
4. Save a separate labeled copy under `evaluation/data/labels/`.
5. Run the strict validator. Only a fully labeled 0/1 file becomes the final dataset.

For higher-confidence research, use two independent reviewers and adjudicate
disagreements before validation.

