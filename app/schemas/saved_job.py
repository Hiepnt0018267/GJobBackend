import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.job import (
    EmploymentType,
    ExperienceRequirement,
    Industry,
    JobStatus,
    SalaryType,
    WorkMode,
)


class SavedJobStatusResponse(BaseModel):
    saved: bool
    saved_at: datetime | None = None


class SavedJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    company_logo_url: str | None = None
    location: str | None
    salary_min: int | None
    salary_max: int | None
    salary_type: SalaryType | None
    salary_fixed: int | None
    salary_currency: str
    employment_type: EmploymentType | None
    experience_requirement: ExperienceRequirement | None
    work_mode: WorkMode | None
    industry: Industry | None
    status: JobStatus
    created_at: datetime


class SavedJobListItem(BaseModel):
    id: uuid.UUID
    saved_at: datetime
    job: SavedJobSummary


class SavedJobListResponse(BaseModel):
    items: list[SavedJobListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
