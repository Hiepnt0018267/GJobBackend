import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.application import JobApplicationCreate, JobApplicationResponse
from app.services.application_service import ApplicationService


router = APIRouter(prefix="/jobs", tags=["Job Applications"])


@router.post("/{job_id}/applications", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED, summary="Submit an application for an approved job")
def submit_application(
    job_id: uuid.UUID,
    payload: JobApplicationCreate,
    current_user: User = Depends(require_role(UserRole.CANDIDATE)),
    db: Session = Depends(get_db),
):
    return ApplicationService(db).submit_application(current_user, job_id, payload)
