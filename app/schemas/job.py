"""
Job schemas (Task 04).
Public listing + detail — no auth required.
"""
import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel

from app.models.job import EmploymentType, ExperienceLevel, JobStatus


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
    skills: Optional[List[str]]
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
