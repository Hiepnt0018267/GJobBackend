import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.models.job import JobStatus
from app.schemas.job import JobCreateRequest, JobUpdateRequest, RecruiterJobListResponse, RecruiterJobResponse, RecruiterJobSortOption
from app.schemas.recruiter import RecruiterDashboardSummary, RecruiterProfileResponse, UpdateRecruiterProfileRequest
from app.services.recruiter_job_service import RecruiterJobService
from app.services.recruiter_service import RecruiterService

router = APIRouter(prefix="/recruiters", tags=["Recruiter Profile"])


@router.get("/me", response_model=RecruiterProfileResponse, status_code=status.HTTP_200_OK, summary="Get current recruiter profile")
def get_my_recruiter_profile(current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).get_profile(current_user)


@router.patch("/me", response_model=RecruiterProfileResponse, status_code=status.HTTP_200_OK, summary="Update current recruiter profile")
def update_my_recruiter_profile(payload: UpdateRecruiterProfileRequest, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).update_profile(current_user, payload)


@router.get("/me/dashboard", response_model=RecruiterDashboardSummary, status_code=status.HTTP_200_OK, summary="Get current recruiter dashboard summary")
def get_my_dashboard_summary(current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).dashboard_summary(current_user)


@router.get("/jobs", response_model=RecruiterJobListResponse, summary="List current recruiter's jobs")
def list_my_jobs(
    keyword: str | None = Query(default=None, max_length=255),
    job_status: JobStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort: RecruiterJobSortOption = Query(default=RecruiterJobSortOption.newest),
    current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db),
):
    return RecruiterJobService(db).list_jobs(current_user, keyword, job_status, page, page_size, sort)


@router.post("/jobs", response_model=RecruiterJobResponse, status_code=status.HTTP_201_CREATED, summary="Create recruiter job")
def create_my_job(payload: JobCreateRequest, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterJobService(db).create_job(current_user, payload)


@router.get("/jobs/{job_id}", response_model=RecruiterJobResponse, summary="Get a recruiter-owned job")
def get_my_job(job_id: uuid.UUID, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterJobService(db).get_job(current_user, job_id)


@router.patch("/jobs/{job_id}", response_model=RecruiterJobResponse, summary="Edit a recruiter-owned job")
def update_my_job(job_id: uuid.UUID, payload: JobUpdateRequest, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterJobService(db).update_job(current_user, job_id, payload)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a recruiter-owned job")
def delete_my_job(job_id: uuid.UUID, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    RecruiterJobService(db).delete_job(current_user, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/jobs/{job_id}/close", response_model=RecruiterJobResponse, summary="Close an approved recruiter-owned job")
def close_my_job(job_id: uuid.UUID, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterJobService(db).close_job(current_user, job_id)
