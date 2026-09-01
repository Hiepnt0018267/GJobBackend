import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.cv import CV


class CVRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_candidate(self, candidate_id: uuid.UUID) -> list[CV]:
        return (
            self.db.query(CV).options(joinedload(CV.template))
            .filter(CV.candidate_id == candidate_id)
            .order_by(CV.is_default.desc(), CV.updated_at.desc())
            .all()
        )

    def get_for_candidate(self, cv_id: uuid.UUID, candidate_id: uuid.UUID) -> CV | None:
        return (
            self.db.query(CV).options(joinedload(CV.template))
            .filter(CV.id == cv_id, CV.candidate_id == candidate_id)
            .first()
        )

    def has_for_candidate(self, candidate_id: uuid.UUID) -> bool:
        return self.db.query(CV.id).filter(CV.candidate_id == candidate_id).first() is not None

    def get_newest_for_candidate(self, candidate_id: uuid.UUID) -> CV | None:
        return (
            self.db.query(CV)
            .filter(CV.candidate_id == candidate_id)
            .order_by(CV.created_at.desc(), CV.id.desc())
            .first()
        )

    def add(self, cv: CV) -> None:
        self.db.add(cv)

    def delete(self, cv: CV) -> None:
        self.db.delete(cv)
        self.db.flush()

    def clear_default(self, candidate_id: uuid.UUID) -> None:
        self.db.query(CV).filter(CV.candidate_id == candidate_id, CV.is_default.is_(True)).update(
            {CV.is_default: False}, synchronize_session="fetch"
        )

    def commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, cv: CV) -> CV:
        self.db.refresh(cv)
        return cv
