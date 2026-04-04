"""Agile CRM Client for SolarAdmin AI.

Wraps the Agile CRM REST API for contact management, deal pipeline
operations, note creation, and task management.

All functions handle auth headers automatically via HTTP Basic Auth.
Returns None on failure (never raises) to keep callers simple.

Rate limiting: Agile CRM allows ~500 requests per 10 minutes for
paid plans. A token bucket proactively paces requests to stay under limits.

API Docs: https://github.com/agilecrm/rest-api
"""

import base64
import logging
import threading
import time
from typing import Any

import api_helpers
import config

logger = logging.getLogger(__name__)

BASE_URL_TEMPLATE = "https://{domain}.agilecrm.com/dev/api"


def _base_url() -> str:
    return BASE_URL_TEMPLATE.format(domain=config.AGILECRM_DOMAIN)


def _headers() -> dict:
    credentials = f"{config.AGILECRM_EMAIL}:{config.AGILECRM_API_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token bucket for proactive Agile CRM API rate limiting.

    Default: 6 requests/second with burst capacity of 12.
    Agile CRM allows ~500 req/10min for paid plans (~0.83/s).
    We use a higher burst for interactive use but rely on the bucket
    to smooth sustained load.
    """

    def __init__(self, rate: float = 6.0, capacity: int = 12):
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                wait = (1.0 - self._tokens) / self._rate

            if time.monotonic() + wait > deadline:
                logger.warning("[AGILECRM] Rate limiter timeout")
                return False
            time.sleep(min(wait, 0.25))

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


_rate_limiter = _TokenBucket()


def _request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict | list | None:
    """Make an authenticated request to the Agile CRM API.

    Args:
        method: HTTP method
        endpoint: API endpoint path (e.g. '/contacts')
        data: Request body dict
        params: Query parameters dict

    Returns:
        Response JSON (dict or list) or None on failure
    """
    if not config.AGILECRM_API_KEY or not config.AGILECRM_DOMAIN:
        logger.warning("[AGILECRM] No API key or domain configured; skipping call")
        return None
    _rate_limiter.acquire()
    try:
        url = f"{_base_url()}{endpoint}"
        kwargs: dict[str, Any] = {"headers": _headers(), "timeout": 15}
        if data is not None:
            kwargs["json"] = data
        if params is not None:
            kwargs["params"] = params
        resp = api_helpers.request_with_retry(method, url, **kwargs)
        if resp.status_code in (200, 201, 204):
            if resp.status_code == 204 or not resp.text.strip():
                return {"success": True}
            return resp.json()
        logger.error("[AGILECRM] %s %s -> HTTP %d: %s", method, endpoint, resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("[AGILECRM] Request failed: %s", e)
        return None


# ── Contact Operations ─────────────────────────────────────────────────────

def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact by ID.

    Args:
        contact_id: Agile CRM contact ID

    Returns:
        Contact dict or None
    """
    result = _request("GET", f"/contacts/{contact_id}")
    if result:
        logger.info("[AGILECRM] Got contact: %s", contact_id)
    return result


def create_contact(data: dict) -> dict | None:
    """Create a new contact in Agile CRM.

    Args:
        data: Dict with keys like name/firstname/lastname, email, phone.
              Automatically maps to Agile CRM properties format.

    Returns:
        Created contact dict or None
    """
    payload = _build_contact_payload(data)
    result = _request("POST", "/contacts", payload)
    if result:
        logger.info("[AGILECRM] Contact created: %s", result.get("id", "unknown"))
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a single property on an Agile CRM contact.

    Args:
        contact_id: Agile CRM contact ID
        field: Property name (e.g. 'email', 'phone', 'custom field name')
        value: New value

    Returns:
        Updated contact dict or None
    """
    existing = get_contact(contact_id)
    if not existing:
        return None

    prop_type = _get_property_type(field)
    properties = existing.get("properties", [])
    updated = False
    for prop in properties:
        if prop.get("name") == field:
            prop["value"] = str(value)
            updated = True
            break
    if not updated:
        properties.append({"type": prop_type, "name": field, "value": str(value)})

    result = _request("PUT", "/contacts/edit-properties", {
        "id": contact_id,
        "properties": properties,
    })
    if result:
        logger.info("[AGILECRM] Updated contact %s: %s=%s", contact_id, field, value)
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to an Agile CRM contact.

    Args:
        contact_id: Agile CRM contact ID
        tag: Tag string to add

    Returns:
        Updated contact dict or None
    """
    result = _request("PUT", "/contacts/edit/tags", {
        "id": contact_id,
        "tags": [tag],
    })
    if result:
        logger.info("[AGILECRM] Tag '%s' added to contact %s", tag, contact_id)
    return result


