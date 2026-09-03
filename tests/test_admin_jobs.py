"""Task 10A: ADMIN-only job moderation integration tests."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication
from app.models.cv import CV
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


client = TestClient(app)
ADMIN_JOBS_BASE = "/api/v1/admin/jobs"
PUBLIC_JOBS_BASE = "/api/v1/jobs"
CV_BASE = "/api/v1/candidate/cvs"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(role: str = "CANDIDATE") -> str:
    email = f"task10a_{uuid.uuid4().hex[:12]}@example.com"
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": "Task 10A", "role": role})
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token() -> str:
    email = f"task10a_admin_{uuid.uuid4().hex[:12]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(email=email, password_hash=hash_password("password123"), full_name="Task 10A Admin", role=UserRole.ADMIN))
        db.commit()
    finally:
        db.close()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_job(
    job_status: JobStatus = JobStatus.PENDING,
    *,
    title: str | None = None,
    company_name: str = "GJob",
) -> str:
    db = SessionLocal()
    try:
        job = Job(
            title=title or f"__task10a__ {job_status.value} {uuid.uuid4().hex}",
            description="Admin moderation integration test",
            company_name=company_name,
            status=job_status,
        )
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _get_persisted_status(job_id: str) -> JobStatus:
    db = SessionLocal()
    try:
        return db.scalar(select(Job.status).where(Job.id == uuid.UUID(job_id)))
    finally:
        db.close()


def _create_cv(token: str) -> str:
    response = client.post(
        CV_BASE,
        json={"title": "Task 10A CV", "template_id": MODERN_TEMPLATE_ID, "personal_info": {"full_name": "Candidate"}},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _cleanup_task_records() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like("task10a_%@example.com"))))
        job_ids = list(db.scalars(select(Job.id).where(Job.title.like(r"\_\_task10a\_\_%", escape="\\"))))
        if user_ids:
            db.query(JobApplication).filter(JobApplication.candidate_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(CV).filter(CV.candidate_id.in_(user_ids)).delete(synchronize_session=False)
        if job_ids:
            db.query(JobApplication).filter(JobApplication.job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if user_ids:
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_task_data():
    _cleanup_task_records()
    yield
    _cleanup_task_records()


def test_admin_job_list_requires_admin_role():
    params = {"search": "role-check"}
    assert client.get(ADMIN_JOBS_BASE, params=params).status_code == 401
    assert client.get(ADMIN_JOBS_BASE, params=params, headers=_headers(_token("CANDIDATE"))).status_code == 403
    assert client.get(ADMIN_JOBS_BASE, params=params, headers=_headers(_token("RECRUITER"))).status_code == 403
    assert client.get(ADMIN_JOBS_BASE, params=params, headers=_headers(_admin_token())).status_code == 200


def test_admin_lists_all_statuses_filters_and_paginates():
    admin_token = _admin_token()
    job_ids = {job_status: _create_job(job_status) for job_status in JobStatus}

    all_jobs = client.get(ADMIN_JOBS_BASE, params={"page": 1, "page_size": 100}, headers=_headers(admin_token))
    assert all_jobs.status_code == 200, all_jobs.text
    assert {job_id for job_id in job_ids.values()}.issubset({item["id"] for item in all_jobs.json()["items"]})

    for job_status, job_id in job_ids.items():
        response = client.get(ADMIN_JOBS_BASE, params={"status": job_status.value, "page_size": 100}, headers=_headers(admin_token))
        assert response.status_code == 200, response.text
        assert job_id in {item["id"] for item in response.json()["items"]}
        assert all(item["status"] == job_status.value for item in response.json()["items"])

    paged = client.get(ADMIN_JOBS_BASE, params={"page": 1, "page_size": 1}, headers=_headers(admin_token))
    assert paged.status_code == 200
    assert paged.json()["page"] == 1
    assert paged.json()["page_size"] == 1
    assert len(paged.json()["items"]) == 1
    assert client.get(ADMIN_JOBS_BASE, params={"status": "INVALID"}, headers=_headers(admin_token)).status_code == 422


def test_admin_searches_titles_and_company_names_case_insensitively():
    admin_token = _admin_token()
    search_marker = uuid.uuid4().hex
    title_match_id = _create_job(title=f"__task10a__ Backend Engineer {search_marker}")
    company_match_id = _create_job(title="__task10a__ Product Designer", company_name=f"Backend Labs {search_marker}")
    _create_job(title="__task10a__ Mobile Engineer", company_name="Other Company")

    response = client.get(ADMIN_JOBS_BASE, params={"search": search_marker[:12].upper()}, headers=_headers(admin_token))
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()["items"]} == {title_match_id, company_match_id}
    assert response.json()["total"] == 2


@pytest.mark.parametrize("job_status", list(JobStatus))
def test_admin_search_combines_with_each_status_and_keeps_filtered_total(job_status: JobStatus):
    search_marker = uuid.uuid4().hex
    matching_job_id = _create_job(job_status, title=f"__task10a__ Searchable {search_marker}")
    other_status = next(status for status in JobStatus if status != job_status)
    _create_job(other_status, title=f"__task10a__ Searchable {search_marker}")

    response = client.get(
        ADMIN_JOBS_BASE,
        params={"status": job_status.value, "search": search_marker},
        headers=_headers(_admin_token()),
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [matching_job_id]
    assert response.json()["items"][0]["status"] == job_status.value


def test_admin_search_handles_whitespace_unicode_special_characters_and_pagination():
    admin_token = _admin_token()
    first_id = _create_job(title="__task10a__ Kỹ sư Python A")
    second_id = _create_job(title="__task10a__ Kỹ sư Python B")
    newest_id = _create_job(title="__task10a__ Kỹ sư Python C")

    unicode_response = client.get(ADMIN_JOBS_BASE, params={"search": "kỹ SƯ"}, headers=_headers(admin_token))
    assert unicode_response.status_code == 200, unicode_response.text
    assert unicode_response.json()["total"] == 3

    whitespace_response = client.get(ADMIN_JOBS_BASE, params={"search": "   ", "page_size": 100}, headers=_headers(admin_token))
    unfiltered_response = client.get(ADMIN_JOBS_BASE, params={"page_size": 100}, headers=_headers(admin_token))
    assert whitespace_response.status_code == 200, whitespace_response.text
    assert whitespace_response.json()["total"] == unfiltered_response.json()["total"]

    special_response = client.get(ADMIN_JOBS_BASE, params={"search": "%_'"}, headers=_headers(admin_token))
    assert special_response.status_code == 200, special_response.text

    page_one = client.get(
        ADMIN_JOBS_BASE,
        params={"search": "Kỹ sư Python", "page": 1, "page_size": 2},
        headers=_headers(admin_token),
    )
    page_two = client.get(
        ADMIN_JOBS_BASE,
        params={"search": "Kỹ sư Python", "page": 2, "page_size": 2},
        headers=_headers(admin_token),
    )
    assert page_one.status_code == 200, page_one.text
    assert page_two.status_code == 200, page_two.text
    assert page_one.json()["total"] == 3
    assert [item["id"] for item in page_one.json()["items"]] == [newest_id, second_id]
    assert [item["id"] for item in page_two.json()["items"]] == [first_id]


def test_admin_can_view_job_detail_in_every_status_and_gets_404_for_missing_job():
    admin_token = _admin_token()
    for job_status in JobStatus:
        job_id = _create_job(job_status)
        response = client.get(f"{ADMIN_JOBS_BASE}/{job_id}", headers=_headers(admin_token))
        assert response.status_code == 200, response.text
        assert response.json()["status"] == job_status.value
        assert response.json()["id"] == job_id
    assert client.get(f"{ADMIN_JOBS_BASE}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 404


def test_admin_approves_pending_job_persists_status_updates_dashboard_and_makes_job_public():
    admin_token = _admin_token()
    job_id = _create_job()
    dashboard_before = client.get("/api/v1/admin/dashboard", headers=_headers(admin_token)).json()["jobs"]

    response = client.patch(
        f"{ADMIN_JOBS_BASE}/{job_id}/approve",
        json={"status": "REJECTED", "title": "Client cannot edit this"},
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == JobStatus.APPROVED.value
    assert _get_persisted_status(job_id) == JobStatus.APPROVED
    assert client.get(f"{PUBLIC_JOBS_BASE}/{job_id}").status_code == 200

    dashboard_after = client.get("/api/v1/admin/dashboard", headers=_headers(admin_token)).json()["jobs"]
    assert dashboard_after["pending"] == dashboard_before["pending"] - 1
    assert dashboard_after["approved"] == dashboard_before["approved"] + 1


def test_admin_rejects_pending_job_and_rejected_job_stays_private():
    admin_token = _admin_token()
    job_id = _create_job()
    response = client.patch(f"{ADMIN_JOBS_BASE}/{job_id}/reject", headers=_headers(admin_token))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == JobStatus.REJECTED.value
    assert _get_persisted_status(job_id) == JobStatus.REJECTED
    assert client.get(f"{PUBLIC_JOBS_BASE}/{job_id}").status_code == 404


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_admin_moderation_actions_return_404_for_missing_job(action: str):
    response = client.patch(f"{ADMIN_JOBS_BASE}/{uuid.uuid4()}/{action}", headers=_headers(_admin_token()))
    assert response.status_code == 404


@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("job_status", [JobStatus.APPROVED, JobStatus.REJECTED, JobStatus.CLOSED])
def test_admin_rejects_invalid_state_transitions(action: str, job_status: JobStatus):
    response = client.patch(f"{ADMIN_JOBS_BASE}/{_create_job(job_status)}/{action}", headers=_headers(_admin_token()))
    assert response.status_code == 409


@pytest.mark.parametrize("role", ["CANDIDATE", "RECRUITER"])
@pytest.mark.parametrize("action", ["approve", "reject"])
def test_non_admin_cannot_moderate_jobs(role: str, action: str):
    job_id = _create_job()
    assert client.patch(f"{ADMIN_JOBS_BASE}/{job_id}/{action}").status_code == 401
    assert client.patch(f"{ADMIN_JOBS_BASE}/{job_id}/{action}", headers=_headers(_token(role))).status_code == 403


def test_pending_job_becomes_eligible_for_application_only_after_admin_approval():
    candidate_token = _token()
    admin_token = _admin_token()
    job_id = _create_job()
    cv_id = _create_cv(candidate_token)

    pending_application = client.post(f"{PUBLIC_JOBS_BASE}/{job_id}/applications", json={"cv_id": cv_id}, headers=_headers(candidate_token))
    assert pending_application.status_code == 409

    assert client.patch(f"{ADMIN_JOBS_BASE}/{job_id}/approve", headers=_headers(admin_token)).status_code == 200
    approved_application = client.post(f"{PUBLIC_JOBS_BASE}/{job_id}/applications", json={"cv_id": cv_id}, headers=_headers(candidate_token))
    assert approved_application.status_code == 201, approved_application.text
