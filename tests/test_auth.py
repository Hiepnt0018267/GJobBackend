"""
Task 02 — Authentication & Authorization tests
Run: pytest tests/test_auth.py -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE = "/api/v1/auth"


# ──────────────────────────────────────────────────────────────────────────────
# Register
# ──────────────────────────────────────────────────────────────────────────────

def test_register_candidate():
    import uuid
    unique_email = f"candidate_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(f"{BASE}/register", json={
        "email": unique_email,
        "password": "password123",
        "full_name": "Nguyen Van A",
        "role": "CANDIDATE",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user"]["email"] == unique_email
    assert data["user"]["role"] == "CANDIDATE"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_recruiter():
    import uuid
    unique_email = f"recruiter_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(f"{BASE}/register", json={
        "email": unique_email,
        "password": "password123",
        "full_name": "Recruiter B",
        "role": "RECRUITER",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["role"] == "RECRUITER"


def test_register_admin_denied():
    """Public registration with ADMIN role must be denied."""
    import uuid
    unique_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(f"{BASE}/register", json={
        "email": unique_email,
        "password": "password123",
        "full_name": "Admin Hacker",
        "role": "ADMIN",
    })
    assert resp.status_code == 403, resp.text


def test_register_duplicate_email():
    import uuid
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/register", json={
        "email": email, "password": "password123", "full_name": "Dup User",
    })
    resp = client.post(f"{BASE}/register", json={
        "email": email, "password": "password123", "full_name": "Dup User2",
    })
    assert resp.status_code == 409, resp.text


def test_register_invalid_email():
    resp = client.post(f"{BASE}/register", json={
        "email": "not-an-email",
        "password": "password123",
        "full_name": "Bad Email",
    })
    assert resp.status_code == 422, resp.text


def test_register_short_password():
    import uuid
    resp = client.post(f"{BASE}/register", json={
        "email": f"short_{uuid.uuid4().hex[:8]}@example.com",
        "password": "123",
        "full_name": "Short Pass",
    })
    assert resp.status_code == 422, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def registered_user():
    """Register a test user once and return (email, password)."""
    import uuid
    email = f"login_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "testpassword"
    client.post(f"{BASE}/register", json={
        "email": email, "password": password, "full_name": "Login Tester",
    })
    return email, password


def test_login_success(registered_user):
    email, password = registered_user
    resp = client.post(f"{BASE}/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_wrong_password(registered_user):
    email, _ = registered_user
    resp = client.post(f"{BASE}/login", json={"email": email, "password": "WRONG_PASS"})
    assert resp.status_code == 401, resp.text


def test_login_unknown_email():
    resp = client.post(f"{BASE}/login", json={
        "email": "nobody_xyz@example.com", "password": "password123",
    })
    assert resp.status_code == 401, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Current user (/me)
# ──────────────────────────────────────────────────────────────────────────────

def _get_token(email, password) -> str:
    resp = client.post(f"{BASE}/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_me_valid_token(registered_user):
    email, password = registered_user
    token = _get_token(email, password)
    resp = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == email
    assert "password_hash" not in resp.json()


def test_me_no_token():
    # FastAPI's HTTPBearer returns 403 when Authorization header is entirely absent
    resp = client.get(f"{BASE}/me")
    assert resp.status_code in (401, 403), resp.text


def test_me_invalid_token():
    resp = client.get(f"{BASE}/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Role-based authorization (using require_role dependency on a test endpoint)
# ──────────────────────────────────────────────────────────────────────────────

# We'll add a temporary test router inline
from fastapi import Depends
from app.core.dependencies import require_role
from app.models.user import UserRole, User

@app.get("/test/admin-only", tags=["_test"])
def admin_only(user: User = Depends(require_role(UserRole.ADMIN))):
    return {"ok": True}

@app.get("/test/candidate-only", tags=["_test"])
def candidate_only(user: User = Depends(require_role(UserRole.CANDIDATE))):
    return {"ok": True}


def _register_and_login(role: str) -> str:
    import uuid
    email = f"rbac_{role.lower()}_{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/register", json={
        "email": email, "password": "password123",
        "full_name": f"RBAC {role}", "role": role,
    })
    resp = client.post(f"{BASE}/login", json={"email": email, "password": "password123"})
    return resp.json()["access_token"]


def test_candidate_accesses_candidate_endpoint():
    token = _register_and_login("CANDIDATE")
    resp = client.get("/test/candidate-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


def test_candidate_denied_admin_endpoint():
    token = _register_and_login("CANDIDATE")
    resp = client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, resp.text


def test_recruiter_denied_admin_endpoint():
    token = _register_and_login("RECRUITER")
    resp = client.get("/test/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, resp.text
