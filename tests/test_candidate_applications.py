"""Task 11A: candidate-owned application-management integration tests."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication, JobApplicationStatus
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


client = TestClient(app)
APPLICATIONS_BASE = "/api/v1/candidate/applications"
JOBS_BASE = "/api/v1/jobs"
CV_BASE = "/api/v1/candidate/cvs"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _token(role: str = "CANDIDATE") -> str:
    email = f"task11a_{uuid.uuid4().hex[:12]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Task 11A", "role": role},
    )
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _admin_token() -> str:
    email = f"task11a_admin_{uuid.uuid4().hex[:12]}@example.com"
    db = SessionLocal()
    try:
        db.add(
            User(
                email=email,
                password_hash=hash_password("password123"),
                full_name="Task 11A Admin",
                role=UserRole.ADMIN,
            )
        )
        db.commit()
    finally:
        db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_job(
    title: str | None = None,
    company_name: str = "GJob Labs",
    job_status: JobStatus = JobStatus.APPROVED,
) -> str:
    db = SessionLocal()
    try:
        job = Job(
            title=title or f"Task 11A Job {uuid.uuid4().hex}",
            description="Candidate application management test",
            company_name=company_name,
            location="Ha Noi",
            status=job_status,
        )
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _create_cv(token: str, title: str = "Application CV") -> dict:
    response = client.post(
        CV_BASE,
        json={
            "title": title,
            "template_id": MODERN_TEMPLATE_ID,
            "personal_info": {"full_name": "Candidate"},
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _apply(token: str, job_id: str, cv_id: str) -> dict:
    response = client.post(
        f"{JOBS_BASE}/{job_id}/applications",
        json={"cv_id": cv_id},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_application_status(application_id: str, application_status: JobApplicationStatus) -> None:
    db = SessionLocal()
    try:
        application = db.get(JobApplication, uuid.UUID(application_id))
        assert application is not None
        application.status = application_status
        db.commit()
    finally:
        db.close()


def _set_job_status(job_id: str, job_status: JobStatus) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(job_id))
        assert job is not None
        job.status = job_status
        db.commit()
    finally:
        db.close()


def test_candidate_application_endpoints_require_candidate_role():
    application_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    recruiter_headers = _headers(_token("RECRUITER"))
    admin_headers = _headers(_admin_token())
    endpoints = [
        ("get", APPLICATIONS_BASE),
        ("get", f"{APPLICATIONS_BASE}/by-job/{job_id}"),
        ("get", f"{APPLICATIONS_BASE}/{application_id}"),
        ("patch", f"{APPLICATIONS_BASE}/{application_id}/withdraw"),
    ]
    for method, endpoint in endpoints:
        assert getattr(client, method)(endpoint).status_code == 401
        assert getattr(client, method)(endpoint, headers=recruiter_headers).status_code == 403
        assert getattr(client, method)(endpoint, headers=admin_headers).status_code == 403


def test_candidate_can_only_read_and_withdraw_own_application():
    owner, other = _token(), _token()
    application = _apply(owner, _create_job(), _create_cv(owner)["id"])

    assert client.get(f"{APPLICATIONS_BASE}/{application['id']}", headers=_headers(other)).status_code == 404
    assert client.patch(
        f"{APPLICATIONS_BASE}/{application['id']}/withdraw", headers=_headers(other)
    ).status_code == 404


def test_list_filters_searches_paginates_and_never_returns_other_candidates_applications():
    token, other = _token(), _token()
    cv = _create_cv(token)
    first = _apply(token, _create_job("Senior Python Engineer", "GJob Labs"), cv["id"])
    second = _apply(token, _create_job("Content Writer", "Blue Ocean"), cv["id"])
    third = _apply(token, _create_job("Frontend Engineer", "GJob Labs"), cv["id"])
    _set_application_status(second["id"], JobApplicationStatus.REVIEWING)
    other_application = _apply(other, _create_job("Private Other Candidate Job"), _create_cv(other)["id"])

    listed = client.get(APPLICATIONS_BASE, headers=_headers(token))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    item_ids = {item["id"] for item in payload["items"]}
    assert {first["id"], second["id"], third["id"]}.issubset(item_ids)
    assert other_application["id"] not in item_ids

    filtered = client.get(f"{APPLICATIONS_BASE}?status=REVIEWING", headers=_headers(token))
    assert filtered.status_code == 200, filtered.text
    assert [item["id"] for item in filtered.json()["items"]] == [second["id"]]

    title_search = client.get(f"{APPLICATIONS_BASE}?search=python", headers=_headers(token))
    assert title_search.status_code == 200, title_search.text
    assert first["id"] in {item["id"] for item in title_search.json()["items"]}

    company_search = client.get(f"{APPLICATIONS_BASE}?search=%20%20gjob%20%20labs%20%20", headers=_headers(token))
    assert company_search.status_code == 200, company_search.text
    assert {first["id"], third["id"]}.issubset({item["id"] for item in company_search.json()["items"]})

    first_page = client.get(f"{APPLICATIONS_BASE}?page=1&page_size=1", headers=_headers(token))
    second_page = client.get(f"{APPLICATIONS_BASE}?page=2&page_size=1", headers=_headers(token))
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] >= 3
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]
    assert client.get(f"{APPLICATIONS_BASE}?status=NOT_A_STATUS", headers=_headers(token)).status_code == 422


def test_detail_uses_current_cv_reference_and_by_job_includes_non_public_jobs():
    token = _token()
    cv = _create_cv(token, "Original title")
    job_id = _create_job("Reference Job")
    application = _apply(token, job_id, cv["id"])
    updated_cv = client.patch(
        f"{CV_BASE}/{cv['id']}", json={"title": "Updated title"}, headers=_headers(token)
    )
    assert updated_cv.status_code == 200, updated_cv.text
    _set_job_status(job_id, JobStatus.CLOSED)

    detail = client.get(f"{APPLICATIONS_BASE}/{application['id']}", headers=_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["cv"]["title"] == "Updated title"
    assert detail.json()["job"]["status"] == "CLOSED"

    by_job = client.get(f"{APPLICATIONS_BASE}/by-job/{job_id}", headers=_headers(token))
    assert by_job.status_code == 200, by_job.text
    assert by_job.json()["has_applied"] is True
    assert by_job.json()["application"]["status"] == "SUBMITTED"
    assert client.get(
        f"{APPLICATIONS_BASE}/by-job/{uuid.uuid4()}", headers=_headers(token)
    ).json() == {"has_applied": False, "application": None}


@pytest.mark.parametrize(
    "application_status",
    [
        JobApplicationStatus.SUBMITTED,
        JobApplicationStatus.REVIEWING,
        JobApplicationStatus.SHORTLISTED,
    ],
)
def test_candidate_can_withdraw_only_eligible_application_statuses(application_status: JobApplicationStatus):
    token = _token()
    application = _apply(token, _create_job(), _create_cv(token)["id"])
    _set_application_status(application["id"], application_status)

    withdrawn = client.patch(
        f"{APPLICATIONS_BASE}/{application['id']}/withdraw", headers=_headers(token)
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "WITHDRAWN"
    assert client.patch(
        f"{APPLICATIONS_BASE}/{application['id']}/withdraw", headers=_headers(token)
    ).status_code == 409
    by_job = client.get(f"{APPLICATIONS_BASE}/by-job/{application['job_id']}", headers=_headers(token))
    assert by_job.json()["has_applied"] is True
    assert by_job.json()["application"]["status"] == "WITHDRAWN"


@pytest.mark.parametrize(
    "application_status",
    [
        JobApplicationStatus.REJECTED,
        JobApplicationStatus.HIRED,
        JobApplicationStatus.WITHDRAWN,
    ],
)
def test_candidate_cannot_withdraw_terminal_application_statuses(application_status: JobApplicationStatus):
    token = _token()
    application = _apply(token, _create_job(), _create_cv(token)["id"])
    _set_application_status(application["id"], application_status)

    response = client.patch(
        f"{APPLICATIONS_BASE}/{application['id']}/withdraw", headers=_headers(token)
    )
    assert response.status_code == 409
