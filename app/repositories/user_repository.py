import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def add(self, user: User) -> User:
        """Stage a user inside a caller-owned transaction."""
        self.db.add(user)
        self.db.flush()
        return user

    def list_active_admin_ids(self) -> list[uuid.UUID]:
        return list(
            self.db.scalars(
                select(User.id)
                .where(
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
                .order_by(User.id)
            )
        )

    def email_exists(self, email: str) -> bool:
        return self.db.query(User.id).filter(User.email == email).first() is not None

    def update(self, user: User, fields: dict) -> User:
        """Apply a dict of field→value to the user row and persist."""
        for key, value in fields.items():
            setattr(user, key, value)
        self.db.commit()
        self.db.refresh(user)
        return user
