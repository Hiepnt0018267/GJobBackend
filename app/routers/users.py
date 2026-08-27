from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserProfile
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["User Profile"])


@router.get(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    summary="Get current user full profile",
)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the full profile of the authenticated user.
    Identity is determined solely from the JWT — not from request body.
    """
    return UserProfile.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile (partial update)",
)
def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Partially updates the authenticated user's profile.
    - Identity comes from JWT (get_current_user) — never from request body.
    - role, is_active, email, password_hash are immutable via this endpoint.
    - Only fields present in the request body are updated (PATCH semantics).
    """
    service = UserService(db)
    return service.update_profile(current_user, payload)
