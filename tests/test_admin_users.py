"""Task 10C: ADMIN-only user management integration tests."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV, CVSourceType
from app.models.job import Job, JobStatus
from app.models.saved_job import SavedJob
from app.models.user import User, UserRole
from app.services.admin_user_service import AdminUserService


client = TestClient(app)
BASE = "/api/v1/admin/users"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(
    role: UserRole = UserRole.CANDIDATE,
    *,
    full_name: str = "Task 10C User",
    is_active: bool = True,
) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"task10c_{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(role: UserRole = UserRole.CANDIDATE) -> str:
    user = _create_user(role)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token() -> str:
    return _token(UserRole.ADMIN)


def _cleanup_task_records() -> None:
    db = SessionLocal()
    try:
        user_ids = list(
            db.scalars(select(User.id).where(User.email.like("task10c_%@example.com")))
        )
        if user_ids:
            db.query(SavedJob).filter(SavedJob.candidate_id.in_(user_ids)).delete(
                synchronize_session=False
            )
            db.query(JobApplication).filter(JobApplication.candidate_id.in_(user_ids)).delete(
                synchronize_session=False
            )
            db.query(CV).filter(CV.candidate_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(Job).filter(Job.recruiter_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_task_data():
    _cleanup_task_records()
    yield
    _cleanup_task_records()


def test_user_management_requires_an_admin():
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers=_headers(_token(UserRole.CANDIDATE))).status_code == 403
    assert client.get(BASE, headers=_headers(_token(UserRole.RECRUITER))).status_code == 403
    assert client.get(BASE, headers=_headers(_admin_token())).status_code == 200


def test_admin_searches_filters_and_paginates_users_server_side():
    admin_token = _admin_token()
    marker = uuid.uuid4().hex[:10]
    email_match = _create_user(UserRole.CANDIDATE, full_name="Other Name")
    named_match = _create_user(UserRole.RECRUITER, full_name=f"Nguyen {marker} Engineer")
    inactive_match = _create_user(UserRole.RECRUITER, full_name=f"Inactive {marker}", is_active=False)
    _create_user(UserRole.CANDIDATE, full_name="Unrelated User")

    # Make the marker part of the first account email only.
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == email_match.id).update(
            {User.email: f"task10c_{marker}@example.com"}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        BASE,
        params={"search": marker.upper(), "page_size": 100},
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()["items"]} == {
        str(email_match.id),
        str(named_match.id),
        str(inactive_match.id),
    }
    assert response.json()["total"] == 3

    combined = client.get(
        BASE,
        params={"search": marker, "role": "RECRUITER", "is_active": "false"},
        headers=_headers(admin_token),
    )
    assert combined.status_code == 200, combined.text
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["id"] == str(inactive_match.id)

    whitespace = client.get(BASE, params={"search": "   ", "page_size": 100}, headers=_headers(admin_token))
    unfiltered = client.get(BASE, params={"page_size": 100}, headers=_headers(admin_token))
    assert whitespace.status_code == 200
    assert whitespace.json()["total"] == unfiltered.json()["total"]
    assert client.get(BASE, params={"search": "%_'"}, headers=_headers(admin_token)).status_code == 200

    paged = client.get(
        BASE,
        params={"search": marker, "page": 1, "page_size": 2},
        headers=_headers(admin_token),
    )
    assert paged.status_code == 200
    assert paged.json()["total"] == 3
    assert paged.json()["page"] == 1
    assert paged.json()["page_size"] == 2
    assert paged.json()["total_pages"] == 2
    assert len(paged.json()["items"]) == 2


def test_admin_views_safe_user_detail_and_handles_missing_user():
    user = _create_user(
        UserRole.RECRUITER,
        full_name="Task 10C Detail",
    )
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == user.id).update(
            {
                User.phone: "0900000000",
                User.address: "Ho Chi Minh City",
                User.bio: "Recruiter support detail",
                User.avatar_url: "https://example.com/avatar.png",
            },
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"{BASE}/{user.id}", headers=_headers(_admin_token()))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["phone"] == "0900000000"
    assert body["address"] == "Ho Chi Minh City"
    assert body["bio"] == "Recruiter support detail"
    assert "password_hash" not in body
    assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_headers(_admin_token())).status_code == 404


def test_admin_user_overview_is_role_aware_and_read_only():
    candidate = _create_user(UserRole.CANDIDATE)
    recruiter = _create_user(UserRole.RECRUITER)
    administrator = _create_user(UserRole.ADMIN)
    admin_token = _admin_token()

    candidate_response = client.get(
        f"{BASE}/{candidate.id}/overview", headers=_headers(admin_token)
    )
    assert candidate_response.status_code == 200, candidate_response.text
    candidate_body = candidate_response.json()
    assert candidate_body["role"] == "CANDIDATE"
    assert candidate_body["candidate"]["cv_total"] == 0
    assert candidate_body["candidate"]["application_total"] == 0
    assert candidate_body["candidate"]["saved_job_total"] == 0
    assert candidate_body["recruiter"] is None

    recruiter_response = client.get(
        f"{BASE}/{recruiter.id}/overview", headers=_headers(admin_token)
    )
    assert recruiter_response.status_code == 200, recruiter_response.text
    recruiter_body = recruiter_response.json()
    assert recruiter_body["role"] == "RECRUITER"
    assert recruiter_body["recruiter"]["job_total"] == 0
    assert recruiter_body["recruiter"]["current_plan"]["code"] == "FREE"
    assert recruiter_body["recruiter"]["revenue"] == "0"
    assert recruiter_body["candidate"] is None

    admin_response = client.get(
        f"{BASE}/{administrator.id}/overview", headers=_headers(admin_token)
    )
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.json()["administrator"]["audit_action_total"] == 0

    assert client.get(f"{BASE}/{candidate.id}/overview").status_code == 401
    assert client.get(
        f"{BASE}/{candidate.id}/overview", headers=_headers(_token(UserRole.CANDIDATE))
    ).status_code == 403
    assert client.get(
        f"{BASE}/{uuid.uuid4()}/overview", headers=_headers(admin_token)
    ).status_code == 404


def test_role_overview_counts_candidate_and_recruiter_activity() -> None:
    candidate = _create_user(UserRole.CANDIDATE)
    recruiter = _create_user(UserRole.RECRUITER)
    admin_token = _admin_token()
    db = SessionLocal()
    try:
        cv = CV(
            candidate_id=candidate.id,
            source_type=CVSourceType.UPLOADED,
            title="Overview CV",
            is_default=True,
            storage_key=f"tests/{uuid.uuid4().hex}.pdf",
            original_filename="overview.pdf",
            mime_type="application/pdf",
            file_size=100,
            uploaded_at=datetime.now(timezone.utc),
        )
        job = Job(
            recruiter_id=recruiter.id,
            title="Overview Job",
            description="Role overview test",
            company_name="Overview Company",
            status=JobStatus.APPROVED,
        )
        db.add_all([cv, job])
        db.flush()
        db.add_all(
            [
                JobApplication(
                    candidate_id=candidate.id,
                    job_id=job.id,
                    cv_id=cv.id,
                    status=JobApplicationStatus.HIRED,
                ),
                SavedJob(candidate_id=candidate.id, job_id=job.id),
            ]
        )
        db.commit()
    finally:
        db.close()

    candidate_body = client.get(
        f"{BASE}/{candidate.id}/overview", headers=_headers(admin_token)
    ).json()["candidate"]
    assert candidate_body["cv_total"] == 1
    assert candidate_body["uploaded_cv_total"] == 1
    assert candidate_body["application_total"] == 1
    assert candidate_body["hired_total"] == 1
    assert candidate_body["saved_job_total"] == 1
    assert candidate_body["recent_cvs"][0]["title"] == "Overview CV"

    recruiter_body = client.get(
        f"{BASE}/{recruiter.id}/overview", headers=_headers(admin_token)
    ).json()["recruiter"]
    assert recruiter_body["job_total"] == 1
    assert recruiter_body["approved_job_total"] == 1
    assert recruiter_body["received_application_total"] == 1
    assert recruiter_body["recent_jobs"][0]["application_total"] == 1


def test_admin_deactivates_and_reactivates_account_and_old_token_is_denied():
    target = _create_user(UserRole.CANDIDATE)
    target_login = client.post(
        "/api/v1/auth/login",
        json={"email": target.email, "password": "password123"},
    )
    assert target_login.status_code == 200
    target_token = target_login.json()["access_token"]
    admin_token = _admin_token()

    deactivated = client.patch(f"{BASE}/{target.id}/deactivate", headers=_headers(admin_token))
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=_headers(target_token)).status_code == 403
    assert client.post(
        "/api/v1/auth/login",
        json={"email": target.email, "password": "password123"},
    ).status_code == 403
    assert client.patch(f"{BASE}/{target.id}/deactivate", headers=_headers(admin_token)).status_code == 409

    activated = client.patch(f"{BASE}/{target.id}/activate", headers=_headers(admin_token))
    assert activated.status_code == 200, activated.text
    assert activated.json()["is_active"] is True
    assert client.patch(f"{BASE}/{target.id}/activate", headers=_headers(admin_token)).status_code == 409
    assert client.get("/api/v1/auth/me", headers=_headers(target_token)).status_code == 200


def test_admin_cannot_deactivate_self_or_missing_users_and_non_admin_cannot_change_status():
    admin = _create_user(UserRole.ADMIN)
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    target = _create_user(UserRole.CANDIDATE)
    candidate_token = _token(UserRole.CANDIDATE)

    self_response = client.patch(f"{BASE}/{admin.id}/deactivate", headers=_headers(admin_token))
    assert self_response.status_code == 409
    assert client.patch(f"{BASE}/{target.id}/deactivate", headers=_headers(candidate_token)).status_code == 403
    assert client.patch(f"{BASE}/{uuid.uuid4()}/deactivate", headers=_headers(admin_token)).status_code == 404
    assert client.patch(f"{BASE}/{uuid.uuid4()}/activate", headers=_headers(admin_token)).status_code == 404


def test_service_protects_the_last_active_admin(monkeypatch):
    target = _create_user(UserRole.ADMIN)
    current_admin = _create_user(UserRole.ADMIN)
    db = SessionLocal()
    try:
        service = AdminUserService(db)
        monkeypatch.setattr(service.repository, "count_active_admins", lambda: 1)
        with pytest.raises(HTTPException) as exc_info:
            service.deactivate_user(target.id, current_admin)
        assert exc_info.value.status_code == 409
        assert "last active admin" in exc_info.value.detail
        assert db.scalar(select(User.is_active).where(User.id == target.id)) is True
    finally:
        db.close()
