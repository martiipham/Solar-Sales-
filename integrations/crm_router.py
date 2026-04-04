"""CRM Router — Abstraction layer for multi-CRM support.

Routes all CRM operations to whichever platform is configured.
Priority order: GoHighLevel → HubSpot → Salesforce → Agile CRM

Agents and workers call crm_router functions directly —
they never need to know which CRM is live.

Usage:
    from integrations.crm_router import crm
    crm.get_contact("abc123")
    crm.create_contact({"name": "Jane Smith", "email": "jane@example.com"})
    crm.move_pipeline_stage("abc123", "qualified")
"""

import logging
from typing import Any
import config

logger = logging.getLogger(__name__)

# Lazy-load clients to avoid import errors when optional deps are missing
_ghl = None
_hubspot = None
_salesforce = None
_agilecrm = None


def _get_ghl():
    """Lazy-load GHL client."""
    global _ghl
    if _ghl is None:
        from integrations import ghl_client
        _ghl = ghl_client
    return _ghl


def _get_hubspot():
    """Lazy-load HubSpot client."""
    global _hubspot
    if _hubspot is None:
        from integrations import hubspot_client
        _hubspot = hubspot_client
    return _hubspot


def _get_salesforce():
    """Lazy-load Salesforce client."""
    global _salesforce
    if _salesforce is None:
        from integrations import salesforce_client
        _salesforce = salesforce_client
    return _salesforce


def _get_agilecrm():
    """Lazy-load Agile CRM client."""
    global _agilecrm
    if _agilecrm is None:
        from integrations import agilecrm_client
        _agilecrm = agilecrm_client
    return _agilecrm


def active_crm() -> str:
    """Return the name of the currently configured CRM.

    Checks configuration in priority order: GHL → HubSpot → Salesforce → Agile CRM.
    Falls back to 'none' if nothing is configured.

    Returns:
        CRM name string: 'ghl' | 'hubspot' | 'salesforce' | 'agilecrm' | 'none'
    """
    if config.GHL_API_KEY:
        return "ghl"
    if config.HUBSPOT_API_KEY:
        return "hubspot"
    if config.SALESFORCE_USERNAME:
        return "salesforce"
    if config.AGILECRM_API_KEY:
        return "agilecrm"
    return "none"


def all_configured_crms() -> list[str]:
    """Return all CRMs that have credentials configured.

    Returns:
        List of CRM name strings
    """
    crms = []
    if config.GHL_API_KEY:
        crms.append("ghl")
    if config.HUBSPOT_API_KEY:
        crms.append("hubspot")
    if config.SALESFORCE_USERNAME:
        crms.append("salesforce")
    if config.AGILECRM_API_KEY:
        crms.append("agilecrm")
    return crms


def _route(ghl_fn, hubspot_fn, sf_fn, *args, agilecrm_fn=None, **kwargs) -> Any:
    """Route a call to the active CRM's function.

    Args:
        ghl_fn: GHL client function name string
        hubspot_fn: HubSpot client function name string
        sf_fn: Salesforce client function name string
        agilecrm_fn: Agile CRM client function name string (defaults to ghl_fn)
        *args, **kwargs: Arguments forwarded to the chosen function

    Returns:
        Result from the active CRM's function, or None if unconfigured
    """
    crm = active_crm()
    fn_name = agilecrm_fn or ghl_fn
    try:
        if crm == "ghl":
            return getattr(_get_ghl(), ghl_fn)(*args, **kwargs)
        if crm == "hubspot":
            return getattr(_get_hubspot(), hubspot_fn)(*args, **kwargs)
        if crm == "salesforce":
            return getattr(_get_salesforce(), sf_fn)(*args, **kwargs)
        if crm == "agilecrm":
            return getattr(_get_agilecrm(), fn_name)(*args, **kwargs)
    except Exception as e:
        logger.error(f"[CRM_ROUTER] {crm}.{ghl_fn} failed: {e}")
        return None
    logger.warning("[CRM_ROUTER] No CRM configured — call skipped")
    return None


