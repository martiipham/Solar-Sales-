"""Comprehensive tests for CRM integrations: router, clients, and field mapper.

Tests cover:
  - CRM router routing logic for all three providers
  - Individual client functions with mocked HTTP responses
  - Field mapper bidirectional mapping
  - Edge cases: missing config, API failures, empty data
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure solaradmin is importable
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_crm_globals():
    """Reset lazy-loaded CRM client globals between tests."""
    import integrations.crm_router as router
    router._ghl = None
    router._hubspot = None
    router._salesforce = None
    router._agilecrm = None
    yield


@pytest.fixture()
def mock_ghl_config(monkeypatch):
    """Configure environment for GHL as the active CRM."""
    import config as cfg
    monkeypatch.setattr(cfg, "GHL_API_KEY", "test-ghl-key")
    monkeypatch.setattr(cfg, "GHL_LOCATION_ID", "loc_test_123")
    monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "")
    monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "")
    return cfg


@pytest.fixture()
def mock_hubspot_config(monkeypatch):
    """Configure environment for HubSpot as the active CRM."""
    import config as cfg
    monkeypatch.setattr(cfg, "GHL_API_KEY", "")
    monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "test-hubspot-key")
    monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "")
    return cfg


@pytest.fixture()
def mock_salesforce_config(monkeypatch):
    """Configure environment for Salesforce as the active CRM."""
    import config as cfg
    monkeypatch.setattr(cfg, "GHL_API_KEY", "")
    monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "")
    monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "test@salesforce.com")
    monkeypatch.setattr(cfg, "SALESFORCE_PASSWORD", "testpass")
    monkeypatch.setattr(cfg, "SALESFORCE_SECURITY_TOKEN", "token123")
    monkeypatch.setattr(cfg, "SALESFORCE_CLIENT_ID", "client_id")
    monkeypatch.setattr(cfg, "SALESFORCE_CLIENT_SECRET", "client_secret")
    return cfg


@pytest.fixture()
def mock_agilecrm_config(monkeypatch):
    """Configure environment for Agile CRM as the active CRM."""
    import config as cfg
    monkeypatch.setattr(cfg, "GHL_API_KEY", "")
    monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "")
    monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "")
    monkeypatch.setattr(cfg, "AGILECRM_DOMAIN", "testsolar")
    monkeypatch.setattr(cfg, "AGILECRM_EMAIL", "test@solar.com")
    monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "test-agile-key")
    return cfg


@pytest.fixture()
def mock_no_crm_config(monkeypatch):
    """Configure environment with no CRM."""
    import config as cfg
    monkeypatch.setattr(cfg, "GHL_API_KEY", "")
    monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "")
    monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "")
    monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "")
    return cfg


def _mock_response(status_code=200, json_data=None):
    """Create a mock HTTP response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    return resp


# ═════════════════════════════════════════════════════════════════════════════
# CRM ROUTER TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestCRMRouterDetection:
    """Test CRM detection and priority ordering."""

    def test_active_crm_ghl(self, mock_ghl_config):
        from integrations.crm_router import active_crm
        assert active_crm() == "ghl"

    def test_active_crm_hubspot(self, mock_hubspot_config):
        from integrations.crm_router import active_crm
        assert active_crm() == "hubspot"

    def test_active_crm_salesforce(self, mock_salesforce_config):
        from integrations.crm_router import active_crm
        assert active_crm() == "salesforce"

    def test_active_crm_agilecrm(self, mock_agilecrm_config):
        from integrations.crm_router import active_crm
        assert active_crm() == "agilecrm"

    def test_active_crm_none(self, mock_no_crm_config):
        from integrations.crm_router import active_crm
        assert active_crm() == "none"

    def test_ghl_takes_priority_over_hubspot(self, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "GHL_API_KEY", "ghl-key")
        monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "hs-key")
        monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "")
        from integrations.crm_router import active_crm
        assert active_crm() == "ghl"

    def test_hubspot_takes_priority_over_salesforce(self, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "GHL_API_KEY", "")
        monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "hs-key")
        monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "user@sf.com")
        from integrations.crm_router import active_crm
        assert active_crm() == "hubspot"

    def test_salesforce_takes_priority_over_agilecrm(self, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "GHL_API_KEY", "")
        monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "")
        monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "user@sf.com")
        monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "agile-key")
        from integrations.crm_router import active_crm
        assert active_crm() == "salesforce"

    def test_all_configured_crms(self, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "GHL_API_KEY", "ghl-key")
        monkeypatch.setattr(cfg, "HUBSPOT_API_KEY", "hs-key")
        monkeypatch.setattr(cfg, "SALESFORCE_USERNAME", "user@sf.com")
        monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "agile-key")
        from integrations.crm_router import all_configured_crms
        result = all_configured_crms()
        assert "ghl" in result
        assert "hubspot" in result
        assert "salesforce" in result
        assert "agilecrm" in result

    def test_is_configured_true(self, mock_ghl_config):
        from integrations.crm_router import is_configured
        assert is_configured() is True

    def test_is_configured_false(self, mock_no_crm_config):
        from integrations.crm_router import is_configured
        assert is_configured() is False

    def test_status_dict(self, mock_ghl_config):
        from integrations.crm_router import status
        s = status()
        assert s["active"] == "ghl"
        assert s["ghl"] is True
        assert s["hubspot"] is False
        assert s["salesforce"] is False
        assert s["agilecrm"] is False

    def test_status_dict_agilecrm(self, mock_agilecrm_config):
        from integrations.crm_router import status
        s = status()
        assert s["active"] == "agilecrm"
        assert s["agilecrm"] is True


