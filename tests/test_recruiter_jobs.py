"""Task 06A: recruiter-owned job management integration tests."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.job import Job, JobStatus


client = TestClient(app)
BASE = "/api/v1/recruiters/jobs"


def _token(role="RECRUITER"):
    email = f"task06a_{uuid.uuid4().hex[:12]}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "full_name": "Task 06A", "role": role,
    })
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return response.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _payload(**overrides):
    value = {
        "title": "Backend Engineer", "description": "Build reliable APIs.",
        "company_name": "GJob", "location": "Ho Chi Minh City",
        "employment_type": "FULL_TIME", "level": "JUNIOR",
        "experience_requirement": "ONE_TO_THREE_YEARS", "work_mode": "HYBRID",
        "industry": "INFORMATION_TECHNOLOGY", "vacancies": 2,
        "salary_type": "RANGE", "salary_min": 15000000, "salary_max": 25000000,
        "skills": ["Python", "FastAPI"], "requirements": "Python experience", "benefits": "Health insurance",
    }
    value.update(overrides)
    return value


def _create(token, **overrides):
    response = client.post(BASE, json=_payload(**overrides), headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _set_status(job_id, status):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == uuid.UUID(job_id)).one()
        job.status = JobStatus(status)
        db.commit()
    finally:
        db.close()


def test_management_requires_recruiter_role():
    assert client.get(BASE).status_code in (401, 403)
    assert client.get(BASE, headers=_headers(_token("CANDIDATE"))).status_code == 403


def test_create_forces_pending_and_rejects_server_fields():
    token = _token()
    created = _create(token)
    assert created["status"] == "PENDING"
    assert created["recruiter_id"]
    response = client.post(BASE, json=_payload(status="APPROVED"), headers=_headers(token))
    assert response.status_code == 422


def test_salary_rules_and_partial_update_are_validated():
    token = _token()
    assert client.post(BASE, json=_payload(salary_max=1), headers=_headers(token)).status_code == 422
    fixed = _create(token, salary_type="FIXED", salary_min=None, salary_max=None, salary_fixed=20000000)
    invalid = client.patch(f"{BASE}/{fixed['id']}", json={"salary_type": "RANGE"}, headers=_headers(token))
    assert invalid.status_code == 422


def test_ownership_list_and_lifecycle_rules():
    owner, other = _token(), _token()
    job = _create(owner)
    job_id = job["id"]
    assert client.get(f"{BASE}/{job_id}", headers=_headers(other)).status_code == 404
    assert client.patch(f"{BASE}/{job_id}", json={"title": "Nope"}, headers=_headers(other)).status_code == 404
    assert client.delete(f"{BASE}/{job_id}", headers=_headers(other)).status_code == 404
    assert client.patch(f"{BASE}/{job_id}/close", headers=_headers(other)).status_code == 404
    assert client.get(BASE, headers=_headers(other)).json()["total"] == 0

    _set_status(job_id, "APPROVED")
    edited = client.patch(f"{BASE}/{job_id}", json={"title": "Senior Backend Engineer"}, headers=_headers(owner))
    assert edited.status_code == 200 and edited.json()["status"] == "PENDING"
    _set_status(job_id, "APPROVED")
    assert client.delete(f"{BASE}/{job_id}", headers=_headers(owner)).status_code == 409
    closed = client.patch(f"{BASE}/{job_id}/close", headers=_headers(owner))
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert client.patch(f"{BASE}/{job_id}", json={"title": "Changed"}, headers=_headers(owner)).status_code == 409


def test_pending_delete_dashboard_and_public_visibility():
    token = _token()
    job = _create(token)
    dashboard = client.get("/api/v1/recruiters/me/dashboard", headers=_headers(token)).json()
    assert dashboard["pending_jobs"] >= 1
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert client.delete(f"{BASE}/{job['id']}", headers=_headers(token)).status_code == 204
    assert client.get(f"{BASE}/{job['id']}", headers=_headers(token)).status_code == 404
