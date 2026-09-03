import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class AdminUserRepository:
    """Persistence operations for the admin-only user management module."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        role: UserRole | None,
        is_active: bool | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        query = self.db.query(User)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                )
            )
        if role is not None:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active.is_(is_active))

        total = query.count()
        items = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def count_active_admins(self) -> int:
        return (
            self.db.query(func.count(User.id))
            .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .scalar()
            or 0
        )

    def transition_active_status(
        self,
        user_id: uuid.UUID,
        *,
        expected_current_status: bool,
        target_status: bool,
    ) -> User | None:
        """Atomically change a user status only when its current value is expected."""
        affected_rows = (
            self.db.query(User)
            .filter(User.id == user_id, User.is_active.is_(expected_current_status))
            .update(
                {User.is_active: target_status, User.updated_at: func.now()},
                synchronize_session=False,
            )
        )
        if affected_rows == 0:
            return None
        self.db.commit()
        return self.get_by_id(user_id)
