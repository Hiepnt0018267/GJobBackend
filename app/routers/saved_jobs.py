import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.saved_job import SavedJobListResponse, SavedJobStatusResponse
from app.services.saved_job_service import SavedJobService


router = APIRouter(prefix="/candidate/saved-jobs", tags=["Candidate Saved Jobs"])


@router.get("", response_model=SavedJobListResponse, summary="List current candidate's saved jobs")
def list_my_saved_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return SavedJobService(db).list_saved_jobs(current_user, page, page_size)


@router.get(
    "/by-job/{job_id}",
    response_model=SavedJobStatusResponse,
    summary="Get current candidate's saved status for a job",
)
def get_my_saved_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return SavedJobService(db).get_status(current_user, job_id)


@router.post(
    "/{job_id}",
    response_model=SavedJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Save an approved job",
)
def save_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return SavedJobService(db).save_job(current_user, job_id)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a job from current candidate's saved jobs",
)
def unsave_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    SavedJobService(db).unsave_job(current_user, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
