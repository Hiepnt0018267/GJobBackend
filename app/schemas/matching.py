"""Canonical, deterministic inputs for future CV/JD matching."""

import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

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


class SkillEvidenceSource(str, Enum):
    CV_SKILL = "CV_SKILL"
    PROJECT_TECHNOLOGY = "PROJECT_TECHNOLOGY"


class MatchExplanationCode(str, Enum):
    SKILL_COVERAGE = "SKILL_COVERAGE"
    SKILL_NOT_FOUND_IN_CV = "SKILL_NOT_FOUND_IN_CV"


class MatchedSkillEvidence(_CanonicalModel):
    skill: str
    normalized_name: str
    sources: list[SkillEvidenceSource]


class SkillMatchComponent(_CanonicalModel):
    available: bool
    score: float = Field(ge=0.0, le=100.0)
    configured_weight: float = Field(ge=0.0, le=1.0)
    effective_weight: float = Field(ge=0.0, le=1.0)
    job_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    evidence: list[MatchedSkillEvidence]


class BaselineMatchComponents(_CanonicalModel):
    skills: SkillMatchComponent


class MatchExplanation(_CanonicalModel):
    code: MatchExplanationCode
    message: str
    evidence: list[str] = Field(default_factory=list)


class BaselineMatchResult(_CanonicalModel):
    """Feature compatibility, not hiring probability or a hiring recommendation."""

    algorithm_version: str
    cv_id: uuid.UUID
    job_id: uuid.UUID
    overall_score: float = Field(ge=0.0, le=100.0)
    components: BaselineMatchComponents
    strengths: list[MatchExplanation]
    gaps: list[MatchExplanation]


class SemanticMatchingResult(_CanonicalModel):
    """Raw semantic similarity; not a hiring probability or recommendation."""

    cv_id: uuid.UUID
    job_id: uuid.UUID
    semantic_similarity: float = Field(ge=-1.0, le=1.0)
    provider: str
    model: str
    dimensions: int = Field(gt=0)
    engine_version: str


class MatchComponentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_SIGNALS = "INSUFFICIENT_SIGNALS"
    UNAVAILABLE = "UNAVAILABLE"


class MatchComponentErrorCode(str, Enum):
    INSUFFICIENT_MATCHING_SIGNALS = "INSUFFICIENT_MATCHING_SIGNALS"
    EMBEDDING_PROVIDER_UNAVAILABLE = "EMBEDDING_PROVIDER_UNAVAILABLE"
    EMBEDDING_INPUT_TOO_LONG = "EMBEDDING_INPUT_TOO_LONG"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"


class CandidateMatchRequest(_CanonicalModel):
    cv_id: uuid.UUID


class BaselineMatchComponentResponse(_CanonicalModel):
    status: MatchComponentStatus
    result: BaselineMatchResult | None = None
    error_code: MatchComponentErrorCode | None = None


class SemanticMatchComponentResponse(_CanonicalModel):
    status: MatchComponentStatus
    result: SemanticMatchingResult | None = None
    error_code: MatchComponentErrorCode | None = None


class CVJobMatchResponse(_CanonicalModel):
    cv_id: uuid.UUID
    job_id: uuid.UUID
    baseline: BaselineMatchComponentResponse
    semantic: SemanticMatchComponentResponse
    baseline_engine_version: str
    semantic_engine_version: str
    computed_at: datetime
    cached: bool
