"""Task 10E: ADMIN-only CV template catalog management integration tests."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.application import JobApplication
from app.models.cv import CV
from app.models.cv_template import CVTemplate
from app.models.user import User, UserRole


client = TestClient(app)
BASE = "/api/v1/admin/cv-templates"
PUBLIC_BASE = "/api/v1/cv-templates"
CV_BASE = "/api/v1/candidate/cvs"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user(role: UserRole) -> User:
    db = SessionLocal()
    try:
        user = User(
            email=f"task10e_{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("password123"),
            full_name="Task 10E User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user
    finally:
        db.close()


def _token(role: UserRole) -> str:
    user = _create_user(role)
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token() -> str:
    return _token(UserRole.ADMIN)


def _create_template(token: str, **overrides) -> dict:
    payload = {
        "name": f"__task10e__ Template {uuid.uuid4().hex}",
        "description": "Task 10E catalog test template",
        "layout_key": "MODERN",
        "thumbnail_url": "https://example.com/template.png",
        "is_active": True,
        "is_featured": False,
        "sort_order": 50,
    }
    payload.update(overrides)
    response = client.post(BASE, json=payload, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


VALID_THEME = {
    "primary_color": "#0F766E",
    "font_family": "ARIAL",
    "font_scale": "LARGE",
    "section_spacing": "RELAXED",
    "heading_style": "UNDERLINE",
}


def _create_cv(token: str, template_id: str) -> dict:
    response = client.post(
        CV_BASE,
        json={"title": "Task 10E CV", "template_id": template_id, "personal_info": {"full_name": "Candidate"}},
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _cleanup_task_records() -> None:
    db = SessionLocal()
    try:
        user_ids = list(db.scalars(select(User.id).where(User.email.like("task10e_%@example.com"))))
        template_ids = list(
            db.scalars(
                select(CVTemplate.id).where(CVTemplate.name.like(r"\_\_task10e\_\_%", escape="\\"))
            )
        )
        if user_ids:
            db.query(JobApplication).filter(JobApplication.candidate_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(CV).filter(CV.candidate_id.in_(user_ids)).delete(synchronize_session=False)
        if template_ids:
            db.query(CV).filter(CV.template_id.in_(template_ids)).delete(synchronize_session=False)
            db.query(CVTemplate).filter(CVTemplate.id.in_(template_ids)).delete(synchronize_session=False)
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


def test_admin_cv_template_routes_require_admin():
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers=_headers(_token(UserRole.CANDIDATE))).status_code == 403
    assert client.get(BASE, headers=_headers(_token(UserRole.RECRUITER))).status_code == 403
    assert client.get(BASE, headers=_headers(_admin_token())).status_code == 200


def test_admin_creates_metadata_for_all_renderer_layouts_and_validates_payload():
    admin_token = _admin_token()
    created = [
        _create_template(admin_token, layout_key=layout_key, name=f"__task10e__ {layout_key} {uuid.uuid4().hex}")
        for layout_key in ("MODERN", "CLASSIC", "MINIMAL")
    ]
    assert {item["layout_key"] for item in created} == {"MODERN", "CLASSIC", "MINIMAL"}
    assert all(item["usage_count"] == 0 for item in created)

    assert client.post(BASE, json={"name": "Bad", "layout_key": "CUSTOM"}, headers=_headers(admin_token)).status_code == 422
    assert client.post(
        BASE,
        json={"name": "Bad URL", "layout_key": "MODERN", "thumbnail_url": "not-a-url"},
        headers=_headers(admin_token),
    ).status_code == 422


def test_theme_config_is_typed_validated_and_exposed_by_admin_and_public_apis():
    admin_token = _admin_token()
    created = _create_template(admin_token, theme_config=VALID_THEME)
    assert created["theme_config"] == VALID_THEME

    public_item = next(item for item in client.get(PUBLIC_BASE).json()["items"] if item["id"] == created["id"])
    assert public_item["theme_config"] == VALID_THEME

    detail = client.get(f"{BASE}/{created['id']}", headers=_headers(admin_token))
    assert detail.status_code == 200
    assert detail.json()["theme_config"] == VALID_THEME

    invalid_cases = [
        {**VALID_THEME, "primary_color": "javascript:alert(1)"},
        {**VALID_THEME, "font_family": "COMIC_SANS_RANDOM"},
        {**VALID_THEME, "font_scale": "999"},
        {**VALID_THEME, "section_spacing": "12px"},
        {**VALID_THEME, "heading_style": "<style>"},
    ]
    for invalid_theme in invalid_cases:
        response = client.post(
            BASE,
            json={"name": "Invalid theme", "layout_key": "MODERN", "theme_config": invalid_theme},
            headers=_headers(admin_token),
        )
        assert response.status_code == 422


def test_existing_templates_receive_layout_defaults_and_used_templates_can_update_theme():
    admin_token = _admin_token()
    classic = _create_template(admin_token, layout_key="CLASSIC")
    assert classic["theme_config"] == {
        "primary_color": "#0F172A",
        "font_family": "INTER",
        "font_scale": "NORMAL",
        "section_spacing": "NORMAL",
        "heading_style": "UNDERLINE",
    }

    candidate_token = _token(UserRole.CANDIDATE)
    cv = _create_cv(candidate_token, classic["id"])
    updated_theme = {**VALID_THEME, "primary_color": "#7C3AED"}
    updated = client.patch(
        f"{BASE}/{classic['id']}",
        json={"theme_config": updated_theme},
        headers=_headers(admin_token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["theme_config"] == updated_theme
    assert updated.json()["layout_key"] == "CLASSIC"
    assert client.get(f"{CV_BASE}/{cv['id']}", headers=_headers(candidate_token)).json()["template"]["theme_config"] == updated_theme
    assert client.post(
        BASE,
        json={"name": "Invalid feature", "layout_key": "MODERN", "is_active": False, "is_featured": True},
        headers=_headers(admin_token),
    ).status_code == 422


def test_admin_lists_all_templates_with_server_side_search_filters_pagination_and_usage_count():
    admin_token = _admin_token()
    marker = uuid.uuid4().hex[:10]
    first = _create_template(admin_token, name=f"__task10e__ Alpha {marker}", description="Searchable description", sort_order=12)
    second = _create_template(admin_token, name=f"__task10e__ Beta {marker}", is_featured=True, sort_order=11)
    inactive = _create_template(admin_token, name=f"__task10e__ Gamma {marker}", is_active=False, sort_order=10)

    search = client.get(BASE, params={"search": marker.upper(), "page_size": 100}, headers=_headers(admin_token))
    assert search.status_code == 200, search.text
    assert {item["id"] for item in search.json()["items"]} == {first["id"], second["id"], inactive["id"]}
    assert search.json()["total"] == 3

    description_search = client.get(BASE, params={"search": "searchable description"}, headers=_headers(admin_token))
    assert description_search.status_code == 200
    assert [item["id"] for item in description_search.json()["items"]] == [first["id"]]

    combined = client.get(
        BASE,
        params={"search": marker, "is_active": "true", "is_featured": "true"},
        headers=_headers(admin_token),
    )
    assert combined.status_code == 200
    assert combined.json()["total"] == 1
    assert combined.json()["items"][0]["id"] == second["id"]

    paged = client.get(BASE, params={"search": marker, "page": 1, "page_size": 2}, headers=_headers(admin_token))
    assert paged.status_code == 200
    assert paged.json()["total"] == 3
    assert paged.json()["total_pages"] == 2
    assert [item["id"] for item in paged.json()["items"]] == [second["id"], inactive["id"]]
    assert client.get(BASE, params={"search": "   "}, headers=_headers(admin_token)).status_code == 200


def test_admin_gets_template_detail_updates_safe_metadata_and_blocks_unknown_template():
    admin_token = _admin_token()
    created = _create_template(admin_token)
    response = client.get(f"{BASE}/{created['id']}", headers=_headers(admin_token))
    assert response.status_code == 200, response.text
    assert response.json()["usage_count"] == 0

    updated = client.patch(
        f"{BASE}/{created['id']}",
        json={"name": "__task10e__ Updated", "description": "Updated description", "layout_key": "CLASSIC", "thumbnail_url": None, "sort_order": 3},
        headers=_headers(admin_token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "__task10e__ Updated"
    assert updated.json()["thumbnail_url"] is None
    assert updated.json()["layout_key"] == "CLASSIC"
    assert updated.json()["sort_order"] == 3
    assert client.patch(f"{BASE}/{created['id']}", json={"is_active": False}, headers=_headers(admin_token)).status_code == 422
    assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_headers(admin_token)).status_code == 404


def test_used_template_cannot_change_layout_but_usage_count_and_existing_cv_remain_safe_after_deactivation():
    admin_token = _admin_token()
    template = _create_template(admin_token, layout_key="MODERN")
    candidate_token = _token(UserRole.CANDIDATE)
    cv = _create_cv(candidate_token, template["id"])

    detail = client.get(f"{BASE}/{template['id']}", headers=_headers(admin_token))
    assert detail.status_code == 200
    assert detail.json()["usage_count"] == 1
    blocked_update = client.patch(f"{BASE}/{template['id']}", json={"layout_key": "CLASSIC"}, headers=_headers(admin_token))
    assert blocked_update.status_code == 409
    assert client.get(f"{BASE}/{template['id']}", headers=_headers(admin_token)).json()["layout_key"] == "MODERN"
    assert client.delete(f"{BASE}/{template['id']}", headers=_headers(admin_token)).status_code == 409

    deactivated = client.patch(f"{BASE}/{template['id']}/deactivate", headers=_headers(admin_token))
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["is_featured"] is False
    assert client.get(f"{CV_BASE}/{cv['id']}", headers=_headers(candidate_token)).status_code == 200
    assert client.patch(f"{CV_BASE}/{cv['id']}", json={"title": "Updated while inactive"}, headers=_headers(candidate_token)).status_code == 200
    assert client.post(CV_BASE, json={"title": "New CV", "template_id": template["id"], "personal_info": {"full_name": "Candidate"}}, headers=_headers(candidate_token)).status_code == 422
    assert client.patch(f"{CV_BASE}/{cv['id']}", json={"template_id": template["id"]}, headers=_headers(candidate_token)).status_code == 422
    deleted = client.delete(f"{BASE}/{template['id']}", headers=_headers(admin_token))
    assert deleted.status_code == 204
    assert client.get(f"{BASE}/{template['id']}", headers=_headers(admin_token)).status_code == 404
    assert template["id"] not in {item["id"] for item in client.get(PUBLIC_BASE).json()["items"]}
    assert client.get(f"{CV_BASE}/{cv['id']}", headers=_headers(candidate_token)).status_code == 200
    assert client.post(CV_BASE, json={"title": "New CV after template deletion", "template_id": template["id"], "personal_info": {"full_name": "Candidate"}}, headers=_headers(candidate_token)).status_code == 422


def test_active_public_catalog_and_candidate_selection_follow_template_lifecycle():
    admin_token = _admin_token()
    active = _create_template(admin_token, is_active=True)
    inactive = _create_template(admin_token, is_active=False)
    public_ids = {item["id"] for item in client.get(PUBLIC_BASE).json()["items"]}
    assert active["id"] in public_ids
    assert inactive["id"] not in public_ids

    candidate_token = _token(UserRole.CANDIDATE)
    assert _create_cv(candidate_token, active["id"])["template_id"] == active["id"]
    reactivated = client.patch(f"{BASE}/{inactive['id']}/activate", headers=_headers(admin_token))
    assert reactivated.status_code == 200
    assert reactivated.json()["is_featured"] is False
    assert inactive["id"] in {item["id"] for item in client.get(PUBLIC_BASE).json()["items"]}
    assert _create_cv(candidate_token, inactive["id"])["template_id"] == inactive["id"]
    assert client.patch(f"{BASE}/{inactive['id']}/activate", headers=_headers(admin_token)).status_code == 409
    assert client.patch(f"{BASE}/{inactive['id']}/deactivate", headers=_headers(admin_token)).status_code == 200
    assert client.patch(f"{BASE}/{inactive['id']}/deactivate", headers=_headers(admin_token)).status_code == 409


def test_feature_lifecycle_disallows_inactive_templates_and_deactivation_clears_featured_status():
    admin_token = _admin_token()
    template = _create_template(admin_token)
    featured = client.patch(f"{BASE}/{template['id']}/feature", headers=_headers(admin_token))
    assert featured.status_code == 200
    assert featured.json()["is_featured"] is True
    assert client.patch(f"{BASE}/{template['id']}/feature", headers=_headers(admin_token)).status_code == 409
    assert client.patch(f"{BASE}/{template['id']}/unfeature", headers=_headers(admin_token)).status_code == 200
    assert client.patch(f"{BASE}/{template['id']}/unfeature", headers=_headers(admin_token)).status_code == 409
    assert client.patch(f"{BASE}/{template['id']}/feature", headers=_headers(admin_token)).status_code == 200
    deactivated = client.patch(f"{BASE}/{template['id']}/deactivate", headers=_headers(admin_token))
    assert deactivated.status_code == 200
    assert deactivated.json()["is_featured"] is False
    assert client.patch(f"{BASE}/{template['id']}/feature", headers=_headers(admin_token)).status_code == 409


def test_dashboard_counts_and_openapi_reflect_template_lifecycle_with_safe_admin_delete_route():
    admin_token = _admin_token()
    before = client.get("/api/v1/admin/dashboard", headers=_headers(admin_token)).json()["cv_templates"]
    template = _create_template(admin_token)
    after_create = client.get("/api/v1/admin/dashboard", headers=_headers(admin_token)).json()["cv_templates"]
    assert after_create == {"total": before["total"] + 1, "active": before["active"] + 1, "inactive": before["inactive"]}
    assert client.delete(f"{BASE}/{template['id']}", headers=_headers(admin_token)).status_code == 204
    after_delete = client.get("/api/v1/admin/dashboard", headers=_headers(admin_token)).json()["cv_templates"]
    assert after_delete == {"total": after_create["total"] - 1, "active": after_create["active"] - 1, "inactive": after_create["inactive"]}
    paths = app.openapi()["paths"]
    assert BASE in paths and "delete" not in paths[BASE]
    assert f"{BASE}/{{template_id}}" in paths and "delete" in paths[f"{BASE}/{{template_id}}"]
