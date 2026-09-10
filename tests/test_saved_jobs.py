import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job, JobStatus, SalaryType, WorkMode
from app.models.saved_job import SavedJob
from app.models.user import User


client = TestClient(app)
BASE = "/api/v1/candidate/saved-jobs"
MARKER = "__saved_jobs_test__"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _identity(role: str = "CANDIDATE") -> dict[str, str]:
    email = f"{MARKER}{uuid.uuid4().hex}@example.com"
    registration_role = "CANDIDATE" if role == "ADMIN" else role
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "full_name": f"Saved Jobs {role}",
            "role": registration_role,
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    if role == "ADMIN":
        db = SessionLocal()
        db.query(User).filter(User.email == email).update({"role": role})
        db.commit()
        db.close()
    return {
        "id": login.json()["user"]["id"],
        "token": login.json()["access_token"],
    }


def _job(status: JobStatus = JobStatus.APPROVED) -> Job:
    db = SessionLocal()
    job = Job(
        title=f"{MARKER}{uuid.uuid4().hex}",
        description="Saved jobs test description",
        company_name="Saved Jobs Company",
        location="Hà Nội",
        salary_type=SalaryType.NEGOTIABLE,
        work_mode=WorkMode.HYBRID,
        status=status,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    db.expunge(job)
    db.close()
    return job


@pytest.fixture(autouse=True)
def cleanup_saved_job_test_data():
    yield
    db = SessionLocal()
    user_ids = [row[0] for row in db.query(User.id).filter(User.email.like(f"{MARKER}%")).all()]
    job_ids = [row[0] for row in db.query(Job.id).filter(Job.title.like(f"{MARKER}%")).all()]
    if user_ids:
        db.query(SavedJob).filter(SavedJob.candidate_id.in_(user_ids)).delete(synchronize_session=False)
    if job_ids:
        db.query(SavedJob).filter(SavedJob.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    if user_ids:
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_candidate_can_save_approved_job_idempotently():
    candidate = _identity()
    job = _job()

    first = client.post(f"{BASE}/{job.id}", headers=_headers(candidate["token"]))
    duplicate = client.post(f"{BASE}/{job.id}", headers=_headers(candidate["token"]))

    assert first.status_code == 200, first.text
    assert duplicate.status_code == 200, duplicate.text
    assert first.json()["saved"] is True
    assert duplicate.json()["saved"] is True
    assert duplicate.json()["saved_at"] == first.json()["saved_at"]

    db = SessionLocal()
    assert db.query(SavedJob).filter(
        SavedJob.candidate_id == uuid.UUID(candidate["id"]),
        SavedJob.job_id == job.id,
    ).count() == 1
    db.close()


def test_saved_status_and_unsave_are_idempotent():
    candidate = _identity()
    job = _job()
    headers = _headers(candidate["token"])

    assert client.get(f"{BASE}/by-job/{job.id}", headers=headers).json() == {
        "saved": False,
        "saved_at": None,
    }
    assert client.post(f"{BASE}/{job.id}", headers=headers).status_code == 200
    saved_status = client.get(f"{BASE}/by-job/{job.id}", headers=headers)
    assert saved_status.status_code == 200
    assert saved_status.json()["saved"] is True
    assert saved_status.json()["saved_at"] is not None

    assert client.delete(f"{BASE}/{job.id}", headers=headers).status_code == 204
    assert client.delete(f"{BASE}/{job.id}", headers=headers).status_code == 204
    assert client.get(f"{BASE}/by-job/{job.id}", headers=headers).json()["saved"] is False


def test_saved_list_is_owned_paginated_and_keeps_closed_jobs():
    first_candidate = _identity()
    second_candidate = _identity()
    older_job = _job()
    newer_job = _job()
    other_job = _job()
    first_headers = _headers(first_candidate["token"])

    assert client.post(f"{BASE}/{older_job.id}", headers=first_headers).status_code == 200
    assert client.post(f"{BASE}/{newer_job.id}", headers=first_headers).status_code == 200
    assert client.post(f"{BASE}/{other_job.id}", headers=_headers(second_candidate["token"])).status_code == 200

    db = SessionLocal()
    db.query(Job).filter(Job.id == older_job.id).update({"status": JobStatus.CLOSED})
    db.commit()
    db.close()

    first_page = client.get(BASE, params={"page": 1, "page_size": 1}, headers=first_headers)
    second_page = client.get(BASE, params={"page": 2, "page_size": 1}, headers=first_headers)
    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total"] == 2
    assert first_page.json()["total_pages"] == 2
    assert first_page.json()["items"][0]["job"]["id"] == str(newer_job.id)
    assert second_page.json()["items"][0]["job"]["id"] == str(older_job.id)
    assert second_page.json()["items"][0]["job"]["status"] == "CLOSED"
    assert str(other_job.id) not in first_page.text + second_page.text


@pytest.mark.parametrize("job_status", [JobStatus.PENDING, JobStatus.REJECTED, JobStatus.CLOSED])
def test_candidate_cannot_newly_save_non_public_job(job_status: JobStatus):
    candidate = _identity()
    job = _job(job_status)
    response = client.post(f"{BASE}/{job.id}", headers=_headers(candidate["token"]))
    assert response.status_code == 409


def test_guest_recruiter_and_admin_cannot_use_saved_job_endpoints():
    recruiter = _identity("RECRUITER")
    admin = _identity("ADMIN")
    job = _job()
    endpoints = [
        ("get", BASE),
        ("get", f"{BASE}/by-job/{job.id}"),
        ("post", f"{BASE}/{job.id}"),
        ("delete", f"{BASE}/{job.id}"),
    ]

    for method, endpoint in endpoints:
        assert client.request(method, endpoint).status_code == 401
        assert client.request(method, endpoint, headers=_headers(recruiter["token"])).status_code == 403
        assert client.request(method, endpoint, headers=_headers(admin["token"])).status_code == 403


def test_candidate_cannot_remove_another_candidates_saved_job():
    owner = _identity()
    other = _identity()
    job = _job()
    assert client.post(f"{BASE}/{job.id}", headers=_headers(owner["token"])).status_code == 200

    assert client.delete(f"{BASE}/{job.id}", headers=_headers(other["token"])).status_code == 204
    owner_status = client.get(f"{BASE}/by-job/{job.id}", headers=_headers(owner["token"]))
    assert owner_status.json()["saved"] is True


def test_database_unique_constraint_prevents_duplicate_saved_jobs():
    candidate = _identity()
    job = _job()
    candidate_id = uuid.UUID(candidate["id"])
    db = SessionLocal()
    try:
        db.add(SavedJob(candidate_id=candidate_id, job_id=job.id))
        db.commit()
        db.add(SavedJob(candidate_id=candidate_id, job_id=job.id))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_saved_jobs_cascade_when_candidate_or_job_is_deleted():
    first_candidate = _identity()
    second_candidate = _identity()
    first_job = _job()
    second_job = _job()
    assert client.post(f"{BASE}/{first_job.id}", headers=_headers(first_candidate["token"])).status_code == 200
    assert client.post(f"{BASE}/{second_job.id}", headers=_headers(second_candidate["token"])).status_code == 200

    db = SessionLocal()
    db.query(Job).filter(Job.id == first_job.id).delete()
    db.query(User).filter(User.id == uuid.UUID(second_candidate["id"])).delete()
    db.commit()
    assert db.query(SavedJob).filter(SavedJob.job_id == first_job.id).count() == 0
    assert db.query(SavedJob).filter(
        SavedJob.candidate_id == uuid.UUID(second_candidate["id"])
    ).count() == 0
    db.close()
