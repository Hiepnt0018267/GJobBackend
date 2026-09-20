import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.job import JobListResponse, JobResponse


class AdminJobRecruiterAccount(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminJobCompanyProfile(BaseModel):
    id: uuid.UUID
    company_name: str | None
    company_website: str | None
    company_description: str | None
    company_address: str | None
    company_logo_url: str | None
    industry: str | None
    company_size: int | None

    model_config = ConfigDict(from_attributes=True)


class AdminJobResponse(JobResponse):
    recruiter_id: uuid.UUID | None
    recruiter_account: AdminJobRecruiterAccount | None = None
    company_profile: AdminJobCompanyProfile | None = None


class AdminJobListResponse(JobListResponse):
    items: list[AdminJobResponse]
