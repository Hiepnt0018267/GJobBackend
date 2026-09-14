"""Pure ORM-to-domain mapping for future matching algorithms."""

from collections.abc import Iterable

from app.models.cv import CV
from app.models.job import Job
from app.models.skill import Skill, normalize_skill_name
from app.schemas.cv import (
    CVCertificateItem,
    CVEducationItem,
    CVExperienceItem,
    CVLanguageItem,
    CVPersonalInfo,
    CVProjectItem,
    CVSkillItem,
    CVSkillLevel,
)
from app.schemas.matching import (
    CanonicalCertificate,
    CanonicalCVMatchingInput,
    CanonicalEducation,
    CanonicalExperience,
    CanonicalJobMatchingInput,
    CanonicalLanguage,
    CanonicalLocation,
    CanonicalProject,
    CanonicalSalaryMetadata,
    CanonicalSkill,
)


def compact_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    compacted = " ".join(value.split())
    return compacted or None


def normalize_multiline_text(value: str | None) -> str | None:
    if value is None:
        return None
    lines = [" ".join(line.split()) for line in value.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    normalized: list[str] = []
    for line in lines:
        if line or (normalized and normalized[-1]):
            normalized.append(line)
    return "\n".join(normalized) or None


def _location(value: str | None) -> CanonicalLocation | None:
    display = compact_whitespace(value)
    if display is None:
        return None
    return CanonicalLocation(value=display, normalized_value=display.casefold())


def _canonical_skills(
    values: Iterable[tuple[str, CVSkillLevel | None]],
) -> list[CanonicalSkill]:
    level_rank = {
        None: 0,
        CVSkillLevel.BEGINNER: 1,
        CVSkillLevel.INTERMEDIATE: 2,
        CVSkillLevel.ADVANCED: 3,
        CVSkillLevel.EXPERT: 4,
    }
    unique: dict[str, CanonicalSkill] = {}
    for raw_name, level in values:
        name = compact_whitespace(raw_name)
        if name is None:
            continue
        normalized = normalize_skill_name(name)
        if normalized not in unique:
            unique[normalized] = CanonicalSkill(
                name=name,
                normalized_name=normalized,
                level=level,
            )
            continue
        current = unique[normalized]
        preferred_name = min((current.name, name), key=lambda item: (item.casefold(), item))
        preferred_level = max(
            (current.level, level), key=lambda item: level_rank.get(item, 0)
        )
        unique[normalized] = CanonicalSkill(
            name=preferred_name,
            normalized_name=normalized,
            level=preferred_level,
        )
    return [unique[key] for key in sorted(unique)]


def _section(title: str, values: Iterable[str | None]) -> str | None:
    lines = [value for item in values if (value := normalize_multiline_text(item))]
    return f"{title}:\n" + "\n".join(lines) if lines else None


def _semantic_text(sections: Iterable[str | None]) -> str:
    return "\n\n".join(section for section in sections if section)


def build_cv_matching_input(cv: CV) -> CanonicalCVMatchingInput:
    personal_info = CVPersonalInfo.model_validate(cv.personal_info or {})
    experiences = [CVExperienceItem.model_validate(item) for item in (cv.experiences or [])]
    educations = [CVEducationItem.model_validate(item) for item in (cv.educations or [])]
    skills = [CVSkillItem.model_validate(item) for item in (cv.skills or [])]
    projects = [CVProjectItem.model_validate(item) for item in (cv.projects or [])]
    certificates = [CVCertificateItem.model_validate(item) for item in (cv.certificates or [])]
    languages = [CVLanguageItem.model_validate(item) for item in (cv.languages or [])]

    canonical_skills = _canonical_skills((item.name, item.level) for item in skills)
    canonical_experiences = [
        CanonicalExperience(
            company_name=compact_whitespace(item.company_name) or item.company_name,
            position=compact_whitespace(item.position) or item.position,
            start_date=item.start_date,
            end_date=item.end_date,
            is_current=item.is_current,
            description=normalize_multiline_text(item.description),
        )
        for item in experiences
    ]
    canonical_educations = [
        CanonicalEducation(
            school_name=compact_whitespace(item.school_name) or item.school_name,
            degree=compact_whitespace(item.degree),
            field_of_study=compact_whitespace(item.field_of_study),
            start_date=item.start_date,
            end_date=item.end_date,
            is_current=item.is_current,
            description=normalize_multiline_text(item.description),
        )
        for item in educations
    ]
    canonical_projects = [
        CanonicalProject(
            name=compact_whitespace(item.name) or item.name,
            role=compact_whitespace(item.role),
            start_date=item.start_date,
            end_date=item.end_date,
            description=normalize_multiline_text(item.description),
            technologies=_canonical_skills((technology, None) for technology in item.technologies),
        )
        for item in projects
    ]
    canonical_certificates = [
        CanonicalCertificate(
            name=compact_whitespace(item.name) or item.name,
            organization=compact_whitespace(item.organization),
            issue_date=item.issue_date,
            expiration_date=item.expiration_date,
        )
        for item in certificates
    ]
    canonical_languages = [
        CanonicalLanguage(
            name=(name := compact_whitespace(item.name)) or item.name,
            normalized_name=((name or item.name).casefold()),
            proficiency=item.proficiency,
        )
        for item in languages
    ]
    objective = normalize_multiline_text(cv.career_objective)
    semantic_text = _semantic_text(
        (
            _section("CAREER OBJECTIVE", [objective]),
            _section("SKILLS", [item.name for item in canonical_skills]),
            _section(
                "EXPERIENCE",
                [part for item in canonical_experiences for part in (item.position, item.description)],
            ),
            _section(
                "EDUCATION",
                [part for item in canonical_educations for part in (item.degree, item.field_of_study, item.description)],
            ),
            _section(
                "PROJECTS",
                [part for item in canonical_projects for part in (item.name, item.role, item.description)],
            ),
            _section("CERTIFICATES", [item.name for item in canonical_certificates]),
            _section(
                "LANGUAGES",
                [f"{item.name} ({item.proficiency.value})" if item.proficiency else item.name for item in canonical_languages],
            ),
        )
    )
    return CanonicalCVMatchingInput(
        cv_id=cv.id,
        career_objective=objective,
        skills=canonical_skills,
        experiences=canonical_experiences,
        educations=canonical_educations,
        projects=canonical_projects,
        certificates=canonical_certificates,
        languages=canonical_languages,
        location=_location(personal_info.address),
        semantic_text=semantic_text,
    )


def build_job_matching_input(
    job: Job, taxonomy_skills: Iterable[Skill] = ()
) -> CanonicalJobMatchingInput:
    taxonomy_values = [(skill.name, None) for skill in taxonomy_skills]
    skill_values = taxonomy_values or [(name, None) for name in (job.skills or [])]
    skills = _canonical_skills(skill_values)
    title = compact_whitespace(job.title) or job.title
    description = normalize_multiline_text(job.description) or job.description
    requirements = normalize_multiline_text(job.requirements)
    semantic_text = _semantic_text(
        (
            _section("TITLE", [title]),
            _section("DESCRIPTION", [description]),
            _section("REQUIREMENTS", [requirements]),
            _section("SKILLS", [item.name for item in skills]),
            _section("INDUSTRY", [job.industry.value if job.industry else None]),
            _section("LEVEL", [job.level.value if job.level else None]),
            _section(
                "EXPERIENCE REQUIREMENT",
                [job.experience_requirement.value if job.experience_requirement else None],
            ),
        )
    )
    return CanonicalJobMatchingInput(
        job_id=job.id,
        title=title,
        description=description,
        requirements=requirements,
        skills=skills,
        location=_location(job.location),
        industry=job.industry,
        employment_type=job.employment_type,
        experience_level=job.experience_level,
        level=job.level,
        experience_requirement=job.experience_requirement,
        work_mode=job.work_mode,
        status=job.status,
        salary=CanonicalSalaryMetadata(
            salary_type=job.salary_type,
            minimum=job.salary_min,
            maximum=job.salary_max,
            fixed=job.salary_fixed,
            currency=job.salary_currency,
        ),
        vacancies=job.vacancies,
        semantic_text=semantic_text,
    )
