from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evaluation.audit import audit_dataset, main as audit_main
from evaluation.common import EvaluationConfig, EvaluationDataError
from evaluation.generate_pairs import DRAFT_FIELDS, generate_pairs
from evaluation.validate_labels import validate_labeled_file


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    root = tmp_path / "external-data"
    categories = ["INFORMATION-TECHNOLOGY", "FINANCE", "HUMAN-RESOURCES"]
    resumes = []
    for index in range(9):
        category = categories[index % len(categories)]
        resumes.append({
            "ID": f"cv-{index}",
            "Resume_str": f"{category} specialist profile {index} with python analysis communication operations and project delivery experience.",
            "Resume_html": "<p>available</p>",
            "Category": category,
        })
    resumes.append({"ID": "cv-empty", "Resume_str": "", "Resume_html": "", "Category": "FINANCE"})
    resumes.append({**resumes[0], "ID": "cv-duplicate-text"})
    _write_csv(root / "nested-cv" / "Resume.csv", ["ID", "Resume_str", "Resume_html", "Category"], resumes)

    job_rows = []
    titles = ["Python Engineer", "Data Analyst", "Accountant", "Financial Analyst", "HR Specialist", "Recruiter", "Network Engineer", "Project Manager", "Sales Manager", "Teacher"]
    for index, title in enumerate(titles):
        job_rows.append({
            "job_id": f"job-{index}", "company_id": f"company-{index % 4}", "title": title,
            "description": f"Unique vacancy {index} for {title} requiring domain delivery, communication, analysis and practical responsibilities.",
            "formatted_experience_level": "Mid-Senior level" if index % 2 else "Entry level",
            "skills_desc": f"{title} communication analysis",
            "formatted_work_type": "Full-time",
        })
    job_rows.append({"job_id": "job-invalid", "company_id": "company-0", "title": "", "description": "short", "formatted_experience_level": "", "skills_desc": "", "formatted_work_type": ""})
    _write_csv(root / "nested-jd" / "job_postings.csv", list(job_rows[0]), job_rows)
    _write_csv(root / "nested-jd" / "job_skills.csv", ["job_id", "skill_abr"], [{"job_id": f"job-{i}", "skill_abr": ["IT", "FIN", "HR"][i % 3]} for i in range(9)])
    _write_csv(root / "nested-jd" / "job_industries.csv", ["job_id", "industry_id"], [{"job_id": f"job-{i}", "industry_id": str(i % 3)} for i in range(10)])
    _write_csv(root / "nested-jd" / "companies.csv", ["company_id", "name"], [{"company_id": f"company-{i}", "name": f"Company {i}"} for i in range(4)])
    _write_csv(root / "nested-jd" / "company_industries.csv", ["company_id", "industry"], [{"company_id": f"company-{i}", "industry": "Technology"} for i in range(4)])
    _write_csv(root / "nested-jd" / "company_specialities.csv", ["company_id", "speciality"], [{"company_id": f"company-{i}", "speciality": "Services"} for i in range(4)])
    _write_csv(root / "nested-jd" / "benefits.csv", ["job_id", "type"], [{"job_id": "job-0", "type": "Medical"}])
    _write_csv(root / "nested-jd" / "employee_counts.csv", ["company_id", "employee_count"], [{"company_id": f"company-{i}", "employee_count": 100 + i} for i in range(4)])
    return root


def _config(seed: int = 42) -> EvaluationConfig:
    return EvaluationConfig(
        seed=seed, minimum_cv_chars=20, minimum_job_description_chars=20,
        cv_sample_size=6, job_sample_size=8, pair_target=12,
        max_pairs_per_cv=2, max_pairs_per_job=2, candidate_pool_limit=8,
    )


def test_audit_counts_filtering_and_leakage(dataset_dir: Path) -> None:
    report = audit_dataset(dataset_dir, _config())
    assert report["resume"]["rows"] == 11
    assert report["resume"]["missing_resume_text"] == 1
    assert report["resume"]["duplicate_resume_text"]["groups"] == 1
    assert report["resume"]["eligible_count"] == 10
    assert report["jobs"]["rows"] == 11
    assert report["jobs"]["eligible_count"] == 10
    assert report["join_coverage"]["job_to_company"]["percent"] == 100.0


def test_pair_generation_is_deterministic_diverse_and_bounded(dataset_dir: Path) -> None:
    first, first_report = generate_pairs(dataset_dir, _config())
    second, second_report = generate_pairs(dataset_dir, _config())
    assert first == second
    assert first_report == second_report
    assert len(first) == 12
    assert len({(row["cv_id"], row["job_id"]) for row in first}) == 12
    assert {row["pair_type"] for row in first} == {
        "POSITIVE_CANDIDATE", "HARD_NEGATIVE_CANDIDATE", "EASY_NEGATIVE_CANDIDATE"
    }
    assert all(row["label"] == "" for row in first)
    assert first_report["max_pairs_observed"]["per_cv"] <= 2
    assert first_report["max_pairs_observed"]["per_job"] <= 2


def test_validator_rejects_missing_and_duplicate_labels(dataset_dir: Path, tmp_path: Path) -> None:
    rows, _ = generate_pairs(dataset_dir, _config())
    labeled = tmp_path / "labeled.csv"
    invalid = [dict(rows[0]), dict(rows[0])]
    invalid[0]["label"] = ""
    invalid[0]["label_reason"] = ""
    invalid[1]["label"] = "2"
    invalid[1]["label_reason"] = "invalid"
    _write_csv(labeled, DRAFT_FIELDS, invalid)
    with pytest.raises(EvaluationDataError, match="label must be 0 or 1"):
        validate_labeled_file(labeled, tmp_path / "final.csv", data_dir=dataset_dir)


def test_validator_accepts_complete_human_labels(dataset_dir: Path, tmp_path: Path) -> None:
    rows, _ = generate_pairs(dataset_dir, _config())
    for index, row in enumerate(rows):
        row["label"] = str(index % 2)
        row["label_reason"] = "Human-reviewed role, skills and responsibility evidence."
    labeled, final = tmp_path / "labeled.csv", tmp_path / "final.csv"
    _write_csv(labeled, DRAFT_FIELDS, rows)
    summary = validate_labeled_file(labeled, final, data_dir=dataset_dir)
    assert summary == {"rows": 12, "label_0": 6, "label_1": 6}
    with final.open("r", encoding="utf-8", newline="") as handle:
        final_rows = list(csv.DictReader(handle))
    assert len(final_rows) == 12
    assert "cv_text_preview" not in final_rows[0]


def test_cli_reports_missing_data_path(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Dataset directory does not exist"):
        audit_main(["--data-dir", str(tmp_path / "missing")])
