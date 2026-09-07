import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.schemas.cv import CVResponse
from app.schemas.cv_template import CVTemplateSummary
from app.schemas.job import JobResponse


class RecruiterApplicationCandidateSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationCandidateDetail(RecruiterApplicationCandidateSummary):
    phone: str | None


class RecruiterApplicationJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    status: JobStatus

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationCVSummary(BaseModel):
    id: uuid.UUID
    title: str
    source_type: CVSourceType
    template: CVTemplateSummary | None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationListItem(BaseModel):
    id: uuid.UUID
    status: JobApplicationStatus
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    cv_id: uuid.UUID
    candidate: RecruiterApplicationCandidateSummary
    job: RecruiterApplicationJobSummary
    cv: RecruiterApplicationCVSummary
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecruiterApplicationDetail(RecruiterApplicationListItem):
    candidate: RecruiterApplicationCandidateDetail
    job: JobResponse
    cv: CVResponse


class RecruiterApplicationListResponse(BaseModel):
    items: list[RecruiterApplicationListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
