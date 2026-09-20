"""Persistence operations for current CV/job match records."""

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.cv import CV
from app.models.cv_job_match import CVJobMatch
from app.models.job import Job


class CVJobMatchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_pair(
        self,
        cv_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> CVJobMatch | None:
        return (
            self.db.query(CVJobMatch)
            .filter(CVJobMatch.cv_id == cv_id, CVJobMatch.job_id == job_id)
            .first()
        )

    def lock_sources(self, cv_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        cv_exists = (
            self.db.query(CV.id)
            .filter(CV.id == cv_id)
            .with_for_update()
            .first()
            is not None
        )
        job_exists = (
            self.db.query(Job.id)
            .filter(Job.id == job_id)
            .with_for_update()
            .first()
            is not None
        )
        return cv_exists and job_exists

    def upsert(self, values: dict[str, object]) -> CVJobMatch:
        update_values = {
            key: value
            for key, value in values.items()
            if key not in {"id", "cv_id", "job_id", "created_at"}
        }
        statement = (
            insert(CVJobMatch)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_cv_job_matches_cv_job",
                set_=update_values,
            )
            .returning(CVJobMatch)
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(statement).one()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
