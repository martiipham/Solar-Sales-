"""CRM Integration API — endpoints for the CRM setup wizard.

Provides provider listing, connection testing, field mapping retrieval,
and configuration persistence for the frontend CRM Integration Wizard.

Blueprint: crm_integration_bp
  GET  /api/crm/providers              — list available CRM providers + credential fields
  GET  /api/crm/field-mapping/<provider> — canonical → CRM field mapping table
  POST /api/crm/test-connection        — test CRM credentials by fetching contacts
  POST /api/crm/save-config            — persist CRM credentials + field mapping overrides
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from api.auth import require_auth
from memory.database import fetch_one, get_conn

logger = logging.getLogger(__name__)

crm_integration_bp = Blueprint("crm_integration", __name__)

# Provider metadata: credential fields required per CRM
PROVIDERS = {
    "ghl": {
        "id": "ghl",
        "name": "GoHighLevel",
        "description": "Full-featured CRM with built-in SMS, pipeline management, and webhooks.",
        "credentials": [
            {"key": "GHL_API_KEY", "label": "API Key", "type": "password", "required": True},
            {"key": "GHL_LOCATION_ID", "label": "Location ID", "type": "text", "required": True},
        ],
    },
    "hubspot": {
        "id": "hubspot",
        "name": "HubSpot",
        "description": "Popular CRM with marketing automation, contact management, and deal tracking.",
        "credentials": [
            {"key": "HUBSPOT_API_KEY", "label": "Private App Token", "type": "password", "required": True},
        ],
    },
    "salesforce": {
        "id": "salesforce",
        "name": "Salesforce",
        "description": "Enterprise CRM with extensive customization, reporting, and integrations.",
        "credentials": [
            {"key": "SALESFORCE_USERNAME", "label": "Username", "type": "text", "required": True},
            {"key": "SALESFORCE_PASSWORD", "label": "Password", "type": "password", "required": True},
            {"key": "SALESFORCE_SECURITY_TOKEN", "label": "Security Token", "type": "password", "required": True},
            {"key": "SALESFORCE_CLIENT_ID", "label": "Client ID", "type": "text", "required": False},
            {"key": "SALESFORCE_CLIENT_SECRET", "label": "Client Secret", "type": "password", "required": False},
        ],
    },
    "custom": {
        "id": "custom",
        "name": "Custom CRM",
        "description": "Connect any CRM via REST API with custom field mapping.",
        "credentials": [
            {"key": "CUSTOM_CRM_BASE_URL", "label": "Base URL", "type": "text", "required": True},
            {"key": "CUSTOM_CRM_API_KEY", "label": "API Key", "type": "password", "required": True},
            {"key": "CUSTOM_CRM_AUTH_HEADER", "label": "Auth Header Name", "type": "text", "required": False},
        ],
    },
}


@crm_integration_bp.route("/api/crm/providers", methods=["GET"])
@require_auth()
def list_providers():
    """Return available CRM providers with credential requirements and current status."""
    try:
        from integrations.crm_router import active_crm, all_configured_crms
        current = active_crm()
        configured = all_configured_crms()

        providers = []
        for pid, meta in PROVIDERS.items():
            providers.append({
                **meta,
                "active": pid == current,
                "configured": pid in configured,
            })
        return jsonify({"providers": providers, "active": current}), 200
    except Exception as e:
        logger.error(f"[CRM_INTEGRATION] list_providers error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@crm_integration_bp.route("/api/crm/field-mapping/<provider>", methods=["GET"])
@require_auth()
def get_field_mapping(provider):
    """Return the canonical-to-CRM field mapping for a given provider."""
    try:
        from integrations.crm_field_mapper import _FIELD_MAP, canonical_fields

        if provider not in _FIELD_MAP and provider != "custom":
            return jsonify({"error": f"Unknown provider: {provider}"}), 400

        fields = canonical_fields()

        if provider == "custom":
            mapping = [{"canonical": f, "crm_field": f, "editable": True} for f in fields]
        else:
            crm_map = _FIELD_MAP[provider]
            mapping = []
            for f in fields:
                mapping.append({
                    "canonical": f,
                    "crm_field": crm_map.get(f, ""),
                    "editable": True,
                })

        # Check for saved custom overrides
        row = fetch_one(
            "SELECT value FROM app_settings WHERE key = ?",
            (f"crm.field_mapping.{provider}",),
        )
        if row:
            overrides = json.loads(row["value"])
            for item in mapping:
                if item["canonical"] in overrides:
                    item["crm_field"] = overrides[item["canonical"]]
                    item["custom"] = True

        return jsonify({"provider": provider, "mapping": mapping}), 200
    except Exception as e:
        logger.error(f"[CRM_INTEGRATION] get_field_mapping error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@crm_integration_bp.route("/api/crm/test-connection", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def test_connection():
    """Test CRM connection with provided credentials.

    Body:
        provider: str — 'ghl' | 'hubspot' | 'salesforce' | 'custom'
        credentials: dict — key/value pairs matching the provider's credential fields
    """
    data = request.get_json(force=True) or {}
    provider = str(data.get("provider", "")).strip()
    credentials = data.get("credentials", {})

    if provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}"}), 400

    required = [c["key"] for c in PROVIDERS[provider]["credentials"] if c["required"]]
    missing = [k for k in required if not credentials.get(k)]
    if missing:
        return jsonify({"error": f"Missing required credentials: {', '.join(missing)}"}), 400

    try:
        result = _test_provider_connection(provider, credentials)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"[CRM_INTEGRATION] test_connection error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "provider": provider,
        }), 200


@crm_integration_bp.route("/api/crm/save-config", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def save_config():
    """Save CRM configuration: credentials + field mapping overrides.

    Body:
        provider: str
        credentials: dict
        field_mapping: dict — { canonical_field: crm_field_name } overrides
    """
    data = request.get_json(force=True) or {}
    provider = str(data.get("provider", "")).strip()
    credentials = data.get("credentials", {})
    field_mapping = data.get("field_mapping", {})

    if provider not in PROVIDERS:
        return jsonify({"error": f"Unknown provider: {provider}"}), 400

    try:
        now = datetime.utcnow().isoformat()
        with get_conn() as conn:
            # Save credentials as individual settings
            for key, value in credentials.items():
                if not value:
                    continue
                conn.execute(
                    "INSERT INTO app_settings (key, value, category, description, updated_at) "
                    "VALUES (?, ?, 'crm_credentials', ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                    (f"crm.cred.{key}", str(value), f"{provider} credential: {key}", now),
                )

            # Save field mapping overrides
            if field_mapping:
                conn.execute(
                    "INSERT INTO app_settings (key, value, category, description, updated_at) "
                    "VALUES (?, ?, 'crm_mapping', ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                    (
                        f"crm.field_mapping.{provider}",
                        json.dumps(field_mapping),
                        f"Custom field mapping overrides for {provider}",
                        now,
                    ),
                )

            # Set active CRM
            conn.execute(
                "INSERT INTO app_settings (key, value, category, description, updated_at) "
                "VALUES (?, ?, 'crm', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                ("crm.active", provider, "Active CRM provider", now),
            )

        logger.info(f"[CRM_INTEGRATION] Saved config for provider={provider}")
        return jsonify({"ok": True, "provider": provider}), 200
    except Exception as e:
        logger.error(f"[CRM_INTEGRATION] save_config error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ── Internal helpers ─────────────────────────────────────────────────────────

def _test_provider_connection(provider: str, credentials: dict) -> dict:
    """Test connectivity to a CRM provider using the supplied credentials.

    Returns a result dict with success status, contact count, and details.
    """
    if provider == "ghl":
        return _test_ghl(credentials)
    if provider == "hubspot":
        return _test_hubspot(credentials)
    if provider == "salesforce":
        return _test_salesforce(credentials)
    if provider == "custom":
        return _test_custom(credentials)
    return {"success": False, "error": f"No test handler for {provider}"}


def _test_ghl(creds: dict) -> dict:
    """Test GoHighLevel connection by fetching contacts."""
    import requests

    api_key = creds.get("GHL_API_KEY", "")
    location_id = creds.get("GHL_LOCATION_ID", "")
    url = f"https://services.leadconnectorhq.com/contacts/?locationId={location_id}&limit=5"
    headers = {"Authorization": f"Bearer {api_key}", "Version": "2021-07-28"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            contacts = data.get("contacts", [])
            return {
                "success": True,
                "provider": "ghl",
                "message": f"Connected successfully. Found {len(contacts)} recent contact(s).",
                "contacts_found": len(contacts),
                "sample_fields": list(contacts[0].keys()) if contacts else [],
            }
        return {
            "success": False,
            "provider": "ghl",
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.RequestException as e:
        return {"success": False, "provider": "ghl", "error": str(e)}


def _test_hubspot(creds: dict) -> dict:
    """Test HubSpot connection by fetching contacts."""
    import requests

    token = creds.get("HUBSPOT_API_KEY", "")
    url = "https://api.hubapi.com/crm/v3/objects/contacts?limit=5"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            return {
                "success": True,
                "provider": "hubspot",
                "message": f"Connected successfully. Found {data.get('total', len(results))} contact(s).",
                "contacts_found": data.get("total", len(results)),
                "sample_fields": list(results[0].get("properties", {}).keys()) if results else [],
            }
        return {
            "success": False,
            "provider": "hubspot",
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.RequestException as e:
        return {"success": False, "provider": "hubspot", "error": str(e)}


def _test_salesforce(creds: dict) -> dict:
    """Test Salesforce connection by authenticating and querying contacts."""
    import requests

    try:
        # OAuth2 password flow
        auth_url = "https://login.salesforce.com/services/oauth2/token"
        auth_data = {
            "grant_type": "password",
            "client_id": creds.get("SALESFORCE_CLIENT_ID", ""),
            "client_secret": creds.get("SALESFORCE_CLIENT_SECRET", ""),
            "username": creds.get("SALESFORCE_USERNAME", ""),
            "password": creds.get("SALESFORCE_PASSWORD", "") + creds.get("SALESFORCE_SECURITY_TOKEN", ""),
        }
        auth_resp = requests.post(auth_url, data=auth_data, timeout=10)
        if auth_resp.status_code != 200:
            return {
                "success": False,
                "provider": "salesforce",
                "error": f"Auth failed: {auth_resp.text[:200]}",
            }

        auth_json = auth_resp.json()
        instance_url = auth_json["instance_url"]
        access_token = auth_json["access_token"]

        # Query contacts
        query_url = f"{instance_url}/services/data/v58.0/query?q=SELECT+Id,FirstName,LastName,Email+FROM+Contact+LIMIT+5"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(query_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("records", [])
            return {
                "success": True,
                "provider": "salesforce",
                "message": f"Connected successfully. Found {data.get('totalSize', len(records))} contact(s).",
                "contacts_found": data.get("totalSize", len(records)),
                "sample_fields": list(records[0].keys()) if records else [],
            }
        return {
            "success": False,
            "provider": "salesforce",
            "error": f"Query failed: HTTP {resp.status_code}",
        }
    except requests.RequestException as e:
        return {"success": False, "provider": "salesforce", "error": str(e)}


def _test_custom(creds: dict) -> dict:
    """Test custom CRM connection by hitting the base URL."""
    import requests

    base_url = creds.get("CUSTOM_CRM_BASE_URL", "").rstrip("/")
    api_key = creds.get("CUSTOM_CRM_API_KEY", "")
    auth_header = creds.get("CUSTOM_CRM_AUTH_HEADER", "Authorization")

    try:
        headers = {auth_header: f"Bearer {api_key}"}
        resp = requests.get(f"{base_url}/contacts?limit=5", headers=headers, timeout=10)
        if resp.status_code == 200:
            return {
                "success": True,
                "provider": "custom",
                "message": f"Connected successfully (HTTP 200).",
                "contacts_found": 0,
                "sample_fields": [],
            }
        return {
            "success": False,
            "provider": "custom",
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.RequestException as e:
        return {"success": False, "provider": "custom", "error": str(e)}
