"""Canonical matching input tests; no AI, network, scoring, or embeddings."""

import copy
import uuid
from types import SimpleNamespace

import pytest

from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtractionStatus
from app.models.job import (
    EmploymentType,
    ExperienceRequirement,
    Industry,
    Job,
    JobLevel,
    JobStatus,
    SalaryType,
    WorkMode,
)
from app.models.skill import Skill
from app.services.matching_input_mapper import (
    build_cv_matching_input,
    build_job_matching_input,
    normalize_multiline_text,
)
from app.services.matching_input_service import (
    CVNotReadyForMatchingError,
    JobNotReadyForMatchingError,
    MatchingInputService,
)


CV_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
JOB_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CANDIDATE_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


def _structured_cv(source_type: CVSourceType, cv_id: uuid.UUID = CV_ID) -> CV:
    return CV(
        id=cv_id,
        candidate_id=CANDIDATE_ID,
        source_type=source_type,
        title="Synthetic candidate CV",
        personal_info={
            "full_name": "Synthetic Candidate",
            "email": "candidate@example.com",
            "phone": "0900000000",
            "address": "  Hà   Nội ",
            "avatar_url": "https://example.com/private-photo.jpg",
            "date_of_birth": "1990-01-01",
        },
        career_objective="  Xây dựng   sản phẩm hữu ích. ",
        educations=[
            {
                "school_name": "Đại học Tổng hợp",
                "degree": "Kỹ sư",
                "field_of_study": "Công nghệ thông tin",
                "description": "  Hệ thống   thông tin ",
            }
        ],
        experiences=[
            {
                "company_name": "Synthetic Company",
                "position": " Backend   Developer ",
                "start_date": "2022-01-01",
                "is_current": True,
                "description": " Phát triển   API FastAPI. ",
            }
        ],
        skills=[
            {"name": " Python ", "level": "ADVANCED"},
            {"name": "python", "level": "BEGINNER"},
            {"name": " Trí   tuệ nhân tạo "},
        ],
        projects=[
            {
                "name": "GJob",
                "role": "Backend",
                "description": "Nền tảng tuyển dụng",
                "technologies": [" FastAPI ", "fastapi", "PostgreSQL"],
                "project_url": "https://example.com/private-project",
            }
        ],
        certificates=[
            {
                "name": "Cloud Fundamentals",
                "organization": "Synthetic Academy",
                "credential_url": "https://example.com/private-credential",
            }
        ],
        languages=[{"name": " Tiếng   Anh ", "proficiency": "PROFESSIONAL"}],
    )


def _job(status: JobStatus = JobStatus.APPROVED) -> Job:
    return Job(
        id=JOB_ID,
        title=" Backend   Developer ",
        description=" Xây dựng   dịch vụ API. ",
        company_name="Brand That Must Not Affect Matching",
        location=" Thanh Xuân,   Hà Nội ",
        salary_type=SalaryType.RANGE,
        salary_min=20_000_000,
        salary_max=35_000_000,
        salary_currency="VND",
        employment_type=EmploymentType.FULL_TIME,
        level=JobLevel.SENIOR,
        experience_requirement=ExperienceRequirement.THREE_TO_FIVE_YEARS,
        work_mode=WorkMode.HYBRID,
        industry=Industry.INFORMATION_TECHNOLOGY,
        vacancies=2,
        requirements=" Python và   FastAPI ",
        benefits="Sensitive internal benefit text",
        skills=["Legacy Skill"],
        status=status,
    )


def test_builder_cv_maps_structured_fields_without_sensitive_semantic_data() -> None:
    canonical = build_cv_matching_input(_structured_cv(CVSourceType.BUILDER))

    assert [skill.normalized_name for skill in canonical.skills] == [
        "python",
        "trí tuệ nhân tạo",
    ]
    assert canonical.experiences[0].position == "Backend Developer"
    assert canonical.educations[0].field_of_study == "Công nghệ thông tin"
    assert canonical.location is not None
    assert canonical.location.normalized_value == "hà nội"
    lowered = canonical.semantic_text.casefold()
    for excluded in (
        "synthetic candidate",
        "candidate@example.com",
        "0900000000",
        "private-photo.jpg",
        "1990-01-01",
        "hà nội",
        "synthetic company",
    ):
        assert excluded not in lowered


def test_cv_mapping_does_not_mutate_jsonb_values() -> None:
    cv = _structured_cv(CVSourceType.BUILDER)
    before = copy.deepcopy(
        {field: getattr(cv, field) for field in ("personal_info", "skills", "experiences")}
    )

    build_cv_matching_input(cv)

    assert {field: getattr(cv, field) for field in before} == before


def test_builder_and_confirmed_uploaded_have_equivalent_feature_content() -> None:
    builder = build_cv_matching_input(_structured_cv(CVSourceType.BUILDER))
    uploaded = build_cv_matching_input(
        _structured_cv(
            CVSourceType.UPLOADED,
            uuid.UUID("44444444-4444-4444-8444-444444444444"),
        )
    )

    assert builder.model_dump(exclude={"cv_id"}) == uploaded.model_dump(
        exclude={"cv_id"}
    )


@pytest.mark.parametrize(
    "latest_status",
    [None, CVExtractionStatus.PROCESSING, CVExtractionStatus.FAILED],
)
def test_uploaded_cv_without_usable_success_is_rejected(
    latest_status: CVExtractionStatus | None,
) -> None:
    service = MatchingInputService.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(
        get_by_id_for_matching=lambda _cv_id: _structured_cv(CVSourceType.UPLOADED)
    )
    service.extraction_repository = SimpleNamespace(
        has_confirmed_for_cv=lambda _cv_id: False,
        get_latest_successful_for_cv=lambda _cv_id: None,
        get_latest_for_cv=lambda _cv_id: (
            SimpleNamespace(status=latest_status) if latest_status else None
        ),
    )

    with pytest.raises(CVNotReadyForMatchingError):
        service.build_cv_input(CV_ID)


