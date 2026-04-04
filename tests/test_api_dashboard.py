"""Integration tests for the Dashboard API.

Covers: /api/health, /api/dashboard/summary, /api/agents/config,
        /api/crm/*, /api/leads, /api/voice/status, /api/support/message.

These endpoints power the main SolarAdmin dashboard frontend.
"""

import json
import pytest


class TestHealth:
    """GET /api/health (unauthenticated)"""

    def test_health_returns_ok(self, client, _patch_db):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "dashboard-api"
        assert "timestamp" in data

    def test_health_includes_crm_status(self, client, _patch_db):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "crm" in data


class TestDashboardSummary:
    """GET /api/dashboard/summary"""

    def test_summary_empty_db(self, client, auth_headers):
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["calls_today"] == 0
        assert data["emails_today"] == 0
        assert data["leads_today"] == 0
        assert data["hot_leads"] == 0
        assert data["proposals_sent"] == 0
        assert data["contacts_total"] == 0

    def test_summary_with_data(self, client, auth_headers, seed_lead, seed_call, seed_email):
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        # Lead with score 8.5 counts as hot
        assert data["hot_leads"] >= 1

    def test_summary_returns_all_expected_fields(self, client, auth_headers):
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        data = resp.get_json()
        expected_fields = [
            "calls_today", "emails_today", "leads_today", "hot_leads",
            "proposals_sent", "crm_last_sync", "contacts_total",
            "calls_this_week", "pending_approvals",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


class TestLeads:
    """GET /api/leads, PATCH /api/leads/<id>/status, POST /api/leads/<id>/proposal"""

    def test_leads_list_empty(self, client, auth_headers):
        resp = client.get("/api/leads", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["leads"] == []
        assert data["count"] == 0

    def test_leads_list_with_data(self, client, auth_headers, seed_lead):
        resp = client.get("/api/leads", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        lead = data["leads"][0]
        assert lead["name"] == "Jane Solar"
        assert lead["qualification_score"] == 8.5
        assert lead["status"] == "new"

    def test_leads_list_respects_limit(self, client, auth_headers, seed_lead):
        resp = client.get("/api/leads?limit=1", headers=auth_headers)
        data = resp.get_json()
        assert len(data["leads"]) <= 1

    def test_update_lead_status(self, client, auth_headers, seed_lead):
        resp = client.patch(f"/api/leads/{seed_lead}/status",
                            headers=auth_headers,
                            json={"status": "contacted"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "contacted"

    def test_update_lead_invalid_status(self, client, auth_headers, seed_lead):
        resp = client.patch(f"/api/leads/{seed_lead}/status",
                            headers=auth_headers,
                            json={"status": "invalid_status"})
        assert resp.status_code == 400

    def test_update_lead_missing_status(self, client, auth_headers, seed_lead):
        resp = client.patch(f"/api/leads/{seed_lead}/status",
                            headers=auth_headers, json={})
        assert resp.status_code == 400

    def test_trigger_proposal(self, client, auth_headers, seed_lead):
        resp = client.post(f"/api/leads/{seed_lead}/proposal",
                           headers=auth_headers)
        assert resp.status_code == 202
        assert resp.get_json()["ok"] is True

    def test_trigger_proposal_not_found(self, client, auth_headers):
        resp = client.post("/api/leads/99999/proposal",
                           headers=auth_headers)
        assert resp.status_code == 404


class TestAgentsConfig:
    """GET/PATCH /api/agents/config"""

    def test_agents_config_get_empty(self, client, auth_headers):
        resp = client.get("/api/agents/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "agents" in data
        assert "schedule" in data

    def test_agents_config_toggle(self, client, auth_headers):
        # Disable an agent
        resp = client.patch("/api/agents/config", headers=auth_headers,
                            json={"agent_id": "scout", "enabled": False})
        assert resp.status_code == 200
        assert resp.get_json()["enabled"] is False

        # Verify it persisted
        resp2 = client.get("/api/agents/config", headers=auth_headers)
        agents = resp2.get_json()["agents"]
        assert agents.get("scout") is False

        # Re-enable
        resp3 = client.patch("/api/agents/config", headers=auth_headers,
                             json={"agent_id": "scout", "enabled": True})
        assert resp3.status_code == 200

    def test_agents_config_missing_id(self, client, auth_headers):
        resp = client.patch("/api/agents/config", headers=auth_headers,
                            json={"enabled": True})
        assert resp.status_code == 400


class TestVoiceStatus:
    """GET /api/voice/status"""

    def test_voice_status_offline(self, client, auth_headers):
        resp = client.get("/api/voice/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("offline", "needs_setup", "live")

    def test_voice_status_fields(self, client, auth_headers):
        resp = client.get("/api/voice/status", headers=auth_headers)
        data = resp.get_json()
        assert "retell" in data
        assert "elevenlabs" in data
        assert "agent_ready" in data


class TestSupportMessage:
    """POST /api/support/message"""

    def test_support_message_empty(self, client, auth_headers):
        resp = client.post("/api/support/message", headers=auth_headers,
                           json={"message": ""})
        assert resp.status_code == 400

    def test_support_message_missing(self, client, auth_headers):
        resp = client.post("/api/support/message", headers=auth_headers,
                           json={})
        assert resp.status_code == 400


class TestCRMEndpoints:
    """GET /api/crm/* endpoints"""

    def test_crm_status(self, client, auth_headers):
        resp = client.get("/api/crm/status", headers=auth_headers)
        assert resp.status_code == 200

    def test_crm_pipeline_empty(self, client, auth_headers):
        resp = client.get("/api/crm/pipeline", headers=auth_headers)
        # May be 200 with empty stages or 500 if CRM not configured
        assert resp.status_code in (200, 500)

    def test_crm_contacts_empty(self, client, auth_headers):
        resp = client.get("/api/crm/contacts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["contacts"] == []

    def test_crm_contacts_limit(self, client, auth_headers):
        resp = client.get("/api/crm/contacts?limit=5", headers=auth_headers)
        assert resp.status_code == 200

    def test_crm_metrics_empty(self, client, auth_headers):
        resp = client.get("/api/crm/metrics", headers=auth_headers)
        assert resp.status_code == 200
