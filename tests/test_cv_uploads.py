"""Task 12C: secure candidate-owned PDF/DOCX CV upload integration tests."""

from io import BytesIO
from pathlib import Path
import uuid

import fitz
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication
from app.models.cv import CV
from app.models.job import Job, JobStatus
from app.models.user import User, UserRole


client = TestClient(app)
CV_BASE = "/api/v1/candidate/cvs"
JOBS_BASE = "/api/v1/jobs"
RECRUITER_BASE = "/api/v1/recruiters/applications"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token(role: str = "CANDIDATE") -> tuple[str, str]:
    email = f"task12c_{uuid.uuid4().hex[:16]}@example.com"
    if role == "ADMIN":
        db = SessionLocal()
        try:
            user = User(email=email, password_hash=hash_password("password123"), full_name="Task 12C Admin", role=UserRole.ADMIN)
            db.add(user)
            db.commit()
        finally:
            db.close()
    else:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "password123", "full_name": "Task 12C", "role": role},
        )
        assert registered.status_code == 201, registered.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        user_id = str(db.scalar(select(User.id).where(User.email == email)))
    finally:
        db.close()
    return login.json()["access_token"], user_id


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Task 12C CV")
    try:
        return document.tobytes()
    finally:
        document.close()


def _docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Task 12C CV")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _upload(token: str, filename: str = "candidate.pdf", content: bytes | None = None, mime_type: str = "application/pdf", title: str = "Uploaded CV"):
    return client.post(
        f"{CV_BASE}/upload",
        data={"title": title},
        files={"file": (filename, _pdf_bytes() if content is None else content, mime_type)},
        headers=_headers(token),
    )


def _create_job(recruiter_id: str) -> str:
    db = SessionLocal()
    try:
        job = Job(
            recruiter_id=uuid.UUID(recruiter_id),
            title=f"Task 12C Job {uuid.uuid4().hex}",
            description="Secure CV-file access test",
            company_name="GJob",
            status=JobStatus.APPROVED,
        )
        db.add(job)
        db.commit()
        return str(job.id)
    finally:
        db.close()


def _use_temp_storage(monkeypatch, tmp_path: Path) -> Path:
    root = tmp_path / "private-cv-uploads"
    monkeypatch.setattr(settings, "CV_UPLOAD_STORAGE_ROOT", str(root))
    return root


def test_upload_requires_authenticated_candidate_role(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    assert client.post(f"{CV_BASE}/upload", data={"title": "No auth"}, files={"file": ("cv.pdf", _pdf_bytes(), "application/pdf")}).status_code == 401
    recruiter, _ = _token("RECRUITER")
    admin, _ = _token("ADMIN")
    assert _upload(recruiter).status_code == 403
    assert _upload(admin).status_code == 403


def test_uploads_pdf_and_docx_without_exposing_storage_key(monkeypatch, tmp_path):
    root = _use_temp_storage(monkeypatch, tmp_path)
    token, candidate_id = _token()

    pdf = _upload(token)
    assert pdf.status_code == 201, pdf.text
    payload = pdf.json()
    assert payload["source_type"] == "UPLOADED"
    assert payload["template_id"] is None and payload["template"] is None
    assert payload["original_filename"] == "candidate.pdf"
    assert payload["mime_type"] == "application/pdf"
    assert payload["file_size"] > 0 and payload["uploaded_at"]
    assert "storage_key" not in payload
    assert list((root / "cvs" / candidate_id).glob("*.pdf"))

    docx = _upload(
        token,
        filename="candidate.docx",
        content=_docx_bytes(),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        title="DOCX CV",
    )
    assert docx.status_code == 201, docx.text
    assert docx.json()["source_type"] == "UPLOADED"
    assert docx.json()["mime_type"].endswith("document")

    downloaded = client.get(f"{CV_BASE}/{payload['id']}/file", headers=_headers(token))
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.content.startswith(b"%PDF-")


def test_upload_validation_rejects_mismatch_fake_empty_and_oversize(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    token, _ = _token()
    assert _upload(token, filename="cv.exe", mime_type="application/octet-stream").status_code == 422
    assert _upload(token, filename="cv.pdf", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document").status_code == 422
    assert _upload(token, filename="cv.pdf", content=b"%PDF-not-a-real-document").status_code == 422
    assert _upload(token, filename="cv.docx", content=b"not-a-docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document").status_code == 422
    assert _upload(token, content=b"").status_code == 422

    monkeypatch.setattr(settings, "CV_UPLOAD_MAX_BYTES", 64)
    assert _upload(token, content=_pdf_bytes()).status_code == 422


def test_upload_sanitizes_filename_and_unused_file_is_deleted(monkeypatch, tmp_path):
    root = _use_temp_storage(monkeypatch, tmp_path)
    token, candidate_id = _token()
    created = _upload(token, filename="../../unsafe-name.pdf")
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["original_filename"] == "unsafe-name.pdf"
    stored_files = list((root / "cvs" / candidate_id).glob("*.pdf"))
    assert len(stored_files) == 1
    assert client.delete(f"{CV_BASE}/{payload['id']}", headers=_headers(token)).status_code == 204
    assert not stored_files[0].exists()


def test_uploaded_cv_can_be_default_applied_and_cannot_be_deleted_while_referenced(monkeypatch, tmp_path):
    root = _use_temp_storage(monkeypatch, tmp_path)
    candidate_token, candidate_id = _token()
    recruiter_token, recruiter_id = _token("RECRUITER")
    uploaded = _upload(candidate_token)
    assert uploaded.status_code == 201, uploaded.text
    cv = uploaded.json()
    assert cv["is_default"] is True

    builder = client.post(
        CV_BASE,
        json={"title": "Builder CV", "template_id": MODERN_TEMPLATE_ID, "personal_info": {"full_name": "Task 12C"}},
        headers=_headers(candidate_token),
    )
    assert builder.status_code == 201, builder.text
    assert builder.json()["is_default"] is False and builder.json()["source_type"] == "BUILDER"

    job_id = _create_job(recruiter_id)
    applied = client.post(f"{JOBS_BASE}/{job_id}/applications", json={"cv_id": cv["id"]}, headers=_headers(candidate_token))
    assert applied.status_code == 201, applied.text
    assert client.delete(f"{CV_BASE}/{cv['id']}", headers=_headers(candidate_token)).status_code == 409
    assert list((root / "cvs" / candidate_id).glob("*.pdf"))

    own_file = client.get(f"{CV_BASE}/{cv['id']}/file", headers=_headers(candidate_token))
    assert own_file.status_code == 200
    recruiter_file = client.get(f"{RECRUITER_BASE}/{applied.json()['id']}/cv-file", headers=_headers(recruiter_token))
    assert recruiter_file.status_code == 200
    other_recruiter, _ = _token("RECRUITER")
    assert client.get(f"{RECRUITER_BASE}/{applied.json()['id']}/cv-file", headers=_headers(other_recruiter)).status_code == 404

    db = SessionLocal()
    try:
        stored = db.get(CV, uuid.UUID(cv["id"]))
        assert stored is not None and stored.template_id is None and stored.storage_key
        assert db.query(JobApplication).filter(JobApplication.cv_id == stored.id).count() == 1
    finally:
        db.close()