def test_unconfirmed_successful_uploaded_cv_uses_extracted_result() -> None:
    extracted = {
        "personal_info": {"address": "Đà Nẵng"},
        "career_objective": "Build reliable distributed systems",
        "educations": [],
        "experiences": [],
        "skills": [{"name": "Rust"}],
        "projects": [],
        "certificates": [],
        "languages": [],
    }
    service = MatchingInputService.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(
        get_by_id_for_matching=lambda _cv_id: _structured_cv(CVSourceType.UPLOADED)
    )
    service.extraction_repository = SimpleNamespace(
        has_confirmed_for_cv=lambda _cv_id: False,
        get_latest_successful_for_cv=lambda _cv_id: SimpleNamespace(
            structured_result=extracted
        ),
        get_latest_for_cv=lambda _cv_id: None,
    )

    canonical = service.build_cv_input(CV_ID)

    assert [skill.normalized_name for skill in canonical.skills] == ["rust"]
    assert canonical.location is not None
    assert canonical.location.normalized_value == "đà nẵng"


def test_failed_retry_does_not_hide_an_older_successful_extraction() -> None:
    successful = SimpleNamespace(
        structured_result={
            "personal_info": {},
            "career_objective": None,
            "educations": [],
            "experiences": [],
            "skills": [{"name": "FastAPI"}],
            "projects": [],
            "certificates": [],
            "languages": [],
        }
    )
    service = MatchingInputService.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(
        get_by_id_for_matching=lambda _cv_id: _structured_cv(CVSourceType.UPLOADED)
    )
    service.extraction_repository = SimpleNamespace(
        has_confirmed_for_cv=lambda _cv_id: False,
        get_latest_successful_for_cv=lambda _cv_id: successful,
        get_latest_for_cv=lambda _cv_id: SimpleNamespace(
            status=CVExtractionStatus.FAILED
        ),
    )

    assert service.build_cv_input(CV_ID).skills[0].normalized_name == "fastapi"


def test_confirmed_uploaded_cv_maps_without_ai_call() -> None:
    service = MatchingInputService.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(
        get_by_id_for_matching=lambda _cv_id: _structured_cv(CVSourceType.UPLOADED)
    )
    service.extraction_repository = SimpleNamespace(
        has_confirmed_for_cv=lambda _cv_id: True
    )

    assert service.build_cv_input(CV_ID).skills[0].normalized_name == "python"


def test_confirmed_candidate_data_precedes_a_later_successful_extraction() -> None:
    service = MatchingInputService.__new__(MatchingInputService)
    service.cv_repository = SimpleNamespace(
        get_by_id_for_matching=lambda _cv_id: _structured_cv(CVSourceType.UPLOADED)
    )
    service.extraction_repository = SimpleNamespace(
        has_confirmed_for_cv=lambda _cv_id: True,
        get_latest_successful_for_cv=lambda _cv_id: pytest.fail(
            "confirmed data must short-circuit newer AI results"
        ),
    )

    canonical = service.build_cv_input(CV_ID)

    assert canonical.skills[0].normalized_name == "python"


def test_job_mapper_prefers_taxonomy_and_has_stable_serializable_output() -> None:
    taxonomy = [
        Skill(name=" Python ", normalized_name="python"),
        Skill(name="FastAPI", normalized_name="fastapi"),
        Skill(name="PYTHON", normalized_name="python"),
    ]

    first = build_job_matching_input(_job(), taxonomy)
    second = build_job_matching_input(_job(), reversed(taxonomy))

    assert [skill.normalized_name for skill in first.skills] == ["fastapi", "python"]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.location is not None
    assert first.location.normalized_value == "thanh xuân, hà nội"
    lowered = first.semantic_text.casefold()
    assert "brand that must not affect matching" not in lowered
    assert "sensitive internal benefit text" not in lowered
    assert "20000000" not in lowered
    assert "thanh xuân" not in lowered


def test_job_mapper_falls_back_to_legacy_skill_array() -> None:
    canonical = build_job_matching_input(_job(), [])

    assert [(skill.name, skill.normalized_name) for skill in canonical.skills] == [
        ("Legacy Skill", "legacy skill")
    ]


def test_candidate_facing_job_service_rejects_unapproved_job() -> None:
    job = _job(JobStatus.PENDING)
    service = MatchingInputService.__new__(MatchingInputService)
    service.job_repository = SimpleNamespace(get_by_id_for_matching=lambda _job_id: job)

    with pytest.raises(JobNotReadyForMatchingError):
        service.build_job_input(JOB_ID)


def test_sparse_builder_cv_remains_matchable_and_deterministic() -> None:
    cv = CV(
        id=CV_ID,
        candidate_id=CANDIDATE_ID,
        source_type=CVSourceType.BUILDER,
        title="Sparse CV",
        personal_info={},
        career_objective=None,
        educations=[],
        experiences=[],
        skills=[],
        projects=[],
        certificates=[],
        languages=[],
    )

    canonical = build_cv_matching_input(cv)

    assert canonical.semantic_text == ""
    assert canonical.model_dump(mode="json")["skills"] == []


def test_multiline_descriptions_keep_paragraphs_deterministically() -> None:
    value = "  Dòng đầu   có khoảng trắng.  \n\n\n  Dòng thứ hai. "

    assert normalize_multiline_text(value) == (
        "Dòng đầu có khoảng trắng.\n\nDòng thứ hai."
    )
