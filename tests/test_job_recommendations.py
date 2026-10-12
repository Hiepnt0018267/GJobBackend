"""Task 15A candidate recommendation foundation integration tests."""

import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core import database
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.application import JobApplication, JobApplicationStatus
from app.models.cv import CV, CVSourceType
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.services import job_recommendation_service, ranking_cache
from app.services.ranking_cache import RankingCache


client = TestClient(app)
BASE = "/api/v1/candidate/jobs/recommendations"
TEMPLATE_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


class _World:
    def __init__(self):
        self.users = []
        self.jobs = []

    def user(self, role=UserRole.CANDIDATE):
        db = SessionLocal()
        try:
            user = User(
                email=f"task15a_{uuid.uuid4().hex}@example.com",
                password_hash="not-used",
                full_name="Task 15A Principal",
                role=role,
            )
            db.add(user)
            db.commit()
            self.users.append(user.id)
            return user.id, create_access_token({"sub": str(user.id), "role": role.value})
        finally:
            db.close()

    def cv(self, candidate_id, *, default=False, skills=None, projects=None):
        db = SessionLocal()
        try:
            cv = CV(
                candidate_id=candidate_id,
                source_type=CVSourceType.BUILDER,
                template_id=TEMPLATE_ID,
                title=f"Task 15A CV {uuid.uuid4().hex[:8]}",
                is_default=default,
                personal_info={},
                career_objective=None,
                educations=[], experiences=[], certificates=[], languages=[],
                skills=skills or [], projects=projects or [],
            )
            db.add(cv)
            db.commit()
            return cv.id
        finally:
            db.close()

    def job(self, prefix, index, *, status=JobStatus.APPROVED, skills=None):
        db = SessionLocal()
        try:
            job = Job(
                title=f"{prefix} {index}",
                description="Backend platform role",
                requirements="Build reliable APIs",
                company_name="Task 15A Labs",
                location="Ha Noi",
                skills=skills or ["Python"],
                status=status,
                created_at=datetime.now(timezone.utc) + timedelta(seconds=index),
            )
            db.add(job)
            db.commit()
            self.jobs.append(job.id)
            return job.id
        finally:
            db.close()

    def application(self, candidate_id, cv_id, job_id, state):
        db = SessionLocal()
        try:
            db.add(JobApplication(
                candidate_id=candidate_id, cv_id=cv_id, job_id=job_id, status=state
            ))
            db.commit()
        finally:
            db.close()

    def cleanup(self):
        db = SessionLocal()
        try:
            if self.users:
                db.query(JobApplication).filter(
                    JobApplication.candidate_id.in_(self.users)
                ).delete(synchronize_session=False)
            if self.jobs:
                db.query(Job).filter(Job.id.in_(self.jobs)).delete(synchronize_session=False)
            if self.users:
                db.query(CV).filter(CV.candidate_id.in_(self.users)).delete(synchronize_session=False)
                db.query(User).filter(User.id.in_(self.users)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.fixture
def world():
    value = _World()
    try:
        yield value
    finally:
        value.cleanup()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _forbid_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Recommendation GET must not resolve or call an embedding provider")
    monkeypatch.setattr(ranking_cache, "get_embedding_provider", forbidden)
    monkeypatch.setattr(RankingCache, "precompute", forbidden)


def test_candidate_only_global_rank_cache_only_pagination_and_grounded_reasons(world, monkeypatch):
    candidate_id, token = world.user()
    cv_id = world.cv(
        candidate_id,
        default=True,
        skills=[{"name": "Python", "level": "ADVANCED"}],
        projects=[{
            "name": "API", "technologies": ["FastAPI"],
        }],
    )
    prefix = f"Task15A-Rank-{uuid.uuid4().hex[:10]}"
    job_ids = [world.job(prefix, index, skills=["Python", "FastAPI"]) for index in range(12)]
    pending_job = job_ids[7]
    # The oldest job is deliberately the best match, proving rank happens before page slicing.
    scores = {job_id: 0.05 + index * 0.04 for index, job_id in enumerate(job_ids)}
    scores[job_ids[0]] = 0.99
    calls = []

    def cached_vector(self, kind, canonical):
        calls.append((kind, canonical.cv_id if kind == "cv" else canonical.job_id))
        if kind == "cv":
            return "ranked", [1.0, 0.0]
        if canonical.job_id == pending_job:
            return "pending", None
        score = scores[canonical.job_id]
        return "ranked", [score, math.sqrt(1 - score * score)]

    _forbid_provider(monkeypatch)
    monkeypatch.setattr(RankingCache, "vector", cached_vector)
    queries = []
    listener = lambda connection, cursor, statement, parameters, context, executemany: queries.append(statement)
    event.listen(database.engine, "before_cursor_execute", listener)
    try:
        first = client.get(
            BASE, headers=_headers(token),
            params={"search": prefix, "page_size": 5},
        )
    finally:
        event.remove(database.engine, "before_cursor_execute", listener)

    assert first.status_code == 200, first.text
    data = first.json()
    assert len(queries) <= 7, "Pool loading must remain bounded, not N+1 per job"
    assert data["total"] == 12 and data["ranked_count"] == 11 and data["pending_count"] == 1
    assert data["items"][0]["id"] == str(job_ids[0])
    assert data["selected_cv_id"] == str(cv_id)
    assert data["candidate_signal_status"] == "ranked"
    assert data["items"][0]["recommendation_rank"] == 1
    assert len(data["items"][0]["reasons"]) == 2
    assert {reason["evidence"][0] for reason in data["items"][0]["reasons"]} == {"FastAPI", "Python"}
    assert all("%" not in reason["message"] and "điểm" not in reason["message"] for reason in data["items"][0]["reasons"])
    assert all(key not in str(data) for key in ("semantic_match_score", "provider", "model", "cosine"))

    snapshot = data["ranking_snapshot"]
    call_count = len(calls)
    second = client.get(
        BASE, headers=_headers(token),
        params={"search": prefix, "page_size": 5, "page": 2, "ranking_snapshot": snapshot},
    )
    assert second.status_code == 200, second.text
    assert len(calls) == call_count, "Snapshot traversal must not reread vectors"
    seen = [item["id"] for item in data["items"] + second.json()["items"]]
    third = client.get(
        BASE, headers=_headers(token),
        params={"search": prefix, "page_size": 5, "page": 3, "ranking_snapshot": snapshot},
    )
    seen += [item["id"] for item in third.json()["items"]]
    assert len(seen) == len(set(seen)) == 12
    assert third.json()["items"][-1]["id"] == str(pending_job)
    assert third.json()["items"][-1]["recommendation_status"] == "pending"
    assert client.get(
        BASE, headers=_headers(token), params={"search": prefix, "page": 2}
    ).status_code == 422


def test_cv_selection_fallback_explicit_ownership_and_signal_unavailable(world, monkeypatch):
    candidate_id, token = world.user()
    empty_default = world.cv(candidate_id, default=True)
    usable_fallback = world.cv(
        candidate_id, skills=[{"name": "Python", "level": "INTERMEDIATE"}]
    )
    other_id, _ = world.user()
    foreign_cv = world.cv(other_id, default=True, skills=[{"name": "Python"}])
    prefix = f"Task15A-CV-{uuid.uuid4().hex[:10]}"
    world.job(prefix, 1)

    _forbid_provider(monkeypatch)
    monkeypatch.setattr(RankingCache, "vector", lambda self, kind, canonical: ("ranked", [1.0, 0.0]))

    automatic = client.get(BASE, headers=_headers(token), params={"search": prefix})
    assert automatic.status_code == 200, automatic.text
    assert automatic.json()["selected_cv_id"] == str(usable_fallback)
    assert automatic.json()["items"][0]["recommendation_status"] == "ranked"

    explicit_usable = client.get(
        BASE, headers=_headers(token), params={"search": prefix, "cv_id": str(usable_fallback)}
    )
    assert explicit_usable.status_code == 200
    assert explicit_usable.json()["selected_cv_id"] == str(usable_fallback)

    explicit_empty = client.get(
        BASE, headers=_headers(token), params={"search": prefix, "cv_id": str(empty_default)}
    )
    assert explicit_empty.status_code == 200
    assert explicit_empty.json()["selected_cv_id"] == str(empty_default)
    assert explicit_empty.json()["candidate_signal_status"] == "unavailable"
    assert explicit_empty.json()["items"][0]["recommendation_status"] == "unavailable"
    assert client.get(
        BASE, headers=_headers(token), params={"search": prefix, "cv_id": str(foreign_cv)}
    ).status_code == 404


def test_all_application_states_are_ineligible_and_missing_job_cache_stays_visible(world, monkeypatch):
    candidate_id, token = world.user()
    cv_id = world.cv(candidate_id, default=True, skills=[{"name": "Python"}])
    prefix = f"Task15A-Eligibility-{uuid.uuid4().hex[:10]}"
    states = list(JobApplicationStatus)
    excluded = []
    for index, state in enumerate(states):
        job_id = world.job(prefix, index)
        excluded.append(job_id)
        world.application(candidate_id, cv_id, job_id, state)
    eligible = [world.job(prefix, 10 + index) for index in range(4)]
    hidden = [
        world.job(prefix, 20, status=JobStatus.PENDING),
        world.job(prefix, 21, status=JobStatus.REJECTED),
        world.job(prefix, 22, status=JobStatus.CLOSED),
    ]

    _forbid_provider(monkeypatch)
    monkeypatch.setattr(
        RankingCache, "vector",
        lambda self, kind, canonical: ("ranked", [1.0, 0.0]) if kind == "cv" else ("pending", None),
    )
    response = client.get(BASE, headers=_headers(token), params={"search": prefix})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 4
    assert {item["id"] for item in response.json()["items"]} == set(map(str, eligible))
    assert all(item["recommendation_status"] == "pending" for item in response.json()["items"])
    assert not set(map(str, excluded)) & {item["id"] for item in response.json()["items"]}
    assert not set(map(str, hidden)) & {item["id"] for item in response.json()["items"]}


def test_ranked_pending_unavailable_error_order_and_no_score_threshold(world, monkeypatch):
    candidate_id, token = world.user()
    world.cv(candidate_id, default=True, skills=[{"name": "Python"}])
    prefix = f"Task15A-States-{uuid.uuid4().hex[:10]}"
    job_ids = [world.job(prefix, index) for index in range(4)]
    states = {
        job_ids[0]: ("ranked", [-1.0, 0.0]),
        job_ids[1]: ("pending", None),
        job_ids[2]: ("unavailable", None),
        job_ids[3]: ("error", None),
    }
    _forbid_provider(monkeypatch)

    def cached_vector(self, kind, canonical):
        return ("ranked", [1.0, 0.0]) if kind == "cv" else states[canonical.job_id]

    monkeypatch.setattr(RankingCache, "vector", cached_vector)
    response = client.get(BASE, headers=_headers(token), params={"search": prefix})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 4
    assert [item["recommendation_status"] for item in data["items"]] == [
        "ranked", "error", "unavailable", "pending"
    ]
    assert data["items"][0]["id"] == str(job_ids[0])
    assert data["items"][0]["recommendation_rank"] == 1
    assert data["ranked_count"] == data["pending_count"] == data["unavailable_count"] == data["error_count"] == 1


def test_candidate_without_usable_cv_is_unavailable_without_job_vector_reads(world, monkeypatch):
    candidate_id, token = world.user()
    prefix = f"Task15A-NoCV-{uuid.uuid4().hex[:10]}"
    world.job(prefix, 1)
    job_reads = []
    _forbid_provider(monkeypatch)

    def cached_vector(self, kind, canonical):
        job_reads.append((kind, canonical))
        return "ranked", [1.0, 0.0]

    monkeypatch.setattr(RankingCache, "vector", cached_vector)
    response = client.get(BASE, headers=_headers(token), params={"search": prefix})
    assert response.status_code == 200, response.text
    assert response.json()["selected_cv_id"] is None
    assert response.json()["candidate_signal_status"] == "unavailable"
    assert response.json()["items"][0]["recommendation_status"] == "unavailable"
    assert not job_reads


def test_candidate_embedding_cache_miss_is_pending_without_job_reads_or_provider(world, monkeypatch):
    candidate_id, token = world.user()
    world.cv(candidate_id, default=True, skills=[{"name": "Python"}])
    prefix = f"Task15A-CandidateMiss-{uuid.uuid4().hex[:10]}"
    for index in range(3):
        world.job(prefix, index)
    reads = []
    _forbid_provider(monkeypatch)

    def cached_vector(self, kind, canonical):
        reads.append(kind)
        if kind != "cv":
            raise AssertionError("Job vectors are irrelevant while candidate signal is pending")
        return "pending", None

    monkeypatch.setattr(RankingCache, "vector", cached_vector)
    response = client.get(BASE, headers=_headers(token), params={"search": prefix})
    assert response.status_code == 200, response.text
    assert response.json()["candidate_signal_status"] == "pending"
    assert response.json()["pending_count"] == response.json()["total"] == 3
    assert all(item["recommendation_status"] == "pending" for item in response.json()["items"])
    assert reads == ["cv"]


def test_snapshot_is_bound_to_candidate_cv_filters_profile_and_pool(world, monkeypatch):
    candidate_id, token = world.user()
    cv_id = world.cv(candidate_id, default=True, skills=[{"name": "Python"}])
    other_id, other_token = world.user()
    world.cv(other_id, default=True, skills=[{"name": "Python"}])
    prefix = f"Task15A-Snapshot-{uuid.uuid4().hex[:10]}"
    world.job(prefix, 1)
    world.job(prefix, 2)
    _forbid_provider(monkeypatch)
    monkeypatch.setattr(RankingCache, "vector", lambda self, kind, canonical: ("ranked", [1.0, 0.0]))

    first = client.get(
        BASE, headers=_headers(token), params={"search": prefix, "page_size": 1}
    )
    assert first.status_code == 200
    snapshot = first.json()["ranking_snapshot"]
    common = {"search": prefix, "page_size": 1, "page": 2, "ranking_snapshot": snapshot}
    assert client.get(BASE, headers=_headers(other_token), params=common).status_code == 409
    assert client.get(BASE, headers=_headers(token), params={**common, "location": "Da Nang"}).status_code == 409
    assert client.get(BASE, headers=_headers(token), params={**common, "cv_id": str(cv_id)}).status_code == 409

    db = SessionLocal()
    try:
        cv = db.get(CV, cv_id)
        cv.skills = [{"name": "Go"}]
        db.commit()
    finally:
        db.close()
    assert client.get(BASE, headers=_headers(token), params=common).status_code == 409
    refreshed = client.get(
        BASE, headers=_headers(token), params={"search": prefix, "page_size": 1}
    )
    assert refreshed.status_code == 200
    common["ranking_snapshot"] = refreshed.json()["ranking_snapshot"]
    with monkeypatch.context() as scoped:
        scoped.setattr(job_recommendation_service, "runtime_identity", lambda: {"profile": "changed"})
        assert client.get(BASE, headers=_headers(token), params=common).status_code == 409
    world.job(prefix, 3)
    assert client.get(BASE, headers=_headers(token), params=common).status_code == 409


def test_authorization_validation_and_public_contract_do_no_ranking_work(world, monkeypatch):
    candidate_id, candidate_token = world.user()
    world.cv(candidate_id, default=True, skills=[{"name": "Python"}])
    _, recruiter_token = world.user(UserRole.RECRUITER)
    prefix = f"Task15A-Auth-{uuid.uuid4().hex[:10]}"
    world.job(prefix, 1)
    calls = []
    monkeypatch.setattr(
        RankingCache, "vector",
        lambda *args, **kwargs: calls.append(1) or ("ranked", [1.0, 0.0]),
    )
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers=_headers(recruiter_token)).status_code == 403
    for params in (
        {"page": 0}, {"page_size": 101}, {"ranking_snapshot": "bad"},
        {"salary_min": 2, "salary_max": 1},
    ):
        assert client.get(BASE, headers=_headers(candidate_token), params=params).status_code == 422
    assert not calls
    operation = app.openapi()["paths"][BASE]["get"]
    serialized = str(operation)
    assert "semantic_match_score" not in serialized
    assert "provider" not in serialized and "model" not in serialized
