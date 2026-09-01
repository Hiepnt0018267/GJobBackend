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
        return CVTemplateCatalogResponse(items=self.repository.list_active())

    def require_active_template(self, template_id: uuid.UUID) -> CVTemplate:
        template = self.repository.get_active_by_id(template_id)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CV template does not exist or is inactive.",
            )
        return template

