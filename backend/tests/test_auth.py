import pytest
from backend.app.auth.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hashing():
    pw = "SecretOMRPassword2026!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_flow():
    payload = {"sub": "42", "role": "TEACHER", "email": "test@school.edu"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["role"] == "TEACHER"
    assert decoded["email"] == "test@school.edu"


def test_login_api_success(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": admin_user.email, "password": "AdminPass123!"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"
    assert data["user"]["email"] == admin_user.email


def test_login_api_bad_password(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": admin_user.email, "password": "WrongPassword"}
    )
    assert resp.status_code == 401


def test_admin_only_endpoints(client, teacher_headers, admin_headers):
    # Teacher attempting to access /api/users should be forbidden (403)
    resp_teacher = client.get("/api/users", headers=teacher_headers)
    assert resp_teacher.status_code == 403

    # Admin accessing /api/users should succeed (200)
    resp_admin = client.get("/api/users", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert isinstance(resp_admin.json(), list)
