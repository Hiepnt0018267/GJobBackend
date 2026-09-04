import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.application import JobApplicationStatus
from app.models.user import User, UserRole
from app.schemas.recruiter_application import (
    RecruiterApplicationDetail,
    RecruiterApplicationListResponse,
)
from app.services.recruiter_application_service import RecruiterApplicationService


router = APIRouter(prefix="/recruiters", tags=["Recruiter Applications"])


@router.get("/applications", response_model=RecruiterApplicationListResponse, summary="List applications for recruiter-owned jobs")
def list_recruiter_applications(
    search: str | None = Query(default=None, max_length=200),
    application_status: JobApplicationStatus | None = Query(default=None, alias="status"),
    job_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return RecruiterApplicationService(db).list_applications(
        current_user, application_status, search, job_id, page, page_size
    )


@router.get("/jobs/{job_id}/applications", response_model=RecruiterApplicationListResponse, summary="List applications for one recruiter-owned job")
def list_recruiter_job_applications(
    job_id: uuid.UUID,
    search: str | None = Query(default=None, max_length=200),
    application_status: JobApplicationStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return RecruiterApplicationService(db).list_job_applications(
        current_user, job_id, application_status, search, page, page_size
    )


@router.get("/applications/{application_id}", response_model=RecruiterApplicationDetail, summary="Get an application for a recruiter-owned job")
def get_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return RecruiterApplicationService(db).get_application(current_user, application_id)


def _transition(application_id: uuid.UUID, action: str, current_user: User, db: Session):
    return RecruiterApplicationService(db).transition_application(current_user, application_id, action)


@router.patch("/applications/{application_id}/review", response_model=RecruiterApplicationDetail, summary="Move a submitted application to reviewing")
def review_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return _transition(application_id, "review", current_user, db)


@router.patch("/applications/{application_id}/shortlist", response_model=RecruiterApplicationDetail, summary="Move a reviewing application to shortlisted")
def shortlist_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return _transition(application_id, "shortlist", current_user, db)


@router.patch("/applications/{application_id}/reject", response_model=RecruiterApplicationDetail, summary="Reject an active application")
def reject_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return _transition(application_id, "reject", current_user, db)


@router.patch("/applications/{application_id}/hire", response_model=RecruiterApplicationDetail, summary="Hire a shortlisted application")
def hire_recruiter_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
    db: Session = Depends(get_db),
):
    return _transition(application_id, "hire", current_user, db)
