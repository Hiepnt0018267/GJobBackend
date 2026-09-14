import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.user import User, UserRole
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_extraction_service import CandidateCVExtractionService
from app.services.cv_structured_extraction_service import (
    CVAIProviderUnavailableError,
    CVExtractionValidationError,
)
from app.services.document_text_extractor import EmptyDocumentTextError


client = TestClient(app)
BASE = "/api/v1/candidate/cvs"

EXTRACTED_PAYLOAD = {
    "personal_info": {
        "full_name": "Nguyễn Văn A",
        "email": "nguyenvana@example.com",
    },
    "career_objective": "Xây dựng hệ thống backend ổn định.",
    "educations": [{"school_name": "Đại học Bách khoa Hà Nội"}],
    "experiences": [
        {"company_name": "ABC Company", "position": "Backend Developer"}
    ],
    "skills": [{"name": "Python"}, {"name": "FastAPI"}],
    "projects": [],
    "certificates": [],
    "languages": [],
}


class StubStructuredExtractor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.call_count = 0

    async def extract_uploaded_cv(self, cv: CV) -> StructuredCVExtractionResult:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        return StructuredCVExtractionResult.model_validate(EXTRACTED_PAYLOAD)


def _create_user(role: UserRole = UserRole.CANDIDATE) -> tuple[User, str]:
    email = f"cv-extraction-{uuid.uuid4().hex}@example.com"
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        full_name="CV Extraction Test",
        role=role,
    )
    db = SessionLocal()
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    user.id = user_id
    return user, login.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_cv(candidate_id: uuid.UUID, source_type: CVSourceType) -> CV:
    now = datetime.now(timezone.utc)
    values = {
        "candidate_id": candidate_id,
        "source_type": source_type,
        "title": f"Extraction CV {uuid.uuid4().hex[:8]}",
        "personal_info": {"full_name": "Original Candidate"},
        "career_objective": "Original objective",
        "educations": [{"school_name": "Original University"}],
        "experiences": [],
        "skills": [{"name": "Original Skill"}],
        "projects": [],
        "certificates": [],
        "languages": [],
    }
    if source_type == CVSourceType.UPLOADED:
        values.update(
            storage_key=f"cvs/{candidate_id}/{uuid.uuid4()}.pdf",
            original_filename="synthetic-cv.pdf",
            mime_type="application/pdf",
            file_size=1024,
            uploaded_at=now,
        )
    else:
        values["template_id"] = uuid.UUID("10000000-0000-0000-0000-000000000001")
    cv = CV(**values)
    db = SessionLocal()
    try:
        db.add(cv)
        db.commit()
        db.refresh(cv)
        cv_id = cv.id
    finally:
        db.close()
    cv.id = cv_id
    return cv


def _install_extractor(monkeypatch, extractor: StubStructuredExtractor) -> None:
    monkeypatch.setattr(
        "app.services.cv_extraction_service.CVStructuredExtractionService",
        lambda: extractor,
    )


def _latest_row(cv_id: uuid.UUID) -> CVExtraction | None:
    db = SessionLocal()
    try:
        return (
            db.query(CVExtraction)
            .filter(CVExtraction.cv_id == cv_id)
            .order_by(CVExtraction.created_at.desc(), CVExtraction.id.desc())
            .first()
        )
    finally:
        db.close()


def test_trigger_success_persists_typed_draft_metadata_without_mutating_cv(
    monkeypatch,
) -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extractor = StubStructuredExtractor()
    _install_extractor(monkeypatch, extractor)

    db = SessionLocal()
    try:
        before = db.get(CV, cv.id)
        original_sections = {
            "personal_info": before.personal_info,
            "career_objective": before.career_objective,
            "educations": before.educations,
            "experiences": before.experiences,
            "skills": before.skills,
            "projects": before.projects,
            "certificates": before.certificates,
            "languages": before.languages,
        }
    finally:
        db.close()

    response = client.post(f"{BASE}/{cv.id}/extractions", headers=_headers(token))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["provider"] == settings.ai_provider.strip().lower()
    assert body["model"] == settings.gemini_model
    assert body["result"]["personal_info"]["full_name"] == "Nguyễn Văn A"
    assert "structured_result" not in body
    assert "storage_key" not in body
    assert extractor.call_count == 1

    db = SessionLocal()
    try:
        stored = db.query(CVExtraction).filter(CVExtraction.cv_id == cv.id).one()
        reloaded_cv = db.get(CV, cv.id)
        assert stored.structured_result["skills"] == [
            {"name": "Python", "level": None},
            {"name": "FastAPI", "level": None},
        ]
        assert stored.completed_at is not None
        for field, value in original_sections.items():
            assert getattr(reloaded_cv, field) == value
    finally:
        db.close()


