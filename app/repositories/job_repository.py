"""
Job repository — database access layer (Task 04).
Only handles approved public jobs for listing/search.
"""
import math
import uuid
from typing import Optional, Tuple, List

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus, EmploymentType, ExperienceLevel
from app.schemas.job import JobSortOption


# ── Sort helpers ──────────────────────────────────────────────────────────────

def _apply_sort(query, sort: JobSortOption):
    if sort == JobSortOption.newest:
        return query.order_by(Job.created_at.desc())
    elif sort == JobSortOption.oldest:
        return query.order_by(Job.created_at.asc())
    elif sort == JobSortOption.salary_high:
        return query.order_by(Job.salary_max.desc().nulls_last(), Job.created_at.desc())
    elif sort == JobSortOption.salary_low:
        return query.order_by(Job.salary_min.asc().nulls_last(), Job.created_at.desc())
    return query.order_by(Job.created_at.desc())


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
        if keyword:
            kw = f"%{keyword.strip()}%"
            q = q.filter(
                or_(
                    Job.title.ilike(kw),
                    Job.description.ilike(kw),
                    Job.company_name.ilike(kw),
                    # Convert ARRAY to searchable string
                    func.array_to_string(Job.skills, " ").ilike(kw),
                )
            )

        if location:
            q = q.filter(Job.location.ilike(f"%{location.strip()}%"))

        if employment_type:
            q = q.filter(Job.employment_type == employment_type)

        if experience_level:
            q = q.filter(Job.experience_level == experience_level)

        if salary_min is not None:
            # Job must pay at least salary_min
            q = q.filter(
                (Job.salary_max >= salary_min) | (Job.salary_min >= salary_min)
            )

        if salary_max is not None:
            # Job must be within budget
            q = q.filter(
                (Job.salary_min <= salary_max) | (Job.salary_max <= salary_max)
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
