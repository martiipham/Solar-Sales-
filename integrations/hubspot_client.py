"""HubSpot CRM Client for SolarAdmin AI.

Wraps the HubSpot CRM API v3 for contact management, deal pipeline
operations, note creation, and task management.

All functions handle auth headers automatically.
Returns None on failure (never raises) to keep callers simple.

Rate limiting: HubSpot allows 100 requests per 10 seconds for private apps.
A token bucket proactively paces requests to stay under limits.
"""

import logging
import threading
import time
from typing import Any

import api_helpers
import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hubapi.com"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token bucket for proactive HubSpot API rate limiting.

    Default: 8 requests/second with burst capacity of 15.
    HubSpot allows ~100 req/10s for private apps.
    """

    def __init__(self, rate: float = 8.0, capacity: int = 15):
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
                logger.warning("[HUBSPOT] Rate limiter timeout")
                return False
            time.sleep(min(wait, 0.25))

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


_rate_limiter = _TokenBucket()


def _request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict | None:
    """Make an authenticated request to the HubSpot API.

    Args:
        method: HTTP method
        endpoint: API endpoint path (e.g. '/crm/v3/objects/contacts')
        data: Request body dict
        params: Query parameters dict

    Returns:
        Response JSON dict or None on failure
    """
    if not config.HUBSPOT_API_KEY:
        logger.warning("[HUBSPOT] No API key configured; skipping call")
        return None
    _rate_limiter.acquire()
    try:
        url = f"{BASE_URL}{endpoint}"
        kwargs = {"headers": _headers(), "timeout": 15}
        if data is not None:
            kwargs["json"] = data
        if params is not None:
            kwargs["params"] = params
        resp = api_helpers.request_with_retry(method, url, **kwargs)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.error("[HUBSPOT] %s %s -> HTTP %d: %s", method, endpoint, resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("[HUBSPOT] Request failed: %s", e)
        return None


# ── Contact Operations ─────────────────────────────────────────────────────

def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact by ID.

    Args:
        contact_id: HubSpot contact ID

    Returns:
        Contact dict with 'id' and 'properties' keys, or None
    """
    result = _request("GET", f"/crm/v3/objects/contacts/{contact_id}",
                       params={"properties": "firstname,lastname,email,phone,city,state,lifecyclestage"})
    if result:
        logger.info("[HUBSPOT] Got contact: %s", contact_id)
    return result


def create_contact(data: dict) -> dict | None:
    """Create a new contact in HubSpot.

    Args:
        data: Dict with keys like name/firstname/lastname, email, phone.
              Automatically maps 'name' to firstname/lastname split.

    Returns:
        Created contact dict or None
    """
    properties = _map_contact_input(data)
    result = _request("POST", "/crm/v3/objects/contacts", {"properties": properties})
    if result:
        logger.info("[HUBSPOT] Contact created: %s", result.get("id", "unknown"))
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a single property on a HubSpot contact.

    Args:
        contact_id: HubSpot contact ID
        field: Property name (e.g. 'email', 'phone', 'lifecyclestage')
        value: New value

    Returns:
        Updated contact dict or None
    """
    result = _request("PATCH", f"/crm/v3/objects/contacts/{contact_id}",
                       {"properties": {field: value}})
    if result:
        logger.info("[HUBSPOT] Updated contact %s: %s=%s", contact_id, field, value)
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a HubSpot contact via the 'hs_tag' property.

    HubSpot doesn't have native tags; we use a semicolon-separated custom property.

    Args:
        contact_id: HubSpot contact ID
        tag: Tag string to add

    Returns:
        Updated contact dict or None
    """
    existing = get_contact(contact_id)
    if not existing:
        return None
    current_tags = existing.get("properties", {}).get("hs_tag", "") or ""
    tag_list = [t.strip() for t in current_tags.split(";") if t.strip()]
    if tag not in tag_list:
        tag_list.append(tag)
    new_tags = ";".join(tag_list)
    return update_contact_field(contact_id, "hs_tag", new_tags)


# ── Pipeline / Deal Operations ─────────────────────────────────────────────

