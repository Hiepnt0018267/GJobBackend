import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.job import JobStatus
from app.models.user import User, UserRole
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.schemas.admin_job import AdminJobListResponse, AdminJobResponse
from app.schemas.admin_user import (
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserRoleOverviewResponse,
)
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.admin_job_service import AdminJobService
from app.services.admin_user_service import AdminUserService


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Get system-wide admin dashboard statistics")
def get_admin_dashboard(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminDashboardService(db).get_dashboard_stats()


@router.get("/users", response_model=AdminUserListResponse, summary="List users for admin management")
def list_users_for_admin(
    search: str | None = Query(default=None, max_length=200),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).list_users(role, is_active, search, page, page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse, summary="Get a user for admin management")
def get_user_for_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).get_user(user_id)


@router.get(
    "/users/{user_id}/overview",
    response_model=AdminUserRoleOverviewResponse,
    summary="Get role-aware user activity overview",
)
def get_user_overview_for_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).get_user_overview(user_id)


@router.patch("/users/{user_id}/activate", response_model=AdminUserDetailResponse, summary="Activate a user account")
def activate_user_for_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).activate_user(user_id, current_user)


@router.patch("/users/{user_id}/deactivate", response_model=AdminUserDetailResponse, summary="Deactivate a user account")
def deactivate_user_for_admin(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminUserService(db).deactivate_user(user_id, current_user)


@router.get("/jobs", response_model=AdminJobListResponse, summary="List jobs for admin moderation")
def list_jobs_for_admin(
    job_status: JobStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=200),
    recruiter_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminJobService(db).list_jobs(job_status, search, recruiter_id, page, page_size)


@router.get("/jobs/{job_id}", response_model=AdminJobResponse, summary="Get a job for admin moderation")
def get_job_for_admin(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminJobService(db).get_job(job_id)


@router.patch("/jobs/{job_id}/approve", response_model=AdminJobResponse, summary="Approve a pending job")
def approve_pending_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminJobService(db).approve_job(job_id, current_user)


@router.patch("/jobs/{job_id}/reject", response_model=AdminJobResponse, summary="Reject a pending job")
def reject_pending_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    return AdminJobService(db).reject_job(job_id, current_user)