# ── Pipeline / Deal Operations ─────────────────────────────────────────────

def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a contact's associated deal to a pipeline stage.

    Finds deals for the contact and updates the milestone (stage).

    Args:
        contact_id: Agile CRM contact ID
        stage_id: Target milestone/track name

    Returns:
        Updated deal dict or None
    """
    deals = _get_deals_for_contact(contact_id)
    if not deals:
        logger.warning("[AGILECRM] No deals found for contact %s", contact_id)
        return None
    deal = deals[0] if isinstance(deals, list) else deals
    deal_id = deal.get("id")
    result = _request("PUT", "/opportunity/partial-update", {
        "id": deal_id,
        "milestone": stage_id,
    })
    if result:
        logger.info("[AGILECRM] Deal %s moved to stage %s", deal_id, stage_id)
    return result


def get_pipeline_stages(pipeline_id: str = "") -> list:
    """Get all pipeline tracks (milestones) from Agile CRM.

    Args:
        pipeline_id: Pipeline track ID (not used; Agile CRM uses milestone strings)

    Returns:
        List of milestone dicts with 'id' and 'name'
    """
    result = _request("GET", "/milestone/pipelines")
    if not result:
        return []
    if isinstance(result, list):
        stages = []
        for pipeline in result:
            milestones = pipeline.get("milestones", "").split(",")
            for ms in milestones:
                ms = ms.strip()
                if ms:
                    stages.append({"id": ms, "name": ms, "pipeline": pipeline.get("id")})
        return stages
    return []


def create_deal(contact_id: str, pipeline_id: str, stage_id: str,
                deal_name: str = "", value: float = 0) -> dict | None:
    """Create a deal and associate it with a contact.

    Args:
        contact_id: Agile CRM contact ID
        pipeline_id: Pipeline track ID
        stage_id: Initial milestone name
        deal_name: Deal name (auto-generated if empty)
        value: Monetary value (AUD)

    Returns:
        Created deal dict or None
    """
    from datetime import datetime
    name = deal_name or f"Solar Lead - {datetime.utcnow().strftime('%Y-%m-%d')}"
    deal = _request("POST", "/opportunity", {
        "name": name,
        "expected_value": value,
        "milestone": stage_id,
        "pipeline_id": pipeline_id,
        "contact_ids": [str(contact_id)],
    })
    if deal:
        logger.info("[AGILECRM] Deal created: %s for contact %s", deal.get("id"), contact_id)
    return deal


# ── Task Operations ────────────────────────────────────────────────────────

def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a task associated with a contact.

    Args:
        contact_id: Agile CRM contact ID
        title: Task description
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    from datetime import datetime
    try:
        due_ts = int(datetime.strptime(due_date, "%Y-%m-%d").timestamp())
    except ValueError:
        due_ts = int(time.time()) + 86400

    task = _request("POST", "/tasks", {
        "subject": title,
        "type": "TODO",
        "priority_type": "NORMAL",
        "due": due_ts,
        "contacts": [str(contact_id)],
    })
    if task:
        logger.info("[AGILECRM] Task created for contact %s: %s", contact_id, title)
    return task


# ── Notes ──────────────────────────────────────────────────────────────────

def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a note to an Agile CRM contact.

    Args:
        contact_id: Agile CRM contact ID
        note_body: Note text

    Returns:
        Created note dict or None
    """
    note = _request("POST", "/notes", {
        "subject": "SolarAdmin AI Note",
        "description": note_body,
        "contact_ids": [str(contact_id)],
    })
    if note:
        logger.info("[AGILECRM] Note added to contact %s", contact_id)
    return note


