"""
Job router — public endpoints (Task 04).
No authentication required for listing or detail.
Query parameters are declared via FastAPI Query() for proper 422 handling.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import (
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    JobLevel,
    SalaryType,
    WorkMode,
)
from app.schemas.job import JobDetailResponse, JobListResponse, JobSortOption
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List / search / filter jobs (public)",
)
def list_jobs(
    search: Optional[str] = Query(None, description="Search in title, description, company, skills"),
    keyword: Optional[str] = Query(None, include_in_schema=False, description="Deprecated alias for search"),
    location: Optional[str] = Query(None, description="Partial match on location"),
    employment_type: Optional[EmploymentType] = Query(None),
    experience_level: Optional[ExperienceLevel] = Query(None),
    industry: Optional[Industry] = Query(None),
    experience_requirement: Optional[ExperienceRequirement] = Query(None),
    level: Optional[JobLevel] = Query(None),
    work_mode: Optional[WorkMode] = Query(None),
    salary_type: Optional[SalaryType] = Query(None),
    salary_min: Optional[int] = Query(None, ge=0, description="Minimum salary filter"),
    salary_max: Optional[int] = Query(None, ge=0, description="Maximum salary filter"),
    skill: Optional[str] = Query(None, max_length=255, description="Exact normalized skill filter"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    sort: JobSortOption = Query(JobSortOption.newest, description="Sort order"),
    db: Session = Depends(get_db),
):
    """
    Public job listing with search and filtering.

    Only **APPROVED** jobs are returned.

    **Sort options:** newest | oldest | salary_high | salary_low
    """
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="salary_min must be less than or equal to salary_max",
        )

    service = JobService(db)
    return service.list_jobs(
        keyword=search if search and search.strip() else keyword,
        location=location,
        employment_type=employment_type,
        experience_level=experience_level,
        industry=industry,
        experience_requirement=experience_requirement,
        level=level,
        work_mode=work_mode,
        salary_type=salary_type,
        salary_min=salary_min,
        salary_max=salary_max,
        skill=skill,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job detail (public)",
)
def get_job_detail(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Return full detail for a single job.
    Returns **404** if the job does not exist or is PENDING/REJECTED.
    """
    service = JobService(db)
    return service.get_job_detail(job_id)
