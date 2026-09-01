"""Task 07A: candidate-owned CV Builder API integration tests."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.cv import CV
from app.models.cv_template import CVTemplate, CVTemplateLayoutKey
from app.models.user import User, UserRole


client = TestClient(app)
BASE = "/api/v1/candidate/cvs"
TEMPLATE_CATALOG = "/api/v1/cv-templates"
MODERN_TEMPLATE_ID = "10000000-0000-0000-0000-000000000001"


def _token(role: str = "CANDIDATE") -> str:
    email = f"task07a_{uuid.uuid4().hex[:12]}@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Task 07A", "role": role},
    )
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token() -> str:
    email = f"task07a_admin_{uuid.uuid4().hex[:12]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(email=email, password_hash=hash_password("password123"), full_name="Task 07A Admin", role=UserRole.ADMIN))
        db.commit()
    finally:
        db.close()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _payload(**overrides):
    value = {
        "title": "CV Backend Developer",
        "template_id": MODERN_TEMPLATE_ID,
        "personal_info": {"full_name": "Nguyen Van A", "email": "a@example.com", "github_url": "https://github.com/example"},
        "career_objective": "Build reliable backend systems.",
        "educations": [{"school_name": "University", "degree": "Bachelor", "start_date": "2020-09-01", "end_date": "2024-06-01"}],
        "experiences": [{"company_name": "GJob", "position": "Developer", "start_date": "2024-01-01", "is_current": True}],
        "skills": [{"name": "Python", "level": "ADVANCED"}],
        "projects": [{"name": "GJob", "technologies": ["FastAPI", "PostgreSQL"], "project_url": "https://example.com/project"}],
        "certificates": [{"name": "AWS Certified", "organization": "AWS"}],
        "languages": [{"name": "English", "proficiency": "PROFESSIONAL"}],
    }
    value.update(overrides)
    return value


def _create(token: str, **overrides) -> dict:
    response = client.post(BASE, json=_payload(**overrides), headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def test_auth_role_and_server_managed_fields_are_enforced():
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers=_headers(_token("RECRUITER"))).status_code == 403
    assert client.get(BASE, headers=_headers(_admin_token())).status_code == 403

    token = _token()
    assert client.post(BASE, json=_payload(candidate_id=str(uuid.uuid4())), headers=_headers(token)).status_code == 422
    assert client.post(BASE, json=_payload(is_default=True), headers=_headers(token)).status_code == 422


def test_create_uses_current_candidate_and_first_cv_is_default():
    token = _token()
    first = _create(token)
    second = _create(token, title="CV Data Engineer")
    assert first["is_default"] is True
    assert second["is_default"] is False
    assert first["experiences"][0]["is_current"] is True

    db = SessionLocal()
    try:
        stored = db.query(CV).filter(CV.id == uuid.UUID(first["id"])).one()
        assert stored.candidate_id is not None
        assert stored.personal_info["email"] == "a@example.com"
        assert str(stored.template_id) == MODERN_TEMPLATE_ID
    finally:
        db.close()


def test_cv_avatar_url_is_created_returned_updated_and_can_be_cleared():
    token = _token()
    initial_avatar = "https://cdn.example.com/cvs/initial-avatar.jpg"
    created = _create(token, personal_info={"full_name": "Nguyen Van A", "avatar_url": initial_avatar})
    assert str(created["personal_info"]["avatar_url"]) == initial_avatar

    detail = client.get(f"{BASE}/{created['id']}", headers=_headers(token))
    assert detail.status_code == 200
    assert str(detail.json()["personal_info"]["avatar_url"]) == initial_avatar

    changed_avatar = "https://cdn.example.com/cvs/updated-avatar.png"
    updated = client.patch(
        f"{BASE}/{created['id']}",
        json={"personal_info": {"avatar_url": changed_avatar}},
        headers=_headers(token),
    )
    assert updated.status_code == 200, updated.text
    assert str(updated.json()["personal_info"]["avatar_url"]) == changed_avatar

    cleared = client.patch(
        f"{BASE}/{created['id']}",
        json={"personal_info": {"avatar_url": None}},
        headers=_headers(token),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["personal_info"]["avatar_url"] is None


def test_cv_avatar_url_is_optional_and_rejects_invalid_urls():
    token = _token()
    created = _create(token, personal_info={"full_name": "Nguyen Van A"})
    assert created["personal_info"]["avatar_url"] is None

    invalid = client.post(
        BASE,
        json=_payload(personal_info={"full_name": "Nguyen Van A", "avatar_url": "not-a-url"}),
        headers=_headers(token),
    )
    assert invalid.status_code == 422


def test_list_detail_and_idor_protection():
    owner, other = _token(), _token()
    created = _create(owner)
    assert client.get(BASE, headers=_headers(owner)).json()["total"] == 1
    detail = client.get(f"{BASE}/{created['id']}", headers=_headers(owner))
    assert detail.status_code == 200 and detail.json()["skills"][0]["name"] == "Python"
    assert detail.json()["template"]["layout_key"] == "MODERN"
    assert client.get(f"{BASE}/{created['id']}", headers=_headers(other)).status_code == 404
    assert client.patch(f"{BASE}/{created['id']}", json={"title": "Nope"}, headers=_headers(other)).status_code == 404
    assert client.delete(f"{BASE}/{created['id']}", headers=_headers(other)).status_code == 404


def test_update_replaces_structured_sections_and_rejects_invalid_data():
    token = _token()
    created = _create(token)
    patch = {
        "title": "CV Platform Engineer",
        "personal_info": {"full_name": "Nguyen B", "portfolio_url": "https://example.com"},
        "educations": [],
        "experiences": [{"company_name": "Platform", "position": "Engineer", "start_date": "2024-01-01", "is_current": True}],
        "skills": [{"name": "Kubernetes", "level": "EXPERT"}],
        "projects": [],
        "certificates": [],
        "languages": [{"name": "Vietnamese", "proficiency": "NATIVE"}],
    }
    updated = client.patch(f"{BASE}/{created['id']}", json=patch, headers=_headers(token))
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "CV Platform Engineer"
    assert updated.json()["educations"] == []
    assert updated.json()["skills"][0]["level"] == "EXPERT"

    invalid = client.patch(
        f"{BASE}/{created['id']}",
        json={"educations": [{"school_name": "University", "start_date": "2025-01-01", "end_date": "2024-01-01"}]},
        headers=_headers(token),
    )
    assert invalid.status_code == 422


def test_set_default_keeps_exactly_one_default_and_delete_reassigns():
    token = _token()
    first = _create(token, title="First")
    second = _create(token, title="Second")
    selected = client.patch(f"{BASE}/{second['id']}/default", headers=_headers(token))
    assert selected.status_code == 200 and selected.json()["is_default"] is True
    items = client.get(BASE, headers=_headers(token)).json()["items"]
    assert [item["id"] for item in items if item["is_default"]] == [second["id"]]

    assert client.delete(f"{BASE}/{second['id']}", headers=_headers(token)).status_code == 204
    items_after_delete = client.get(BASE, headers=_headers(token)).json()["items"]
    assert [item["id"] for item in items_after_delete if item["is_default"]] == [first["id"]]
    assert client.get(f"{BASE}/{second['id']}", headers=_headers(token)).status_code == 404


def test_public_template_catalog_returns_seeded_active_templates_in_order():
    response = client.get(TEMPLATE_CATALOG)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [item["layout_key"] for item in items[:3]] == ["MODERN", "CLASSIC", "MINIMAL"]
    assert [item["name"] for item in items[:3]] == ["Modern", "Classic", "Minimal"]
    assert all("id" in item and "is_featured" in item for item in items)


def test_candidate_can_change_to_an_active_template_without_changing_cv_content():
    token = _token()
    created = _create(token)
    original_content = created["experiences"]
    updated = client.patch(
        f"{BASE}/{created['id']}",
        json={"template_id": "10000000-0000-0000-0000-000000000002"},
        headers=_headers(token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["template"]["layout_key"] == "CLASSIC"
    assert updated.json()["experiences"] == original_content


def test_inactive_or_unknown_templates_are_rejected_and_hidden_from_catalog():
    inactive_id = uuid.uuid4()
    db = SessionLocal()
    try:
        db.add(
            CVTemplate(
                id=inactive_id,
                name="Inactive test template",
                layout_key=CVTemplateLayoutKey.MODERN,
                is_active=False,
                sort_order=0,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        assert str(inactive_id) not in [item["id"] for item in client.get(TEMPLATE_CATALOG).json()["items"]]
        token = _token()
        assert client.post(BASE, json=_payload(template_id=str(inactive_id)), headers=_headers(token)).status_code == 422
        assert client.post(BASE, json=_payload(template_id=str(uuid.uuid4())), headers=_headers(token)).status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.query(CVTemplate).filter(CVTemplate.id == inactive_id).delete()
            db.commit()
        finally:
            db.close()


def test_cv_using_a_later_inactive_template_remains_readable():
    template_id = uuid.uuid4()
    db = SessionLocal()
    try:
        db.add(
            CVTemplate(
                id=template_id,
                name="Template retained by existing CV",
                layout_key=CVTemplateLayoutKey.MINIMAL,
                is_active=True,
                sort_order=99,
            )
        )
        db.commit()
    finally:
        db.close()

    token = _token()
    created = _create(token, template_id=str(template_id))
    try:
        db = SessionLocal()
        try:
            db.query(CVTemplate).filter(CVTemplate.id == template_id).update({CVTemplate.is_active: False})
            db.commit()
        finally:
            db.close()

        assert client.get(f"{BASE}/{created['id']}", headers=_headers(token)).status_code == 200
        assert str(template_id) not in [item["id"] for item in client.get(TEMPLATE_CATALOG).json()["items"]]
        assert client.patch(f"{BASE}/{created['id']}", json={"template_id": str(template_id)}, headers=_headers(token)).status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.query(CV).filter(CV.id == uuid.UUID(created["id"])).delete()
            db.query(CVTemplate).filter(CVTemplate.id == template_id).delete()
            db.commit()
        finally:
            db.close()
