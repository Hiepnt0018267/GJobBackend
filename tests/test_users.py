"""
Task 03 — User Profile Management tests
Run: pytest tests/test_users.py -v

Also covers regression for Task 02 (register/login/auth/me).
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH_BASE = "/api/v1/auth"
USER_BASE = "/api/v1/users"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _register_and_login(role: str = "CANDIDATE") -> dict:
    """Register a fresh user and return login response dict."""
    email = f"profile_{uuid.uuid4().hex[:8]}@example.com"
    password = "testpassword"
    client.post(f"{AUTH_BASE}/register", json={
        "email": email,
        "password": password,
        "full_name": f"Test {role}",
        "role": role,
    })
    resp = client.post(f"{AUTH_BASE}/login", json={"email": email, "password": password})
    data = resp.json()
    return {
        "token": data["access_token"],
        "user": data["user"],
        "email": email,
        "password": password,
    }


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────────────
# GET /users/me
# ──────────────────────────────────────────────────────────────────────────────

def test_get_profile_authenticated():
    ctx = _register_and_login()
    resp = client.get(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == ctx["email"]
    assert data["role"] == "CANDIDATE"
    # Profile fields present (nullable)
    assert "phone" in data
    assert "avatar_url" in data
    assert "address" in data
    assert "bio" in data
    assert "updated_at" in data
    # Must never contain password
    assert "password" not in data
    assert "password_hash" not in data


def test_get_profile_no_token():
    resp = client.get(f"{USER_BASE}/me")
    assert resp.status_code in (401, 403)


def test_get_profile_invalid_token():
    resp = client.get(f"{USER_BASE}/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# PATCH /users/me
# ──────────────────────────────────────────────────────────────────────────────

def test_update_profile_valid():
    ctx = _register_and_login()
    resp = client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "full_name": "Updated Name",
        "phone": "0901234567",
        "address": "Ha Noi",
        "bio": "Software Engineering student",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["full_name"] == "Updated Name"
    assert data["phone"] == "0901234567"
    assert data["address"] == "Ha Noi"
    assert data["bio"] == "Software Engineering student"
    assert "password_hash" not in data


def test_update_partial_only_bio():
    ctx = _register_and_login()
    resp = client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "bio": "Only bio updated",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["bio"] == "Only bio updated"


def test_update_profile_no_token():
    resp = client.patch(f"{USER_BASE}/me", json={"full_name": "Hacker"})
    assert resp.status_code in (401, 403)


def test_update_profile_invalid_data():
    ctx = _register_and_login()
    # full_name as blank string → 422
    resp = client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "full_name": "   ",
    })
    assert resp.status_code == 422, resp.text


def test_cannot_change_role_via_profile():
    """role must be ignored/rejected if sent in body — user stays CANDIDATE."""
    ctx = _register_and_login("CANDIDATE")
    # Send role in payload — the schema does NOT accept it (422) or silently ignores it
    resp = client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "role": "ADMIN",
        "full_name": "Hacker",
    })
    # Expect either 422 (field not accepted) or 200 with role still CANDIDATE
    if resp.status_code == 200:
        assert resp.json()["role"] == "CANDIDATE", "role must not change"
    else:
        assert resp.status_code == 422


def test_cannot_change_is_active_via_profile():
    """is_active must not be changeable through PATCH /users/me."""
    ctx = _register_and_login("CANDIDATE")
    resp = client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "is_active": False,
    })
    if resp.status_code == 200:
        assert resp.json()["is_active"] is True, "is_active must not change"
    else:
        assert resp.status_code == 422


def test_update_persists_on_get():
    """After PATCH, GET /users/me should return the updated values."""
    ctx = _register_and_login()
    client.patch(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]), json={
        "bio": "Persistent bio",
    })
    resp = client.get(f"{USER_BASE}/me", headers=_auth_headers(ctx["token"]))
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Persistent bio"


# ──────────────────────────────────────────────────────────────────────────────
# Regression — Task 02 auth still works
# ──────────────────────────────────────────────────────────────────────────────

def test_regression_register():
    email = f"reg_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(f"{AUTH_BASE}/register", json={
        "email": email, "password": "password123", "full_name": "Reg User",
    })
    assert resp.status_code == 201, resp.text


def test_regression_login():
    ctx = _register_and_login()
    assert ctx["token"]


def test_regression_auth_me():
    ctx = _register_and_login()
    resp = client.get(f"{AUTH_BASE}/me", headers=_auth_headers(ctx["token"]))
    assert resp.status_code == 200
    assert resp.json()["email"] == ctx["email"]
