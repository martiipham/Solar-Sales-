"""Integration tests for the Emails API (/api/emails/*).

These endpoints power the EmailTemplates.tsx frontend page and the
email approval workflow in the dashboard.

Covers: list emails, stats, get single email, approve/edit/discard, bulk discard.
"""

import pytest
from memory.database import insert


class TestListEmails:
    """GET /api/emails"""

    def test_list_emails_empty(self, client, auth_headers):
        resp = client.get("/api/emails", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["emails"] == []
        assert data["total"] == 0

    def test_list_emails_with_data(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 1
        email = data["emails"][0]
        assert email["from_email"] == "customer@example.com"
        assert email["subject"] == "Solar panel inquiry"
        assert email["status"] == "pending"

    def test_list_emails_filter_by_status(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails?status=pending", headers=auth_headers)
        data = resp.get_json()
        assert all(e["status"] == "pending" for e in data["emails"])

    def test_list_emails_filter_by_classification(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails?classification=inquiry", headers=auth_headers)
        data = resp.get_json()
        assert all(e["classification"] == "inquiry" for e in data["emails"])

    def test_list_emails_search(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails?search=Solar", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] >= 1

    def test_list_emails_pagination(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails?limit=1&offset=0", headers=auth_headers)
        data = resp.get_json()
        assert data["limit"] == 1
        assert data["offset"] == 0

    def test_list_emails_urgency_filter(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails?urgency_min=5", headers=auth_headers)
        data = resp.get_json()
        # seed_email has urgency_score=7, should appear
        assert data["total"] >= 1


class TestEmailStats:
    """GET /api/emails/stats"""

    def test_email_stats_empty(self, client, auth_headers):
        resp = client.get("/api/emails/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["pending"] == 0
        assert data["sent"] == 0

    def test_email_stats_with_pending(self, client, auth_headers, seed_email):
        resp = client.get("/api/emails/stats", headers=auth_headers)
        data = resp.get_json()
        assert data["pending"] >= 1

    def test_email_stats_fields(self, client, auth_headers):
        resp = client.get("/api/emails/stats", headers=auth_headers)
        data = resp.get_json()
        for key in ["pending", "sent", "today_total", "today_pending", "discarded_today"]:
            assert key in data, f"Missing field: {key}"


class TestGetEmail:
    """GET /api/emails/<id>"""

    def test_get_email_success(self, client, auth_headers, seed_email):
        resp = client.get(f"/api/emails/{seed_email}", headers=auth_headers)
        assert resp.status_code == 200
        email = resp.get_json()["email"]
        assert email["from_email"] == "customer@example.com"
        assert "body" in email  # Full body included

    def test_get_email_not_found(self, client, auth_headers):
        resp = client.get("/api/emails/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestEmailApproval:
    """POST /gate/email-approve"""

    def test_discard_email(self, client, auth_headers, seed_email):
        resp = client.post("/gate/email-approve", headers=auth_headers, json={
            "email_id": seed_email,
            "action": "discard",
        })
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "discarded"

        # Verify it's now discarded
        resp2 = client.get(f"/api/emails/{seed_email}", headers=auth_headers)
        assert resp2.get_json()["email"]["status"] == "discarded"

    def test_approve_already_discarded(self, client, auth_headers, seed_email):
        # First discard
        client.post("/gate/email-approve", headers=auth_headers, json={
            "email_id": seed_email, "action": "discard",
        })
        # Try to send the discarded email
        resp = client.post("/gate/email-approve", headers=auth_headers, json={
            "email_id": seed_email, "action": "send",
        })
        assert resp.status_code == 400
        assert "not pending" in resp.get_json()["error"]

    def test_approve_invalid_action(self, client, auth_headers, seed_email):
        resp = client.post("/gate/email-approve", headers=auth_headers, json={
            "email_id": seed_email, "action": "invalid",
        })
        assert resp.status_code == 400

    def test_approve_missing_email_id(self, client, auth_headers):
        resp = client.post("/gate/email-approve", headers=auth_headers, json={
            "action": "send",
        })
        assert resp.status_code == 400

    def test_approve_nonexistent_email(self, client, auth_headers):
        resp = client.post("/gate/email-approve", headers=auth_headers, json={
            "email_id": 99999, "action": "send",
        })
        assert resp.status_code == 404


class TestBulkDiscard:
    """POST /api/emails/bulk-discard"""

    def test_bulk_discard_success(self, client, auth_headers, _patch_db):
        # Create multiple pending emails
        e1 = insert("emails", {
            "from_email": "a@test.com", "subject": "Test 1",
            "status": "pending", "urgency_score": 1,
        })
        e2 = insert("emails", {
            "from_email": "b@test.com", "subject": "Test 2",
            "status": "pending", "urgency_score": 2,
        })
        resp = client.post("/api/emails/bulk-discard", headers=auth_headers,
                           json={"ids": [e1, e2]})
        assert resp.status_code == 200
        assert resp.get_json()["discarded"] == 2

    def test_bulk_discard_empty_ids(self, client, auth_headers):
        resp = client.post("/api/emails/bulk-discard", headers=auth_headers,
                           json={"ids": []})
        assert resp.status_code == 400

    def test_bulk_discard_missing_ids(self, client, auth_headers):
        resp = client.post("/api/emails/bulk-discard", headers=auth_headers,
                           json={})
        assert resp.status_code == 400

    def test_bulk_discard_skips_non_pending(self, client, auth_headers, _patch_db):
        # Create one pending, one sent
        e1 = insert("emails", {
            "from_email": "a@test.com", "subject": "Pending",
            "status": "pending", "urgency_score": 1,
        })
        e2 = insert("emails", {
            "from_email": "b@test.com", "subject": "Already sent",
            "status": "sent", "urgency_score": 1,
        })
        resp = client.post("/api/emails/bulk-discard", headers=auth_headers,
                           json={"ids": [e1, e2]})
        assert resp.status_code == 200
        assert resp.get_json()["discarded"] == 1  # Only the pending one
