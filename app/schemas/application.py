import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import JobApplicationStatus


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
