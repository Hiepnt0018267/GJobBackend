import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.application import JobApplicationStatus
from app.models.user import User, UserRole
from app.schemas.admin_application import AdminApplicationDetail, AdminApplicationListResponse
from app.services.admin_application_service import AdminApplicationService


router = APIRouter(prefix="/admin/applications", tags=["Admin Application Audit"])


@router.get("", response_model=AdminApplicationListResponse, summary="List applications for read-only admin audit")
def list_applications_for_admin(
    search: str | None = Query(default=None, max_length=200),
    application_status: JobApplicationStatus | None = Query(default=None, alias="status"),
    job_id: uuid.UUID | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    recruiter_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminApplicationService(db).list_applications(
        application_status, search, job_id, candidate_id, recruiter_id, page, page_size
    )


@router.get("/{application_id}", response_model=AdminApplicationDetail, summary="Get an application for read-only admin audit")
def get_application_for_admin(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminApplicationService(db).get_application(application_id)
