import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.cv import CVCreateRequest, CVListResponse, CVResponse, CVUpdateRequest
from app.services.cv_service import CVService


router = APIRouter(prefix="/candidate/cvs", tags=["Candidate CVs"])


@router.get("", response_model=CVListResponse, summary="List current candidate's CVs")
def list_my_cvs(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).list_cvs(current_user)


@router.post("", response_model=CVResponse, status_code=status.HTTP_201_CREATED, summary="Create a candidate CV")
def create_my_cv(
    payload: CVCreateRequest,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).create_cv(current_user, payload)


@router.get("/{cv_id}", response_model=CVResponse, summary="Get a candidate-owned CV")
def get_my_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).get_cv(current_user, cv_id)


@router.patch("/{cv_id}", response_model=CVResponse, summary="Update a candidate-owned CV")
def update_my_cv(
    cv_id: uuid.UUID,
    payload: CVUpdateRequest,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).update_cv(current_user, cv_id, payload)


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a candidate-owned CV")
def delete_my_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    CVService(db).delete_cv(current_user, cv_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{cv_id}/default", response_model=CVResponse, summary="Set a candidate-owned CV as default")
def set_my_default_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).set_default_cv(current_user, cv_id)
