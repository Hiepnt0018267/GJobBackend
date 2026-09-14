import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.cv import CV, CVSourceType
from app.models.cv_extraction import CVExtraction, CVExtractionStatus
from app.models.user import UserRole
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.services.cv_extraction_service import CandidateCVExtractionService
from tests.test_cv_extractions import _create_cv, _create_user, _headers


client = TestClient(app)
BASE = "/api/v1/candidate/cvs"

AI_PAYLOAD = {
    "personal_info": {"full_name": "AI Candidate"},
    "career_objective": "AI objective",
    "educations": [],
    "experiences": [],
    "skills": [{"name": "Python"}],
    "projects": [{"name": "AI Project"}],
    "certificates": [],
    "languages": [],
}

REVIEWED_PAYLOAD = {
    "personal_info": {
        "full_name": "Nguyễn Văn A",
        "email": "reviewed@example.com",
    },
    "career_objective": "Nội dung đã được ứng viên xác nhận.",
    "educations": [{"school_name": "Đại học Bách khoa Hà Nội"}],
    "experiences": [
        {"company_name": "GJob", "position": "Backend Developer"}
    ],
    "skills": [{"name": "Python"}, {"name": "FastAPI"}],
    "projects": [],
    "certificates": [],
    "languages": [{"name": "Vietnamese", "proficiency": "NATIVE"}],
}


def _create_extraction(
    cv_id: uuid.UUID,
    extraction_status: CVExtractionStatus = CVExtractionStatus.SUCCEEDED,
    created_at: datetime | None = None,
) -> CVExtraction:
    now = created_at or datetime.now(timezone.utc)
    values = {
        "cv_id": cv_id,
        "status": extraction_status,
        "provider": "gemini",
        "model": "test-model",
        "started_at": now,
        "created_at": now,
        "updated_at": now,
    }
    if extraction_status == CVExtractionStatus.SUCCEEDED:
        values.update(
            structured_result=StructuredCVExtractionResult.model_validate(
                AI_PAYLOAD
            ).model_dump(mode="json"),
            completed_at=now,
        )
    elif extraction_status == CVExtractionStatus.FAILED:
        values.update(
            error_code="AI_RESPONSE_INVALID",
            failure_reason="Kết quả AI không hợp lệ.",
            completed_at=now,
        )
    extraction = CVExtraction(**values)
    db = SessionLocal()
    try:
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        extraction_id = extraction.id
    finally:
        db.close()
    extraction.id = extraction_id
    return extraction


def _confirm_url(cv_id: uuid.UUID, extraction_id: uuid.UUID) -> str:
    return f"{BASE}/{cv_id}/extractions/{extraction_id}/confirm"


def test_candidate_confirms_edited_payload_and_ai_result_stays_immutable() -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)

    response = client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(token),
        json=REVIEWED_PAYLOAD,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmed_at"] is not None
    assert body["cv"]["source_type"] == "UPLOADED"
    assert body["cv"]["skills"] == [
        {"name": "Python", "level": None},
        {"name": "FastAPI", "level": None},
    ]
    assert body["cv"]["projects"] == []
    assert "storage_key" not in body
    assert "structured_result" not in body

    db = SessionLocal()
    try:
        stored_cv = db.get(CV, cv.id)
        stored_extraction = db.get(CVExtraction, extraction.id)
        assert stored_cv.personal_info["full_name"] == "Nguyễn Văn A"
        assert stored_cv.skills == [
            {"name": "Python", "level": None},
            {"name": "FastAPI", "level": None},
        ]
        assert stored_cv.projects == []
        assert stored_cv.source_type == CVSourceType.UPLOADED
        assert stored_extraction.structured_result["skills"] == [
            {"name": "Python", "level": None}
        ]
        assert stored_extraction.structured_result["projects"][0]["name"] == "AI Project"
        assert stored_extraction.confirmed_at is not None
    finally:
        db.close()


@pytest.mark.parametrize(
    "extraction_status",
    [CVExtractionStatus.PROCESSING, CVExtractionStatus.FAILED],
)
def test_processing_and_failed_extractions_cannot_be_confirmed(
    extraction_status: CVExtractionStatus,
) -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id, extraction_status)

    response = client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(token),
        json=REVIEWED_PAYLOAD,
    )

    assert response.status_code == 409
    db = SessionLocal()
    try:
        assert db.get(CV, cv.id).personal_info["full_name"] == "Original Candidate"
        assert db.get(CVExtraction, extraction.id).confirmed_at is None
    finally:
        db.close()


