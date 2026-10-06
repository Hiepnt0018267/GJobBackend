from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from evaluation.common import (
    EvaluationConfig, EvaluationDataError, PAIR_TYPES, REQUIRED_COLUMNS,
    exact_text_hash, iter_csv, make_pair_id, normalize_identifier, normalize_key, normalize_whitespace,
    resolve_dataset_files, stable_rank, tokenize, write_csv,
)


DRAFT_FIELDS = [
    "pair_id", "cv_id", "job_id", "pair_type", "cv_category", "job_title",
    "job_industry", "sampling_score", "cv_text_preview", "job_text_preview",
    "cv_skills_hint", "job_skills_hint", "cv_source_row", "job_source_row",
    "label", "label_reason", "review_notes",
]


@dataclass(frozen=True)
class ResumeRecord:
    cv_id: str
    category: str
    text: str
    source_row: int


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    title: str
    description: str
    skills_description: str
    experience_level: str
    source_row: int
    skill_codes: tuple[str, ...]
    industry_ids: tuple[str, ...]

    @property
    def semantic_text(self) -> str:
        # Deliberately mirrors canonical matching signals and excludes salary,
        # location, company popularity, benefits and contact information.
        return normalize_whitespace(
            " ".join((self.title, self.description, self.skills_description, self.experience_level))
        )


def _balanced_sample(records: list[object], group_getter, id_getter, size: int, seed: int) -> list[object]:
    groups: dict[str, list[object]] = defaultdict(list)
    for record in records:
        groups[group_getter(record)].append(record)
    for key, items in groups.items():
        items.sort(key=lambda item: (stable_rank(seed, key, id_getter(item)), id_getter(item)))
    group_keys = sorted(groups, key=lambda key: stable_rank(seed, "group", key))
    selected: list[object] = []
    offset = 0
    while len(selected) < size:
        added = False
        for key in group_keys:
            if offset < len(groups[key]):
                selected.append(groups[key][offset])
                added = True
                if len(selected) == size:
                    break
        if not added:
            break
        offset += 1
    return selected


def _load_resumes(path: Path, config: EvaluationConfig) -> tuple[list[ResumeRecord], dict[str, int]]:
    records: list[ResumeRecord] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    stats = Counter()
    for source_row, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        cv_id = normalize_identifier(row["ID"])
        category = normalize_whitespace(row["Category"])
        text = normalize_whitespace(row["Resume_str"])
        if not cv_id or not category or len(text) < config.minimum_cv_chars:
            stats["ineligible"] += 1
            continue
        digest = exact_text_hash(text)
        if cv_id in seen_ids or (digest and digest in seen_text):
            stats["duplicate_skipped"] += 1
            continue
        seen_ids.add(cv_id)
        if digest:
            seen_text.add(digest)
        records.append(ResumeRecord(cv_id, category, text, source_row))
    selected = _balanced_sample(
        records, lambda record: normalize_key(record.category), lambda record: record.cv_id,
        config.cv_sample_size, config.seed,
    )
    stats["eligible_unique"] = len(records)
    stats["selected"] = len(selected)
    return list(selected), dict(stats)


def _load_relation(path: Path, key: str, value: str) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for _, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        item_key = normalize_identifier(row.get(key))
        item_value = normalize_whitespace(row.get(value))
        if item_key and item_value:
            mapping[item_key].add(item_value)
    return {key_value: tuple(sorted(values)) for key_value, values in mapping.items()}


def _job_group(record: JobRecord) -> str:
    title_tokens = sorted(tokenize(record.title))
    if title_tokens:
        return title_tokens[0]
    if record.industry_ids:
        return f"industry:{record.industry_ids[0]}"
    return "other"


