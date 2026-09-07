import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import FileResponse
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


@router.post("/upload", response_model=CVResponse, status_code=status.HTTP_201_CREATED, summary="Upload a PDF or DOCX candidate CV")
async def upload_my_cv(
    title: str = Form(..., max_length=255),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return await CVService(db).upload_cv(current_user, title, file)


@router.post("/{cv_id}/photo", response_model=CVResponse, summary="Upload or replace a Builder CV photo")
async def upload_my_cv_photo(
    cv_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return await CVService(db).upload_photo(current_user, cv_id, file)


@router.get("/{cv_id}/photo", summary="Read a candidate-owned Builder CV photo")
def get_my_cv_photo(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    service = CVService(db)
    cv = service.get_cv(current_user, cv_id)
    return FileResponse(service.get_photo_path(cv), media_type="image/webp", headers={"Cache-Control": "private, no-store"})


@router.delete("/{cv_id}/photo", response_model=CVResponse, summary="Remove a Builder CV photo")
def delete_my_cv_photo(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).delete_photo(current_user, cv_id)


@router.get("/{cv_id}", response_model=CVResponse, summary="Get a candidate-owned CV")
def get_my_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).get_cv(current_user, cv_id)


@router.get("/{cv_id}/file", summary="Download a candidate-owned uploaded CV")
def download_my_uploaded_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    service = CVService(db)
    cv = service.get_cv(current_user, cv_id)
    return FileResponse(
        service.get_uploaded_file_path(cv),
        media_type=cv.mime_type,
        filename=cv.original_filename,
        content_disposition_type="attachment",
    )


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
