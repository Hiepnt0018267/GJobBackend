import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.application import JobApplicationStatus
from app.repositories.admin_application_repository import AdminApplicationRepository
from app.schemas.admin_application import (
    AdminApplicationDetail,
    AdminApplicationListItem,
    AdminApplicationListResponse,
)


class AdminApplicationService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminApplicationRepository(db)

    def list_applications(self, application_status: JobApplicationStatus | None, search: str | None, job_id: uuid.UUID | None, candidate_id: uuid.UUID | None, page: int, page_size: int) -> AdminApplicationListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_applications(application_status, normalized_search, job_id, candidate_id, page, page_size)
        return AdminApplicationListResponse(items=[AdminApplicationListItem.model_validate(item) for item in items], page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size) if total else 0)

    def get_application(self, application_id: uuid.UUID) -> AdminApplicationDetail:
        application = self.repository.get_by_id(application_id)
        if application is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
        return AdminApplicationDetail.model_validate(application)
