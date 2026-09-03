import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.admin_cv import AdminCVDetail, AdminCVListResponse
from app.services.admin_cv_service import AdminCVService


router = APIRouter(prefix="/admin/cvs", tags=["Admin Candidate CV Audit"])


@router.get("", response_model=AdminCVListResponse, summary="List candidate CVs for read-only admin audit")
def list_cvs_for_admin(
    search: str | None = Query(default=None, max_length=200),
    template_id: uuid.UUID | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    is_default: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVService(db).list_cvs(search, template_id, candidate_id, is_default, page, page_size)


@router.get("/{cv_id}", response_model=AdminCVDetail, summary="Get a candidate CV for read-only admin audit")
def get_cv_for_admin(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminCVService(db).get_cv(cv_id)