# ── Search ─────────────────────────────────────────────────────────────────

def find_contact_by_phone(phone: str) -> dict | None:
    """Search for a contact by phone number.

    Args:
        phone: Phone number in E.164 format

    Returns:
        Contact dict or None
    """
    result = _request("POST", "/contacts/search/phone", {"phone_number": phone})
    if result:
        if isinstance(result, list):
            return result[0] if result else None
        return result if result.get("id") else None
    return None


def get_contacts(limit: int = 100) -> list:
    """Fetch recent contacts.

    Args:
        limit: Max contacts to return

    Returns:
        List of contact dicts
    """
    result = _request("GET", "/contacts", params={"page_size": min(limit, 100)})
    if result and isinstance(result, list):
        return result
    return []


# ── Status ─────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Check if Agile CRM API credentials are configured."""
    return bool(config.AGILECRM_API_KEY and config.AGILECRM_DOMAIN and config.AGILECRM_EMAIL)


# ── Internal helpers ───────────────────────────────────────────────────────

_SYSTEM_PROPERTIES = {"first_name", "last_name", "email", "phone", "company", "title", "address"}


def _get_property_type(field: str) -> str:
    """Determine Agile CRM property type for a field name."""
    if field in _SYSTEM_PROPERTIES:
        return "SYSTEM"
    return "CUSTOM"


def _map_contact_input(data: dict) -> dict:
    """Map generic contact data to Agile CRM property format.

    Handles 'name' splitting into first_name/last_name and builds
    the properties array that Agile CRM expects.
    """
    props = {}
    if "name" in data:
        parts = data["name"].strip().split(" ", 1)
        props["first_name"] = parts[0]
        props["last_name"] = parts[1] if len(parts) > 1 else ""
    if "firstname" in data or "first_name" in data:
        props["first_name"] = data.get("firstname") or data.get("first_name")
    if "lastname" in data or "last_name" in data:
        props["last_name"] = data.get("lastname") or data.get("last_name")
    if "email" in data:
        props["email"] = data["email"]
    if "phone" in data:
        props["phone"] = data["phone"]
    if "company" in data:
        props["company"] = data["company"]
    for key in data:
        if key not in ("name", "firstname", "lastname", "first_name", "last_name",
                       "email", "phone", "company", "tags"):
            props[key] = data[key]
    return props


def _build_contact_payload(data: dict) -> dict:
    """Build Agile CRM contact creation payload from generic data.

    Agile CRM expects contacts as:
    {
        "tags": ["tag1"],
        "properties": [
            {"type": "SYSTEM", "name": "first_name", "value": "Jane"},
            {"type": "SYSTEM", "name": "email", "subtype": "work", "value": "jane@co.com"},
        ]
    }
    """
    mapped = _map_contact_input(data)
    properties = []
    for key, value in mapped.items():
        prop = {"type": _get_property_type(key), "name": key, "value": str(value)}
        if key == "email":
            prop["subtype"] = "work"
        elif key == "phone":
            prop["subtype"] = "work"
        properties.append(prop)

    payload: dict[str, Any] = {"properties": properties}
    tags = data.get("tags")
    if tags:
        payload["tags"] = tags if isinstance(tags, list) else [tags]
    return payload


def _get_deals_for_contact(contact_id: str) -> list:
    """Get deals associated with a contact.

    Returns:
        List of deal dicts
    """
    result = _request("GET", f"/contacts/{contact_id}/deals")
    if result and isinstance(result, list):
        return result
    return []
