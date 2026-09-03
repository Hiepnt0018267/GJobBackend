"""
Job service — business logic layer (Task 04).
"""
import math
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import EmploymentType, ExperienceLevel, ExperienceRequirement, Industry, JobLevel, SalaryType, WorkMode
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobListResponse, JobResponse, JobSortOption


class JobService:
    def __init__(self, db: Session) -> None:
        self.repo = JobRepository(db)

    def list_jobs(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        employment_type: Optional[EmploymentType] = None,
        experience_level: Optional[ExperienceLevel] = None,
        industry: Optional[Industry] = None,
        experience_requirement: Optional[ExperienceRequirement] = None,
        level: Optional[JobLevel] = None,
        work_mode: Optional[WorkMode] = None,
        salary_type: Optional[SalaryType] = None,
        salary_min: Optional[int] = None,
        salary_max: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
        sort: JobSortOption = JobSortOption.newest,
    ) -> JobListResponse:
        """Return paginated public job listing."""
        items, total = self.repo.get_public_jobs(
            keyword=keyword,
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
            page=page,
            page_size=page_size,
            sort=sort,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return JobListResponse(
            items=[JobResponse.model_validate(j) for j in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def get_job_detail(self, job_id: uuid.UUID) -> JobResponse:
        """Return job detail — 404 if not found or not publicly viewable."""
        job = self.repo.get_by_id_public(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found.",
            )
        return JobResponse.model_validate(job)
