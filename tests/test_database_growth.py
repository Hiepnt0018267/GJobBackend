"""Regression coverage for the first justified database-growth batch."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.application import JobApplication, JobApplicationStatus
from app.models.application_status_history import ApplicationStatusHistory
from app.models.cv import CV
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.services.admin_job_service import AdminJobService
from app.services.candidate_application_service import CandidateApplicationService


client = TestClient(app)
MODERN_TEMPLATE_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _user(role: UserRole, name: str) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"db_growth_{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name=name,
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(user: User) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _job(*, recruiter_id: uuid.UUID | None, status: JobStatus) -> Job:
    db = SessionLocal()
    try:
        job = Job(
            recruiter_id=recruiter_id,
            title=f"Database growth {uuid.uuid4().hex}",
            description="Database growth regression test",
            company_name="GJob",
            status=status,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        db.expunge(job)
        return job
    finally:
        db.close()


def _cv(candidate_id: uuid.UUID) -> CV:
    db = SessionLocal()
    try:
        cv = CV(
            candidate_id=candidate_id,
            template_id=MODERN_TEMPLATE_ID,
            title="Database growth CV",
            personal_info={"full_name": "Candidate"},
        )
        db.add(cv)
        db.commit()
        db.refresh(cv)
        db.expunge(cv)
        return cv
    finally:
        db.close()


def test_application_lifecycle_writes_ordered_history_with_actors() -> None:
    candidate = _user(UserRole.CANDIDATE, "History Candidate")
    recruiter = _user(UserRole.RECRUITER, "History Recruiter")
    job = _job(recruiter_id=recruiter.id, status=JobStatus.APPROVED)
    cv = _cv(candidate.id)

    submitted = client.post(
        f"/api/v1/jobs/{job.id}/applications",
        json={"cv_id": str(cv.id)},
        headers=_headers(_token(candidate)),
    )
    assert submitted.status_code == 201, submitted.text
    application_id = uuid.UUID(submitted.json()["id"])

    reviewed = client.patch(
        f"/api/v1/recruiters/applications/{application_id}/review",
        headers=_headers(_token(recruiter)),
    )
    assert reviewed.status_code == 200, reviewed.text
    withdrawn = client.patch(
        f"/api/v1/candidate/applications/{application_id}/withdraw",
        headers=_headers(_token(candidate)),
    )
    assert withdrawn.status_code == 200, withdrawn.text

    db = SessionLocal()
    try:
        rows = (
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.application_id == application_id)
            .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
            .all()
        )
        assert [(row.from_status, row.to_status) for row in rows] == [
            (None, JobApplicationStatus.SUBMITTED),
            (JobApplicationStatus.SUBMITTED, JobApplicationStatus.REVIEWING),
            (JobApplicationStatus.REVIEWING, JobApplicationStatus.WITHDRAWN),
        ]
        assert [row.changed_by_user_id for row in rows] == [
            candidate.id,
            recruiter.id,
            candidate.id,
        ]
    finally:
        db.close()


def test_admin_mutations_write_safe_audit_logs() -> None:
    admin = _user(UserRole.ADMIN, "Audit Admin")
    candidate = _user(UserRole.CANDIDATE, "Audit Target")
    job = _job(recruiter_id=None, status=JobStatus.PENDING)
    headers = _headers(_token(admin))

    assert client.patch(f"/api/v1/admin/jobs/{job.id}/approve", headers=headers).status_code == 200
    assert client.patch(f"/api/v1/admin/users/{candidate.id}/deactivate", headers=headers).status_code == 200
    created_template = client.post(
        "/api/v1/admin/cv-templates",
        headers=headers,
        json={
            "name": f"Database growth {uuid.uuid4().hex}",
            "description": "Audit regression",
            "layout_key": "MODERN",
            "is_active": True,
            "is_featured": False,
            "sort_order": 999,
        },
    )
    assert created_template.status_code == 201, created_template.text

    db = SessionLocal()
    try:
        logs = db.query(AdminAuditLog).filter(AdminAuditLog.admin_user_id == admin.id).all()
        by_action = {log.action: log for log in logs}
        assert by_action["JOB_APPROVED"].entity_id == job.id
        assert by_action["USER_DEACTIVATED"].entity_id == candidate.id
        assert by_action["CV_TEMPLATE_CREATED"].entity_id == uuid.UUID(created_template.json()["id"])
        assert "password" not in str([log.metadata_ for log in logs]).lower()
    finally:
        db.close()


def test_application_history_failure_rolls_back_status_change(monkeypatch) -> None:
    candidate = _user(UserRole.CANDIDATE, "Rollback Candidate")
    job = _job(recruiter_id=None, status=JobStatus.APPROVED)
    cv = _cv(candidate.id)
    db = SessionLocal()
    try:
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            cv_id=cv.id,
            status=JobApplicationStatus.REVIEWING,
        )
        db.add(application)
        db.commit()
        application_id = application.id

        service = CandidateApplicationService(db)
        original_add = db.add

        def fail_history_add(instance, *args, **kwargs):
            if isinstance(instance, ApplicationStatusHistory):
                raise RuntimeError("simulated history failure")
            return original_add(instance, *args, **kwargs)

        monkeypatch.setattr(db, "add", fail_history_add)
        with pytest.raises(RuntimeError, match="simulated history failure"):
            service.withdraw_application(candidate, application_id)
    finally:
        db.close()

    verification_db = SessionLocal()
    try:
        persisted = verification_db.get(JobApplication, application_id)
        assert persisted is not None
        assert persisted.status == JobApplicationStatus.REVIEWING
    finally:
        verification_db.close()


def test_admin_audit_failure_rolls_back_job_moderation(monkeypatch) -> None:
    admin = _user(UserRole.ADMIN, "Audit Rollback Admin")
    job = _job(recruiter_id=None, status=JobStatus.PENDING)
    db = SessionLocal()
    try:
        current_admin = db.get(User, admin.id)
        assert current_admin is not None
        service = AdminJobService(db)

        def fail_audit(**kwargs):
            raise RuntimeError("simulated audit failure")

        monkeypatch.setattr(service.audit_repository, "add", fail_audit)
        with pytest.raises(RuntimeError, match="simulated audit failure"):
            service.approve_job(job.id, current_admin)
    finally:
        db.close()

    verification_db = SessionLocal()
    try:
        persisted = verification_db.get(Job, job.id)
        assert persisted is not None
        assert persisted.status == JobStatus.PENDING
    finally:
        verification_db.close()
