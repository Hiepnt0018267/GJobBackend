import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.cv_template import CVTemplate, CVTemplateLayoutKey, default_cv_template_theme_config
from app.repositories.admin_cv_template_repository import AdminCVTemplateRepository
from app.schemas.admin_cv_template import (
    AdminCVTemplateCreate,
    AdminCVTemplateListResponse,
    AdminCVTemplateResponse,
    AdminCVTemplateUpdate,
)


class AdminCVTemplateService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminCVTemplateRepository(db)

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

    def create_template(self, payload: AdminCVTemplateCreate) -> AdminCVTemplateResponse:
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
        return self.get_template(template.id)

    def update_template_metadata(
        self,
        template_id: uuid.UUID,
        payload: AdminCVTemplateUpdate,
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
        return self.get_template(template_id)

    def activate_template(self, template_id: uuid.UUID) -> AdminCVTemplateResponse:
        if self.repository.transition_active_status(
            template_id,
            expected_current_status=False,
            target_status=True,
        ):
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if template.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV đã ở trạng thái hoạt động.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def deactivate_template(self, template_id: uuid.UUID) -> AdminCVTemplateResponse:
        if self.repository.transition_active_status(
            template_id,
            expected_current_status=True,
            target_status=False,
            clear_featured=True,
        ):
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if not template.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV đã ngừng hoạt động.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def feature_template(self, template_id: uuid.UUID) -> AdminCVTemplateResponse:
        if self.repository.transition_featured_status(
            template_id,
            expected_current_status=False,
            target_status=True,
        ):
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

    def unfeature_template(self, template_id: uuid.UUID) -> AdminCVTemplateResponse:
        if self.repository.transition_featured_status(
            template_id,
            expected_current_status=True,
            target_status=False,
        ):
            return self.get_template(template_id)
        template, _ = self._get_template_or_404(template_id)
        if not template.is_featured:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mẫu CV chưa được đánh dấu nổi bật.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV template state changed.")

    def delete_template(self, template_id: uuid.UUID) -> None:
        template, usage_count = self._get_template_or_404(template_id)
        if usage_count > 0 and template.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Deactivate a template that is already in use before deleting it.",
            )
        self.repository.archive(template)

    def _get_template_or_404(self, template_id: uuid.UUID) -> tuple[CVTemplate, int]:
        result = self.repository.get_template_with_usage(template_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV template not found.")
        return result

    @staticmethod
    def _to_response(template: CVTemplate, usage_count: int) -> AdminCVTemplateResponse:
        return AdminCVTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            layout_key=template.layout_key,
            theme_config=template.theme_config,
            thumbnail_url=template.thumbnail_url,
            is_active=template.is_active,
            is_featured=template.is_featured,
            sort_order=template.sort_order,
            created_at=template.created_at,
            updated_at=template.updated_at,
            usage_count=usage_count,
        )
