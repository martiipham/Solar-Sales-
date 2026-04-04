"""Retell AI API Client — Agent and phone number management.

Handles creating and configuring Retell AI agents for each solar company client.
Each client gets their own Retell agent pointed at our custom LLM endpoint.

Also supports ElevenLabs voice configuration for premium voice quality.

API Reference: https://docs.retellai.com
"""

import logging

import requests

import api_helpers
import config

logger = logging.getLogger(__name__)

RETELL_BASE = "https://api.retellai.com"


def _retell_headers() -> dict:
    """Return authenticated headers for Retell API."""
    return {
        "Authorization": f"Bearer {config.RETELL_API_KEY}",
        "Content-Type":  "application/json",
    }


def _retell_request(method: str, endpoint: str, data: dict = None) -> dict | None:
    """Make an authenticated request to the Retell API.

    Args:
        method: HTTP method
        endpoint: API endpoint path
        data: Request body

    Returns:
        Response JSON dict or None on failure
    """
    if not config.RETELL_API_KEY:
        logger.warning("[RETELL] No API key configured")
        return None
    try:
        url  = f"{RETELL_BASE}{endpoint}"
        resp = api_helpers.request_with_retry(method, url, headers=_retell_headers(), json=data, timeout=20)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.error(f"[RETELL] {method} {endpoint} → {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[RETELL] Request failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# AGENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_agent(
    agent_name: str,
    llm_webhook_url: str,
    voice_id: str = None,
    language: str = "en-AU",
    ambient_sound: str = "office",
) -> dict | None:
    """Create a Retell AI agent with our custom LLM endpoint.

    Args:
        agent_name: Display name for the agent
        llm_webhook_url: URL of our /voice/response endpoint
        voice_id: ElevenLabs or Retell voice ID (optional)
        language: Language code (en-AU for Australian English)
        ambient_sound: Background sound (office, coffee-shop, etc.)

    Returns:
        Created agent dict or None
    """
    payload = {
        "agent_name": agent_name,
        "llm_websocket_url": llm_webhook_url,  # Retell calls this endpoint
        "voice_id":   voice_id or config.get("RETELL_DEFAULT_VOICE_ID", "11labs-Adrian"),
        "language":   language,
        "ambient_sound": ambient_sound,
        "response_engine": {
            "type": "retell-llm",
            "llm_id": None,  # Not using Retell's built-in LLM — custom endpoint
        },
        "enable_backchannel": True,      # AI says "mmm", "yes" while user speaks
        "backchannel_frequency": 0.8,
        "reminder_trigger_ms": 15000,    # Prompt if silent for 15s
        "reminder_max_count": 2,
        "normalize_for_speech": True,    # Convert numbers/dates to speakable form
        "end_call_after_silence_ms": 30000,
        "post_call_analysis_data": [
            {"name": "outcome", "type": "string", "description": "Call outcome"},
            {"name": "lead_score", "type": "number", "description": "Lead score 1-10"},
        ],
    }

    result = _retell_request("POST", "/v2/create-agent", payload)
    if result:
        agent_id = result.get("agent_id")
        print(f"[RETELL] Agent created: {agent_name} (id={agent_id})")
    return result


def update_agent(agent_id: str, updates: dict) -> dict | None:
    """Update an existing Retell agent.

    Args:
        agent_id: Retell agent ID
        updates: Fields to update

    Returns:
        Updated agent dict or None
    """
    result = _retell_request("PATCH", f"/v2/update-agent/{agent_id}", updates)
    if result:
        print(f"[RETELL] Agent updated: {agent_id}")
    return result


def get_agent(agent_id: str) -> dict | None:
    """Fetch a Retell agent by ID.

    Args:
        agent_id: Retell agent ID

    Returns:
        Agent dict or None
    """
    return _retell_request("GET", f"/v2/get-agent/{agent_id}")