# ── Public API ──────────────────────────────────────────────────────────────

def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact record from the active CRM.

    Args:
        contact_id: CRM-specific contact identifier

    Returns:
        Contact dict or None
    """
    return _route("get_contact", "get_contact", "get_contact", contact_id)


def create_contact(data: dict) -> dict | None:
    """Create a new contact in the active CRM.

    Args:
        data: Contact data dict. Common keys: name/firstname/lastname,
              email, phone, company. CRM-specific fields are passed through.

    Returns:
        Created contact dict or None
    """
    return _route("create_contact", "create_contact", "create_contact", data)


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a single field on a contact in the active CRM.

    Args:
        contact_id: CRM contact id
        field: Field/property name
        value: New value

    Returns:
        Updated contact dict or None
    """
    return _route("update_contact_field", "update_contact_field", "update_contact_field",
                  contact_id, field, value)


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a contact in the active CRM.

    Args:
        contact_id: CRM contact id
        tag: Tag string

    Returns:
        Result dict or None
    """
    return _route("add_contact_tag", "add_contact_tag", "add_contact_tag", contact_id, tag)


def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a contact/deal to a specific pipeline stage in the active CRM.

    Args:
        contact_id: CRM contact id
        stage_id: Target stage id or name (CRM-specific)

    Returns:
        Result dict or None
    """
    return _route("move_pipeline_stage", "move_pipeline_stage", "move_pipeline_stage",
                  contact_id, stage_id)


def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a task associated with a contact in the active CRM.

    Args:
        contact_id: CRM contact id
        title: Task description
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    return _route("create_task", "create_task", "create_task", contact_id, title, due_date)


def send_sms(contact_id: str, message: str) -> dict | None:
    """Send an SMS to a contact via the active CRM.

    Note: HubSpot, Salesforce, and Agile CRM do not natively send SMS —
    this falls back to None for those platforms. Use a dedicated SMS provider instead.

    Args:
        contact_id: CRM contact id
        message: SMS message text

    Returns:
        Result dict or None
    """
    crm = active_crm()
    if crm == "ghl":
        return _get_ghl().send_sms(contact_id, message)
    logger.warning(f"[CRM_ROUTER] SMS not supported natively by {crm} — skipped")
    return None


def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a note to a contact in the active CRM.

    Args:
        contact_id: CRM contact id
        note_body: Note text

    Returns:
        Result dict or None
    """
    return _route("add_note", "add_note", "add_note", contact_id, note_body)


def get_pipeline_stages(pipeline_id: str = None) -> list:
    """Get pipeline stages from the active CRM.

    Args:
        pipeline_id: Pipeline id (required for GHL and HubSpot, optional for others)

    Returns:
        List of stage dicts or empty list
    """
    result = _route(
        "get_pipeline_stages", "get_pipeline_stages", "get_pipeline_stages",
        pipeline_id or "",
    )
    return result if result is not None else []


def is_configured() -> bool:
    """Check if at least one CRM is configured.

    Returns:
        True if any CRM credentials are present
    """
    return active_crm() != "none"


def find_contact_by_phone(phone: str) -> dict | None:
    """Search for a contact by phone number across the active CRM.

    Args:
        phone: Phone number in E.164 format (e.g. +61412345678)

    Returns:
        Contact dict or None if not found
    """
    return _route(
        "find_contact_by_phone", "find_contact_by_phone", "find_contact_by_phone",
        phone,
    )


def status() -> dict:
    """Return configuration status of all CRM integrations.

    Returns:
        Dict with CRM names as keys and bool configured status as values
    """
    return {
        "active": active_crm(),
        "ghl": bool(config.GHL_API_KEY),
        "hubspot": bool(config.HUBSPOT_API_KEY),
        "salesforce": bool(config.SALESFORCE_USERNAME),
        "agilecrm": bool(config.AGILECRM_API_KEY),
    }
