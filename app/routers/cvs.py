import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Response, UploadFile, status
from app.services.ranking_precompute import precompute_entity
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.cv import CVCreateRequest, CVListResponse, CVResponse, CVUpdateRequest
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.cv_extraction_api import (
    CVExtractionConfirmationResponse,
    CVExtractionResponse,
)
from app.services.cv_extraction_service import CandidateCVExtractionService
from app.services.cv_service import CVService


router = APIRouter(prefix="/candidate/cvs", tags=["Candidate CVs"])


@router.get("/extraction-policy", summary="Get safe CV extraction request timing contract")
def cv_extraction_policy(current_user: User = Depends(require_role(UserRole.CANDIDATE))):
    return {"operation_timeout_ms": int(settings.cv_extraction_total_timeout_seconds * 1000),
            "request_timeout_ms": int((settings.cv_extraction_total_timeout_seconds + settings.cv_extraction_network_margin_seconds) * 1000)}


@router.get("", response_model=CVListResponse, summary="List current candidate's CVs")
def list_my_cvs(
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CVService(db).list_cvs(current_user)


@router.post("", response_model=CVResponse, status_code=status.HTTP_201_CREATED, summary="Create a candidate CV")
def create_my_cv(
    payload: CVCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    cv = CVService(db).create_cv(current_user, payload)
    background_tasks.add_task(precompute_entity, "cv", cv.id)
    return cv


@router.post("/upload", response_model=CVResponse, status_code=status.HTTP_201_CREATED, summary="Upload a PDF or DOCX candidate CV")
async def upload_my_cv(
    title: str = Form(..., max_length=255),
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return await CVService(db).upload_cv(current_user, title, file)


@router.post(
    "/{cv_id}/extractions",
    response_model=CVExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": CVExtractionResponse,
            "description": "An existing active extraction was reused.",
        }
    },
    summary="Extract structured data from a candidate-owned uploaded CV",
)
async def trigger_my_cv_extraction(
    cv_id: uuid.UUID,
    response: Response,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    extraction, created = await CandidateCVExtractionService(db).trigger(
        current_user, cv_id
    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    if created:
        background_tasks.add_task(precompute_entity, "cv", cv_id)
    return extraction


@router.get(
    "/{cv_id}/extractions/latest",
    response_model=CVExtractionResponse,
    summary="Get the latest structured extraction for a candidate-owned CV",
)
def get_my_latest_cv_extraction(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return CandidateCVExtractionService(db).get_latest(current_user, cv_id)


@router.post(
    "/{cv_id}/extractions/{extraction_id}/confirm",
    response_model=CVExtractionConfirmationResponse,
    summary="Confirm reviewed structured data from a CV extraction",
)
def confirm_my_cv_extraction(
    cv_id: uuid.UUID,
    extraction_id: uuid.UUID,
    payload: StructuredCVExtractionResult,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    result = CandidateCVExtractionService(db).confirm(
        current_user,
        cv_id,
        extraction_id,
        payload,
    )
    background_tasks.add_task(precompute_entity, "cv", cv_id)
    return result


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
    return CVService(db).get_cv_response(current_user, cv_id)


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    cv = CVService(db).update_cv(current_user, cv_id, payload)
    background_tasks.add_task(precompute_entity, "cv", cv_id)
    return cv


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
