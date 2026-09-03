import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import JobApplicationStatus
from app.models.job import JobStatus, WorkMode
from app.schemas.cv import CVListItem, CVResponse


class JobApplicationCreate(BaseModel):
    cv_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class JobApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    cv_id: uuid.UUID
    status: JobApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateApplicationJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    status: JobStatus
    location: str | None
    work_mode: WorkMode | None

    model_config = ConfigDict(from_attributes=True)


class CandidateApplicationListItem(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    cv_id: uuid.UUID
    status: JobApplicationStatus
    created_at: datetime
    updated_at: datetime
    job: CandidateApplicationJobSummary
    cv: CVListItem

    model_config = ConfigDict(from_attributes=True)


class CandidateApplicationListResponse(BaseModel):
    items: list[CandidateApplicationListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class CandidateApplicationDetail(CandidateApplicationListItem):
    cv: CVResponse


class CandidateApplicationAppliedSummary(BaseModel):
    id: uuid.UUID
    status: JobApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateApplicationByJobResponse(BaseModel):
    has_applied: bool
    application: CandidateApplicationAppliedSummary | None = None
