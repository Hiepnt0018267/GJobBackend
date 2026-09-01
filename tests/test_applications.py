"""Task 08A: secure candidate job-application integration tests."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


client = TestClient(app)
JOBS_BASE = "/api/v1/jobs"
CV_BASE = "/api/v1/candidate/cvs"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _token(role: str = "CANDIDATE") -> str:
    email = f"task08a_{uuid.uuid4().hex[:12]}@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Task 08A", "role": role})
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token() -> str:
    email = f"task08a_admin_{uuid.uuid4().hex[:12]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(email=email, password_hash=hash_password("password123"), full_name="Task 08A Admin", role=UserRole.ADMIN))
        db.commit()
    finally:
        db.close()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_job(job_status: JobStatus = JobStatus.APPROVED) -> str:
    db = SessionLocal()
    try:
        job = Job(title=f"Task 08A Job {uuid.uuid4().hex}", description="Secure application test", company_name="GJob", status=job_status)
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _create_cv(token: str) -> dict:
    response = client.post(CV_BASE, json={"title": "Application CV", "template_id": MODERN_TEMPLATE_ID, "personal_info": {"full_name": "Candidate"}}, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _apply(token: str, job_id: str, cv_id: str):
    return client.post(f"{JOBS_BASE}/{job_id}/applications", json={"cv_id": cv_id}, headers=_headers(token))


def test_submit_requires_authenticated_candidate_role():
    job_id = _create_job()
    assert client.post(f"{JOBS_BASE}/{job_id}/applications", json={"cv_id": str(uuid.uuid4())}).status_code == 401
    assert _apply(_token("RECRUITER"), job_id, str(uuid.uuid4())).status_code == 403
    assert _apply(_admin_token(), job_id, str(uuid.uuid4())).status_code == 403


def test_candidate_submits_approved_job_with_own_cv_and_server_managed_fields():
    token = _token()
    job_id = _create_job()
    cv = _create_cv(token)
    response = _apply(token, job_id, cv["id"])
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["cv_id"] == cv["id"]
    assert payload["status"] == "SUBMITTED"
    assert payload["candidate_id"]
    assert client.post(f"{JOBS_BASE}/{job_id}/applications", json={"cv_id": cv["id"], "status": "HIRED"}, headers=_headers(token)).status_code == 422


@pytest.mark.parametrize("job_status", [JobStatus.PENDING, JobStatus.REJECTED, JobStatus.CLOSED])
def test_application_rejects_non_approved_jobs(job_status: JobStatus):
    token = _token()
    response = _apply(token, _create_job(job_status), _create_cv(token)["id"])
    assert response.status_code == 409


def test_application_rejects_missing_job_and_other_candidates_cv():
    owner, other = _token(), _token()
    cv = _create_cv(owner)
    assert _apply(owner, str(uuid.uuid4()), cv["id"]).status_code == 404
    assert _apply(other, _create_job(), cv["id"]).status_code == 404


def test_duplicate_application_is_rejected_and_database_constraint_preserves_one_record():
    token = _token()
    job_id = _create_job()
    cv = _create_cv(token)
    first = _apply(token, job_id, cv["id"])
    assert first.status_code == 201, first.text
    assert _apply(token, job_id, cv["id"]).status_code == 409

    db = SessionLocal()
    try:
        application = db.query(JobApplication).filter(JobApplication.job_id == uuid.UUID(job_id)).one()
        assert db.query(JobApplication).filter(JobApplication.job_id == uuid.UUID(job_id), JobApplication.candidate_id == application.candidate_id).count() == 1
        db.add(JobApplication(job_id=application.job_id, candidate_id=application.candidate_id, cv_id=application.cv_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_another_candidate_can_apply_to_the_same_job_and_used_cv_cannot_be_deleted():
    first, second = _token(), _token()
    job_id = _create_job()
    first_cv = _create_cv(first)
    second_cv = _create_cv(second)
    assert _apply(first, job_id, first_cv["id"]).status_code == 201
    assert _apply(second, job_id, second_cv["id"]).status_code == 201
    assert client.delete(f"{CV_BASE}/{first_cv['id']}", headers=_headers(first)).status_code == 409


def test_unused_cv_can_still_be_deleted():
    token = _token()
    cv = _create_cv(token)
    assert client.delete(f"{CV_BASE}/{cv['id']}", headers=_headers(token)).status_code == 204
