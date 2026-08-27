from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UpdateProfileRequest, UserProfile

# Fields that are NEVER allowed to be changed through the profile update API
_IMMUTABLE_FIELDS = {"role", "is_active", "email", "password_hash", "id", "created_at"}


class UserService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)

    def get_profile(self, user: User) -> UserProfile:
        """Return the full profile for the given user."""
        return UserProfile.model_validate(user)

    def update_profile(self, user: User, payload: UpdateProfileRequest) -> UserProfile:
        """
        Apply only the fields explicitly provided in the request body.
        Immutable fields (role, is_active, email, password_hash…) are stripped
        before the update — the repo never receives them even if somehow injected.
        """
        # Build update dict: only non-None values sent by the client
        raw = payload.model_dump(exclude_unset=True)

        # Enforce: strip any immutable field that might be in the dict
        safe_fields = {k: v for k, v in raw.items() if k not in _IMMUTABLE_FIELDS}

        if not safe_fields:
            # Nothing to update — return current state
            return UserProfile.model_validate(user)

        # Stamp updated_at explicitly (SQLAlchemy onupdate fires on flush,
        # but we set it here to be explicit and consistent)
        safe_fields["updated_at"] = datetime.now(timezone.utc)

        updated_user = self.repo.update(user, safe_fields)
        return UserProfile.model_validate(updated_user)
