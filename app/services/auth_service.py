from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserPublic


class AuthService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)

    def register(self, payload: RegisterRequest) -> User:
        # Enforce: public registration cannot create ADMIN
        if payload.role == UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Creating an account with ADMIN role is not allowed.",
            )

        # Check duplicate email
        if self.repo.email_exists(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
        )
        return self.repo.create(user)

    def login(self, payload: LoginRequest) -> LoginResponse:
        user = self.repo.get_by_email(payload.email)

        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated.",
            )

        token = create_access_token(data={"sub": str(user.id), "role": user.role})
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserPublic.model_validate(user),
        )
