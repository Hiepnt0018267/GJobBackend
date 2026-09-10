import math
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.cv_template import CVTemplate, CVTemplateLayoutKey, default_cv_template_theme_config
from app.models.user import User
from app.repositories.admin_audit_log_repository import AdminAuditLogRepository
from app.repositories.admin_cv_template_repository import AdminCVTemplateRepository
from app.schemas.admin_cv_template import (
    AdminCVTemplateCreate,
    AdminCVTemplateListResponse,
    AdminCVTemplateResponse,
    AdminCVTemplateUpdate,
)
from app.services.cv_storage_service import CVFileValidationError, CVStorageService


class AdminCVTemplateService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminCVTemplateRepository(db)
        self.audit_repository = AdminAuditLogRepository(db)
        self.storage = CVStorageService()

    def list_templates(
        self,
        search: str | None,
        is_active: bool | None,
        is_featured: bool | None,
        page: int,
        page_size: int,
    ) -> AdminCVTemplateListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_templates(normalized_search, is_active, is_featured, page, page_size)
        return AdminCVTemplateListResponse(
            items=[self._to_response(template, usage_count) for template, usage_count in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_template(self, template_id: uuid.UUID) -> AdminCVTemplateResponse:
        template, usage_count = self._get_template_or_404(template_id)
        return self._to_response(template, usage_count)

    def create_template(self, payload: AdminCVTemplateCreate, current_user: User) -> AdminCVTemplateResponse:
        if payload.is_featured and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Inactive CV templates cannot be featured.",
            )
        values = payload.model_dump()
        values["thumbnail_url"] = str(payload.thumbnail_url) if payload.thumbnail_url else None
        values["theme_config"] = (
            payload.theme_config.model_dump(mode="json")
            if payload.theme_config is not None
            else default_cv_template_theme_config(payload.layout_key)
        )
        template = self.repository.create(CVTemplate(**values))
        self._commit_audit(current_user, "CV_TEMPLATE_CREATED", template.id)
        return self.get_template(template.id)

    def update_template_metadata(
        self,
        template_id: uuid.UUID,
        payload: AdminCVTemplateUpdate,
        current_user: User,
    ) -> AdminCVTemplateResponse:
        template, usage_count = self._get_template_or_404(template_id)
        fields = payload.model_dump(exclude_unset=True)
        if "thumbnail_url" in fields:
            fields["thumbnail_url"] = str(payload.thumbnail_url) if payload.thumbnail_url else None
        if "theme_config" in fields:
            fields["theme_config"] = payload.theme_config.model_dump(mode="json")
        requested_layout_key = fields.get("layout_key")
        if (
            requested_layout_key is not None
            and requested_layout_key != template.layout_key
            and usage_count > 0
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Không thể thay đổi bố cục của mẫu CV đang được sử dụng.",
            )
        self.repository.update_metadata(template, fields)
        self._commit_audit(
            current_user,
            "CV_TEMPLATE_UPDATED",
            template.id,
            {"changed_fields": sorted(fields)},
        )
        return self.get_template(template_id)

    def activate_template(self, template_id: uuid.UUID, current_user: User) -> AdminCVTemplateResponse:
        if self.repository.transition_active_status(
            template_id,
            expected_current_status=False,
            target_status=True,
        ):
            self._commit_audit(current_user, "CV_TEMPLATE_ACTIVATED", template_id)
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if template.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV đã ở trạng thái hoạt động.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def deactivate_template(self, template_id: uuid.UUID, current_user: User) -> AdminCVTemplateResponse:
        if self.repository.transition_active_status(
            template_id,
            expected_current_status=True,
            target_status=False,
            clear_featured=True,
        ):
            self._commit_audit(current_user, "CV_TEMPLATE_DEACTIVATED", template_id)
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if not template.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV đã ngừng hoạt động.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def feature_template(self, template_id: uuid.UUID, current_user: User) -> AdminCVTemplateResponse:
        if self.repository.transition_featured_status(
            template_id,
            expected_current_status=False,
            target_status=True,
        ):
            self._commit_audit(current_user, "CV_TEMPLATE_FEATURED", template_id)
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if not template.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ mẫu CV đang hoạt động mới có thể được đánh dấu nổi bật.",
            )
        if template.is_featured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV đã được đánh dấu nổi bật.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def unfeature_template(self, template_id: uuid.UUID, current_user: User) -> AdminCVTemplateResponse:
        if self.repository.transition_featured_status(
            template_id,
            expected_current_status=True,
            target_status=False,
        ):
            self._commit_audit(current_user, "CV_TEMPLATE_UNFEATURED", template_id)
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if not template.is_featured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV chưa được đánh dấu nổi bật.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def delete_template(self, template_id: uuid.UUID, current_user: User) -> None:
        template, usage_count = self._get_template_or_404(template_id)
        if usage_count > 0 and template.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Deactivate a template that is already in use before deleting it.",
            )
        self.repository.archive(template)
        self._commit_audit(current_user, "CV_TEMPLATE_DELETED", template_id)

    async def upload_thumbnail(
        self,
        template_id: uuid.UUID,
        upload: UploadFile,
        current_user: User,
    ) -> AdminCVTemplateResponse:
        template, _ = self._get_template_or_404(template_id)
        try:
            new_key, original_filename = await self.storage.store_template_thumbnail(template.id, upload)
        except CVFileValidationError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        old_key = template.thumbnail_storage_key
        template.thumbnail_storage_key = new_key
        template.thumbnail_original_filename = original_filename
        try:
            self._commit_audit(current_user, "CV_TEMPLATE_THUMBNAIL_UPLOADED", template_id)
        except Exception:
            self.storage.delete_file(new_key)
            raise
        self.storage.delete_file(old_key)
        return self.get_template(template_id)

    def delete_thumbnail(self, template_id: uuid.UUID, current_user: User) -> AdminCVTemplateResponse:
        template, _ = self._get_template_or_404(template_id)
        old_key = template.thumbnail_storage_key
        template.thumbnail_storage_key = None
        template.thumbnail_original_filename = None
        self._commit_audit(current_user, "CV_TEMPLATE_THUMBNAIL_DELETED", template_id)
        self.storage.delete_file(old_key)
        return self.get_template(template_id)

    def get_thumbnail_path(self, template_id: uuid.UUID):
        template, _ = self._get_template_or_404(template_id)
        try:
            return self.storage.get_file_path(template.thumbnail_storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV template thumbnail not found.") from exc

    def _get_template_or_404(self, template_id: uuid.UUID) -> tuple[CVTemplate, int]:
        result = self.repository.get_template_with_usage(template_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV template not found.")
        return result

    def _commit_audit(
        self,
        current_user: User,
        action: str,
        template_id: uuid.UUID,
        metadata: dict[str, object] | None = None,
    ) -> None:
        try:
            self.audit_repository.add(
                admin_user_id=current_user.id,
                action=action,
                entity_type="CV_TEMPLATE",
                entity_id=template_id,
                metadata=metadata,
            )
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise

    @staticmethod
    def _to_response(template: CVTemplate, usage_count: int) -> AdminCVTemplateResponse:
        return AdminCVTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            layout_key=template.layout_key,
            theme_config=template.theme_config,
            thumbnail_url=(f"/api/v1/cv-templates/{template.id}/thumbnail?v={int(template.updated_at.timestamp())}" if template.thumbnail_storage_key else template.thumbnail_url),
            thumbnail_original_filename=template.thumbnail_original_filename,
            is_active=template.is_active,
            is_featured=template.is_featured,
            sort_order=template.sort_order,
            created_at=template.created_at,
            updated_at=template.updated_at,
            usage_count=usage_count,
        )