def _load_jobs(files: dict[str, Path], config: EvaluationConfig) -> tuple[list[JobRecord], dict[str, int]]:
    skill_codes = _load_relation(files["job_skills.csv"], "job_id", "skill_abr")
    industry_ids = _load_relation(files["job_industries.csv"], "job_id", "industry_id")
    records: list[JobRecord] = []
    seen_ids: set[str] = set()
    seen_descriptions: set[str] = set()
    stats = Counter()
    path = files["job_postings.csv"]
    for source_row, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        job_id = normalize_identifier(row["job_id"])
        title = normalize_whitespace(row["title"])
        description = normalize_whitespace(row["description"])
        if not job_id or not title or len(description) < config.minimum_job_description_chars:
            stats["ineligible"] += 1
            continue
        digest = exact_text_hash(description)
        if job_id in seen_ids or (digest and digest in seen_descriptions):
            stats["duplicate_skipped"] += 1
            continue
        seen_ids.add(job_id)
        if digest:
            seen_descriptions.add(digest)
        records.append(JobRecord(
            job_id=job_id, title=title, description=description,
            skills_description=normalize_whitespace(row.get("skills_desc")),
            experience_level=normalize_whitespace(row.get("formatted_experience_level")),
            source_row=source_row, skill_codes=skill_codes.get(job_id, ()),
            industry_ids=industry_ids.get(job_id, ()),
        ))
    selected = _balanced_sample(
        records, _job_group, lambda record: record.job_id, config.job_sample_size, config.seed
    )
    stats["eligible_unique"] = len(records)
    stats["selected"] = len(selected)
    return list(selected), dict(stats)


class CandidateRetriever:
    def __init__(self, jobs: list[JobRecord], seed: int, pool_limit: int):
        self.jobs = {job.job_id: job for job in jobs}
        self.seed = seed
        self.pool_limit = pool_limit
        self.job_tokens = {job.job_id: tokenize(job.semantic_text) for job in jobs}
        self.title_tokens = {job.job_id: tokenize(job.title) for job in jobs}
        self.index: dict[str, set[str]] = defaultdict(set)
        for job_id, tokens in self.job_tokens.items():
            for token in tokens:
                self.index[token].add(job_id)
        self.stable_jobs = sorted(self.jobs, key=lambda job_id: stable_rank(seed, "job", job_id))

    def score(self, resume: ResumeRecord, job_id: str) -> float:
        cv_tokens = tokenize(f"{resume.category} {resume.text}")
        category_tokens = tokenize(resume.category.replace("-", " "))
        job_tokens = self.job_tokens[job_id]
        title_tokens = self.title_tokens[job_id]
        title_overlap = len(cv_tokens & title_tokens) / max(1, len(title_tokens))
        category_overlap = len(category_tokens & title_tokens) / max(1, len(category_tokens))
        body_overlap = len(cv_tokens & job_tokens) / max(1, min(40, len(job_tokens)))
        return round(min(1.0, 0.45 * title_overlap + 0.35 * category_overlap + 0.20 * body_overlap), 6)

    def ranked(self, resume: ResumeRecord, pair_type: str, usage: Counter[str]) -> list[tuple[str, float]]:
        cv_tokens = tokenize(f"{resume.category} {resume.text}")
        informative = sorted(
            (token for token in cv_tokens if token in self.index),
            key=lambda token: (len(self.index[token]), stable_rank(self.seed, resume.cv_id, token)),
        )[:16]
        related: set[str] = set()
        for token in informative:
            related.update(self.index[token])
            if len(related) >= self.pool_limit:
                break
        related_ordered = sorted(related, key=lambda job_id: stable_rank(self.seed, resume.cv_id, job_id))[:self.pool_limit]
        scored = [(job_id, self.score(resume, job_id)) for job_id in related_ordered]

        if pair_type == "POSITIVE_CANDIDATE":
            candidates = sorted(scored, key=lambda item: (-item[1], usage[item[0]], stable_rank(self.seed, "p", resume.cv_id, item[0])))
        elif pair_type == "HARD_NEGATIVE_CANDIDATE":
            # Related, partial-overlap cases are intentionally preferred. This is
            # only review prioritization; the human label remains blank.
            candidates = sorted(
                (item for item in scored if item[1] > 0),
                key=lambda item: (usage[item[0]], abs(item[1] - 0.18), stable_rank(self.seed, "h", resume.cv_id, item[0])),
            )
        else:
            related_ids = set(related_ordered)
            bounded = [job_id for job_id in self.stable_jobs if job_id not in related_ids][:self.pool_limit]
            candidates = sorted(
                ((job_id, self.score(resume, job_id)) for job_id in bounded),
                key=lambda item: (usage[item[0]], item[1], stable_rank(self.seed, "e", resume.cv_id, item[0])),
            )

        if len(candidates) < self.pool_limit:
            existing = {job_id for job_id, _ in candidates}
            fallback = [job_id for job_id in self.stable_jobs if job_id not in existing][:self.pool_limit - len(candidates)]
            candidates.extend((job_id, self.score(resume, job_id)) for job_id in fallback)
        return candidates