class TestCRMRouterRouting:
    """Test that router dispatches to the correct CRM client."""

    @patch("integrations.ghl_client.get_contact")
    def test_routes_to_ghl(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = {"id": "c1", "firstName": "Jane"}
        from integrations.crm_router import get_contact
        result = get_contact("c1")
        mock_fn.assert_called_once_with("c1")
        assert result["id"] == "c1"

    @patch("integrations.hubspot_client.get_contact")
    def test_routes_to_hubspot(self, mock_fn, mock_hubspot_config):
        mock_fn.return_value = {"id": "101", "properties": {"firstname": "Jane"}}
        from integrations.crm_router import get_contact
        result = get_contact("101")
        mock_fn.assert_called_once_with("101")
        assert result["id"] == "101"

    @patch("integrations.salesforce_client.get_contact")
    def test_routes_to_salesforce(self, mock_fn, mock_salesforce_config):
        mock_fn.return_value = {"Id": "003xx", "FirstName": "Jane"}
        from integrations.crm_router import get_contact
        result = get_contact("003xx")
        mock_fn.assert_called_once_with("003xx")
        assert result["Id"] == "003xx"

    def test_returns_none_when_no_crm(self, mock_no_crm_config):
        from integrations.crm_router import get_contact
        result = get_contact("c1")
        assert result is None

    @patch("integrations.ghl_client.create_contact")
    def test_create_contact_routes(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = {"contact": {"id": "new1"}}
        from integrations.crm_router import create_contact
        data = {"name": "John Smith", "email": "john@example.com"}
        result = create_contact(data)
        mock_fn.assert_called_once_with(data)
        assert result is not None

    @patch("integrations.ghl_client.move_pipeline_stage")
    def test_move_pipeline_routes(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = {"success": True}
        from integrations.crm_router import move_pipeline_stage
        result = move_pipeline_stage("c1", "stage_hot")
        mock_fn.assert_called_once_with("c1", "stage_hot")
        assert result is not None

    @patch("integrations.agilecrm_client.get_contact")
    def test_routes_to_agilecrm(self, mock_fn, mock_agilecrm_config):
        mock_fn.return_value = {"id": 5001, "properties": [{"name": "first_name", "value": "Jane"}]}
        from integrations.crm_router import get_contact
        result = get_contact("5001")
        mock_fn.assert_called_once_with("5001")
        assert result["id"] == 5001

    @patch("integrations.ghl_client.get_contact")
    def test_router_catches_exceptions(self, mock_fn, mock_ghl_config):
        mock_fn.side_effect = Exception("API timeout")
        from integrations.crm_router import get_contact
        result = get_contact("c1")
        assert result is None

    @patch("integrations.ghl_client.find_contact_by_phone")
    def test_find_contact_by_phone_routes_to_ghl(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = {"id": "c99", "phone": "+61412345678"}
        from integrations.crm_router import find_contact_by_phone
        result = find_contact_by_phone("+61412345678")
        mock_fn.assert_called_once_with("+61412345678")
        assert result["id"] == "c99"

    @patch("integrations.hubspot_client.find_contact_by_phone")
    def test_find_contact_by_phone_routes_to_hubspot(self, mock_fn, mock_hubspot_config):
        mock_fn.return_value = {"id": "hs-101", "properties": {"phone": "+61412345678"}}
        from integrations.crm_router import find_contact_by_phone
        result = find_contact_by_phone("+61412345678")
        mock_fn.assert_called_once_with("+61412345678")
        assert result["id"] == "hs-101"

    @patch("integrations.ghl_client.get_pipeline_stages")
    def test_get_pipeline_stages_routes_to_ghl(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = [{"id": "s1", "name": "New Lead"}, {"id": "s2", "name": "Qualified"}]
        from integrations.crm_router import get_pipeline_stages
        result = get_pipeline_stages("pipe_abc")
        mock_fn.assert_called_once_with("pipe_abc")
        assert len(result) == 2
        assert result[0]["name"] == "New Lead"


class TestCRMRouterSMS:
    """Test SMS routing (only supported by GHL)."""

    @patch("integrations.ghl_client.send_sms")
    def test_sms_routes_to_ghl(self, mock_fn, mock_ghl_config):
        mock_fn.return_value = {"messageId": "msg1"}
        from integrations.crm_router import send_sms
        result = send_sms("c1", "Hello!")
        mock_fn.assert_called_once_with("c1", "Hello!")
        assert result is not None

    def test_sms_returns_none_for_hubspot(self, mock_hubspot_config):
        from integrations.crm_router import send_sms
        result = send_sms("c1", "Hello!")
        assert result is None

    def test_sms_returns_none_for_salesforce(self, mock_salesforce_config):
        from integrations.crm_router import send_sms
        result = send_sms("c1", "Hello!")
        assert result is None

    def test_sms_returns_none_for_agilecrm(self, mock_agilecrm_config):
        from integrations.crm_router import send_sms
        result = send_sms("c1", "Hello!")
        assert result is None


class TestCRMRouterNotes:
    """Test note routing (HubSpot and Salesforce only)."""

    @patch("integrations.hubspot_client.add_note")
    def test_note_routes_to_hubspot(self, mock_fn, mock_hubspot_config):
        mock_fn.return_value = {"id": "note1"}
        from integrations.crm_router import add_note
        result = add_note("c1", "Test note")
        mock_fn.assert_called_once_with("c1", "Test note")
        assert result is not None

    @patch("integrations.salesforce_client.add_note")
    def test_note_routes_to_salesforce(self, mock_fn, mock_salesforce_config):
        mock_fn.return_value = {"id": "note_sf"}
        from integrations.crm_router import add_note
        result = add_note("c1", "Test note")
        mock_fn.assert_called_once_with("c1", "Test note")
        assert result is not None

    @patch("integrations.agilecrm_client.add_note")
    def test_note_routes_to_agilecrm(self, mock_fn, mock_agilecrm_config):
        mock_fn.return_value = {"id": "note_agile"}
        from integrations.crm_router import add_note
        result = add_note("c1", "Test note")
        mock_fn.assert_called_once_with("c1", "Test note")
        assert result is not None


# ═════════════════════════════════════════════════════════════════════════════
# GHL CLIENT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestGHLClient:
    """Test GHL client functions with mocked HTTP."""

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_get_contact(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"id": "c1", "firstName": "Jane"})
        from integrations import ghl_client
        result = ghl_client.get_contact("c1")
        assert result["id"] == "c1"

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_create_contact(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(201, {"contact": {"id": "new1"}})
        from integrations import ghl_client
        result = ghl_client.create_contact({"name": "Jane Smith", "email": "jane@test.com"})
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_update_contact_field(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"id": "c1"})
        from integrations import ghl_client
        result = ghl_client.update_contact_field("c1", "monthly_bill", "350")
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_move_pipeline_stage(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"success": True})
        from integrations import ghl_client
        result = ghl_client.move_pipeline_stage("c1", "stage_hot")
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_send_sms(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"messageId": "msg1"})
        from integrations import ghl_client
        result = ghl_client.send_sms("c1", "Your solar quote is ready!")
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_add_contact_tag(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"tags": ["hot_lead"]})
        from integrations import ghl_client
        result = ghl_client.add_contact_tag("c1", "hot_lead")
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_create_task(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"id": "task1"})
        from integrations import ghl_client
        result = ghl_client.create_task("c1", "Follow up on quote", "2026-04-10")
        assert result is not None

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_get_pipeline_stages(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(200, {"stages": [
            {"id": "s1", "name": "New"},
            {"id": "s2", "name": "Qualified"},
        ]})
        from integrations import ghl_client
        result = ghl_client.get_pipeline_stages("pipe1")
        assert len(result) == 2

    @patch("integrations.ghl_client.api_helpers.request_with_retry")
    def test_returns_none_on_failure(self, mock_req, mock_ghl_config):
        mock_req.return_value = _mock_response(500, {"error": "Internal server error"})
        from integrations import ghl_client
        result = ghl_client.get_contact("c1")
        assert result is None

    def test_returns_none_without_api_key(self, mock_no_crm_config):
        from integrations import ghl_client
        result = ghl_client.get_contact("c1")
        assert result is None

    def test_is_configured(self, mock_ghl_config):
        from integrations import ghl_client
        assert ghl_client.is_configured() is True

    def test_is_not_configured(self, mock_no_crm_config, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "GHL_LOCATION_ID", "")
        from integrations import ghl_client
        assert ghl_client.is_configured() is False


# ═════════════════════════════════════════════════════════════════════════════
# HUBSPOT CLIENT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestHubSpotClient:
    """Test HubSpot client functions with mocked HTTP."""

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_get_contact(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {
            "id": "101", "properties": {"firstname": "Jane", "lastname": "Solar"}
        })
        from integrations import hubspot_client
        result = hubspot_client.get_contact("101")
        assert result["id"] == "101"

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_create_contact(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(201, {"id": "102"})
        from integrations import hubspot_client
        result = hubspot_client.create_contact({
            "name": "Jane Solar", "email": "jane@solar.com", "phone": "+61400000001"
        })
        assert result is not None
        # Verify name was split into firstname/lastname
        call_args = mock_req.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json", {})
        assert body["properties"]["firstname"] == "Jane"
        assert body["properties"]["lastname"] == "Solar"

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_update_contact_field(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {"id": "101"})
        from integrations import hubspot_client
        result = hubspot_client.update_contact_field("101", "phone", "+61400000002")
        assert result is not None

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_create_task(self, mock_req, mock_hubspot_config):
        # First call creates task, second associates it
        mock_req.return_value = _mock_response(200, {"id": "task1"})
        from integrations import hubspot_client
        result = hubspot_client.create_task("101", "Follow up", "2026-04-10")
        assert result is not None

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_add_note(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {"id": "note1"})
        from integrations import hubspot_client
        result = hubspot_client.add_note("101", "AI score: 8.5/10")
        assert result is not None

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_find_contact_by_phone(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {
            "results": [{"id": "101", "properties": {"firstname": "Jane"}}]
        })
        from integrations import hubspot_client
        result = hubspot_client.find_contact_by_phone("+61400000001")
        assert result is not None
        assert result["id"] == "101"

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_find_contact_by_phone_not_found(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {"results": []})
        from integrations import hubspot_client
        result = hubspot_client.find_contact_by_phone("+61499999999")
        assert result is None

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_get_pipeline_stages(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {"results": [
            {"id": "s1", "label": "New"},
            {"id": "s2", "label": "Qualified"},
        ]})
        from integrations import hubspot_client
        stages = hubspot_client.get_pipeline_stages("default")
        assert len(stages) == 2

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_get_contacts(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(200, {"results": [
            {"id": "101"}, {"id": "102"}
        ]})
        from integrations import hubspot_client
        contacts = hubspot_client.get_contacts(limit=10)
        assert len(contacts) == 2

    @patch("integrations.hubspot_client.api_helpers.request_with_retry")
    def test_returns_none_on_error(self, mock_req, mock_hubspot_config):
        mock_req.return_value = _mock_response(500, {"error": "server error"})
        from integrations import hubspot_client
        result = hubspot_client.get_contact("101")
        assert result is None

    def test_returns_none_without_api_key(self, mock_no_crm_config):
        from integrations import hubspot_client
        result = hubspot_client.get_contact("101")
        assert result is None

    def test_is_configured(self, mock_hubspot_config):
        from integrations import hubspot_client
        assert hubspot_client.is_configured() is True

    def test_is_not_configured(self, mock_no_crm_config):
        from integrations import hubspot_client
        assert hubspot_client.is_configured() is False


# ═════════════════════════════════════════════════════════════════════════════
# SALESFORCE CLIENT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestSalesforceClient:
    """Test Salesforce client functions with mocked HTTP."""

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_get_contact(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(200, {
            "Id": "003xx", "FirstName": "Jane", "LastName": "Solar"
        })
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.get_contact("003xx")
        assert result["Id"] == "003xx"

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_create_contact(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(201, {"id": "003new", "success": True})
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.create_contact({
            "name": "Jane Solar", "email": "jane@solar.com"
        })
        assert result is not None
        # Verify name was split into FirstName/LastName
        call_args = mock_req.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json", {})
        assert body["FirstName"] == "Jane"
        assert body["LastName"] == "Solar"

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_update_contact_field(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(204, None)
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.update_contact_field("003xx", "Phone", "+61400000002")
        assert result is not None

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_create_task(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(201, {"id": "00Txx", "success": True})
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.create_task("003xx", "Follow up on quote", "2026-04-10")
        assert result is not None

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_get_pipeline_stages(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(200, {
            "fields": [
                {"name": "StageName", "picklistValues": [
                    {"value": "Prospecting", "label": "Prospecting", "active": True},
                    {"value": "Qualification", "label": "Qualification", "active": True},
                ]}
            ]
        })
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        stages = salesforce_client.get_pipeline_stages()
        assert len(stages) == 2
        assert stages[0]["value"] == "Prospecting"

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_find_contact_by_phone(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(200, {
            "records": [{"Id": "003xx", "FirstName": "Jane", "Phone": "+61400000001"}]
        })
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.find_contact_by_phone("+61400000001")
        assert result is not None
        assert result["Id"] == "003xx"

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_find_contact_by_phone_not_found(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(200, {"records": []})
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.find_contact_by_phone("+61499999999")
        assert result is None

    @patch("integrations.salesforce_client._ensure_auth", return_value=True)
    @patch("integrations.salesforce_client.api_helpers.request_with_retry")
    def test_returns_none_on_error(self, mock_req, mock_auth, mock_salesforce_config):
        mock_req.return_value = _mock_response(500, {"error": "server error"})
        from integrations import salesforce_client
        salesforce_client._instance_url = "https://test.salesforce.com"
        result = salesforce_client.get_contact("003xx")
        assert result is None

    def test_returns_none_without_auth(self, mock_no_crm_config):
        from integrations import salesforce_client
        # Reset auth state
        salesforce_client._access_token = ""
        salesforce_client._instance_url = ""
        salesforce_client._token_expiry = 0
        result = salesforce_client.get_contact("003xx")
        assert result is None

    def test_is_configured(self, mock_salesforce_config):
        from integrations import salesforce_client
        assert salesforce_client.is_configured() is True

    def test_is_not_configured(self, mock_no_crm_config, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "SALESFORCE_CLIENT_ID", "")
        from integrations import salesforce_client
        assert salesforce_client.is_configured() is False


class TestSalesforceSOQLInjection:
    """Test SOQL injection prevention."""

    def test_safe_escapes_quotes(self):
        from integrations.salesforce_client import _safe
        assert _safe("O'Brien") == "O\\'Brien"

    def test_safe_handles_normal_input(self):
        from integrations.salesforce_client import _safe
        assert _safe("+61400000001") == "+61400000001"

    def test_safe_handles_empty_string(self):
        from integrations.salesforce_client import _safe
        assert _safe("") == ""


# ═════════════════════════════════════════════════════════════════════════════
# AGILE CRM CLIENT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAgileCRMClient:
    """Test Agile CRM client functions with mocked HTTP."""

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_get_contact(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, {
            "id": 5001,
            "properties": [{"type": "SYSTEM", "name": "first_name", "value": "Jane"}],
        })
        from integrations import agilecrm_client
        result = agilecrm_client.get_contact("5001")
        assert result["id"] == 5001

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_create_contact(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(201, {"id": 5002})
        from integrations import agilecrm_client
        result = agilecrm_client.create_contact({
            "name": "Jane Solar", "email": "jane@solar.com", "phone": "+61400000001"
        })
        assert result is not None
        call_args = mock_req.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json", {})
        prop_names = [p["name"] for p in body["properties"]]
        assert "first_name" in prop_names
        assert "last_name" in prop_names
        assert "email" in prop_names

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_add_contact_tag(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, {"id": 5001, "tags": ["hot_lead"]})
        from integrations import agilecrm_client
        result = agilecrm_client.add_contact_tag("5001", "hot_lead")
        assert result is not None

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_create_task(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, {"id": "task1"})
        from integrations import agilecrm_client
        result = agilecrm_client.create_task("5001", "Follow up on quote", "2026-04-10")
        assert result is not None

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_add_note(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, {"id": "note1"})
        from integrations import agilecrm_client
        result = agilecrm_client.add_note("5001", "AI score: 8.5/10")
        assert result is not None

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_find_contact_by_phone(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, {
            "id": 5001,
            "properties": [{"name": "first_name", "value": "Jane"}],
        })
        from integrations import agilecrm_client
        result = agilecrm_client.find_contact_by_phone("+61400000001")
        assert result is not None
        assert result["id"] == 5001

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_get_pipeline_stages(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, [
            {"id": "p1", "milestones": "New,Qualified,Won,Lost"},
        ])
        from integrations import agilecrm_client
        stages = agilecrm_client.get_pipeline_stages()
        assert len(stages) == 4
        assert stages[0]["name"] == "New"

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_get_contacts(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(200, [
            {"id": 5001}, {"id": 5002}
        ])
        from integrations import agilecrm_client
        contacts = agilecrm_client.get_contacts(limit=10)
        assert len(contacts) == 2

    @patch("integrations.agilecrm_client.api_helpers.request_with_retry")
    def test_returns_none_on_error(self, mock_req, mock_agilecrm_config):
        mock_req.return_value = _mock_response(500, {"error": "server error"})
        from integrations import agilecrm_client
        result = agilecrm_client.get_contact("5001")
        assert result is None

    def test_returns_none_without_api_key(self, mock_no_crm_config, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "AGILECRM_DOMAIN", "")
        monkeypatch.setattr(cfg, "AGILECRM_EMAIL", "")
        monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "")
        from integrations import agilecrm_client
        result = agilecrm_client.get_contact("5001")
        assert result is None

    def test_is_configured(self, mock_agilecrm_config):
        from integrations import agilecrm_client
        assert agilecrm_client.is_configured() is True

    def test_is_not_configured(self, mock_no_crm_config, monkeypatch):
        import config as cfg
        monkeypatch.setattr(cfg, "AGILECRM_DOMAIN", "")
        monkeypatch.setattr(cfg, "AGILECRM_EMAIL", "")
        monkeypatch.setattr(cfg, "AGILECRM_API_KEY", "")
        from integrations import agilecrm_client
        assert agilecrm_client.is_configured() is False


# ═════════════════════════════════════════════════════════════════════════════
# FIELD MAPPER TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestFieldMapperToCanonical:
    """Test converting CRM data to canonical format."""

    def test_ghl_to_canonical(self):
        from integrations.crm_field_mapper import to_canonical
        ghl_data = {
            "id": "c1",
            "firstName": "Jane",
            "lastName": "Solar",
            "email": "jane@solar.com",
            "phone": "+61400000001",
            "city": "Perth",
            "state": "WA",
        }
        result = to_canonical("ghl", ghl_data)
        assert result["id"] == "c1"
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Solar"
        assert result["email"] == "jane@solar.com"
        assert result["city"] == "Perth"

    def test_ghl_custom_fields(self):
        from integrations.crm_field_mapper import to_canonical
        ghl_data = {
            "id": "c1",
            "firstName": "Jane",
            "customField": {
                "homeowner_status": "Yes",
                "monthly_bill": "350",
            },
        }
        result = to_canonical("ghl", ghl_data)
        assert result["homeowner_status"] == "Yes"
        assert result["monthly_bill"] == "350"

    def test_hubspot_to_canonical(self):
        from integrations.crm_field_mapper import to_canonical
        hs_data = {
            "id": "101",
            "properties": {
                "firstname": "Jane",
                "lastname": "Solar",
                "email": "jane@solar.com",
                "phone": "+61400000001",
                "city": "Perth",
                "state": "WA",
            },
        }
        result = to_canonical("hubspot", hs_data)
        assert result["id"] == "101"
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Solar"
        assert result["email"] == "jane@solar.com"

    def test_salesforce_to_canonical(self):
        from integrations.crm_field_mapper import to_canonical
        sf_data = {
            "Id": "003xx",
            "attributes": {"type": "Contact"},
            "FirstName": "Jane",
            "LastName": "Solar",
            "Email": "jane@solar.com",
            "Phone": "+61400000001",
            "MailingCity": "Perth",
            "MailingState": "WA",
        }
        result = to_canonical("salesforce", sf_data)
        assert result["id"] == "003xx"
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Solar"
        assert result["city"] == "Perth"

    def test_agilecrm_to_canonical(self):
        from integrations.crm_field_mapper import to_canonical
        agile_data = {
            "id": 5001,
            "properties": [
                {"type": "SYSTEM", "name": "first_name", "value": "Jane"},
                {"type": "SYSTEM", "name": "last_name", "value": "Solar"},
                {"type": "SYSTEM", "name": "email", "subtype": "work", "value": "jane@solar.com"},
                {"type": "SYSTEM", "name": "phone", "subtype": "work", "value": "+61400000001"},
                {"type": "CUSTOM", "name": "homeowner_status", "value": "Yes"},
            ],
            "tags": ["hot_lead", "solar"],
        }
        result = to_canonical("agilecrm", agile_data)
        assert result["id"] == 5001
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Solar"
        assert result["email"] == "jane@solar.com"
        assert result["homeowner_status"] == "Yes"
        assert "hot_lead" in result["tags"]

    def test_unknown_crm_returns_as_is(self):
        from integrations.crm_field_mapper import to_canonical
        data = {"foo": "bar"}
        result = to_canonical("zoho", data)
        assert result == data


class TestFieldMapperFromCanonical:
    """Test converting canonical data to CRM format."""

    def test_canonical_to_ghl(self):
        from integrations.crm_field_mapper import from_canonical
        canonical = {
            "first_name": "Jane",
            "last_name": "Solar",
            "email": "jane@solar.com",
            "phone": "+61400000001",
            "homeowner_status": "Yes",
        }
        result = from_canonical("ghl", canonical)
        assert result["firstName"] == "Jane"
        assert result["lastName"] == "Solar"
        assert result["email"] == "jane@solar.com"
        # Custom fields should be nested under customField
        assert result["customField"]["homeowner_status"] == "Yes"

    def test_canonical_to_hubspot(self):
        from integrations.crm_field_mapper import from_canonical
        canonical = {
            "first_name": "Jane",
            "last_name": "Solar",
            "email": "jane@solar.com",
        }
        result = from_canonical("hubspot", canonical)
        assert result["firstname"] == "Jane"
        assert result["lastname"] == "Solar"
        assert result["email"] == "jane@solar.com"

    def test_canonical_to_salesforce(self):
        from integrations.crm_field_mapper import from_canonical
        canonical = {
            "first_name": "Jane",
            "last_name": "Solar",
            "email": "jane@solar.com",
            "city": "Perth",
        }
        result = from_canonical("salesforce", canonical)
        assert result["FirstName"] == "Jane"
        assert result["LastName"] == "Solar"
        assert result["Email"] == "jane@solar.com"
        assert result["MailingCity"] == "Perth"

    def test_canonical_to_agilecrm(self):
        from integrations.crm_field_mapper import from_canonical
        canonical = {
            "first_name": "Jane",
            "last_name": "Solar",
            "email": "jane@solar.com",
            "homeowner_status": "Yes",
        }
        result = from_canonical("agilecrm", canonical)
        assert "properties" in result
        prop_names = {p["name"]: p["value"] for p in result["properties"]}
        assert prop_names["first_name"] == "Jane"
        assert prop_names["last_name"] == "Solar"
        assert prop_names["email"] == "jane@solar.com"
        assert prop_names["homeowner_status"] == "Yes"

    def test_unknown_crm_returns_as_is(self):
        from integrations.crm_field_mapper import from_canonical
        data = {"first_name": "Jane"}
        result = from_canonical("zoho", data)
        assert result == data


class TestFieldMapperLookup:
    """Test individual field lookup functions."""

    def test_get_crm_field(self):
        from integrations.crm_field_mapper import get_crm_field
        assert get_crm_field("ghl", "first_name") == "firstName"
        assert get_crm_field("hubspot", "first_name") == "firstname"
        assert get_crm_field("salesforce", "first_name") == "FirstName"

    def test_get_crm_field_unknown(self):
        from integrations.crm_field_mapper import get_crm_field
        assert get_crm_field("ghl", "nonexistent_field") is None
        assert get_crm_field("zoho", "first_name") is None

    def test_get_canonical_field(self):
        from integrations.crm_field_mapper import get_canonical_field
        assert get_canonical_field("ghl", "firstName") == "first_name"
        assert get_canonical_field("hubspot", "firstname") == "first_name"
        assert get_canonical_field("salesforce", "FirstName") == "first_name"

    def test_supported_crms(self):
        from integrations.crm_field_mapper import supported_crms
        crms = supported_crms()
        assert "ghl" in crms
        assert "hubspot" in crms
        assert "salesforce" in crms
        assert "agilecrm" in crms

    def test_canonical_fields(self):
        from integrations.crm_field_mapper import canonical_fields
        fields = canonical_fields()
        assert "first_name" in fields
        assert "email" in fields
        assert "phone" in fields
        assert "homeowner_status" in fields


class TestFieldMapperRoundTrip:
    """Test that data survives a canonical round-trip."""

    def test_ghl_round_trip(self):
        from integrations.crm_field_mapper import to_canonical, from_canonical
        original = {
            "id": "c1",
            "firstName": "Jane",
            "lastName": "Solar",
            "email": "jane@solar.com",
            "phone": "+61400000001",
            "city": "Perth",
            "state": "WA",
        }
        canonical = to_canonical("ghl", original)
        back = from_canonical("ghl", canonical)
        assert back["firstName"] == "Jane"
        assert back["lastName"] == "Solar"
        assert back["email"] == "jane@solar.com"

    def test_cross_crm_conversion(self):
        """Convert GHL data to canonical, then output as Salesforce format."""
        from integrations.crm_field_mapper import to_canonical, from_canonical
        ghl_data = {
            "id": "c1",
            "firstName": "Jane",
            "lastName": "Solar",
            "email": "jane@solar.com",
            "phone": "+61400000001",
        }
        canonical = to_canonical("ghl", ghl_data)
        sf_data = from_canonical("salesforce", canonical)
        assert sf_data["FirstName"] == "Jane"
        assert sf_data["LastName"] == "Solar"
        assert sf_data["Email"] == "jane@solar.com"
        assert sf_data["Phone"] == "+61400000001"


# ═════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_contact_data(self):
        from integrations.crm_field_mapper import to_canonical, from_canonical
        assert to_canonical("ghl", {}) == {}
        assert from_canonical("ghl", {}) == {}

    def test_single_name_split(self):
        """Single-word name should work for both HubSpot and Salesforce."""
        from integrations.hubspot_client import _map_contact_input
        result = _map_contact_input({"name": "Madonna"})
        assert result["firstname"] == "Madonna"
        assert result["lastname"] == ""

    def test_salesforce_single_name(self):
        from integrations.salesforce_client import _map_contact_input
        result = _map_contact_input({"name": "Cher"})
        assert result["FirstName"] == "Cher"
        # Salesforce requires LastName
        assert result["LastName"] == "Cher"

    def test_salesforce_missing_name(self):
        from integrations.salesforce_client import _map_contact_input
        result = _map_contact_input({"email": "test@test.com"})
        assert result["LastName"] == "Unknown"

    def test_hubspot_passthrough_properties(self):
        from integrations.hubspot_client import _map_contact_input
        result = _map_contact_input({
            "name": "Jane Solar",
            "lifecyclestage": "lead",
            "custom_prop": "value",
        })
        assert result["firstname"] == "Jane"
        assert result["lifecyclestage"] == "lead"
        assert result["custom_prop"] == "value"

    def test_agilecrm_name_split(self):
        """Name should be split into first_name/last_name for Agile CRM."""
        from integrations.agilecrm_client import _map_contact_input
        result = _map_contact_input({"name": "Jane Solar"})
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Solar"

    def test_agilecrm_single_name(self):
        from integrations.agilecrm_client import _map_contact_input
        result = _map_contact_input({"name": "Madonna"})
        assert result["first_name"] == "Madonna"
        assert result["last_name"] == ""

    def test_ghl_class_client(self, mock_ghl_config):
        from integrations.ghl_client import GHLClient
        client = GHLClient(api_key="test-key", location_id="loc_123")
        assert client.is_configured() is True

    def test_ghl_class_not_configured(self, mock_no_crm_config):
        from integrations.ghl_client import GHLClient
        client = GHLClient(api_key="", location_id="")
        assert client.is_configured() is False
