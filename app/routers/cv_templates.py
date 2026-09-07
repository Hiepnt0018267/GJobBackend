import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cv_template import CVTemplateCatalogResponse
from app.services.admin_cv_template_service import AdminCVTemplateService
from app.services.cv_template_service import CVTemplateService


router = APIRouter(prefix="/cv-templates", tags=["CV Templates"])


@router.get("", response_model=CVTemplateCatalogResponse, summary="List active CV templates")
def list_active_cv_templates(db: Session = Depends(get_db)):
    return CVTemplateService(db).list_active_templates()


@router.get("/{template_id}/thumbnail", summary="Read a CV template thumbnail")
def get_template_thumbnail(template_id: uuid.UUID, db: Session = Depends(get_db)):
    return FileResponse(AdminCVTemplateService(db).get_thumbnail_path(template_id), media_type="image/webp", headers={"Cache-Control": "no-store"})
