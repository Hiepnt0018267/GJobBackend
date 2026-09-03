"""
Job repository — database access layer (Task 04).
Only handles approved public jobs for listing/search.
"""
import math
import uuid
from typing import Optional, Tuple, List

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.job import (
    Job,
    JobStatus,
    EmploymentType,
    ExperienceLevel,
    ExperienceRequirement,
    Industry,
    JobLevel,
    SalaryType,
    WorkMode,
)
from app.schemas.job import JobSortOption, RecruiterJobSortOption


# ── Sort helpers ──────────────────────────────────────────────────────────────

def _apply_sort(query, sort: JobSortOption):
    if sort == JobSortOption.newest:
        return query.order_by(Job.created_at.desc(), Job.id.desc())
    elif sort == JobSortOption.oldest:
        return query.order_by(Job.created_at.asc(), Job.id.asc())
    elif sort == JobSortOption.salary_high:
        return query.order_by(func.coalesce(Job.salary_max, Job.salary_fixed).desc().nulls_last(), Job.created_at.desc(), Job.id.desc())
    elif sort == JobSortOption.salary_low:
        return query.order_by(func.coalesce(Job.salary_min, Job.salary_fixed).asc().nulls_last(), Job.created_at.desc(), Job.id.desc())
    return query.order_by(Job.created_at.desc(), Job.id.desc())


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Public listing ────────────────────────────────────────────────────────

    def get_public_jobs(
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
    ) -> Tuple[List[Job], int]:
        """
        Return (items, total) for the public job listing.
        Only APPROVED jobs are returned.
        """
        q = self.db.query(Job).filter(Job.status == JobStatus.APPROVED)

        # Keyword: search in title, description, company_name, skills array
        normalized_keyword = keyword.strip() if keyword else ""
        if normalized_keyword:
            kw = f"%{normalized_keyword}%"
            q = q.filter(
                or_(
                    Job.title.ilike(kw),
                    Job.description.ilike(kw),
                    Job.company_name.ilike(kw),
                    # Convert ARRAY to searchable string
                    func.array_to_string(Job.skills, " ").ilike(kw),
                )
            )

        normalized_location = location.strip() if location else ""
        if normalized_location:
            q = q.filter(Job.location.ilike(f"%{normalized_location}%"))

        if employment_type:
            q = q.filter(Job.employment_type == employment_type)

        if experience_level:
            q = q.filter(Job.experience_level == experience_level)

        if industry:
            q = q.filter(Job.industry == industry)

        if experience_requirement:
            q = q.filter(Job.experience_requirement == experience_requirement)

        if level:
            q = q.filter(Job.level == level)

        if work_mode:
            q = q.filter(Job.work_mode == work_mode)

        if salary_type:
            q = q.filter(Job.salary_type == salary_type)

        if salary_min is not None:
            q = q.filter(
                or_(
                    and_(Job.salary_type == SalaryType.RANGE, Job.salary_max >= salary_min),
                    and_(Job.salary_type == SalaryType.FIXED, Job.salary_fixed >= salary_min),
                    and_(Job.salary_type.is_(None), Job.salary_max >= salary_min),
                )
            )

        if salary_max is not None:
            q = q.filter(
                or_(
                    and_(Job.salary_type == SalaryType.RANGE, Job.salary_min <= salary_max),
                    and_(Job.salary_type == SalaryType.FIXED, Job.salary_fixed <= salary_max),
                    and_(Job.salary_type.is_(None), Job.salary_min <= salary_max),
                )
            )

        total = q.count()
        q = _apply_sort(q, sort)
        offset = (page - 1) * page_size
        items = q.offset(offset).limit(page_size).all()
        return items, total

    # ── Public detail ─────────────────────────────────────────────────────────

    def get_by_id_public(self, job_id: uuid.UUID) -> Optional[Job]:
        """
        Return job by ID only if publicly viewable (APPROVED or CLOSED).
        PENDING and REJECTED are never returned.
        """
        return (
            self.db.query(Job)
            .filter(
                Job.id == job_id,
                Job.status.in_([JobStatus.APPROVED, JobStatus.CLOSED]),
            )
            .first()
        )

    # ── Internal helpers (for tests and future tasks) ─────────────────────────

    def get_by_id(self, job_id: uuid.UUID) -> Optional[Job]:
        """Get job by ID regardless of status (internal use)."""
        return self.db.query(Job).filter(Job.id == job_id).first()

    def create(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    # ── Recruiter management ─────────────────────────────────────────────────

    def get_for_recruiter(self, job_id: uuid.UUID, recruiter_id: uuid.UUID) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == job_id, Job.recruiter_id == recruiter_id).first()

    def get_recruiter_jobs(
        self, recruiter_id: uuid.UUID, keyword: Optional[str], job_status: Optional[JobStatus],
        page: int, page_size: int, sort: RecruiterJobSortOption,
    ) -> Tuple[List[Job], int]:
        q = self.db.query(Job).filter(Job.recruiter_id == recruiter_id)
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(or_(Job.title.ilike(kw), Job.company_name.ilike(kw), Job.description.ilike(kw)))
        if job_status:
            q = q.filter(Job.status == job_status)
        total = q.count()
        if sort == RecruiterJobSortOption.oldest:
            q = q.order_by(Job.created_at.asc())
        elif sort == RecruiterJobSortOption.updated:
            q = q.order_by(Job.updated_at.desc())
        else:
            q = q.order_by(Job.created_at.desc())
        return q.offset((page - 1) * page_size).limit(page_size).all(), total

    def save(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete(self, job: Job) -> None:
        self.db.delete(job)
        self.db.commit()
