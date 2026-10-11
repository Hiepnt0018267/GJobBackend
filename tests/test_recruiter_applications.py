"""Task 12A: recruiter-owned applicant management integration tests."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication, JobApplicationStatus
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.repositories.candidate_application_repository import CandidateApplicationRepository
from app.repositories.recruiter_application_repository import RecruiterApplicationRepository


client = TestClient(app)
BASE = "/api/v1/recruiters/applications"
JOB_BASE = "/api/v1/recruiters/jobs"
CV_BASE = "/api/v1/candidate/cvs"
JOBS_BASE = "/api/v1/jobs"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(role: UserRole, full_name: str) -> tuple[str, str]:
    email = f"task12a_{uuid.uuid4().hex[:16]}@example.com"
    if role == UserRole.ADMIN:
        db = SessionLocal()
        try:
            user = User(
                email=email,
                password_hash=hash_password("password123"),
                full_name=full_name,
                role=role,
            )
            db.add(user)
            db.commit()
            user_id = str(user.id)
        finally:
            db.close()
    else:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "password123",
                "full_name": full_name,
                "role": role.value,
            },
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


def _create_job(recruiter_id: str, title: str) -> str:
    db = SessionLocal()
    try:
        job = Job(
            recruiter_id=uuid.UUID(recruiter_id),
            title=title,
            description="Recruiter applicant management test",
            company_name="Task 12A Labs",
            status=JobStatus.APPROVED,
        )
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _create_cv(token: str, title: str) -> dict:
    response = client.post(
        CV_BASE,
        json={
            "title": title,
            "template_id": MODERN_TEMPLATE_ID,
            "personal_info": {"full_name": "Task 12A Candidate", "email": "candidate@example.com"},
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _apply(candidate_token: str, job_id: str, cv_id: str) -> dict:
    response = client.post(
        f"{JOBS_BASE}/{job_id}/applications",
        json={"cv_id": cv_id},
        headers=_headers(candidate_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_status(application_id: str, application_status: JobApplicationStatus) -> None:
    db = SessionLocal()
    try:
        application = db.get(JobApplication, uuid.UUID(application_id))
        assert application is not None
        application.status = application_status
        db.commit()
    finally:
        db.close()


def _application_for(
    recruiter_id: str,
    candidate_token: str,
    cv_id: str,
    title: str,
    application_status: JobApplicationStatus = JobApplicationStatus.SUBMITTED,
) -> tuple[str, dict]:
    job_id = _create_job(recruiter_id, title)
    application = _apply(candidate_token, job_id, cv_id)
    if application_status != JobApplicationStatus.SUBMITTED:
        _set_status(application["id"], application_status)
    return job_id, application


def test_recruiter_application_routes_require_recruiter_role():
    candidate_token, _ = _token(UserRole.CANDIDATE, "Task 12A Candidate")
    admin_token, _ = _token(UserRole.ADMIN, "Task 12A Admin")
    application_id = uuid.uuid4()
    job_id = uuid.uuid4()
    endpoints = [
        ("get", BASE),
        ("get", f"{BASE}/{application_id}"),
        ("get", f"{JOB_BASE}/{job_id}/applications"),
        ("patch", f"{BASE}/{application_id}/review"),
        ("patch", f"{BASE}/{application_id}/shortlist"),
        ("patch", f"{BASE}/{application_id}/reject"),
        ("patch", f"{BASE}/{application_id}/hire"),
    ]
    for method, endpoint in endpoints:
        assert getattr(client, method)(endpoint).status_code == 401
        assert getattr(client, method)(endpoint, headers=_headers(candidate_token)).status_code == 403
        assert getattr(client, method)(endpoint, headers=_headers(admin_token)).status_code == 403


def test_global_and_job_scoped_lists_are_owned_filtered_searchable_and_paginated():
    recruiter_token, recruiter_id = _token(UserRole.RECRUITER, "Recruiter Alpha")
    other_recruiter_token, other_recruiter_id = _token(UserRole.RECRUITER, "Recruiter Beta")
    candidate_token, _ = _token(UserRole.CANDIDATE, "Alice Applicant")
    other_candidate_token, _ = _token(UserRole.CANDIDATE, "Bob Applicant")
    candidate_cv = _create_cv(candidate_token, "Python CV")
    other_cv = _create_cv(other_candidate_token, "Design CV")
    first_job, first = _application_for(recruiter_id, candidate_token, candidate_cv["id"], "Senior Python Engineer")
    second_job, second = _application_for(recruiter_id, candidate_token, candidate_cv["id"], "Product Engineer")
    _, other = _application_for(other_recruiter_id, other_candidate_token, other_cv["id"], "Private Designer")
    _set_status(second["id"], JobApplicationStatus.REVIEWING)

    listed = client.get(BASE, params={"page_size": 100}, headers=_headers(recruiter_token))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["total"] == 2
    assert {item["id"] for item in payload["items"]} == {first["id"], second["id"]}
    assert other["id"] not in {item["id"] for item in payload["items"]}
    assert all("password_hash" not in str(item) for item in payload["items"])

    for search, expected_id in (
        ("alice applicant", first["id"]),
        ("task12a_", first["id"]),
        ("python engineer", first["id"]),
        ("python cv", first["id"]),
    ):
        result = client.get(BASE, params={"search": search}, headers=_headers(recruiter_token))
        assert result.status_code == 200, result.text
        assert expected_id in {item["id"] for item in result.json()["items"]}

    whitespace = client.get(BASE, params={"search": "   ", "page_size": 100}, headers=_headers(recruiter_token))
    assert whitespace.status_code == 200 and whitespace.json()["total"] == 2
    filtered = client.get(BASE, params={"status": "REVIEWING"}, headers=_headers(recruiter_token))
    assert [item["id"] for item in filtered.json()["items"]] == [second["id"]]
    assert client.get(BASE, params={"status": "INVALID"}, headers=_headers(recruiter_token)).status_code == 422
    assert client.get(BASE, params={"job_id": first_job}, headers=_headers(recruiter_token)).json()["total"] == 1
    assert client.get(BASE, params={"job_id": second_job}, headers=_headers(recruiter_token)).json()["total"] == 1
    assert client.get(BASE, params={"job_id": _create_job(other_recruiter_id, "Foreign Job")}, headers=_headers(recruiter_token)).json()["total"] == 0

    first_page = client.get(BASE, params={"page": 1, "page_size": 1}, headers=_headers(recruiter_token))
    second_page = client.get(BASE, params={"page": 2, "page_size": 1}, headers=_headers(recruiter_token))
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]

    scoped = client.get(f"{JOB_BASE}/{first_job}/applications", headers=_headers(recruiter_token))
    assert scoped.status_code == 200 and [item["id"] for item in scoped.json()["items"]] == [first["id"]]
    foreign_scoped = client.get(f"{JOB_BASE}/{_create_job(other_recruiter_id, 'Other Job')}/applications", headers=_headers(recruiter_token))
    assert foreign_scoped.status_code == 404
    assert client.get(f"{JOB_BASE}/{uuid.uuid4()}/applications", headers=_headers(recruiter_token)).status_code == 404
    assert client.get(BASE, params={"search": "no matching candidate"}, headers=_headers(recruiter_token)).json()["items"] == []


def test_recruiter_detail_is_owned_and_uses_current_cv_reference():
    recruiter_token, recruiter_id = _token(UserRole.RECRUITER, "Recruiter Detail")
    other_recruiter_token, _ = _token(UserRole.RECRUITER, "Recruiter Other")
    candidate_token, _ = _token(UserRole.CANDIDATE, "Detail Candidate")
    cv = _create_cv(candidate_token, "Original CV title")
    _, application = _application_for(recruiter_id, candidate_token, cv["id"], "Detail Job")

    updated = client.patch(f"{CV_BASE}/{cv['id']}", json={"title": "Current CV title"}, headers=_headers(candidate_token))
    assert updated.status_code == 200, updated.text
    detail = client.get(f"{BASE}/{application['id']}", headers=_headers(recruiter_token))
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["candidate"]["email"].endswith("@example.com")
    assert payload["job"]["title"] == "Detail Job"
    assert payload["cv"]["title"] == "Current CV title"
    assert payload["cv"]["template"]["layout_key"] == "MODERN"
    assert "password_hash" not in str(payload)
    assert client.get(f"{BASE}/{application['id']}", headers=_headers(other_recruiter_token)).status_code == 404
    assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_headers(recruiter_token)).status_code == 404


def test_strict_recruiter_transition_workflow_and_terminal_states():
    recruiter_token, recruiter_id = _token(UserRole.RECRUITER, "Recruiter Workflow")
    candidate_token, _ = _token(UserRole.CANDIDATE, "Workflow Candidate")
    cv = _create_cv(candidate_token, "Workflow CV")

    _, sequential = _application_for(recruiter_id, candidate_token, cv["id"], "Sequential Job")
    application_id = sequential["id"]
    assert client.patch(f"{BASE}/{application_id}/shortlist", headers=_headers(recruiter_token)).status_code == 409
    assert client.patch(f"{BASE}/{application_id}/hire", headers=_headers(recruiter_token)).status_code == 409
    assert client.patch(f"{BASE}/{application_id}/review", headers=_headers(recruiter_token)).json()["status"] == "REVIEWING"
    assert client.patch(f"{BASE}/{application_id}/review", headers=_headers(recruiter_token)).status_code == 409
    assert client.patch(f"{BASE}/{application_id}/hire", headers=_headers(recruiter_token)).status_code == 409
    assert client.patch(f"{BASE}/{application_id}/shortlist", headers=_headers(recruiter_token)).json()["status"] == "SHORTLISTED"
    assert client.patch(f"{BASE}/{application_id}/shortlist", headers=_headers(recruiter_token)).status_code == 409
    assert client.patch(f"{BASE}/{application_id}/hire", headers=_headers(recruiter_token)).json()["status"] == "HIRED"
    for action in ("review", "shortlist", "reject", "hire"):
        assert client.patch(f"{BASE}/{application_id}/{action}", headers=_headers(recruiter_token)).status_code == 409

    for application_status in (
        JobApplicationStatus.SUBMITTED,
        JobApplicationStatus.REVIEWING,
        JobApplicationStatus.SHORTLISTED,
    ):
        _, rejectable = _application_for(
            recruiter_id,
            candidate_token,
            cv["id"],
            f"Reject {application_status.value}",
            application_status,
        )
        rejected = client.patch(f"{BASE}/{rejectable['id']}/reject", headers=_headers(recruiter_token))
        assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
        assert client.patch(f"{BASE}/{rejectable['id']}/reject", headers=_headers(recruiter_token)).status_code == 409

    for terminal_status in (JobApplicationStatus.REJECTED, JobApplicationStatus.WITHDRAWN):
        _, terminal = _application_for(
            recruiter_id,
            candidate_token,
            cv["id"],
            f"Terminal {terminal_status.value}",
            terminal_status,
        )
        for action in ("review", "shortlist", "reject", "hire"):
            assert client.patch(f"{BASE}/{terminal['id']}/{action}", headers=_headers(recruiter_token)).status_code == 409


def test_recruiter_transition_and_candidate_withdraw_do_not_overwrite_each_other():
    recruiter_token, recruiter_id = _token(UserRole.RECRUITER, "Recruiter Race")
    candidate_token, _ = _token(UserRole.CANDIDATE, "Race Candidate")
    cv = _create_cv(candidate_token, "Race CV")
    _, application = _application_for(recruiter_id, candidate_token, cv["id"], "Race Job")
    application_id = application["id"]
    assert client.patch(f"{BASE}/{application_id}/review", headers=_headers(recruiter_token)).status_code == 200

    db = SessionLocal()
    try:
        candidate_id = db.get(JobApplication, uuid.UUID(application_id)).candidate_id
    finally:
        db.close()

    candidate_db, recruiter_db = SessionLocal(), SessionLocal()
    try:
        candidate_repository = CandidateApplicationRepository(candidate_db)
        recruiter_repository = RecruiterApplicationRepository(recruiter_db)
        with ThreadPoolExecutor(max_workers=2) as executor:
            withdraw = executor.submit(
                candidate_repository.withdraw_if_eligible,
                uuid.UUID(application_id),
                candidate_id,
                JobApplicationStatus.REVIEWING,
            )
            shortlist = executor.submit(
                recruiter_repository.transition_if_current,
                uuid.UUID(application_id),
                uuid.UUID(recruiter_id),
                JobApplicationStatus.REVIEWING,
                JobApplicationStatus.SHORTLISTED,
            )
        assert sorted([withdraw.result(), shortlist.result()]) == [False, True]
    finally:
        candidate_db.close()
        recruiter_db.close()

    detail = client.get(f"{BASE}/{application_id}", headers=_headers(recruiter_token))
    assert detail.status_code == 200
    assert detail.json()["status"] in {"WITHDRAWN", "SHORTLISTED"}


def test_openapi_exposes_explicit_actions_without_generic_status_mutation():
    paths = app.openapi()["paths"]
    assert f"{BASE}/{{application_id}}/status" not in paths
    assert set(paths[BASE]) == {"get"}
    assert set(paths[f"{BASE}/{{application_id}}/review"]) == {"patch"}
    assert set(paths[f"{BASE}/{{application_id}}/shortlist"]) == {"patch"}
    assert set(paths[f"{BASE}/{{application_id}}/reject"]) == {"patch"}
    assert set(paths[f"{BASE}/{{application_id}}/hire"]) == {"patch"}


def test_opt_in_global_ai_paging_authorization_and_no_business_writes(monkeypatch):
    from app.services.ranking_cache import RankingCache
    from app.services.cv_structured_extraction_service import CVStructuredExtractionService
    from app.services import ranking_cache
    recruiter_token, recruiter_id = _token(UserRole.RECRUITER, "AI Synthetic Owner")
    other_token, other_id = _token(UserRole.RECRUITER, "AI Synthetic Other")
    ids = [uuid.UUID(recruiter_id), uuid.UUID(other_id)]
    scores = {}; lookups = []
    async def forbidden(*args, **kwargs):
        raise AssertionError("List must not call extraction/embedding")
    monkeypatch.setattr(CVStructuredExtractionService, "extract_from_text", forbidden)
    monkeypatch.setattr(ranking_cache, "get_embedding_provider", lambda: (_ for _ in ()).throw(AssertionError("provider factory in list")))
    def signals(self, kind, canonical):
        lookups.append(kind)
        if kind == "job": return "ranked", [1., 0.]
        value = scores.get(str(canonical.cv_id))
        if value is None: return "pending", None
        return "ranked", [value, (1-value**2)**.5]
    monkeypatch.setattr(RankingCache, "vector", signals)
    try:
        job_id = _create_job(recruiter_id, "AI Synthetic Job")
        applications = []
        for i in range(17):
            candidate_token, candidate_id = _token(UserRole.CANDIDATE, "AI Synthetic Candidate")
            ids.append(uuid.UUID(candidate_id))
            cv = _create_cv(candidate_token, f"AI Synthetic CV {i}")
            applications.append(_apply(candidate_token, job_id, cv["id"]))
            scores[cv["id"]] = .05 + i*.05
        newest = client.get(f"/api/v1/recruiters/jobs/{job_id}/applications", headers=_headers(recruiter_token), params={"page_size":100})
        assert newest.status_code == 200 and newest.json()["total"] == 17 and not lookups
        default_ids = [item["id"] for item in newest.json()["items"]]
        assert default_ids == [item["id"] for item in reversed(applications)]
        denied = client.get(f"/api/v1/recruiters/jobs/{job_id}/applications", headers=_headers(other_token), params={"sort":"ai_match"})
        assert denied.status_code == 404 and not lookups
        assert client.get(BASE, headers=_headers(recruiter_token), params={"sort":"invalid"}).status_code == 422
        assert client.get(BASE, headers=_headers(recruiter_token), params={"ai_top_n":5}).status_code == 422
        # Move the oldest item to top, proving the database is NOT paginated first.
        scores[applications[0]["cv_id"]] = .99
        scores[applications[10]["cv_id"]] = None
        path = f"/api/v1/recruiters/jobs/{job_id}/applications"
        params = {"sort":"ai_match", "page_size":5}
        from sqlalchemy import event
        from app.core import database
        queries = []
        def count_query(connection, cursor, statement, parameters, context, executemany):
            queries.append(statement)
        event.listen(database.engine, "before_cursor_execute", count_query)
        try:
            first = client.get(path, headers=_headers(recruiter_token), params=params)
        finally:
            event.remove(database.engine, "before_cursor_execute", count_query)
        assert len(queries) <= 8  # constant query count for 17 candidates, not N+1
        assert first.status_code == 200 and first.json()["items"][0]["id"] == applications[0]["id"]
        snapshot = first.json()["ranking_snapshot"]
        scores[applications[10]["cv_id"]] = 1.
        seen = [item["id"] for item in first.json()["items"]]
        count = len(lookups)
        for page in (2,3,4):
            response = client.get(path, headers=_headers(recruiter_token), params={**params,"page":page,"ranking_snapshot":snapshot})
            assert response.status_code == 200
            seen.extend(item["id"] for item in response.json()["items"])
        assert len(seen) == len(set(seen)) == 17 and len(lookups) == count
        assert client.get(path, headers=_headers(recruiter_token), params={**params,"page":2}).status_code == 422
        limited = client.get(path, headers=_headers(recruiter_token), params={"sort":"ai_match","ai_top_n":5,"page_size":100})
        assert limited.status_code == 200 and limited.json()["total"] == 5
        assert limited.json()["items"][0]["id"] == applications[10]["id"]
        empty = client.get(path, headers=_headers(recruiter_token), params={"sort":"ai_match", "search":"no-such-application"})
        assert empty.status_code == 200 and empty.json()["total"] == 0
        filtered = client.get(path, headers=_headers(recruiter_token), params={"sort":"ai_match", "status":"REJECTED"})
        assert filtered.status_code == 200 and filtered.json()["total"] == 0
        # A positive search selects a one-applicant logical set BEFORE ranking.
        selected = client.get(path, headers=_headers(recruiter_token), params={"sort":"ai_match", "search":"AI Synthetic CV 16"})
        assert selected.status_code == 200 and selected.json()["total"] == 1
        assert selected.json()["items"][0]["id"] == applications[16]["id"]
        assert selected.json()["items"][0]["ai_rank"] == 1
        db = SessionLocal()
        try:
            statuses = db.query(JobApplication.status).filter(JobApplication.job_id == uuid.UUID(job_id)).all()
            assert all(row[0] == JobApplicationStatus.SUBMITTED for row in statuses)
        finally:
            db.close()
    finally:
        # Only this task's unique synthetic principals; FK cascades remove their
        # CV/job/application fixtures. No DEV engine can reach this guarded test.
        db = SessionLocal()
        try:
            db.query(JobApplication).filter(JobApplication.candidate_id.in_(ids)).delete(synchronize_session=False)
            db.query(Job).filter(Job.recruiter_id.in_(ids)).delete(synchronize_session=False)
            db.flush()
            for user_id in ids:
                user = db.get(User, user_id)
                if user is not None: db.delete(user)
            db.commit()
        finally:
            db.close()


def test_robustness_invalid_params_and_unauthorized_job_do_no_ai_work(monkeypatch):
    from app.services.applicant_ranking_service import ApplicantRankingService
    token,user_id=_token(UserRole.RECRUITER,"Robustness Synthetic Recruiter")
    def forbidden(*args,**kwargs): raise AssertionError("Invalid/unauthorized request performed AI work")
    monkeypatch.setattr(ApplicantRankingService,"list",forbidden)
    try:
        for params in [{"sort":"invalid"},{"sort":"ai_match","ai_top_n":0},
                       {"sort":"ai_match","ai_top_n":-1},{"sort":"ai_match","page_size":101},
                       {"sort":"ai_match","page":0},{"sort":"ai_match","ranking_snapshot":"bad"}]:
            assert client.get(BASE,headers=_headers(token),params=params).status_code==422
        denied=client.get(f"{JOB_BASE}/{uuid.uuid4()}/applications",headers=_headers(token),params={"sort":"ai_match"})
        assert denied.status_code==404
    finally:
        db=SessionLocal()
        try:
            row=db.get(User,uuid.UUID(user_id))
            if row is not None: db.delete(row)
            db.commit()
        finally: db.close()
