"""Candidate-only cache-backed job recommendation endpoint."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.job import (
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    JobLevel,
    SalaryType,
    WorkMode,
)
from app.models.user import User, UserRole
from app.schemas.job_recommendation import CandidateJobRecommendationListResponse
from app.services.job_recommendation_service import CandidateJobRecommendationService


router = APIRouter(prefix="/candidate/jobs", tags=["Candidate Job Recommendations"])


@router.get(
    "/recommendations",
    response_model=CandidateJobRecommendationListResponse,
    summary="List cache-backed job recommendations for the current candidate",
)
def list_candidate_job_recommendations(
    cv_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    keyword: str | None = Query(default=None, max_length=200, include_in_schema=False),
    location: str | None = Query(default=None, max_length=255),
    employment_type: EmploymentType | None = Query(default=None),
    experience_level: ExperienceLevel | None = Query(default=None),
    industry: Industry | None = Query(default=None),
    experience_requirement: ExperienceRequirement | None = Query(default=None),
    level: JobLevel | None = Query(default=None),
    work_mode: WorkMode | None = Query(default=None),
    salary_type: SalaryType | None = Query(default=None),
    salary_min: int | None = Query(default=None, ge=0),
    salary_max: int | None = Query(default=None, ge=0),
    skill: str | None = Query(default=None, max_length=255),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    ranking_snapshot: str | None = Query(default=None, pattern="^[0-9a-f]{32}$"),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="salary_min must be less than or equal to salary_max",
        )
    effective_keyword = search if search and search.strip() else keyword
    filters = {
        "keyword": effective_keyword,
        "location": location,
        "employment_type": employment_type,
        "experience_level": experience_level,
        "industry": industry,
        "experience_requirement": experience_requirement,
        "level": level,
        "work_mode": work_mode,
        "salary_type": salary_type,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "skill": skill,
    }
    return CandidateJobRecommendationService(db).list(
        candidate_id=current_user.id,
        cv_id=cv_id,
        filters=filters,
        page=page,
        page_size=page_size,
        snapshot=ranking_snapshot,
    )
