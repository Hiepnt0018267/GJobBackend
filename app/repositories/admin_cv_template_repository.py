import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.cv import CV
from app.models.cv_template import CVTemplate


class AdminCVTemplateRepository:
    """Database access for the admin CV-template catalog only."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _usage_count_column():
        return (
            select(func.count(CV.id))
            .where(CV.template_id == CVTemplate.id)
            .correlate(CVTemplate)
            .scalar_subquery()
            .label("usage_count")
        )

    def list_templates(
        self,
        search: str | None,
        is_active: bool | None,
        is_featured: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[CVTemplate, int]], int]:
        base_query = self.db.query(CVTemplate).filter(CVTemplate.is_deleted.is_(False))
        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.filter(
                or_(CVTemplate.name.ilike(search_pattern), CVTemplate.description.ilike(search_pattern))
            )
        if is_active is not None:
            base_query = base_query.filter(CVTemplate.is_active.is_(is_active))
        if is_featured is not None:
            base_query = base_query.filter(CVTemplate.is_featured.is_(is_featured))

        total = base_query.count()
        usage_count = self._usage_count_column()
        items = (
            base_query.with_entities(CVTemplate, usage_count)
            .order_by(
                CVTemplate.is_featured.desc(),
                CVTemplate.sort_order.asc(),
                CVTemplate.created_at.asc(),
                CVTemplate.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_template_with_usage(self, template_id: uuid.UUID) -> tuple[CVTemplate, int] | None:
        usage_count = self._usage_count_column()
        return (
            self.db.query(CVTemplate, usage_count)
            .filter(CVTemplate.id == template_id, CVTemplate.is_deleted.is_(False))
            .first()
        )

    def create(self, template: CVTemplate) -> CVTemplate:
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def update_metadata(self, template: CVTemplate, fields: dict[str, object]) -> CVTemplate:
        for field, value in fields.items():
            setattr(template, field, value)
        self.db.commit()
        self.db.refresh(template)
        return template

    def archive(self, template: CVTemplate) -> None:
        template.is_deleted = True
        template.is_active = False
        template.is_featured = False
        self.db.commit()

    def transition_active_status(
        self,
        template_id: uuid.UUID,
        *,
        expected_current_status: bool,
        target_status: bool,
        clear_featured: bool = False,
    ) -> bool:
        values: dict[object, object] = {
            CVTemplate.is_active: target_status,
            CVTemplate.updated_at: func.now(),
        }
        if clear_featured:
            values[CVTemplate.is_featured] = False
        affected_rows = (
            self.db.query(CVTemplate)
            .filter(CVTemplate.id == template_id, CVTemplate.is_deleted.is_(False), CVTemplate.is_active.is_(expected_current_status))
            .update(values, synchronize_session=False)
        )
        if affected_rows == 0:
            return False
        self.db.commit()
        return True

    def transition_featured_status(
        self,
        template_id: uuid.UUID,
        *,
        expected_current_status: bool,
        target_status: bool,
    ) -> bool:
        affected_rows = (
            self.db.query(CVTemplate)
            .filter(
                CVTemplate.id == template_id,
                CVTemplate.is_deleted.is_(False),
                CVTemplate.is_active.is_(True),
                CVTemplate.is_featured.is_(expected_current_status),
            )
            .update(
                {CVTemplate.is_featured: target_status, CVTemplate.updated_at: func.now()},
                synchronize_session=False,
            )
        )
        if affected_rows == 0:
            return False
        self.db.commit()
        return True
