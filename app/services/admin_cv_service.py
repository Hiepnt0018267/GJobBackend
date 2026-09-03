import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.admin_cv_repository import AdminCVRepository
from app.schemas.admin_cv import AdminCVDetail, AdminCVListItem, AdminCVListResponse


class AdminCVService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminCVRepository(db)

    def list_cvs(self, search: str | None, template_id: uuid.UUID | None, candidate_id: uuid.UUID | None, is_default: bool | None, page: int, page_size: int) -> AdminCVListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_cvs(normalized_search, template_id, candidate_id, is_default, page, page_size)
        return AdminCVListResponse(items=[AdminCVListItem.model_validate(item) for item in items], page=page, page_size=page_size, total=total, total_pages=math.ceil(total / page_size) if total else 0)

    def get_cv(self, cv_id: uuid.UUID) -> AdminCVDetail:
        cv = self.repository.get_by_id(cv_id)
        if cv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
        return AdminCVDetail.model_validate(cv)
