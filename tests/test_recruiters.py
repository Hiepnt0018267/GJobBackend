import uuid

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job, JobStatus

client = TestClient(app)
BASE = "/api/v1/recruiters"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(role: str = "RECRUITER") -> dict[str, str]:
    email = f"recruiter_{uuid.uuid4().hex[:10]}@example.com"
    registration = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Recruiter Test", "role": role})
    assert registration.status_code == 201, registration.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    return {"email": email, "token": login.json()["access_token"], "id": login.json()["user"]["id"]}


def test_get_recruiter_profile_lazy_creates_empty_profile():
    ctx = _register_and_login()
    response = client.get(f"{BASE}/me", headers=_headers(ctx["token"]))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == ctx["id"]
    assert data["email"] == ctx["email"]
    assert data["company_name"] is None
    assert "password_hash" not in data


def test_patch_recruiter_profile_and_get_persisted_data():
    ctx = _register_and_login()
    payload = {"full_name": "Recruiter Updated", "phone": "0901234567", "company_name": "GJob Co", "company_website": "https://gjob.example", "company_description": "Recruitment platform", "company_address": "Ha Noi", "company_logo_url": "https://gjob.example/logo.png", "industry": "Technology", "company_size": 50}
    response = client.patch(f"{BASE}/me", headers=_headers(ctx["token"]), json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["full_name"] == payload["full_name"]
    assert data["phone"] == payload["phone"]
    assert data["company_name"] == payload["company_name"]
    assert data["company_size"] == 50
    persisted = client.get(f"{BASE}/me", headers=_headers(ctx["token"]))
    assert persisted.status_code == 200
    assert persisted.json()["company_website"] == payload["company_website"]


def test_recruiter_profile_forbids_immutable_fields():
    ctx = _register_and_login()
    response = client.patch(f"{BASE}/me", headers=_headers(ctx["token"]), json={"role": "ADMIN"})
    assert response.status_code == 422


def test_candidate_cannot_access_recruiter_endpoints():
    ctx = _register_and_login("CANDIDATE")
    assert client.get(f"{BASE}/me", headers=_headers(ctx["token"])).status_code == 403
    assert client.patch(f"{BASE}/me", headers=_headers(ctx["token"]), json={"company_name": "Nope"}).status_code == 403
    assert client.get(f"{BASE}/me/dashboard", headers=_headers(ctx["token"])).status_code == 403


def test_dashboard_counts_only_current_recruiter_jobs():
    ctx = _register_and_login()
    other = _register_and_login()
    db = SessionLocal()
    jobs = [
        Job(recruiter_id=uuid.UUID(ctx["id"]), title="Dashboard Pending", description="test", company_name="GJob", status=JobStatus.PENDING),
        Job(recruiter_id=uuid.UUID(ctx["id"]), title="Dashboard Approved", description="test", company_name="GJob", status=JobStatus.APPROVED),
        Job(recruiter_id=uuid.UUID(other["id"]), title="Other Recruiter", description="test", company_name="Other", status=JobStatus.APPROVED),
    ]
    try:
        db.add_all(jobs)
        db.commit()
        response = client.get(f"{BASE}/me/dashboard", headers=_headers(ctx["token"]))
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_jobs"] == 2
        assert data["pending_jobs"] == 1
        assert data["approved_jobs"] == 1
        assert data["rejected_jobs"] == 0
        assert data["closed_jobs"] == 0
    finally:
        for job in jobs:
            db.delete(job)
        db.commit()
        db.close()
