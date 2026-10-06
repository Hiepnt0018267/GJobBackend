from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.common import (
    EvaluationConfig, EvaluationDataError, REQUIRED_COLUMNS, exact_text_hash,
    inspect_columns, iter_csv, length_statistics, near_duplicate_hash,
    normalize_identifier, normalize_whitespace, resolve_dataset_files,
)


def _duplicate_summary(counter: Counter[object]) -> dict[str, int]:
    return {
        "groups": sum(count > 1 for count in counter.values()),
        "excess_rows": sum(count - 1 for count in counter.values() if count > 1),
    }


def _counter_rows(counter: Counter[str], limit: int | None = None) -> list[dict[str, int | str]]:
    items = counter.most_common(limit)
    return [{"value": value, "count": count} for value, count in items]


def _audit_resumes(path: Path, config: EvaluationConfig) -> dict[str, Any]:
    ids: Counter[str] = Counter()
    text_hashes: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    lengths: list[int] = []
    counters = Counter()
    for _, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        counters["rows"] += 1
        cv_id = normalize_identifier(row["ID"])
        text = normalize_whitespace(row["Resume_str"])
        category = normalize_whitespace(row["Category"])
        if cv_id:
            ids[cv_id] += 1
        if text:
            digest = exact_text_hash(text)
            if digest:
                text_hashes[digest] += 1
            lengths.append(len(text))
        else:
            counters["missing_text"] += 1
        if category:
            categories[category] += 1
        else:
            counters["missing_category"] += 1
        if normalize_whitespace(row["Resume_html"]):
            counters["html_available"] += 1
        if len(text) < config.minimum_cv_chars:
            counters["near_empty"] += 1
        if cv_id and text and category and len(text) >= config.minimum_cv_chars:
            counters["eligible"] += 1
    return {
        "rows": counters["rows"], "unique_ids": len(ids),
        "duplicate_ids": _duplicate_summary(ids),
        "duplicate_resume_text": _duplicate_summary(text_hashes),
        "missing_resume_text": counters["missing_text"],
        "missing_category": counters["missing_category"],
        "html_available": counters["html_available"],
        "near_empty_below_chars": config.minimum_cv_chars,
        "near_empty_count": counters["near_empty"], "eligible_count": counters["eligible"],
        "category_distribution": dict(categories.most_common()),
        "text_length": length_statistics(lengths),
    }


def _audit_jobs(path: Path, config: EvaluationConfig) -> tuple[
    dict[str, Any], set[str], dict[str, str], set[str], set[str]
]:
    ids: Counter[str] = Counter()
    descriptions: Counter[str] = Counter()
    near_descriptions: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    work_types: Counter[str] = Counter()
    lengths: list[int] = []
    company_by_job: dict[str, str] = {}
    eligible_ids: set[str] = set()
    complete_core_ids: set[str] = set()
    counters = Counter()
    for _, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        counters["rows"] += 1
        job_id = normalize_identifier(row["job_id"])
        company_id = normalize_identifier(row.get("company_id"))
        title = normalize_whitespace(row["title"])
        description = normalize_whitespace(row["description"])
        if job_id:
            ids[job_id] += 1
        if job_id and company_id:
            company_by_job[job_id] = company_id
        if title:
            titles[title] += 1
        else:
            counters["missing_title"] += 1
        if description:
            exact_digest = exact_text_hash(description)
            near_digest = near_duplicate_hash(description)
            if exact_digest:
                descriptions[exact_digest] += 1
            if near_digest:
                near_descriptions[near_digest] += 1
            lengths.append(len(description))
        else:
            counters["missing_description"] += 1
        if not normalize_whitespace(row.get("formatted_experience_level")):
            counters["missing_experience_level"] += 1
        if not normalize_whitespace(row.get("skills_desc")):
            counters["missing_skills_desc"] += 1
        work_type = normalize_whitespace(row.get("formatted_work_type") or row.get("work_type"))
        if work_type:
            work_types[work_type] += 1
        if job_id and title and description:
            complete_core_ids.add(job_id)
            if len(description) >= config.minimum_job_description_chars:
                eligible_ids.add(job_id)
    return ({
        "rows": counters["rows"], "unique_job_ids": len(ids),
        "duplicate_job_ids": _duplicate_summary(ids),
        "duplicate_descriptions": _duplicate_summary(descriptions),
        "near_duplicate_description_candidates": _duplicate_summary(near_descriptions),
        "missing_title": counters["missing_title"],
        "missing_description": counters["missing_description"],
        "missing_experience_level": counters["missing_experience_level"],
        "missing_skills_desc": counters["missing_skills_desc"],
        "eligible_count": len(eligible_ids), "top_titles": _counter_rows(titles, 30),
        "work_type_distribution": _counter_rows(work_types),
        "description_length": length_statistics(lengths),
    }, set(ids), company_by_job, complete_core_ids, eligible_ids)


def _audit_relation(path: Path, key: str, value: str) -> tuple[dict[str, Any], set[str]]:
    keys: Counter[str] = Counter()
    values: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    counters = Counter()
    for _, row in iter_csv(path, required_columns=REQUIRED_COLUMNS[path.name]):
        counters["rows"] += 1
        normalized_key = normalize_identifier(row.get(key))
        normalized_value = normalize_whitespace(row.get(value))
        if normalized_key:
            keys[normalized_key] += 1
        else:
            counters["missing_key"] += 1
        if normalized_value:
            values[normalized_value] += 1
        else:
            counters["missing_value"] += 1
        if normalized_key and normalized_value:
            pairs[(normalized_key, normalized_value)] += 1
    return ({
        "rows": counters["rows"], "unique_keys": len(keys), "unique_values": len(values),
        "missing_key": counters["missing_key"], "missing_value": counters["missing_value"],
        "duplicate_key_value_pairs": _duplicate_summary(pairs),
        "top_values": _counter_rows(values, 40),
    }, set(keys))