def list_agents() -> list:
    """List all Retell agents in the account.

    Returns:
        List of agent dicts
    """
    result = _retell_request("GET", "/v2/list-agents")
    return result if isinstance(result, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# PHONE NUMBER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def import_phone_number(phone_number: str, agent_id: str, area_code: str = "61") -> dict | None:
    """Import an existing phone number and link it to an agent.

    Args:
        phone_number: Phone number in E.164 format (+61412345678)
        agent_id: Retell agent ID to handle calls on this number
        area_code: Country code

    Returns:
        Phone number record or None
    """
    result = _retell_request("POST", "/v2/import-phone-number", {
        "phone_number":  phone_number,
        "inbound_agent_id": agent_id,
        "area_code":     area_code,
        "nickname":      f"Solar Agent — {phone_number}",
    })
    if result:
        print(f"[RETELL] Phone imported: {phone_number} → agent {agent_id}")
    return result


def update_phone_agent(phone_number: str, agent_id: str) -> dict | None:
    """Update which agent handles inbound calls on a phone number.

    Args:
        phone_number: Phone number in E.164 format
        agent_id: New agent ID

    Returns:
        Updated record or None
    """
    result = _retell_request("PATCH", f"/v2/update-phone-number/{phone_number}", {
        "inbound_agent_id": agent_id,
    })
    if result:
        print(f"[RETELL] Phone {phone_number} now uses agent {agent_id}")
    return result


def list_phone_numbers() -> list:
    """List all imported phone numbers.

    Returns:
        List of phone number records
    """
    result = _retell_request("GET", "/v2/list-phone-numbers")
    return result if isinstance(result, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# OUTBOUND CALLS
# ─────────────────────────────────────────────────────────────────────────────

def create_outbound_call(
    from_number: str,
    to_number: str,
    agent_id: str,
    metadata: dict = None,
) -> dict | None:
    """Initiate an outbound call via Retell.

    Use this for automated callbacks to hot leads.

    Args:
        from_number: Retell-managed phone number in E.164
        to_number: Customer phone number in E.164
        agent_id: Retell agent ID to use for this call
        metadata: Extra context to pass to the agent (contact_id, client_id, etc.)

    Returns:
        Call record dict or None
    """
    payload = {
        "from_number": from_number,
        "to_number":   to_number,
        "agent_id":    agent_id,
        "metadata":    metadata or {},
        "retell_llm_dynamic_variables": metadata or {},
    }
    result = _retell_request("POST", "/v2/create-phone-call", payload)
    if result:
        call_id = result.get("call_id")
        print(f"[RETELL] Outbound call initiated: {from_number} → {to_number} (call={call_id})")
    return result


def get_call(call_id: str) -> dict | None:
    """Fetch call details including transcript and recording.

    Args:
        call_id: Retell call ID

    Returns:
        Call record dict or None
    """
    return _retell_request("GET", f"/v2/get-call/{call_id}")


def list_calls(agent_id: str = None, limit: int = 50) -> list:
    """List recent calls, optionally filtered by agent.

    Args:
        agent_id: Optional agent ID filter
        limit: Max number of calls to return

    Returns:
        List of call records
    """
    params = f"?limit={limit}"
    if agent_id:
        params += f"&agent_id={agent_id}"
    result = _retell_request("GET", f"/v2/list-calls{params}")
    return result if isinstance(result, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# SETUP HELPER — Create a new client's complete voice AI stack
# ─────────────────────────────────────────────────────────────────────────────

def setup_client_voice_agent(
    client_id: str,
    company_name: str,
    phone_number: str,
    webhook_base_url: str,
    elevenlabs_voice_id: str = None,
) -> dict:
    """One-command setup: create agent, link phone, update company profile.

    Args:
        client_id: Company client ID
        company_name: Display name
        phone_number: GHL/Twilio phone number in E.164
        webhook_base_url: Your server's public URL (e.g. https://yourapp.ngrok.io)
        elevenlabs_voice_id: Optional ElevenLabs custom voice ID

    Returns:
        Setup result with agent_id and phone status
    """
    llm_url  = f"{webhook_base_url}/voice/response"
    voice_id = elevenlabs_voice_id or config.get("RETELL_DEFAULT_VOICE_ID", "11labs-Adrian")

    agent = create_agent(
        agent_name=f"{company_name} — AI Receptionist",
        llm_webhook_url=llm_url,
        voice_id=voice_id,
        language="en-AU",
    )

    if not agent:
        return {"success": False, "error": "Agent creation failed"}

    agent_id = agent.get("agent_id")

    # Link phone number
    phone_result = import_phone_number(phone_number, agent_id)

    # Save agent_id to company profile
    try:
        from knowledge.company_kb import upsert_company
        upsert_company(client_id, {
            "retell_agent_id":      agent_id,
            "elevenlabs_voice_id":  elevenlabs_voice_id,
        })
    except Exception as e:
        logger.error(f"[RETELL SETUP] Profile update failed: {e}")

    print(f"[RETELL SETUP] Complete: {company_name} | agent={agent_id} | phone={phone_number}")
    return {
        "success":    True,
        "agent_id":   agent_id,
        "phone":      phone_number,
        "llm_url":    llm_url,
        "phone_linked": phone_result is not None,
    }


def is_configured() -> bool:
    """Check if Retell API key is configured.

    Returns:
        True if configured
    """
    return bool(config.RETELL_API_KEY)