def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a contact's associated deal to a pipeline stage.

    Finds the most recent deal associated with the contact and updates its stage.

    Args:
        contact_id: HubSpot contact ID
        stage_id: Target deal stage ID

    Returns:
        Updated deal dict or None
    """
    deals = _get_associated_deals(contact_id)
    if not deals:
        logger.warning("[HUBSPOT] No deals found for contact %s", contact_id)
        return None
    deal_id = deals[0]["id"]
    result = _request("PATCH", f"/crm/v3/objects/deals/{deal_id}",
                       {"properties": {"dealstage": stage_id}})
    if result:
        logger.info("[HUBSPOT] Deal %s moved to stage %s", deal_id, stage_id)
    return result


def get_pipeline_stages(pipeline_id: str = "") -> list:
    """Get all stages for a deal pipeline.

    Args:
        pipeline_id: HubSpot pipeline ID (defaults to 'default')

    Returns:
        List of stage dicts with 'id', 'label', 'displayOrder'
    """
    pid = pipeline_id or "default"
    result = _request("GET", f"/crm/v3/pipelines/deals/{pid}/stages")
    if not result:
        return []
    return result.get("results", [])


def create_deal(contact_id: str, pipeline_id: str, stage_id: str,
                deal_name: str = "", value: float = 0) -> dict | None:
    """Create a deal and associate it with a contact.

    Args:
        contact_id: HubSpot contact ID to associate
        pipeline_id: Pipeline ID
        stage_id: Initial stage ID
        deal_name: Deal name (auto-generated if empty)
        value: Monetary value (AUD)

    Returns:
        Created deal dict or None
    """
    from datetime import datetime
    name = deal_name or f"Solar Lead — {datetime.utcnow().strftime('%Y-%m-%d')}"
    deal = _request("POST", "/crm/v3/objects/deals", {
        "properties": {
            "dealname": name,
            "pipeline": pipeline_id,
            "dealstage": stage_id,
            "amount": str(value),
        },
    })
    if deal:
        deal_id = deal.get("id")
        _request("PUT", f"/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/deal_to_contact", {})
        logger.info("[HUBSPOT] Deal created: %s for contact %s", deal_id, contact_id)
    return deal


# ── Task Operations ────────────────────────────────────────────────────────

def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a task associated with a contact.

    Args:
        contact_id: HubSpot contact ID
        title: Task description
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    task = _request("POST", "/crm/v3/objects/tasks", {
        "properties": {
            "hs_task_subject": title,
            "hs_task_status": "NOT_STARTED",
            "hs_timestamp": f"{due_date}T09:00:00.000Z",
        },
    })
    if task:
        task_id = task.get("id")
        _request("PUT", f"/crm/v3/objects/tasks/{task_id}/associations/contacts/{contact_id}/task_to_contact", {})
        logger.info("[HUBSPOT] Task created for contact %s: %s", contact_id, title)
    return task


# ── Notes ──────────────────────────────────────────────────────────────────

def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a note to a HubSpot contact.

    Args:
        contact_id: HubSpot contact ID
        note_body: Note text

    Returns:
        Created note dict or None
    """
    note = _request("POST", "/crm/v3/objects/notes", {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": str(int(time.time() * 1000)),
        },
    })
    if note:
        note_id = note.get("id")
        _request("PUT", f"/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact", {})
        logger.info("[HUBSPOT] Note added to contact %s", contact_id)
    return note


# ── Search ─────────────────────────────────────────────────────────────────

def find_contact_by_phone(phone: str) -> dict | None:
    """Search for a contact by phone number.

    Args:
        phone: Phone number in E.164 format

    Returns:
        Contact dict or None
    """
    result = _request("POST", "/crm/v3/objects/contacts/search", {
        "filterGroups": [{
            "filters": [{"propertyName": "phone", "operator": "EQ", "value": phone}],
        }],
        "properties": ["firstname", "lastname", "email", "phone", "city", "state"],
        "limit": 1,
    })
    if result and result.get("results"):
        return result["results"][0]
    return None


def get_contacts(limit: int = 100) -> list:
    """Fetch recent contacts sorted by last modified.

    Args:
        limit: Max contacts to return

    Returns:
        List of contact dicts
    """
    result = _request("GET", "/crm/v3/objects/contacts",
                       params={"limit": min(limit, 100),
                               "properties": "firstname,lastname,email,phone",
                               "sorts": "-hs_lastmodifieddate"})
    if result:
        return result.get("results", [])
    return []


# ── Status ─────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Check if HubSpot API credentials are configured."""
    return bool(config.HUBSPOT_API_KEY)


# ── Internal helpers ───────────────────────────────────────────────────────

def _map_contact_input(data: dict) -> dict:
    """Map generic contact data to HubSpot property names.

    Handles 'name' splitting into firstname/lastname and passes through
    standard HubSpot property names unchanged.
    """
    props = {}
    if "name" in data:
        parts = data["name"].strip().split(" ", 1)
        props["firstname"] = parts[0]
        props["lastname"] = parts[1] if len(parts) > 1 else ""
    if "firstname" in data:
        props["firstname"] = data["firstname"]
    if "lastname" in data:
        props["lastname"] = data["lastname"]
    if "email" in data:
        props["email"] = data["email"]
    if "phone" in data:
        props["phone"] = data["phone"]
    if "company" in data:
        props["company"] = data["company"]
    # Pass through any HubSpot-native properties
    for key in data:
        if key not in ("name", "firstname", "lastname", "email", "phone", "company",
                       "locationId", "tags", "customField", "customFields"):
            props[key] = data[key]
    return props


def _get_associated_deals(contact_id: str) -> list:
    """Get deals associated with a contact.

    Returns:
        List of deal dicts (most recent first)
    """
    result = _request("GET", f"/crm/v3/objects/contacts/{contact_id}/associations/deals")
    if not result:
        return []
    deal_ids = [r["id"] for r in result.get("results", [])]
    deals = []
    for did in deal_ids[:5]:
        deal = _request("GET", f"/crm/v3/objects/deals/{did}")
        if deal:
            deals.append(deal)
    return deals
