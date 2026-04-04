"""Integration tests for the Onboarding API (/api/onboarding/*).

These endpoints power the CRM Wizard frontend page (CRMWizard.tsx) and
the general onboarding flow for new solar company clients.

Covers: status check, company step, CRM step, voice step, knowledge step, complete.
"""

import pytest


class TestOnboardingStatus:
    """GET /api/onboarding/status"""

    def test_status_initial(self, client, auth_headers):
        resp = client.get("/api/onboarding/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_complete"] is False
        assert data["percent_done"] == 0
        assert data["next_step"] == "company"
        assert all(v is False for v in data["steps"].values())

    def test_status_contains_all_steps(self, client, auth_headers):
        resp = client.get("/api/onboarding/status", headers=auth_headers)
        data = resp.get_json()
        expected_steps = ["company", "crm", "voice", "knowledge", "complete"]
        for step in expected_steps:
            assert step in data["steps"], f"Missing step: {step}"


class TestOnboardingCompanyStep:
    """POST /api/onboarding/company"""

    def test_company_step_success(self, client, auth_headers):
        resp = client.post("/api/onboarding/company", headers=auth_headers, json={
            "company_name": "Aussie Solar Pty Ltd",
            "abn": "12345678901",
            "phone": "+61800111222",
            "email": "info@aussiesolar.com.au",
            "website": "https://aussiesolar.com.au",
            "service_areas": "Perth, Fremantle, Joondalup",
            "years_in_business": 8,
            "num_installers": 4,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"]["steps"]["company"] is True
        assert data["status"]["next_step"] == "crm"

    def test_company_step_missing_name(self, client, auth_headers):
        resp = client.post("/api/onboarding/company", headers=auth_headers, json={
            "phone": "+61800111222",
        })
        assert resp.status_code == 400
        assert "company_name" in resp.get_json()["error"]

    def test_company_step_updates_on_repeat(self, client, auth_headers):
        # First submission
        client.post("/api/onboarding/company", headers=auth_headers, json={
            "company_name": "Solar V1",
        })
        # Second submission updates
        resp = client.post("/api/onboarding/company", headers=auth_headers, json={
            "company_name": "Solar V2",
        })
        assert resp.status_code == 200


class TestOnboardingCRMStep:
    """POST /api/onboarding/crm"""

    def test_crm_step_success(self, client, auth_headers, seed_company_profile):
        resp = client.post("/api/onboarding/crm", headers=auth_headers, json={
            "ghl_api_key": "test_ghl_key_12345",
            "ghl_location_id": "loc_test_001",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"]["steps"]["crm"] is True

    def test_crm_step_missing_key(self, client, auth_headers):
        resp = client.post("/api/onboarding/crm", headers=auth_headers, json={
            "ghl_location_id": "loc_test_001",
        })
        assert resp.status_code == 400

    def test_crm_step_missing_location(self, client, auth_headers):
        resp = client.post("/api/onboarding/crm", headers=auth_headers, json={
            "ghl_api_key": "test_key",
        })
        assert resp.status_code == 400


class TestOnboardingVoiceStep:
    """POST /api/onboarding/voice"""

    def test_voice_step_success(self, client, auth_headers, seed_company_profile):
        resp = client.post("/api/onboarding/voice", headers=auth_headers, json={
            "retell_agent_id": "agent_test_001",
            "phone": "+61800999888",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"]["steps"]["voice"] is True

    def test_voice_step_missing_fields(self, client, auth_headers):
        resp = client.post("/api/onboarding/voice", headers=auth_headers, json={
            "retell_agent_id": "agent_test_001",
        })
        assert resp.status_code == 400


class TestOnboardingKnowledgeStep:
    """POST /api/onboarding/knowledge"""

    def test_knowledge_step_success(self, client, auth_headers):
        resp = client.post("/api/onboarding/knowledge", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"]["steps"]["knowledge"] is True


class TestOnboardingComplete:
    """POST /api/onboarding/complete"""

    def test_complete_marks_done(self, client, auth_headers):
        resp = client.post("/api/onboarding/complete", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["status"]["steps"]["complete"] is True

    def test_full_wizard_flow(self, client, auth_headers, seed_company_profile):
        """Walk through the entire onboarding wizard, verifying progress at each step."""
        # Step 1: Company
        r1 = client.post("/api/onboarding/company", headers=auth_headers,
                         json={"company_name": "Full Flow Solar"})
        assert r1.status_code == 200
        assert r1.get_json()["status"]["percent_done"] == 20

        # Step 2: CRM
        r2 = client.post("/api/onboarding/crm", headers=auth_headers,
                         json={"ghl_api_key": "key123", "ghl_location_id": "loc123"})
        assert r2.status_code == 200
        assert r2.get_json()["status"]["percent_done"] == 40

        # Step 3: Voice
        r3 = client.post("/api/onboarding/voice", headers=auth_headers,
                         json={"retell_agent_id": "agent123", "phone": "+61800000000"})
        assert r3.status_code == 200
        assert r3.get_json()["status"]["percent_done"] == 60

        # Step 4: Knowledge
        r4 = client.post("/api/onboarding/knowledge", headers=auth_headers)
        assert r4.status_code == 200
        assert r4.get_json()["status"]["percent_done"] == 80

        # Step 5: Complete
        r5 = client.post("/api/onboarding/complete", headers=auth_headers)
        assert r5.status_code == 200
        assert r5.get_json()["status"]["is_complete"] is True
        assert r5.get_json()["status"]["percent_done"] == 100
