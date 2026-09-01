import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cv import CV
from app.models.user import User
from app.repositories.cv_repository import CVRepository
from app.services.cv_template_service import CVTemplateService
from app.schemas.cv import CVCreateRequest, CVListResponse, CVResponse, CVUpdateRequest


class CVService:
    def __init__(self, db: Session) -> None:
        self.repository = CVRepository(db)
        self.template_service = CVTemplateService(db)

    def _owned_or_404(self, user: User, cv_id: uuid.UUID) -> CV:
        cv = self.repository.get_for_candidate(cv_id, user.id)
        if cv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV not found.")
        return cv

    def list_cvs(self, user: User) -> CVListResponse:
        items = self.repository.list_for_candidate(user.id)
        return CVListResponse(items=items, total=len(items))

    def get_cv(self, user: User, cv_id: uuid.UUID) -> CV:
        return self._owned_or_404(user, cv_id)

    def create_cv(self, user: User, payload: CVCreateRequest) -> CV:
        self.template_service.require_active_template(payload.template_id)
        values = payload.model_dump(mode="json")
        cv = CV(
            **values,
            candidate_id=user.id,
            is_default=not self.repository.has_for_candidate(user.id),
        )
        self.repository.add(cv)
        self.repository.commit()
        return self.repository.refresh(cv)

    def update_cv(self, user: User, cv_id: uuid.UUID, payload: CVUpdateRequest) -> CV:
        cv = self._owned_or_404(user, cv_id)
        changes = payload.model_dump(exclude_unset=True, mode="json")
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one editable field.",
            )
        if "template_id" in changes:
            template_id = changes["template_id"]
            if template_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="template_id cannot be null.",
                )
            self.template_service.require_active_template(template_id)
        for field, value in changes.items():
            # JSONB section columns are non-null and an explicit null resets a section.
            if field == "personal_info" and value is None:
                value = {}
            elif field in {"educations", "experiences", "skills", "projects", "certificates", "languages"} and value is None:
                value = []
            setattr(cv, field, value)
        self.repository.commit()
        return self.repository.refresh(cv)

    def set_default_cv(self, user: User, cv_id: uuid.UUID) -> CV:
        cv = self._owned_or_404(user, cv_id)
        self.repository.clear_default(user.id)
        cv.is_default = True
        self.repository.commit()
        return self.repository.refresh(cv)

    def delete_cv(self, user: User, cv_id: uuid.UUID) -> None:
        cv = self._owned_or_404(user, cv_id)
        was_default = cv.is_default
        try:
            self.repository.delete(cv)
            if was_default:
                replacement = self.repository.get_newest_for_candidate(user.id)
                if replacement is not None:
                    replacement.is_default = True
            self.repository.commit()
        except IntegrityError as exc:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CV is used by an application and cannot be deleted.",
            ) from exc
