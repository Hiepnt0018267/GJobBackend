"""
Job schemas (Task 04).
Public listing + detail — no auth required.
"""
import uuid
from datetime import datetime
from typing import Any, Optional, List
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.job import (
    EmploymentType, ExperienceLevel, JobStatus, JobLevel, ExperienceRequirement,
    WorkMode, SalaryType, Industry,
)


# ── Response schemas ──────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    """Full job detail response — never leaks recruiter sensitive data."""
    id: uuid.UUID
    title: str
    description: str
    company_name: str
    location: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    employment_type: Optional[EmploymentType]
    experience_level: Optional[ExperienceLevel]
    level: Optional[JobLevel]
    experience_requirement: Optional[ExperienceRequirement]
    work_mode: Optional[WorkMode]
    industry: Optional[Industry]
    vacancies: int
    salary_type: Optional[SalaryType]
    salary_fixed: Optional[int]
    salary_currency: str
    skills: Optional[List[str]]
    requirements: Optional[str]
    benefits: Optional[str]
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Paginated list of jobs."""
    items: List[JobResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


# ── Sort option ───────────────────────────────────────────────────────────────

class JobSortOption(str, Enum):
    newest = "newest"
    oldest = "oldest"
    salary_high = "salary_high"
    salary_low = "salary_low"


# ── Recruiter job management schemas (Task 06A) ──────────────────────────────

class RecruiterJobSortOption(str, Enum):
    newest = "newest"
    oldest = "oldest"
    updated = "updated"


class _JobFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    company_name: str = Field(min_length=1, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    employment_type: Optional[EmploymentType] = None
    level: Optional[JobLevel] = None
    experience_requirement: Optional[ExperienceRequirement] = None
    work_mode: Optional[WorkMode] = None
    industry: Optional[Industry] = None
    vacancies: int = Field(ge=1)
    salary_type: SalaryType
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    salary_fixed: Optional[int] = Field(default=None, ge=0)
    salary_currency: str = Field(default="VND", min_length=1, max_length=8)
    skills: List[str] = Field(default_factory=list)
    requirements: str = Field(min_length=1)
    benefits: Optional[str] = None

    @field_validator("title", "description", "company_name", "requirements", "benefits", mode="before")
    @classmethod
    def reject_blank_text(cls, value: Any):
        if value is None:
            return value
        if isinstance(value, str):
            value = value.strip()
        if value == "":
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_salary(self):
        _validate_salary_values(self.salary_type, self.salary_min, self.salary_max, self.salary_fixed)
        return self


class JobCreateRequest(_JobFields):
    """Fields a recruiter may supply when creating a job. Server fields are forbidden."""
    model_config = ConfigDict(extra="forbid")


class JobUpdateRequest(BaseModel):
    """Partial recruiter-owned job edits; status and ownership are server-managed."""
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1)
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    employment_type: Optional[EmploymentType] = None
    level: Optional[JobLevel] = None
    experience_requirement: Optional[ExperienceRequirement] = None
    work_mode: Optional[WorkMode] = None
    industry: Optional[Industry] = None
    vacancies: Optional[int] = Field(default=None, ge=1)
    salary_type: Optional[SalaryType] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    salary_fixed: Optional[int] = Field(default=None, ge=0)
    salary_currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    skills: Optional[List[str]] = None
    requirements: Optional[str] = Field(default=None, min_length=1)
    benefits: Optional[str] = None

    @field_validator("title", "description", "company_name", "requirements", "benefits", mode="before")
    @classmethod
    def reject_blank_text(cls, value: Any):
        return _JobFields.reject_blank_text(value)


class RecruiterJobResponse(JobResponse):
    recruiter_id: uuid.UUID


class RecruiterJobListResponse(BaseModel):
    items: List[RecruiterJobResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


def validate_effective_salary(values: dict[str, Any]) -> None:
    _validate_salary_values(
        values["salary_type"], values.get("salary_min"), values.get("salary_max"), values.get("salary_fixed")
    )


def _validate_salary_values(
    salary_type: SalaryType,
    salary_min: Optional[int],
    salary_max: Optional[int],
    salary_fixed: Optional[int],
) -> None:
    if salary_type == SalaryType.RANGE:
        if salary_min is None or salary_max is None or salary_max < salary_min or salary_fixed is not None:
            raise ValueError("RANGE salary requires salary_min and salary_max (max >= min), with salary_fixed omitted")
    elif salary_type == SalaryType.FIXED:
        if salary_fixed is None or salary_min is not None or salary_max is not None:
            raise ValueError("FIXED salary requires salary_fixed, with salary_min and salary_max omitted")
    elif salary_type == SalaryType.NEGOTIABLE:
        if any(value is not None for value in (salary_min, salary_max, salary_fixed)):
            raise ValueError("NEGOTIABLE salary cannot include salary amounts")
