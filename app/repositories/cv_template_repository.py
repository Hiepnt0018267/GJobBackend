import uuid

from sqlalchemy.orm import Session

from app.models.cv_template import CVTemplate


class CVTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> list[CVTemplate]:
        return (
            self.db.query(CVTemplate)
            .filter(CVTemplate.is_active.is_(True))
            .order_by(CVTemplate.sort_order.asc(), CVTemplate.created_at.asc(), CVTemplate.id.asc())
            .all()
        )

    def get_by_id(self, template_id: uuid.UUID) -> CVTemplate | None:
        return self.db.query(CVTemplate).filter(CVTemplate.id == template_id).first()

    def get_active_by_id(self, template_id: uuid.UUID) -> CVTemplate | None:
        return (
            self.db.query(CVTemplate)
            .filter(CVTemplate.id == template_id, CVTemplate.is_active.is_(True))
            .first()
        )

