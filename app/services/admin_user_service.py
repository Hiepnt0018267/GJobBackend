import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.admin_user_repository import AdminUserRepository
from app.schemas.admin_user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
)


class AdminUserService:
    def __init__(self, db: Session) -> None:
        self.repository = AdminUserRepository(db)

    def list_users(
        self,
        role: UserRole | None,
        is_active: bool | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> AdminUserListResponse:
        normalized_search = search.strip() if search else None
        items, total = self.repository.list_users(role, is_active, normalized_search, page, page_size)
        return AdminUserListResponse(
            items=[AdminUserListItem.model_validate(user) for user in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    def get_user(self, user_id: uuid.UUID) -> AdminUserDetailResponse:
        return AdminUserDetailResponse.model_validate(self._get_user_or_404(user_id))

    def activate_user(self, user_id: uuid.UUID) -> AdminUserDetailResponse:
        updated_user = self.repository.transition_active_status(
            user_id,
            expected_current_status=False,
            target_status=True,
        )
        if updated_user is not None:
            return AdminUserDetailResponse.model_validate(updated_user)

        self._get_user_or_404(user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already active.",
        )

    def deactivate_user(self, user_id: uuid.UUID, current_user: User) -> AdminUserDetailResponse:
        user = self._get_user_or_404(user_id)
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bạn không thể vô hiệu hóa tài khoản của chính mình.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account is already inactive.",
            )
        if user.role == UserRole.ADMIN and self.repository.count_active_admins() <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active admin account cannot be deactivated.",
            )

        updated_user = self.repository.transition_active_status(
            user_id,
            expected_current_status=True,
            target_status=False,
        )
        if updated_user is not None:
            return AdminUserDetailResponse.model_validate(updated_user)

        self._get_user_or_404(user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already inactive.",
        )

    def _get_user_or_404(self, user_id: uuid.UUID) -> User:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user
