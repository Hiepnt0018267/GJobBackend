"""Task 14A.4a persistence, invalidation, authorization and API tests."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.embeddings import EmbeddingProviderUnavailableError
from app.main import app
from app.models.application import JobApplication
from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.cv_job_match import CVJobMatch
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole
from app.schemas.matching import (
    CanonicalCVMatchingInput,
    CanonicalJobMatchingInput,
    CanonicalProject,
    CanonicalSalaryMetadata,
    CanonicalSkill,
    MatchComponentStatus,
    SemanticMatchingResult,
)
from app.services.cv_job_match_service import CVJobMatchService
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job


TEMPLATE_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
client = TestClient(app)


class FakeSemanticService:
    def __init__(
        self,
        *,
        provider: str = "fake",
        model: str = "fake-model",
        error: Exception | None = None,
        before_return=None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.error = error
        self.before_return = before_return
        self.calls = 0

    async def match(self, cv, job) -> SemanticMatchingResult:
        self.calls += 1
        if self.before_return is not None:
            self.before_return()
        if self.error is not None:
            raise self.error
        return SemanticMatchingResult(
            cv_id=cv.cv_id,
            job_id=job.job_id,
            semantic_similarity=0.75,
            provider=self.provider,
            model=self.model,
            dimensions=3,
            engine_version="semantic-v1",
        )


def _user(role: UserRole, label: str) -> User:
    return User(
        email=f"match_{label}_{uuid.uuid4().hex}@example.com",
        password_hash="not-used",
        full_name=label,
        role=role,
    )


def _seed_pair(
    db,
    *,
    job_status: JobStatus = JobStatus.APPROVED,
    job_skills: list[str] | None = None,
) -> tuple[User, User, CV, Job]:
    candidate = _user(UserRole.CANDIDATE, "Candidate")
    recruiter = _user(UserRole.RECRUITER, "Recruiter")
    db.add_all([candidate, recruiter])
    db.flush()
    cv = CV(
        candidate_id=candidate.id,
        template_id=TEMPLATE_ID,
        title="Backend CV",
        personal_info={
            "full_name": "Private Candidate",
            "email": "private@example.com",
        },
        career_objective="Build reliable APIs",
        skills=[{"name": "Python", "level": "ADVANCED"}],
        projects=[{"name": "GJob", "technologies": ["FastAPI"]}],
    )
    job = Job(
        recruiter_id=recruiter.id,
        title="Backend Engineer",
        description="Build reliable APIs",
        requirements="Python",
        company_name="Private Company",
        skills=["Python"] if job_skills is None else job_skills,
        status=job_status,
    )
    db.add_all([cv, job])
    db.commit()
    db.refresh(cv)
    db.refresh(job)
    return candidate, recruiter, cv, job


def _service(db, fake: FakeSemanticService, *, model: str = "fake-model"):
    return CVJobMatchService(
        db,
        semantic_service=fake,
        expected_provider=fake.provider,
        expected_model=model,
    )


def _match_candidate(service, candidate, cv, job):
    return asyncio.run(service.match_for_candidate(candidate, cv.id, job.id))


def _make_uploaded_with_success(db, cv: CV) -> CVExtraction:
    cv.source_type = CVSourceType.UPLOADED
    cv.template_id = None
    cv.storage_key = f"cvs/{cv.candidate_id}/{cv.id}.pdf"
    cv.original_filename = "candidate.pdf"
    cv.mime_type = "application/pdf"
    cv.file_size = 1024
    cv.uploaded_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    extraction = CVExtraction(
        cv_id=cv.id,
        status=CVExtractionStatus.SUCCEEDED,
        provider="fake-gemini",
        model="fake-model",
        structured_result={
            "personal_info": {},
            "career_objective": "Build reliable APIs",
            "educations": [],
            "experiences": [],
            "skills": [{"name": "Python"}],
            "projects": [],
            "certificates": [],
            "languages": [],
        },
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(extraction)
    db.commit()
    return extraction


def _canonical_cv() -> CanonicalCVMatchingInput:
    return CanonicalCVMatchingInput(
        cv_id=uuid.uuid4(),
        skills=[CanonicalSkill(name="Python", normalized_name="python")],
        experiences=[],
        educations=[],
        projects=[
            CanonicalProject(
                name="Project",
                technologies=[
                    CanonicalSkill(name="FastAPI", normalized_name="fastapi")
                ],
            )
        ],
        certificates=[],
        languages=[],
        semantic_text="stable cv semantic text",
    )


def _canonical_job() -> CanonicalJobMatchingInput:
    return CanonicalJobMatchingInput(
        job_id=uuid.uuid4(),
        title="Backend",
        description="Build APIs",
        skills=[CanonicalSkill(name="Python", normalized_name="python")],
        status=JobStatus.APPROVED,
        salary=CanonicalSalaryMetadata(currency="VND"),
        vacancies=1,
        semantic_text="stable job semantic text",
    )


def test_fingerprints_are_deterministic_matching_only_and_pii_free() -> None:
    cv = _canonical_cv()
    job = _canonical_job()
    reordered_cv = cv.model_copy(
        update={
            "cv_id": uuid.uuid4(),
            "location": None,
            "skills": list(reversed(cv.skills)),
        }
    )
    changed_job_metadata = job.model_copy(
        update={
            "job_id": uuid.uuid4(),
            "vacancies": 99,
            "salary": CanonicalSalaryMetadata(
                minimum=99_000_000,
                maximum=120_000_000,
                currency="VND",
            ),
        }
    )

    assert fingerprint_cv(cv) == fingerprint_cv(reordered_cv)
    assert fingerprint_job(job) == fingerprint_job(changed_job_metadata)
    assert len(fingerprint_cv(cv)) == len(fingerprint_job(job)) == 64
    assert fingerprint_cv(cv) != fingerprint_cv(
        cv.model_copy(update={"semantic_text": "changed"})
    )
    assert fingerprint_job(job) != fingerprint_job(
        job.model_copy(update={"semantic_text": "changed"})
    )


def test_first_match_persists_and_second_match_reuses_without_semantic_call() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db)
        fake = FakeSemanticService()
        service = _service(db, fake)

        first = _match_candidate(service, candidate, cv, job)
        second = _match_candidate(service, candidate, cv, job)

        assert first.cached is False
        assert second.cached is True
        assert fake.calls == 1
        assert first.baseline.status == MatchComponentStatus.AVAILABLE
        assert first.semantic.status == MatchComponentStatus.AVAILABLE
        assert first.semantic.result is not None
        assert first.semantic.result.semantic_similarity == 0.75
        records = db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).all()
        assert len(records) == 1
        assert records[0].baseline_result == first.baseline.result.model_dump(mode="json")
        assert records[0].embedding_provider == "fake"
        assert records[0].embedding_model == "fake-model"
        assert records[0].embedding_model_config == "fake-model"
        assert records[0].embedding_dimensions == 3
        assert records[0].computed_at is not None
    finally:
        db.close()


def test_matching_changes_recompute_but_identity_and_salary_changes_reuse() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db)
        fake = FakeSemanticService()
        service = _service(db, fake)
        _match_candidate(service, candidate, cv, job)

        cv.personal_info = {"full_name": "Changed Identity", "email": "new@example.com"}
        job.salary_min = 50_000_000
        job.vacancies = 5
        db.commit()
        assert _match_candidate(service, candidate, cv, job).cached is True
        assert fake.calls == 1

        cv.career_objective = "Changed matching objective"
        db.commit()
        assert _match_candidate(service, candidate, cv, job).cached is False
        assert fake.calls == 2

        job.description = "Changed matching description"
        db.commit()
        assert _match_candidate(service, candidate, cv, job).cached is False
        assert fake.calls == 3
        assert db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).count() == 1
    finally:
        db.close()


def test_engine_and_model_metadata_changes_invalidate_persisted_result() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db)
        first_fake = FakeSemanticService()
        _match_candidate(_service(db, first_fake), candidate, cv, job)
        record = db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).one()
        record.baseline_engine_version = "baseline-old"
        db.commit()

        second_fake = FakeSemanticService()
        assert _match_candidate(_service(db, second_fake), candidate, cv, job).cached is False
        assert second_fake.calls == 1

        third_fake = FakeSemanticService(model="new-model")
        assert _match_candidate(
            _service(db, third_fake, model="new-model"), candidate, cv, job
        ).cached is False
        assert third_fake.calls == 1
    finally:
        db.close()


def test_unconfirmed_uploaded_cv_matches_for_candidate_and_recruiter_then_confirm_recomputes() -> None:
    db = SessionLocal()
    try:
        candidate, recruiter, cv, job = _seed_pair(db)
        extraction = _make_uploaded_with_success(db, cv)
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            cv_id=cv.id,
        )
        db.add(application)
        db.commit()

        first_semantic = FakeSemanticService()
        first = _match_candidate(_service(db, first_semantic), candidate, cv, job)
        assert first.cached is False
        assert first_semantic.calls == 1

        recruiter_semantic = FakeSemanticService()
        recruiter_result = asyncio.run(
            _service(db, recruiter_semantic).match_for_recruiter_application(
                recruiter, application.id
            )
        )
        assert recruiter_result.cv_id == cv.id
        assert recruiter_result.job_id == job.id
        assert recruiter_result.cached is True
        assert recruiter_semantic.calls == 0

        cv.personal_info = {}
        cv.career_objective = "Build safe Rust services"
        cv.educations = []
        cv.experiences = []
        cv.skills = [{"name": "Rust"}]
        cv.projects = []
        cv.certificates = []
        cv.languages = []
        extraction.confirmed_at = datetime.now(timezone.utc)
        db.commit()

        confirmed_semantic = FakeSemanticService()
        confirmed = _match_candidate(
            _service(db, confirmed_semantic), candidate, cv, job
        )
        assert confirmed.cached is False
        assert confirmed_semantic.calls == 1
    finally:
        db.close()


def test_baseline_insufficient_is_explicit_and_semantic_result_is_persisted() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db, job_skills=[])
        response = _match_candidate(
            _service(db, FakeSemanticService()), candidate, cv, job
        )

        assert response.baseline.status == MatchComponentStatus.INSUFFICIENT_SIGNALS
        assert response.baseline.result is None
        assert response.semantic.status == MatchComponentStatus.AVAILABLE
        record = db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).one()
        assert record.baseline_status == "INSUFFICIENT_SIGNALS"
        assert record.baseline_result is None
    finally:
        db.close()


def test_semantic_failure_returns_partial_result_without_persisting_garbage() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db)
        fake = FakeSemanticService(
            error=EmbeddingProviderUnavailableError("offline")
        )
        response = _match_candidate(_service(db, fake), candidate, cv, job)

        assert response.baseline.status == MatchComponentStatus.AVAILABLE
        assert response.semantic.status == MatchComponentStatus.UNAVAILABLE
        assert response.semantic.result is None
        assert response.semantic.error_code == "EMBEDDING_PROVIDER_UNAVAILABLE"
        assert db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).count() == 0
    finally:
        db.close()


def test_source_change_during_embedding_cannot_be_persisted_as_current() -> None:
    db = SessionLocal()
    other_db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db)

        def mutate_cv() -> None:
            current = other_db.get(CV, cv.id)
            assert current is not None
            current.career_objective = "Changed while embedding"
            other_db.commit()

        fake = FakeSemanticService(before_return=mutate_cv)
        with pytest.raises(HTTPException) as exc_info:
            _match_candidate(_service(db, fake), candidate, cv, job)

        assert exc_info.value.status_code == 409
        assert db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).count() == 0
    finally:
        other_db.close()
        db.close()


def test_recruiter_application_context_change_during_embedding_is_rejected() -> None:
    db = SessionLocal()
    other_db = SessionLocal()
    try:
        candidate, recruiter, cv, job = _seed_pair(db)
        replacement_job = Job(
            recruiter_id=recruiter.id,
            title="Replacement job",
            description="Changed application context",
            company_name="Test",
            skills=["Python"],
            status=JobStatus.APPROVED,
        )
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            cv_id=cv.id,
        )
        db.add_all([replacement_job, application])
        db.commit()

        def mutate_application() -> None:
            current = other_db.get(JobApplication, application.id)
            assert current is not None
            current.job_id = replacement_job.id
            other_db.commit()

        fake = FakeSemanticService(before_return=mutate_application)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                _service(db, fake).match_for_recruiter_application(
                    recruiter,
                    application.id,
                )
            )

        assert exc_info.value.status_code == 409
        assert db.query(CVJobMatch).filter_by(cv_id=cv.id, job_id=job.id).count() == 0
    finally:
        other_db.close()
        db.close()


def test_candidate_and_recruiter_authorization_use_owned_domain_context() -> None:
    db = SessionLocal()
    try:
        candidate, recruiter, cv, job = _seed_pair(db)
        other_candidate = _user(UserRole.CANDIDATE, "Other Candidate")
        other_recruiter = _user(UserRole.RECRUITER, "Other Recruiter")
        db.add_all([other_candidate, other_recruiter])
        db.flush()
        foreign_cv = CV(
            candidate_id=other_candidate.id,
            template_id=TEMPLATE_ID,
            title="Foreign CV",
            personal_info={},
            skills=[{"name": "Python"}],
        )
        db.add(foreign_cv)
        db.flush()
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            cv_id=cv.id,
        )
        db.add(application)
        db.commit()

        with pytest.raises(HTTPException) as candidate_error:
            asyncio.run(
                _service(db, FakeSemanticService()).match_for_candidate(
                    candidate, foreign_cv.id, job.id
                )
            )
        assert candidate_error.value.status_code == 404

        owned = asyncio.run(
            _service(db, FakeSemanticService()).match_for_recruiter_application(
                recruiter, application.id
            )
        )
        assert owned.cv_id == cv.id

        with pytest.raises(HTTPException) as recruiter_error:
            asyncio.run(
                _service(db, FakeSemanticService()).match_for_recruiter_application(
                    other_recruiter, application.id
                )
            )
        assert recruiter_error.value.status_code == 404

        tampered_job = Job(
            recruiter_id=recruiter.id,
            title="Tampered application job",
            description="Ownership consistency test",
            company_name="Test",
            skills=["Python"],
            status=JobStatus.APPROVED,
        )
        db.add(tampered_job)
        db.flush()
        tampered_application = JobApplication(
            job_id=tampered_job.id,
            candidate_id=candidate.id,
            cv_id=foreign_cv.id,
        )
        db.add(tampered_application)
        db.commit()
        with pytest.raises(HTTPException) as tampered_error:
            asyncio.run(
                _service(db, FakeSemanticService()).match_for_recruiter_application(
                    recruiter, tampered_application.id
                )
            )
        assert tampered_error.value.status_code == 409
    finally:
        db.close()


def test_candidate_rejects_non_approved_job_and_match_cascades_with_cv() -> None:
    db = SessionLocal()
    try:
        candidate, _, cv, job = _seed_pair(db, job_status=JobStatus.PENDING)
        with pytest.raises(HTTPException) as exc_info:
            _match_candidate(_service(db, FakeSemanticService()), candidate, cv, job)
        assert exc_info.value.status_code == 409

        job.status = JobStatus.APPROVED
        db.commit()
        _match_candidate(_service(db, FakeSemanticService()), candidate, cv, job)
        cv_id = cv.id
        db.delete(cv)
        db.commit()
        assert db.query(CVJobMatch).filter_by(cv_id=cv_id).count() == 0
    finally:
        db.close()


def _headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


def test_match_routes_enforce_roles_and_return_typed_components(monkeypatch) -> None:
    db = SessionLocal()
    try:
        candidate, recruiter, cv, job = _seed_pair(db)
        application = JobApplication(
            job_id=job.id,
            candidate_id=candidate.id,
            cv_id=cv.id,
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        cv_id = cv.id
        job_id = job.id
        application_id = application.id
        candidate_headers = _headers(candidate)
        recruiter_headers = _headers(recruiter)
    finally:
        db.close()

    fake = FakeSemanticService(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
    )
    monkeypatch.setattr(
        "app.services.cv_job_match_service.SemanticMatchingService",
        lambda: fake,
    )

    candidate_path = f"/api/v1/candidate/jobs/{job_id}/match"
    recruiter_path = f"/api/v1/recruiters/applications/{application_id}/match"
    assert client.post(candidate_path, json={"cv_id": str(cv_id)}).status_code == 401
    assert client.post(
        candidate_path, json={"cv_id": str(cv_id)}, headers=recruiter_headers
    ).status_code == 403
    candidate_response = client.post(
        candidate_path,
        json={"cv_id": str(cv_id)},
        headers=candidate_headers,
    )
    assert candidate_response.status_code == 200, candidate_response.text
    assert candidate_response.json()["semantic"]["status"] == "AVAILABLE"
    assert "vector" not in candidate_response.text.casefold()

    assert client.post(recruiter_path, headers=candidate_headers).status_code == 403
    recruiter_response = client.post(recruiter_path, headers=recruiter_headers)
    assert recruiter_response.status_code == 200, recruiter_response.text
    assert recruiter_response.json()["cv_id"] == str(cv_id)