def test_confirmation_enforces_ownership_cv_match_source_and_role() -> None:
    owner, owner_token = _create_user()
    other, other_token = _create_user()
    _, recruiter_token = _create_user(UserRole.RECRUITER)
    _, admin_token = _create_user(UserRole.ADMIN)
    cv = _create_cv(owner.id, CVSourceType.UPLOADED)
    other_cv = _create_cv(owner.id, CVSourceType.UPLOADED)
    builder_cv = _create_cv(owner.id, CVSourceType.BUILDER)
    extraction = _create_extraction(cv.id)
    builder_extraction = _create_extraction(builder_cv.id)

    assert client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(other_token),
        json=REVIEWED_PAYLOAD,
    ).status_code == 404
    assert client.post(
        _confirm_url(other_cv.id, extraction.id),
        headers=_headers(owner_token),
        json=REVIEWED_PAYLOAD,
    ).status_code == 404
    assert client.post(
        _confirm_url(builder_cv.id, builder_extraction.id),
        headers=_headers(owner_token),
        json=REVIEWED_PAYLOAD,
    ).status_code == 422
    assert client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(recruiter_token),
        json=REVIEWED_PAYLOAD,
    ).status_code == 403
    assert client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(admin_token),
        json=REVIEWED_PAYLOAD,
    ).status_code == 403


def test_only_latest_extraction_can_be_confirmed() -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    old = _create_extraction(
        cv.id, created_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    latest = _create_extraction(cv.id)

    stale = client.post(
        _confirm_url(cv.id, old.id),
        headers=_headers(token),
        json=REVIEWED_PAYLOAD,
    )
    accepted = client.post(
        _confirm_url(cv.id, latest.id),
        headers=_headers(token),
        json=REVIEWED_PAYLOAD,
    )

    assert stale.status_code == 409
    assert accepted.status_code == 200


def test_double_confirm_is_idempotent_and_different_payload_cannot_overwrite() -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)
    first = client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(token),
        json=REVIEWED_PAYLOAD,
    )
    changed_payload = {**REVIEWED_PAYLOAD, "skills": [{"name": "Rust"}]}

    second = client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(token),
        json=changed_payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["confirmed_at"] == first.json()["confirmed_at"]
    assert second.json()["cv"]["skills"] == first.json()["cv"]["skills"]
    assert all(item["name"] != "Rust" for item in second.json()["cv"]["skills"])


def test_invalid_reviewed_payload_is_rejected_without_mutation() -> None:
    candidate, token = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)

    response = client.post(
        _confirm_url(cv.id, extraction.id),
        headers=_headers(token),
        json={**REVIEWED_PAYLOAD, "skills": "Python", "candidate_score": 99},
    )

    assert response.status_code == 422
    db = SessionLocal()
    try:
        assert db.get(CV, cv.id).skills == [{"name": "Original Skill"}]
        assert db.get(CVExtraction, extraction.id).confirmed_at is None
    finally:
        db.close()


def test_confirmation_rolls_back_cv_and_metadata_when_commit_fails(monkeypatch) -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)
    db = SessionLocal()

    def fail_commit() -> None:
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            CandidateCVExtractionService(db).confirm(
                candidate,
                cv.id,
                extraction.id,
                StructuredCVExtractionResult.model_validate(REVIEWED_PAYLOAD),
            )
    finally:
        db.close()

    verification_db = SessionLocal()
    try:
        assert verification_db.get(CV, cv.id).skills == [{"name": "Original Skill"}]
        assert verification_db.get(CVExtraction, extraction.id).confirmed_at is None
    finally:
        verification_db.close()


def test_competing_confirmations_apply_exactly_one_complete_payload() -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)
    first_payload = StructuredCVExtractionResult.model_validate(REVIEWED_PAYLOAD)
    second_payload = StructuredCVExtractionResult.model_validate(
        {**REVIEWED_PAYLOAD, "skills": [{"name": "Go"}]}
    )
    barrier = threading.Barrier(2)

    def confirm(payload: StructuredCVExtractionResult):
        db = SessionLocal()
        try:
            barrier.wait()
            return CandidateCVExtractionService(db).confirm(
                SimpleNamespace(id=candidate.id), cv.id, extraction.id, payload
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(confirm, [first_payload, second_payload]))

    assert responses[0].confirmed_at == responses[1].confirmed_at
    assert responses[0].cv.skills == responses[1].cv.skills
    final_names = [skill.name for skill in responses[0].cv.skills]
    assert final_names in (["Python", "FastAPI"], ["Go"])


def test_confirm_path_does_not_call_ai_or_document_extraction() -> None:
    candidate, _ = _create_user()
    cv = _create_cv(candidate.id, CVSourceType.UPLOADED)
    extraction = _create_extraction(cv.id)

    class ExplodingExtractor:
        async def extract_uploaded_cv(self, cv):
            pytest.fail("AI/document extraction was called during confirmation")

    db = SessionLocal()
    try:
        response = CandidateCVExtractionService(
            db, structured_extractor=ExplodingExtractor()
        ).confirm(
            candidate,
            cv.id,
            extraction.id,
            StructuredCVExtractionResult.model_validate(REVIEWED_PAYLOAD),
        )
        assert response.confirmed_at is not None
    finally:
        db.close()