def audit_dataset(data_dir: str | Path, config: EvaluationConfig | None = None) -> dict[str, Any]:
    config = config or EvaluationConfig()
    files = resolve_dataset_files(data_dir)
    resume = _audit_resumes(files["Resume.csv"], config)
    jobs, job_ids, company_by_job, complete_core_ids, eligible_job_ids = _audit_jobs(files["job_postings.csv"], config)
    skills, jobs_with_skills = _audit_relation(files["job_skills.csv"], "job_id", "skill_abr")
    industries, jobs_with_industry = _audit_relation(files["job_industries.csv"], "job_id", "industry_id")
    companies, company_ids = _audit_relation(files["companies.csv"], "company_id", "name")
    company_industries, companies_with_industry = _audit_relation(files["company_industries.csv"], "company_id", "industry")
    company_specialities, _ = _audit_relation(files["company_specialities.csv"], "company_id", "speciality")
    benefits, _ = _audit_relation(files["benefits.csv"], "job_id", "type")
    employee_counts, _ = _audit_relation(files["employee_counts.csv"], "company_id", "employee_count")

    def coverage(covered: int, total: int) -> dict[str, float | int]:
        return {"covered": covered, "total": total, "percent": round(covered / total * 100, 2) if total else 0.0}

    return {
        "config": {"minimum_cv_chars": config.minimum_cv_chars, "minimum_job_description_chars": config.minimum_job_description_chars},
        "inputs": {name: {"path": str(path), "columns": inspect_columns(path)} for name, path in files.items()},
        "resume": resume, "jobs": jobs, "job_skills": skills, "job_industries": industries,
        "metadata": {"companies": companies, "company_industries": company_industries,
                     "company_specialities": company_specialities, "benefits": benefits,
                     "employee_counts": employee_counts},
        "join_coverage": {
            "job_to_skills": coverage(len(job_ids & jobs_with_skills), len(job_ids)),
            "job_to_industry": coverage(len(job_ids & jobs_with_industry), len(job_ids)),
            "job_to_company": coverage(
                sum(company_id in company_ids for company_id in company_by_job.values()), len(job_ids)
            ),
            "company_to_industry": coverage(len(company_ids & companies_with_industry), len(company_ids)),
            "jobs_with_title_and_description": coverage(len(complete_core_ids), len(job_ids)),
            "jobs_with_title_description_and_skill_signal": coverage(len(complete_core_ids & jobs_with_skills), len(job_ids)),
        },
        "limitations": [
            "job skill abbreviations have no code dictionary in the supplied files and remain opaque grouping metadata",
            "near-duplicate JD detection is a deterministic normalized-text candidate check, not semantic deduplication",
            "no CV-to-JD ground-truth labels exist in the raw inputs",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    resume, jobs = report["resume"], report["jobs"]
    lines = ["# Dataset audit", "", "> Statistics only; no resume or job-description text is included.", "",
             "## Resume.csv", "", f"- Rows: {resume['rows']}", f"- Unique IDs: {resume['unique_ids']}",
             f"- Eligible: {resume['eligible_count']}", f"- Missing text: {resume['missing_resume_text']}",
             f"- Duplicate text groups: {resume['duplicate_resume_text']['groups']}",
             f"- Text length: `{resume['text_length']}`", "", "## job_postings.csv", "",
             f"- Rows: {jobs['rows']}", f"- Unique job IDs: {jobs['unique_job_ids']}",
             f"- Eligible: {jobs['eligible_count']}", f"- Missing title: {jobs['missing_title']}",
             f"- Missing description: {jobs['missing_description']}",
             f"- Duplicate description groups: {jobs['duplicate_descriptions']['groups']}",
             f"- Near-duplicate candidates: {jobs['near_duplicate_description_candidates']['groups']}",
             f"- Description length: `{jobs['description_length']}`", "", "## Join coverage", "",
             "| Relation | Covered | Total | Percent |", "|---|---:|---:|---:|"]
    for name, item in report["join_coverage"].items():
        lines.append(f"| {name} | {item['covered']} | {item['total']} | {item['percent']}% |")
    lines.extend(["", "## Limitations", ""] + [f"- {item}" for item in report["limitations"]])
    return "\n".join(lines) + "\n"


def write_audit_reports(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = output / "dataset_audit.json", output / "dataset_audit.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit external CV/JD datasets without importing them into GJob.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", default="evaluation/reports")
    parser.add_argument("--minimum-cv-chars", type=int, default=EvaluationConfig.minimum_cv_chars)
    parser.add_argument("--minimum-job-description-chars", type=int, default=EvaluationConfig.minimum_job_description_chars)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EvaluationConfig(minimum_cv_chars=args.minimum_cv_chars,
                              minimum_job_description_chars=args.minimum_job_description_chars)
    try:
        json_path, markdown_path = write_audit_reports(audit_dataset(args.data_dir, config), args.output_dir)
    except EvaluationDataError as exc:
        raise SystemExit(f"Dataset audit failed: {exc}") from exc
    print(f"Audit complete: {json_path}")
    print(f"Human-readable report: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
