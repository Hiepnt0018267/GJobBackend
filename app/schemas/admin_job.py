import uuid

from app.schemas.job import JobListResponse, JobResponse


class AdminJobResponse(JobResponse):
    recruiter_id: uuid.UUID | None


class AdminJobListResponse(JobListResponse):
    items: list[AdminJobResponse]
