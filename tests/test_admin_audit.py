"""Task 10H: admin-only, read-only application and candidate-CV audit tests."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV
from app.models.cv_template import CVTemplate, CVTemplateLayoutKey
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


client = TestClient(app)
ADMIN_APPLICATIONS = "/api/v1/admin/applications"
ADMIN_CVS = "/api/v1/admin/cvs"
CANDIDATE_CVS = "/api/v1/candidate/cvs"
MARKER = "__task10h__"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(role: UserRole, full_name: str = "Task 10H Candidate") -> tuple[str, str]:
    email = f"task10h_{uuid.uuid4().hex[:12]}@example.com"
    if role == UserRole.ADMIN:
        db = SessionLocal()
        try:
            user = User(email=email, password_hash=hash_password("password123"), full_name=full_name, role=role)
            db.add(user)
            db.commit()
            user_id = str(user.id)
        finally:
            db.close()
    else:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "full_name": full_name, "role": role.value},
        )
        assert registered.status_code == 201, registered.text
        db = SessionLocal()
        try:
            user_id = str(db.scalar(select(User.id).where(User.email == email)))
        finally:
            db.close()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"], user_id


def _create_template(*, active: bool = True) -> str:
    template_id = uuid.uuid4()
    db = SessionLocal()
    try:
        db.add(CVTemplate(id=template_id, name=f"{MARKER} Template {template_id.hex}", layout_key=CVTemplateLayoutKey.MODERN, is_active=active))
        db.commit()
    finally:
        db.close()
    return str(template_id)


def _create_cv(token: str, template_id: str, title: str) -> dict:
    response = client.post(
        CANDIDATE_CVS,
        json={
            "title": title,
            "template_id": template_id,
            "personal_info": {"full_name": "Audit Candidate", "email": "audit@example.com"},
            "skills": [{"name": "Python", "level": "ADVANCED"}],
            "experiences": [{"company_name": "GJob", "position": "Engineer", "is_current": True}],
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_job(title: str, company_name: str) -> str:
    db = SessionLocal()
    try:
        job = Job(title=title, description="Task 10H audit job", company_name=company_name, status=JobStatus.APPROVED)
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _create_application(candidate_id: str, job_id: str, cv_id: str, application_status: JobApplicationStatus) -> str:
    db = SessionLocal()
    try:
        application = JobApplication(candidate_id=uuid.UUID(candidate_id), job_id=uuid.UUID(job_id), cv_id=uuid.UUID(cv_id), status=application_status)
        db.add(application)
        db.commit()
        return str(application.id)
    finally:
        db.close()


def _cleanup_task_data() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like("task10h_%@example.com"))))
        job_ids = list(db.scalars(select(Job.id).where(Job.title.like(r"\_\_task10h\_\_%", escape="\\"))))
        if user_ids:
            db.query(JobApplication).filter(JobApplication.candidate_id.in_(user_ids)).delete(synchronize_session=False)
        if job_ids:
            db.query(JobApplication).filter(JobApplication.job_id.in_(job_ids)).delete(synchronize_session=False)
        if user_ids:
            db.query(CV).filter(CV.candidate_id.in_(user_ids)).delete(synchronize_session=False)
        if job_ids:
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if user_ids:
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(CVTemplate).filter(CVTemplate.name.like(f"{MARKER}%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def setup_function():
    _cleanup_task_data()


def teardown_function():
    _cleanup_task_data()


def test_admin_audit_routes_require_admin_and_expose_no_mutations():
    candidate_token, _ = _token(UserRole.CANDIDATE)
    recruiter_token, _ = _token(UserRole.RECRUITER)
    admin_token, _ = _token(UserRole.ADMIN)
    for endpoint in (ADMIN_APPLICATIONS, ADMIN_CVS):
        assert client.get(endpoint).status_code == 401
        assert client.get(endpoint, headers=_headers(candidate_token)).status_code == 403
        assert client.get(endpoint, headers=_headers(recruiter_token)).status_code == 403
        assert client.get(endpoint, headers=_headers(admin_token)).status_code == 200
        assert client.post(endpoint, headers=_headers(admin_token)).status_code == 405
        assert client.patch(f"{endpoint}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 405
        assert client.delete(f"{endpoint}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 405

    paths = app.openapi()["paths"]
    for endpoint in (ADMIN_APPLICATIONS, ADMIN_CVS):
        assert set(paths[endpoint]) == {"get"}
        assert set(paths[f"{endpoint}/{{{'application_id' if endpoint == ADMIN_APPLICATIONS else 'cv_id'}}}"]) == {"get"}


def test_admin_audits_applications_with_search_filters_pagination_and_current_cv_reference():
    admin_token, _ = _token(UserRole.ADMIN)
    candidate_a_token, candidate_a_id = _token(UserRole.CANDIDATE, "Audit Alice")
    candidate_b_token, candidate_b_id = _token(UserRole.CANDIDATE, "Audit Bob")
    template_id = _create_template()
    cv_a = _create_cv(candidate_a_token, template_id, f"{MARKER} Alice CV")
    cv_b = _create_cv(candidate_b_token, template_id, f"{MARKER} Bob CV")
    job_a = _create_job(f"{MARKER} Backend Engineer", f"{MARKER} GJob Labs")
    job_b = _create_job(f"{MARKER} Product Designer", "Other Company")
    application_a = _create_application(candidate_a_id, job_a, cv_a["id"], JobApplicationStatus.SUBMITTED)
    application_b = _create_application(candidate_b_id, job_b, cv_b["id"], JobApplicationStatus.REVIEWING)

    base_params = {"search": MARKER, "page_size": 100}
    response = client.get(ADMIN_APPLICATIONS, params=base_params, headers=_headers(admin_token))
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert {item["id"] for item in response.json()["items"]} == {application_a, application_b}
    assert all("password_hash" not in str(item) for item in response.json()["items"])

    for query, expected_id in (("audit alice", application_a), ("TASK10H_", application_a), ("backend engineer", application_a), ("gjob labs", application_a)):
        result = client.get(ADMIN_APPLICATIONS, params={"search": query, "page_size": 100}, headers=_headers(admin_token))
        assert result.status_code == 200
        assert expected_id in {item["id"] for item in result.json()["items"]}

    filtered = client.get(ADMIN_APPLICATIONS, params={"status": "SUBMITTED", "job_id": job_a, "candidate_id": candidate_a_id}, headers=_headers(admin_token))
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [application_a]
    assert client.get(ADMIN_APPLICATIONS, params={"status": "INVALID"}, headers=_headers(admin_token)).status_code == 422
    paged = client.get(ADMIN_APPLICATIONS, params={"search": MARKER, "page": 1, "page_size": 1}, headers=_headers(admin_token))
    assert paged.status_code == 200 and paged.json()["total"] == 2 and len(paged.json()["items"]) == 1
    assert client.get(ADMIN_APPLICATIONS, params={"search": "   "}, headers=_headers(admin_token)).status_code == 200

    assert client.patch(f"{CANDIDATE_CVS}/{cv_a['id']}", json={"title": "Current CV after application"}, headers=_headers(candidate_a_token)).status_code == 200
    detail = client.get(f"{ADMIN_APPLICATIONS}/{application_a}", headers=_headers(admin_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["candidate"]["id"] == candidate_a_id
    assert payload["job"]["id"] == job_a
    assert payload["cv"]["id"] == cv_a["id"]
    assert payload["cv"]["title"] == "Current CV after application"
    assert payload["cv"]["skills"][0]["name"] == "Python"
    assert "password_hash" not in str(payload)
    assert client.get(f"{ADMIN_APPLICATIONS}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 404


def test_admin_audits_candidate_cvs_across_owners_and_inactive_templates():
    admin_token, _ = _token(UserRole.ADMIN)
    candidate_a_token, candidate_a_id = _token(UserRole.CANDIDATE, "CV Audit Alice")
    candidate_b_token, candidate_b_id = _token(UserRole.CANDIDATE, "CV Audit Bob")
    active_template_id = _create_template()
    inactive_template_id = _create_template()
    first = _create_cv(candidate_a_token, active_template_id, f"{MARKER} Python CV")
    second = _create_cv(candidate_a_token, active_template_id, f"{MARKER} Platform CV")
    inactive_cv = _create_cv(candidate_b_token, inactive_template_id, f"{MARKER} Inactive Template CV")
    db = SessionLocal()
    try:
        db.query(CVTemplate).filter(CVTemplate.id == uuid.UUID(inactive_template_id)).update({CVTemplate.is_active: False})
        db.commit()
    finally:
        db.close()

    listed = client.get(ADMIN_CVS, params={"search": MARKER, "page_size": 100}, headers=_headers(admin_token))
    assert listed.status_code == 200, listed.text
    assert {item["id"] for item in listed.json()["items"]} == {first["id"], second["id"], inactive_cv["id"]}
    assert all("password_hash" not in str(item) for item in listed.json()["items"])

    for query, expected_id in (("python cv", first["id"]), ("cv audit alice", first["id"]), ("task10h_", first["id"])):
        result = client.get(ADMIN_CVS, params={"search": query, "page_size": 100}, headers=_headers(admin_token))
        assert result.status_code == 200
        assert expected_id in {item["id"] for item in result.json()["items"]}

    filtered = client.get(ADMIN_CVS, params={"template_id": active_template_id, "candidate_id": candidate_a_id, "is_default": "true"}, headers=_headers(admin_token))
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [first["id"]]
    assert client.get(ADMIN_CVS, params={"template_id": str(uuid.uuid4())}, headers=_headers(admin_token)).json()["total"] == 0
    paged = client.get(ADMIN_CVS, params={"search": MARKER, "page": 1, "page_size": 2}, headers=_headers(admin_token))
    assert paged.status_code == 200 and paged.json()["total"] == 3 and len(paged.json()["items"]) == 2

    detail = client.get(f"{ADMIN_CVS}/{inactive_cv['id']}", headers=_headers(admin_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["candidate"]["id"] == candidate_b_id
    assert payload["template"]["id"] == inactive_template_id
    assert payload["template"]["is_active"] is False
    assert payload["personal_info"]["email"] == "audit@example.com"
    assert payload["experiences"][0]["company_name"] == "GJob"
    assert payload["template"]["theme_config"]["primary_color"].startswith("#")
    assert "password_hash" not in str(payload)
    assert client.get(f"{ADMIN_CVS}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 404
