import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.cv import CV
from app.models.user import User


class AdminCVRepository:
    """Read-only persistence queries for candidate-CV audit."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _audit_loads():
        return (joinedload(CV.candidate), joinedload(CV.template))

    def list_cvs(
        self,
        search: str | None,
        template_id: uuid.UUID | None,
        candidate_id: uuid.UUID | None,
        is_default: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CV], int]:
        query = self.db.query(CV)
        if template_id is not None:
            query = query.filter(CV.template_id == template_id)
        if candidate_id is not None:
            query = query.filter(CV.candidate_id == candidate_id)
        if is_default is not None:
            query = query.filter(CV.is_default.is_(is_default))
        if search:
            search_pattern = f"%{search}%"
            query = query.join(CV.candidate).filter(
                or_(CV.title.ilike(search_pattern), User.full_name.ilike(search_pattern), User.email.ilike(search_pattern))
            )

        total = query.count()
        items = (
            query.options(*self._audit_loads())
            .order_by(CV.updated_at.desc(), CV.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, cv_id: uuid.UUID) -> CV | None:
        return self.db.query(CV).options(*self._audit_loads()).filter(CV.id == cv_id).first()
