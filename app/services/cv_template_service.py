import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.cv_template import CVTemplate
from app.repositories.cv_template_repository import CVTemplateRepository
from app.schemas.cv_template import CVTemplateCatalogResponse


class CVTemplateService:
    def __init__(self, db: Session) -> None:
        self.repository = CVTemplateRepository(db)

    def list_active_templates(self) -> CVTemplateCatalogResponse:
        return CVTemplateCatalogResponse(items=[self._to_public(template) for template in self.repository.list_active()])

    @staticmethod
    def _to_public(template: CVTemplate) -> dict:
        return {
            "id": template.id, "name": template.name, "description": template.description,
            "layout_key": template.layout_key, "theme_config": template.theme_config,
            "is_featured": template.is_featured, "sort_order": template.sort_order,
            "thumbnail_url": (f"/api/v1/cv-templates/{template.id}/thumbnail?v={int(template.updated_at.timestamp())}" if template.thumbnail_storage_key else template.thumbnail_url),
        }

    def require_active_template(self, template_id: uuid.UUID) -> CVTemplate:
        template = self.repository.get_active_by_id(template_id)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CV template does not exist or is inactive.",
            )
        return template
