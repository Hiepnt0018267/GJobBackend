import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import JobApplicationStatus
from app.models.cv import CVSourceType
from app.models.job import JobStatus
from app.schemas.admin_cv import AdminCVCandidateSummary, AdminCVDetail, AdminCVTemplateSummary


class AdminApplicationJobSummary(BaseModel):
    id: uuid.UUID
    title: str
    company_name: str
    status: JobStatus

    model_config = ConfigDict(from_attributes=True)


class AdminApplicationCVSummary(BaseModel):
    id: uuid.UUID
    title: str
    source_type: CVSourceType
    template: AdminCVTemplateSummary | None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminApplicationListItem(BaseModel):
    id: uuid.UUID
    status: JobApplicationStatus
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    cv_id: uuid.UUID
    candidate: AdminCVCandidateSummary
    job: AdminApplicationJobSummary
    cv: AdminApplicationCVSummary
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminApplicationDetail(AdminApplicationListItem):
    cv: AdminCVDetail


class AdminApplicationListResponse(BaseModel):
    items: list[AdminApplicationListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
