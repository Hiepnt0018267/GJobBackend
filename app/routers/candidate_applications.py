import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.application import JobApplicationStatus
from app.models.user import User, UserRole
from app.schemas.application import (
    CandidateApplicationByJobResponse,
    CandidateApplicationDetail,
    CandidateApplicationListResponse,
)
from app.services.candidate_application_service import CandidateApplicationService


router = APIRouter(prefix="/candidate/applications", tags=["Candidate Applications"])


@router.get("", response_model=CandidateApplicationListResponse, summary="List current candidate's applications")
def list_my_applications(
    application_status: JobApplicationStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CandidateApplicationService(db).list_applications(
        current_user, application_status, search, page, page_size
    )


@router.get(
    "/by-job/{job_id}",
    response_model=CandidateApplicationByJobResponse,
    summary="Get current candidate's application status for a job",
)
def get_my_application_status_for_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CandidateApplicationService(db).get_application_status_for_job(current_user, job_id)


@router.get("/{application_id}", response_model=CandidateApplicationDetail, summary="Get a candidate-owned application")
def get_my_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CandidateApplicationService(db).get_application(current_user, application_id)


@router.patch(
    "/{application_id}/withdraw",
    response_model=CandidateApplicationDetail,
    summary="Withdraw a candidate-owned application",
)
def withdraw_my_application(
    application_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CandidateApplicationService(db).withdraw_application(current_user, application_id)
