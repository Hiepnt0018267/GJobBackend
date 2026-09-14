"""Canonical, deterministic inputs for future CV/JD matching."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.job import (
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    JobLevel,
    JobStatus,
    SalaryType,
    WorkMode,
)
from app.schemas.cv import CVLanguageProficiency, CVSkillLevel


class _CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalSkill(_CanonicalModel):
    name: str
    normalized_name: str
    level: CVSkillLevel | None = None


class CanonicalLocation(_CanonicalModel):
    value: str
    normalized_value: str


class CanonicalExperience(_CanonicalModel):
    company_name: str
    position: str
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None


class CanonicalEducation(_CanonicalModel):
    school_name: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None


class CanonicalProject(_CanonicalModel):
    name: str
    role: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    technologies: list[CanonicalSkill]


class CanonicalCertificate(_CanonicalModel):
    name: str
    organization: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None


class CanonicalLanguage(_CanonicalModel):
    name: str
    normalized_name: str
    proficiency: CVLanguageProficiency | None = None


class CanonicalSalaryMetadata(_CanonicalModel):
    salary_type: SalaryType | None = None
    minimum: int | None = None
    maximum: int | None = None
    fixed: int | None = None
    currency: str


class CanonicalCVMatchingInput(_CanonicalModel):
    cv_id: uuid.UUID
    career_objective: str | None = None
    skills: list[CanonicalSkill]
    experiences: list[CanonicalExperience]
    educations: list[CanonicalEducation]
    projects: list[CanonicalProject]
    certificates: list[CanonicalCertificate]
    languages: list[CanonicalLanguage]
    location: CanonicalLocation | None = None
    semantic_text: str


class CanonicalJobMatchingInput(_CanonicalModel):
    job_id: uuid.UUID
    title: str
    description: str
    requirements: str | None = None
    skills: list[CanonicalSkill]
    location: CanonicalLocation | None = None
    industry: Industry | None = None
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    level: JobLevel | None = None
    experience_requirement: ExperienceRequirement | None = None
    work_mode: WorkMode | None = None
    status: JobStatus
    salary: CanonicalSalaryMetadata
    vacancies: int
    semantic_text: str
