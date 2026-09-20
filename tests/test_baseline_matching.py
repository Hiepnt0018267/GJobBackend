"""Deterministic baseline matching tests using synthetic canonical fixtures."""

import uuid

import pytest

from app.models.job import JobStatus
from app.schemas.matching import (
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    CanonicalLocation,
    CanonicalProject,
    CanonicalSalaryMetadata,
    CanonicalSkill,
    SkillEvidenceSource,
)
from app.services.baseline_matching_engine import (
    BASELINE_MATCHING_VERSION,
    BaselineMatchingEngine,
    InsufficientMatchingSignalsError,
)


CV_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
JOB_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


def _skill(name: str) -> CanonicalSkill:
    return CanonicalSkill(name=name, normalized_name=" ".join(name.split()).casefold())


def _cv(
    skills: list[str],
    *,
    technologies: list[str] | None = None,
    location: str = "Hà Nội",
    cv_id: uuid.UUID = CV_ID,
) -> CanonicalCVMatchingInput:
    projects = []
    if technologies is not None:
        projects.append(
            CanonicalProject(
                name="Synthetic Project",
                technologies=[_skill(name) for name in technologies],
            )
        )
    return CanonicalCVMatchingInput(
        cv_id=cv_id,
        skills=[_skill(name) for name in skills],
        experiences=[],
        educations=[],
        projects=projects,
        certificates=[],
        languages=[],
        location=CanonicalLocation(
            value=location, normalized_value=location.casefold()
        ),
        semantic_text="This text is intentionally ignored by baseline-v1.",
    )


def _job(
    skills: list[str],
    *,
    status: JobStatus = JobStatus.APPROVED,
    salary: int | None = None,
    location: str = "Hà Nội",
    job_id: uuid.UUID = JOB_ID,
) -> CanonicalJobMatchingInput:
    return CanonicalJobMatchingInput(
        job_id=job_id,
        title="Synthetic Backend Role",
        description="Synthetic description",
        requirements="Synthetic requirements",
        skills=[_skill(name) for name in skills],
        location=CanonicalLocation(
            value=location, normalized_value=location.casefold()
        ),
        status=status,
        salary=CanonicalSalaryMetadata(
            salary_type=None,
            minimum=salary,
            maximum=salary,
            currency="VND",
        ),
        vacancies=1,
        semantic_text="Different semantic text is also ignored.",
    )


def _match(cv: CanonicalCVMatchingInput, job: CanonicalJobMatchingInput):
    return BaselineMatchingEngine().match(cv, job)


def test_exact_skill_match_scores_100() -> None:
    result = _match(
        _cv(["Python", "FastAPI", "PostgreSQL"]),
        _job(["Python", "FastAPI", "PostgreSQL"]),
    )

    assert result.algorithm_version == BASELINE_MATCHING_VERSION
    assert result.overall_score == 100.0
    assert result.components.skills.score == 100.0
    assert result.components.skills.available is True
    assert result.components.skills.configured_weight == 1.0
    assert result.components.skills.effective_weight == 1.0
    assert result.components.skills.missing_skills == []


def test_partial_skill_match_has_exact_coverage_and_truthful_gaps() -> None:
    result = _match(
        _cv(["Python", "PostgreSQL"]),
        _job(["Python", "FastAPI", "Docker", "PostgreSQL"]),
    )

    assert result.overall_score == 50.0
    assert result.components.skills.matched_skills == ["PostgreSQL", "Python"]
    assert result.components.skills.missing_skills == ["Docker", "FastAPI"]
    assert all("Không tìm thấy" in gap.message for gap in result.gaps)
    assert all("ứng viên thiếu" not in gap.message.casefold() for gap in result.gaps)


def test_no_skill_match_scores_zero_without_hiring_judgment() -> None:
    result = _match(_cv(["Python", "FastAPI"]), _job(["Java", "Spring"]))

    assert result.overall_score == 0.0
    assert result.components.skills.matched_skills == []
    assert result.strengths == []
    messages = " ".join(gap.message for gap in result.gaps).casefold()
    assert "hire" not in messages
    assert "reject" not in messages


