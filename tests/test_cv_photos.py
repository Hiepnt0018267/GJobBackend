"""Task 12D: private, candidate-owned builder CV photo integration tests."""

from io import BytesIO
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.user import User


client = TestClient(app)
BASE = "/api/v1/candidate/cvs"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token() -> tuple[str, str]:
    email = f"task12d_{uuid.uuid4().hex[:16]}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Task 12D", "role": "CANDIDATE"},
    )
    assert registered.status_code == 201, registered.text
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert logged_in.status_code == 200, logged_in.text
    db = SessionLocal()
    try:
        user_id = str(db.scalar(select(User.id).where(User.email == email)))
    finally:
        db.close()
    return logged_in.json()["access_token"], user_id


def _create(token: str) -> dict:
    response = client.post(
        BASE,
        json={"title": "Photo CV", "template_id": MODERN_TEMPLATE_ID, "personal_info": {"full_name": "Task 12D"}},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _image_bytes(image_format: str = "PNG") -> bytes:
    image = Image.new("RGB", (120, 160), color=(30, 99, 220))
    data = BytesIO()
    image.save(data, format=image_format)
    return data.getvalue()


def _use_temp_storage(monkeypatch, tmp_path: Path) -> Path:
    root = tmp_path / "private-cv-uploads"
    monkeypatch.setattr(settings, "CV_UPLOAD_STORAGE_ROOT", str(root))
    return root


def test_candidate_can_upload_view_replace_and_delete_a_private_photo(monkeypatch, tmp_path):
    root = _use_temp_storage(monkeypatch, tmp_path)
    token, candidate_id = _token()
    cv = _create(token)

    uploaded = client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.png", _image_bytes(), "image/png")},
        headers=_headers(token),
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["has_managed_photo"] is True
    files_before_replace = list((root / "cv-images" / candidate_id).glob("*.webp"))
    assert len(files_before_replace) == 1

    viewed = client.get(f"{BASE}/{cv['id']}/photo", headers=_headers(token))
    assert viewed.status_code == 200 and viewed.headers["content-type"].startswith("image/webp")
    assert viewed.content.startswith(b"RIFF")

    replaced = client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.jpg", _image_bytes("JPEG"), "image/jpeg")},
        headers=_headers(token),
    )
    assert replaced.status_code == 200 and replaced.json()["has_managed_photo"] is True
    assert len(list((root / "cv-images" / candidate_id).glob("*.webp"))) == 1

    deleted = client.delete(f"{BASE}/{cv['id']}/photo", headers=_headers(token))
    assert deleted.status_code == 200 and deleted.json()["has_managed_photo"] is False
    assert not list((root / "cv-images" / candidate_id).glob("*.webp"))
    assert client.get(f"{BASE}/{cv['id']}/photo", headers=_headers(token)).status_code == 404


def test_photo_rejects_non_images_and_enforces_candidate_ownership(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    owner, _ = _token()
    other, _ = _token()
    cv = _create(owner)
    invalid = client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("not-an-image.png", b"not an image", "image/png")},
        headers=_headers(owner),
    )
    assert invalid.status_code == 422
    assert client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.png", _image_bytes(), "image/png")},
        headers=_headers(other),
    ).status_code == 404
    assert client.get(f"{BASE}/{cv['id']}/photo", headers=_headers(other)).status_code == 404


def test_photo_enforces_byte_and_dimension_limits(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    token, _ = _token()
    cv = _create(token)
    monkeypatch.setattr(settings, "CV_PHOTO_MAX_DIMENSION", 64)
    oversized_dimensions = client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.png", _image_bytes(), "image/png")},
        headers=_headers(token),
    )
    assert oversized_dimensions.status_code == 422
    monkeypatch.setattr(settings, "CV_PHOTO_MAX_DIMENSION", 4096)
    monkeypatch.setattr(settings, "CV_PHOTO_MAX_BYTES", 32)
    assert client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.png", _image_bytes(), "image/png")},
        headers=_headers(token),
    ).status_code == 422


def test_photo_is_not_overwritten_by_a_personal_info_patch(monkeypatch, tmp_path):
    _use_temp_storage(monkeypatch, tmp_path)
    token, _ = _token()
    cv = _create(token)
    assert client.post(
        f"{BASE}/{cv['id']}/photo",
        files={"file": ("portrait.webp", _image_bytes("WEBP"), "image/webp")},
        headers=_headers(token),
    ).status_code == 200
    patched = client.patch(
        f"{BASE}/{cv['id']}",
        json={"personal_info": {"full_name": "Updated candidate"}},
        headers=_headers(token),
    )
    assert patched.status_code == 200 and patched.json()["has_managed_photo"] is True
    assert client.get(f"{BASE}/{cv['id']}/photo", headers=_headers(token)).status_code == 200
