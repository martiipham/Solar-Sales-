"""Integration tests for the Auth API (/api/auth/*).

Covers: login, logout, me, refresh, change-password, and auth guards.
These endpoints power the frontend login page and session management.
"""

import pytest


class TestLogin:
    """POST /api/auth/login"""

    def test_login_success(self, client, seed_owner):
        resp = client.post("/api/auth/login", json={
            "email": seed_owner["email"],
            "password": seed_owner["password"],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["user"]["email"] == seed_owner["email"]
        assert data["user"]["role"] == "owner"
        assert data["user"]["name"] == "Test Owner"

    def test_login_wrong_password(self, client, seed_owner):
        resp = client.post("/api/auth/login", json={
            "email": seed_owner["email"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.get_json()["error"]

    def test_login_nonexistent_user(self, client, _patch_db):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client, _patch_db):
        resp = client.post("/api/auth/login", json={"email": ""})
        assert resp.status_code == 400

    def test_login_email_case_insensitive(self, client, seed_owner):
        resp = client.post("/api/auth/login", json={
            "email": seed_owner["email"].upper(),
            "password": seed_owner["password"],
        })
        assert resp.status_code == 200


class TestAuthMe:
    """GET /api/auth/me"""

    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "owner@test.solar"

    def test_me_no_token(self, client, _patch_db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client, _patch_db):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401


class TestLogout:
    """POST /api/auth/logout"""

    def test_logout_revokes_token(self, client, auth_headers, auth_token):
        # Logout
        resp = client.post("/api/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        # Token should now be revoked
        resp2 = client.get("/api/auth/me", headers=auth_headers)
        assert resp2.status_code == 401

    def test_logout_without_token(self, client, _patch_db):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200  # Graceful no-op


class TestTokenRefresh:
    """POST /api/auth/refresh"""

    def test_refresh_returns_new_token(self, client, auth_headers, auth_token):
        resp = client.post("/api/auth/refresh", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        new_token = data["token"]
        assert new_token != auth_token
        assert "user" in data

        # Old token should be revoked
        resp2 = client.get("/api/auth/me", headers=auth_headers)
        assert resp2.status_code == 401

        # New token should work
        resp3 = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {new_token}"
        })
        assert resp3.status_code == 200


class TestChangePassword:
    """POST /api/auth/change-password"""

    def test_change_password_success(self, client, auth_headers, seed_owner):
        resp = client.post("/api/auth/change-password", headers=auth_headers, json={
            "current": seed_owner["password"],
            "new": "newpassword123",
        })
        assert resp.status_code == 200

        # Can login with new password
        resp2 = client.post("/api/auth/login", json={
            "email": seed_owner["email"],
            "password": "newpassword123",
        })
        assert resp2.status_code == 200

    def test_change_password_wrong_current(self, client, auth_headers):
        resp = client.post("/api/auth/change-password", headers=auth_headers, json={
            "current": "wrongcurrent",
            "new": "newpassword123",
        })
        assert resp.status_code == 400

    def test_change_password_too_short(self, client, auth_headers, seed_owner):
        resp = client.post("/api/auth/change-password", headers=auth_headers, json={
            "current": seed_owner["password"],
            "new": "short",
        })
        assert resp.status_code == 400
        assert "8 characters" in resp.get_json()["error"]


class TestAuthGuards:
    """Verify that protected endpoints reject unauthenticated requests."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/reports/monthly"),
        ("GET", "/api/reports/summary"),
        ("GET", "/api/calls"),
        ("GET", "/api/calls/stats"),
        ("GET", "/api/emails"),
        ("GET", "/api/emails/stats"),
        ("GET", "/api/kb/profile"),
        ("GET", "/api/kb/products"),
        ("GET", "/api/kb/faqs"),
        ("GET", "/api/onboarding/status"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_protected_endpoint_requires_auth(self, client, _patch_db, method, path):
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path)
        assert resp.status_code == 401