def test_extra_candidate_skills_do_not_reduce_coverage() -> None:
    base = _match(_cv(["Python"]), _job(["Python"]))
    extra = _match(_cv(["Python", "Docker", "AWS"]), _job(["Python"]))

    assert base.overall_score == extra.overall_score == 100.0


def test_unicode_skill_and_project_technology_are_explicit_evidence() -> None:
    result = _match(
        _cv(["Trí tuệ nhân tạo"], technologies=["Docker"]),
        _job(["Docker", "Trí tuệ nhân tạo"]),
    )

    assert result.overall_score == 100.0
    evidence = {
        item.normalized_name: item.sources
        for item in result.components.skills.evidence
    }
    assert evidence["docker"] == [SkillEvidenceSource.PROJECT_TECHNOLOGY]
    assert evidence["trí tuệ nhân tạo"] == [SkillEvidenceSource.CV_SKILL]


def test_same_skill_in_cv_and_project_reports_both_evidence_sources() -> None:
    result = _match(_cv(["Python"], technologies=["Python"]), _job(["Python"]))

    assert result.components.skills.evidence[0].sources == [
        SkillEvidenceSource.CV_SKILL,
        SkillEvidenceSource.PROJECT_TECHNOLOGY,
    ]


def test_zero_job_skills_returns_controlled_insufficient_signal_error() -> None:
    with pytest.raises(InsufficientMatchingSignalsError):
        _match(_cv(["Python"]), _job([]))


def test_skill_order_does_not_change_result() -> None:
    first = _match(_cv(["Python", "Docker"]), _job(["Docker", "Python"]))
    second = _match(_cv(["Docker", "Python"]), _job(["Python", "Docker"]))

    assert first.model_dump() == second.model_dump()


def test_score_is_bounded_deterministic_and_json_serializable() -> None:
    cv = _cv(["Python"])
    job = _job(["Python", "Docker", "FastAPI"])

    results = [_match(cv, job) for _ in range(5)]

    assert all(result == results[0] for result in results)
    assert 0.0 <= results[0].overall_score <= 100.0
    assert results[0].overall_score == 33.33
    assert results[0].model_dump(mode="json")["overall_score"] == 33.33


def test_skill_score_is_monotonic_for_added_or_removed_matches() -> None:
    job = _job(["Python", "Docker", "FastAPI"])
    one = _match(_cv(["Python"]), job).overall_score
    two = _match(_cv(["Python", "Docker"]), job).overall_score
    three = _match(_cv(["Python", "Docker", "FastAPI"]), job).overall_score

    assert one < two < three


def test_context_metadata_and_semantic_text_do_not_affect_score() -> None:
    cv = _cv(["Python"], location="Hà Nội")
    job = _job(["Python"], salary=10_000_000, location="Hà Nội")
    changed_cv = cv.model_copy(
        update={
            "location": CanonicalLocation(
                value="Đà Nẵng", normalized_value="đà nẵng"
            ),
            "semantic_text": "Candidate identity and unrelated prose changed",
        }
    )
    changed_job = job.model_copy(
        update={
            "status": JobStatus.CLOSED,
            "salary": CanonicalSalaryMetadata(
                salary_type=None,
                minimum=99_000_000,
                maximum=99_000_000,
                currency="USD",
            ),
            "location": CanonicalLocation(
                value="Remote", normalized_value="remote"
            ),
            "semantic_text": "Company and recruiter identity changed",
        }
    )

    assert _match(cv, job).overall_score == _match(changed_cv, changed_job).overall_score


def test_equivalent_builder_and_uploaded_features_produce_equal_match_details() -> None:
    builder = _match(_cv(["Python"], cv_id=CV_ID), _job(["Python", "Docker"]))
    uploaded = _match(
        _cv(
            ["Python"],
            cv_id=uuid.UUID("77777777-7777-4777-8777-777777777777"),
        ),
        _job(["Python", "Docker"]),
    )

    assert builder.model_dump(exclude={"cv_id"}) == uploaded.model_dump(
        exclude={"cv_id"}
    )
