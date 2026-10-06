# Frozen offline baseline definition

Task 14B.3; frozen before the real 220-pair run. No post-run weight, tokenization,
stopword or default-threshold changes are allowed under this identifier.

## Source decision

Production already has `BaselineMatchingEngine.match`: exact structured-skill
coverage, score 0–100, weight 1, two-decimal rounding; no JD skills raises a controlled
insufficient-signal error. It is useful for structured GJob records but cannot be
fairly applied to all raw benchmark rows without inventing/extracting structured skills.
The source has 35 opaque skill_abr codes without a trustworthy dictionary.
No production code or algorithm is changed or renamed.

This separate evaluation reference is explicitly `baseline-v1-offline-lexical`.
It is **not** a measurement of the production structured-skill baseline. Output folder
`baseline-v1` is the task convention, not an assertion that these algorithms are identical.

## Inputs and preprocessing

Same referenced Resume_str, JD title, description and skills_desc as semantic's raw
source adapter. No CV Category, labels/reasons, sampling fields, semantic predictions,
salary, location or company metadata enter scoring. JD text concatenates title,
description and skills_desc; semantic section headings are not lexical evidence.

Unicode NFKC + casefold; strip email/URL spans; deterministic punctuation tokenization
preserving literal technology punctuation (e.g. C++, C#; .NET normalizes to net). Filter a fixed local
English function-word/boilerplate stopword set. No synonyms, stemming, role dictionary,
skill_abr meanings or inferred skill/seniority. Incidental names/organizations in
source prose may remain; raw text/token vocabulary is not persisted in reports.

## Fixed formula

`score = 0.7 * TF-IDF lexical cosine + 0.3 * JD-title token coverage`

TF = `1 + ln(count)`; IDF = `ln((1+N)/(1+df)) + 1`, fit on all unique referenced
CV/JD entities, in sorted order, without human labels. Cosine is a traditional lexical
statistic, not an embedding or learned semantic model. Title coverage is intersection
of unique normalized title tokens with CV tokens divided by title token count.
Empty vectors/title return component 0. Score range [0,1].

Weight rationale: full-document lexical evidence dominates; title coverage is a small
interpretable role anchor. Weights are hand-selected once, not fit to labels.
Default evaluation threshold = 0.5: halfway on the normalized composite range, not
production calibration. Threshold exploration uses the same metrics/tie policy as
semantic; in-sample best F1 is reported separately and never replaces the frozen default.

No separate skill or seniority scoring: source cannot support those reliably across
all categories without a new parser/dictionary. All 220 pairs must receive a score;
unknown structured signals are not silently skipped.

## Evaluation limits

Raw-text matching only; not production CV extraction quality. Corpus-fitted IDF is
transductive and must be refit/identified for another corpus. The intentionally simple
baseline may be weak. Same 220 difficulty-focused, single-reviewer labels are not a
held-out calibration or representative production prevalence. No hybrid or production
algorithm selection is implemented.