def test_builder_foreign_cv_and_non_candidate_roles_are_blocked_without_ai(
    monkeypatch,
) -> None:
    owner, owner_token = _create_user()
    other, other_token = _create_user()
    _, recruiter_token = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    builder_cv = _create_cv(owner.id, CVSourceType.BUILDER)
    uploaded_cv = _create_cv(owner.id, CVSourceType.UPLOADED)
    extractor = StubStructuredExtractor()
    _install_extractor(monkeypatch, extractor)

    builder = client.post(
        f"{BASE}/{builder_cv.id}/extractions", headers=_headers(owner_token)
    )
    assert builder.status_code == 422
    assert client.post(
        f"{BASE}/{uploaded_cv.id}/extractions", headers=_headers(other_token)
    ).status_code == 404
    assert client.post(
        f"{BASE}/{uploaded_cv.id}/extractions", headers=_headers(recruiter_token)
    ).status_code == 403
    assert client.post(
        f"{BASE}/{uploaded_cv.id}/extractions", headers=_headers(admin_token)
    ).status_code == 403
    assert extractor.call_count == 0
    assert _latest_row(builder_cv.id) is None
    assert _latest_row(uploaded_cv.id) is None


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (
            EmptyDocumentTextError("private parser detail"),
            422,
            "DOCUMENT_EXTRACTION_FAILED",
        ),
        (
            CVAIProviderUnavailableError("private provider detail"),
            503,
            "AI_PROVIDER_UNAVAILABLE",
        ),
        (
            CVExtractionValidationError("raw invalid response"),
            502,
            "AI_RESPONSE_INVALID",
        ),
    ],
)
def test_trigger_failure_persists_safe_failed_resource(
    monkeypatch, error: Exception, status_code: int, error_code: str
) -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extractor = StubStructuredExtractor(error)
    _install_extractor(monkeypatch, extractor)

    response = client.post(f"{BASE}/{cv.id}/extractions", headers=_headers(token))

    assert response.status_code == status_code
    assert "private" not in response.text
    assert "raw invalid response" not in response.text
    stored = _latest_row(cv.id)
    assert stored.status == CVExtractionStatus.FAILED
    assert stored.error_code == error_code
    assert stored.structured_result is None
    assert stored.completed_at is not None
    assert "private" not in stored.failure_reason
    assert "raw invalid response" not in stored.failure_reason

    latest = client.get(
        f"{BASE}/{cv.id}/extractions/latest", headers=_headers(token)
    )
    assert latest.status_code == 200
    assert latest.json()["status"] == "FAILED"
    assert latest.json()["result"] is None
    assert latest.json()["error_code"] == error_code


def test_active_trigger_is_idempotently_reused_without_calling_ai(monkeypatch) -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    now = datetime.now(timezone.utc)
    active = CVExtraction(
        cv_id=cv.id,
        provider="gemini",
        model="test-model",
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db = SessionLocal()
    try:
        db.add(active)
        db.commit()
        active_id = active.id
    finally:
        db.close()
    extractor = StubStructuredExtractor()
    _install_extractor(monkeypatch, extractor)

    response = client.post(f"{BASE}/{cv.id}/extractions", headers=_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == str(active_id)
    assert response.json()["status"] == "PROCESSING"
    assert extractor.call_count == 0


def test_partial_unique_index_prevents_two_processing_attempts() -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    now = datetime.now(timezone.utc)

    first_db = SessionLocal()
    second_db = SessionLocal()
    try:
        first_db.add(
            CVExtraction(
                cv_id=cv.id,
                provider="gemini",
                model="model-a",
                started_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        first_db.commit()
        second_db.add(
            CVExtraction(
                cv_id=cv.id,
                provider="gemini",
                model="model-b",
                started_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            second_db.commit()
        second_db.rollback()
    finally:
        first_db.close()
        second_db.close()


def test_external_extraction_runs_without_an_open_database_transaction() -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    db = SessionLocal()

    class TransactionInspectingExtractor(StubStructuredExtractor):
        async def extract_uploaded_cv(self, cv_source):
            assert db.in_transaction() is False
            return await super().extract_uploaded_cv(cv_source)

    try:
        response, created = asyncio.run(
            CandidateCVExtractionService(
                db, structured_extractor=TransactionInspectingExtractor()
            ).trigger(candidate, cv.id)
        )
        assert created is True
        assert response.status == CVExtractionStatus.SUCCEEDED
    finally:
        db.close()


def test_failed_attempt_can_be_retried_and_latest_returns_new_success(monkeypatch) -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    db = SessionLocal()
    try:
        db.add(
            CVExtraction(
                cv_id=cv.id,
                status=CVExtractionStatus.FAILED,
                provider="gemini",
                model="old-model",
                error_code="AI_PROVIDER_UNAVAILABLE",
                failure_reason="Dịch vụ AI từng không khả dụng.",
                started_at=old_time,
                completed_at=old_time,
                created_at=old_time,
                updated_at=old_time,
            )
        )
        db.commit()
    finally:
        db.close()
    extractor = StubStructuredExtractor()
    _install_extractor(monkeypatch, extractor)

    triggered = client.post(
        f"{BASE}/{cv.id}/extractions", headers=_headers(token)
    )
    latest = client.get(
        f"{BASE}/{cv.id}/extractions/latest", headers=_headers(token)
    )

    assert triggered.status_code == 201
    assert latest.status_code == 200
    assert latest.json()["id"] == triggered.json()["id"]
    assert latest.json()["status"] == "SUCCEEDED"
    db = SessionLocal()
    try:
        assert db.query(CVExtraction).filter(CVExtraction.cv_id == cv.id).count() == 2
    finally:
        db.close()


def test_latest_returns_404_when_owned_cv_has_no_extraction() -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)

    response = client.get(
        f"{BASE}/{cv.id}/extractions/latest", headers=_headers(token)
    )

    assert response.status_code == 404


def test_cv_delete_cascades_extraction_rows() -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        db.add(
            CVExtraction(
                cv_id=cv.id,
                provider="gemini",
                model="test-model",
                started_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        db.query(CV).filter(CV.id == cv.id).delete(synchronize_session=False)
        db.commit()
        assert db.query(CVExtraction).filter(CVExtraction.cv_id == cv.id).count() == 0
    finally:
        db.close()