def _pair_schedule(target: int) -> list[str]:
    desired = {
        "POSITIVE_CANDIDATE": round(target * 0.4),
        "HARD_NEGATIVE_CANDIDATE": round(target * 0.4),
    }
    desired["EASY_NEGATIVE_CANDIDATE"] = target - sum(desired.values())
    schedule: list[str] = []
    pattern = ("POSITIVE_CANDIDATE", "HARD_NEGATIVE_CANDIDATE", "POSITIVE_CANDIDATE", "HARD_NEGATIVE_CANDIDATE", "EASY_NEGATIVE_CANDIDATE")
    while len(schedule) < target:
        for pair_type in pattern:
            if desired[pair_type] > 0:
                schedule.append(pair_type)
                desired[pair_type] -= 1
                if len(schedule) == target:
                    break
    return schedule


def generate_pairs(data_dir: str | Path, config: EvaluationConfig | None = None) -> tuple[list[dict[str, object]], dict[str, object]]:
    config = config or EvaluationConfig()
    files = resolve_dataset_files(data_dir)
    resumes, resume_stats = _load_resumes(files["Resume.csv"], config)
    jobs, job_stats = _load_jobs(files, config)
    if not resumes or not jobs:
        raise EvaluationDataError("No eligible CVs or jobs remain after filtering.")
    if config.pair_target > len(resumes) * config.max_pairs_per_cv:
        raise EvaluationDataError("pair_target exceeds max_pairs_per_cv capacity for the sampled CVs.")
    if config.pair_target > len(jobs) * config.max_pairs_per_job:
        raise EvaluationDataError("pair_target exceeds max_pairs_per_job capacity for the sampled jobs.")

    retriever = CandidateRetriever(jobs, config.seed, config.candidate_pool_limit)
    jobs_by_id = {job.job_id: job for job in jobs}
    cv_usage: Counter[str] = Counter()
    job_usage: Counter[str] = Counter()
    used_pairs: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    cv_cursor = 0
    ordered_cvs = sorted(resumes, key=lambda cv: stable_rank(config.seed, "cv", cv.cv_id))

    for pair_type in _pair_schedule(config.pair_target):
        chosen: tuple[ResumeRecord, str, float] | None = None
        for offset in range(len(ordered_cvs)):
            resume = ordered_cvs[(cv_cursor + offset) % len(ordered_cvs)]
            if cv_usage[resume.cv_id] >= config.max_pairs_per_cv:
                continue
            for job_id, score in retriever.ranked(resume, pair_type, job_usage):
                if job_usage[job_id] >= config.max_pairs_per_job or (resume.cv_id, job_id) in used_pairs:
                    continue
                chosen = resume, job_id, score
                cv_cursor = (cv_cursor + offset + 1) % len(ordered_cvs)
                break
            if chosen:
                break
        if not chosen:
            raise EvaluationDataError(f"Could not satisfy pair constraints after {len(rows)} pairs.")
        resume, job_id, score = chosen
        job = jobs_by_id[job_id]
        shared_terms = sorted(tokenize(resume.text) & tokenize(job.semantic_text))[:20]
        rows.append({
            "pair_id": make_pair_id(resume.cv_id, job.job_id), "cv_id": resume.cv_id,
            "job_id": job.job_id, "pair_type": pair_type, "cv_category": resume.category,
            "job_title": job.title, "job_industry": "|".join(job.industry_ids),
            "sampling_score": f"{score:.6f}",
            "cv_text_preview": resume.text[:config.cv_preview_chars],
            "job_text_preview": job.semantic_text[:config.job_preview_chars],
            "cv_skills_hint": "|".join(shared_terms),
            "job_skills_hint": "|".join(job.skill_codes),
            "cv_source_row": resume.source_row, "job_source_row": job.source_row,
            "label": "", "label_reason": "", "review_notes": "",
        })
        used_pairs.add((resume.cv_id, job.job_id))
        cv_usage[resume.cv_id] += 1
        job_usage[job.job_id] += 1

    type_counts = Counter(str(row["pair_type"]) for row in rows)
    category_counts = Counter(str(row["cv_category"]) for row in rows)
    score_groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        score_groups[str(row["pair_type"])].append(float(str(row["sampling_score"])))
    report: dict[str, object] = {
        "seed": config.seed, "pair_target": config.pair_target, "pairs_generated": len(rows),
        "sample": {"cv": resume_stats, "job": job_stats},
        "unique_cvs": len(cv_usage), "unique_jobs": len(job_usage),
        "pair_type_distribution": dict(type_counts),
        "cv_category_distribution": dict(category_counts.most_common()),
        "selected_job_domain_distribution": dict(Counter(_job_group(job) for job in jobs).most_common()),
        "selected_experience_level_distribution": dict(
            Counter(job.experience_level or "MISSING" for job in jobs).most_common()
        ),
        "sampling_score_distribution": {
            pair_type: {
                "min": min(scores), "median": statistics.median(scores),
                "mean": round(statistics.mean(scores), 6), "max": max(scores),
            }
            for pair_type, scores in score_groups.items()
        },
        "max_pairs_observed": {"per_cv": max(cv_usage.values()), "per_job": max(job_usage.values())},
        "constraints": {"max_pairs_per_cv": config.max_pairs_per_cv, "max_pairs_per_job": config.max_pairs_per_job},
        "ground_truth_status": "unlabeled; sampling_score and pair_type are candidate-generation metadata only",
        "skill_code_note": "skill_abr values are retained as opaque hints because no mapping dictionary was supplied",
    }
    return rows, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an unlabeled, review-ready CV/JD candidate-pair draft.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", default="evaluation/data/derived/evaluation_pairs_draft.csv")
    parser.add_argument("--report", default="evaluation/reports/pair_distribution.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cv-sample-size", type=int, default=120)
    parser.add_argument("--job-sample-size", type=int, default=140)
    parser.add_argument("--pair-target", type=int, default=400)
    parser.add_argument("--max-pairs-per-cv", type=int, default=4)
    parser.add_argument("--max-pairs-per-job", type=int, default=4)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EvaluationConfig(seed=args.seed, cv_sample_size=args.cv_sample_size,
                              job_sample_size=args.job_sample_size, pair_target=args.pair_target,
                              max_pairs_per_cv=args.max_pairs_per_cv,
                              max_pairs_per_job=args.max_pairs_per_job)
    try:
        rows, report = generate_pairs(args.data_dir, config)
        output = Path(args.output)
        write_csv(output, rows, DRAFT_FIELDS)
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except EvaluationDataError as exc:
        raise SystemExit(f"Pair generation failed: {exc}") from exc
    print(f"Draft generated: {output} ({len(rows)} pairs)")
    print(f"Distribution report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
