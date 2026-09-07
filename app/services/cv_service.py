import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cv import CV, CVSourceType
from app.models.user import User
from app.repositories.cv_repository import CVRepository
from app.services.cv_template_service import CVTemplateService
from app.schemas.cv import CVCreateRequest, CVListResponse, CVResponse, CVUpdateRequest
from app.services.cv_storage_service import CVFileValidationError, CVStorageService


class CVService:
    def __init__(self, db: Session) -> None:
        self.repository = CVRepository(db)
        self.template_service = CVTemplateService(db)
        self.storage = CVStorageService()

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

    async def upload_cv(self, user: User, title: str, upload: UploadFile) -> CV:
        normalized_title = title.strip()
        if not normalized_title:
            await upload.close()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CV title must not be blank.",
            )

        try:
            stored_file = await self.storage.store_upload(user.id, upload)
        except CVFileValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

        cv = CV(
            candidate_id=user.id,
            source_type=CVSourceType.UPLOADED,
            title=normalized_title,
            is_default=not self.repository.has_for_candidate(user.id),
            storage_key=stored_file.storage_key,
            original_filename=stored_file.original_filename,
            mime_type=stored_file.mime_type,
            file_size=stored_file.file_size,
            uploaded_at=datetime.now(timezone.utc),
        )
        self.repository.add(cv)
        try:
            self.repository.commit()
        except Exception:
            self.storage.delete_file(stored_file.storage_key)
            raise
        return self.repository.refresh(cv)

    def update_cv(self, user: User, cv_id: uuid.UUID, payload: CVUpdateRequest) -> CV:
        cv = self._owned_or_404(user, cv_id)
        changes = payload.model_dump(exclude_unset=True, mode="json")
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide at least one editable field.",
            )
        if cv.source_type == CVSourceType.UPLOADED and set(changes) - {"title"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Uploaded CV files cannot be replaced or edited as Builder CV content.",
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
        storage_key = cv.storage_key
        photo_storage_key = cv.photo_storage_key
        try:
            self.repository.delete(cv)
            if was_default:
                replacement = self.repository.get_newest_for_candidate(user.id)
                if replacement is not None:
                    replacement.is_default = True
            self.repository.commit()
            self.storage.delete_file(storage_key)
            self.storage.delete_file(photo_storage_key)
        except IntegrityError as exc:
            self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CV is used by an application and cannot be deleted.",
            ) from exc

    def get_uploaded_file_path(self, cv: CV):
        if cv.source_type != CVSourceType.UPLOADED:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This CV does not have an uploaded file.")
        try:
            return self.storage.get_file_path(cv.storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded CV file not found.") from exc

    async def upload_photo(self, user: User, cv_id: uuid.UUID, upload: UploadFile) -> CV:
        cv = self._owned_or_404(user, cv_id)
        if cv.source_type != CVSourceType.BUILDER:
            await upload.close()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only Builder CVs support a managed photo.")
        try:
            new_key = await self.storage.store_photo(user.id, upload)
        except CVFileValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        old_key = cv.photo_storage_key
        cv.photo_storage_key = new_key
        try:
            self.repository.commit()
        except Exception:
            self.storage.delete_file(new_key)
            raise
        self.storage.delete_file(old_key)
        return self.repository.refresh(cv)

    def delete_photo(self, user: User, cv_id: uuid.UUID) -> CV:
        cv = self._owned_or_404(user, cv_id)
        if cv.source_type != CVSourceType.BUILDER:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only Builder CVs support a managed photo.")
        old_key = cv.photo_storage_key
        cv.photo_storage_key = None
        self.repository.commit()
        self.storage.delete_file(old_key)
        return self.repository.refresh(cv)

    def get_photo_path(self, cv: CV):
        if cv.source_type != CVSourceType.BUILDER or not cv.photo_storage_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV photo not found.")
        try:
            return self.storage.get_file_path(cv.photo_storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV photo not found.") from exc
