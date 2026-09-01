from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cv_template import CVTemplateCatalogResponse
from app.services.cv_template_service import CVTemplateService


router = APIRouter(prefix="/cv-templates", tags=["CV Templates"])


@router.get("", response_model=CVTemplateCatalogResponse, summary="List active CV templates")
def list_active_cv_templates(db: Session = Depends(get_db)):
    return CVTemplateService(db).list_active_templates()
