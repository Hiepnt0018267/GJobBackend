import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.admin_cv_template import (
    AdminCVTemplateCreate,
    AdminCVTemplateListResponse,
    AdminCVTemplateResponse,
    AdminCVTemplateUpdate,
)
from app.services.admin_cv_template_service import AdminCVTemplateService


router = APIRouter(prefix="/admin/cv-templates", tags=["Admin CV Templates"])


@router.get("", response_model=AdminCVTemplateListResponse, summary="List CV templates for admin management")
def list_templates_for_admin(
    search: str | None = Query(default=None, max_length=200),
    is_active: bool | None = Query(default=None),
    is_featured: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).list_templates(search, is_active, is_featured, page, page_size)


@router.get("/{template_id}", response_model=AdminCVTemplateResponse, summary="Get a CV template for admin management")
def get_template_for_admin(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).get_template(template_id)


@router.post("", response_model=AdminCVTemplateResponse, status_code=status.HTTP_201_CREATED, summary="Create CV template metadata")
def create_template(
    payload: AdminCVTemplateCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).create_template(payload, current_user)


@router.patch("/{template_id}", response_model=AdminCVTemplateResponse, summary="Update CV template metadata")
def update_template_metadata(
    template_id: uuid.UUID,
    payload: AdminCVTemplateUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).update_template_metadata(template_id, payload, current_user)


@router.post("/{template_id}/thumbnail", response_model=AdminCVTemplateResponse, summary="Upload or replace a CV template thumbnail")
async def upload_template_thumbnail(template_id: uuid.UUID, file: UploadFile = File(...), current_user: User = Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)):
    return await AdminCVTemplateService(db).upload_thumbnail(template_id, file, current_user)


@router.delete("/{template_id}/thumbnail", response_model=AdminCVTemplateResponse, summary="Remove a managed CV template thumbnail")
def delete_template_thumbnail(template_id: uuid.UUID, current_user: User = Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)):
    return AdminCVTemplateService(db).delete_thumbnail(template_id, current_user)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an unused CV template")
def delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    AdminCVTemplateService(db).delete_template(template_id, current_user)


@router.patch("/{template_id}/activate", response_model=AdminCVTemplateResponse, summary="Activate a CV template")
def activate_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).activate_template(template_id, current_user)


@router.patch("/{template_id}/deactivate", response_model=AdminCVTemplateResponse, summary="Deactivate a CV template")
def deactivate_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).deactivate_template(template_id, current_user)


@router.patch("/{template_id}/feature", response_model=AdminCVTemplateResponse, summary="Feature a CV template")
def feature_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).feature_template(template_id, current_user)


@router.patch("/{template_id}/unfeature", response_model=AdminCVTemplateResponse, summary="Remove featured status from a CV template")
def unfeature_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVTemplateService(db).unfeature_template(template_id, current_user)
