from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.recruiter import RecruiterDashboardSummary, RecruiterProfileResponse, UpdateRecruiterProfileRequest
from app.services.recruiter_service import RecruiterService

router = APIRouter(prefix="/recruiters", tags=["Recruiter Profile"])


@router.get("/me", response_model=RecruiterProfileResponse, status_code=status.HTTP_200_OK, summary="Get current recruiter profile")
def get_my_recruiter_profile(current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).get_profile(current_user)


@router.patch("/me", response_model=RecruiterProfileResponse, status_code=status.HTTP_200_OK, summary="Update current recruiter profile")
def update_my_recruiter_profile(payload: UpdateRecruiterProfileRequest, current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).update_profile(current_user, payload)


@router.get("/me/dashboard", response_model=RecruiterDashboardSummary, status_code=status.HTTP_200_OK, summary="Get current recruiter dashboard summary")
def get_my_dashboard_summary(current_user: User = Depends(require_role(UserRole.RECRUITER)), db: Session = Depends(get_db)):
    return RecruiterService(db).dashboard_summary(current_user)
