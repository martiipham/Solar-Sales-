"""HubSpot CRM API Client for Solar Swarm.

Wraps the HubSpot v3 REST API for contact management, deal pipeline
operations, notes, and task creation.

All functions return None on failure (never raises) to keep callers simple.
Requires HUBSPOT_API_KEY (private app token) in environment.
"""

import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hubapi.com"


def _headers() -> dict:
    """Build authenticated HubSpot request headers."""
    return {
        "Authorization": f"Bearer {config.HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
    }


def _request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict | None:
    """Make an authenticated request to the HubSpot API.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        endpoint: API endpoint path (e.g. '/crm/v3/objects/contacts/123')
        data: Request body dict for POST/PUT/PATCH
        params: Query string parameters

    Returns:
        Response JSON dict or None on failure
    """
    if not config.HUBSPOT_API_KEY:
        logger.warning("[HUBSPOT] No API key configured — skipping call")
        return None
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = requests.request(
            method, url, headers=_headers(), json=data, params=params, timeout=15
        )
        if resp.status_code in (200, 201, 204):
            return resp.json() if resp.content else {}
        logger.error(f"[HUBSPOT] {method} {endpoint} → HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[HUBSPOT] Request failed: {e}")
        return None


def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact record from HubSpot.

    Args:
        contact_id: HubSpot contact id

    Returns:
        Contact dict or None
    """
    result = _request("GET", f"/crm/v3/objects/contacts/{contact_id}",
                      params={"properties": "firstname,lastname,email,phone,company,hs_lead_status"})
    if result:
        print(f"[HUBSPOT] Got contact: {contact_id}")
    return result


def get_contact_by_email(email: str) -> dict | None:
    """Search for a contact by email address.

    Args:
        email: Contact's email address

    Returns:
        Contact dict or None
    """
    data = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
        "properties": ["firstname", "lastname", "email", "phone", "company"],
        "limit": 1,
    }
    result = _request("POST", "/crm/v3/objects/contacts/search", data=data)
    if result and result.get("results"):
        return result["results"][0]
    return None


def create_contact(data: dict) -> dict | None:
    """Create a new contact in HubSpot.

    Args:
        data: Dict with firstname, lastname, email, phone, company, etc.

    Returns:
        Created contact dict or None
    """
    payload = {"properties": data}
    result = _request("POST", "/crm/v3/objects/contacts", data=payload)
    if result:
        contact_id = result.get("id", "unknown")
        print(f"[HUBSPOT] Contact created: {contact_id}")
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a property on a HubSpot contact.

    Args:
        contact_id: HubSpot contact id
        field: Property name (e.g. 'lifecyclestage')
        value: New property value

    Returns:
        Updated contact dict or None
    """
    result = _request("PATCH", f"/crm/v3/objects/contacts/{contact_id}",
                      data={"properties": {field: value}})
    if result:
        print(f"[HUBSPOT] Updated contact {contact_id}: {field}={value}")
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a HubSpot contact via the hs_tag property.

    HubSpot doesn't have native tags — this sets a custom 'tags' property.
    Requires a custom multi-checkbox property named 'tags' in your portal.

    Args:
        contact_id: HubSpot contact id
        tag: Tag string to add

    Returns:
        Updated contact dict or None
    """
    # Fetch current tags first to append
    current = get_contact(contact_id)
    existing = current.get("properties", {}).get("tags", "") if current else ""
    tags = set(filter(None, existing.split(";"))) if existing else set()
    tags.add(tag)
    result = update_contact_field(contact_id, "tags", ";".join(tags))
    if result:
        print(f"[HUBSPOT] Tag '{tag}' added to contact {contact_id}")
    return result


def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a deal associated with a contact to a specific pipeline stage.

    Finds the first deal linked to the contact and updates its stage.

    Args:
        contact_id: HubSpot contact id
        stage_id: Target deal stage id (from your HubSpot pipeline config)

    Returns:
        Updated deal dict or None
    """
    # Get associated deals
    assoc = _request("GET", f"/crm/v3/objects/contacts/{contact_id}/associations/deals")
    if not assoc or not assoc.get("results"):
        logger.warning(f"[HUBSPOT] No deals found for contact {contact_id}")
        return None
    deal_id = assoc["results"][0]["id"]
    result = _request("PATCH", f"/crm/v3/objects/deals/{deal_id}",
                      data={"properties": {"dealstage": stage_id}})
    if result:
        print(f"[HUBSPOT] Deal {deal_id} moved to stage {stage_id}")
    return result


def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create an engagement task in HubSpot associated with a contact.

    Args:
        contact_id: HubSpot contact id
        title: Task subject/title
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    # Convert date to millisecond timestamp
    try:
        dt = datetime.strptime(due_date, "%Y-%m-%d")
        due_ts = int(dt.timestamp() * 1000)
    except ValueError:
        due_ts = None

    payload = {
        "properties": {
            "hs_task_subject": title,
            "hs_task_status": "NOT_STARTED",
            "hs_task_type": "TODO",
            **({"hs_timestamp": due_ts} if due_ts else {}),
        }
    }
    result = _request("POST", "/crm/v3/objects/tasks", data=payload)
    if result:
        task_id = result.get("id", "unknown")
        # Associate task with contact
        _request("PUT", f"/crm/v3/objects/tasks/{task_id}/associations/contacts/{contact_id}/task_to_contact")
        print(f"[HUBSPOT] Task created for contact {contact_id}: {title}")
    return result


def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a note engagement to a HubSpot contact.

    Args:
        contact_id: HubSpot contact id
        note_body: Note text content

    Returns:
        Created note dict or None
    """
    payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": int(datetime.now().timestamp() * 1000),
        }
    }
    result = _request("POST", "/crm/v3/objects/notes", data=payload)
    if result:
        note_id = result.get("id", "unknown")
        _request("PUT", f"/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact")
        print(f"[HUBSPOT] Note added to contact {contact_id}")
    return result


def get_pipeline_stages(pipeline_id: str) -> list:
    """Get all stages for a HubSpot deal pipeline.

    Args:
        pipeline_id: HubSpot pipeline id

    Returns:
        List of stage dicts or empty list
    """
    result = _request("GET", f"/crm/v3/pipelines/deals/{pipeline_id}/stages")
    if not result:
        return []
    return result.get("results", [])


def is_configured() -> bool:
    """Check if HubSpot API credentials are properly configured.

    Returns:
        True if API key is set
    """
    return bool(config.HUBSPOT_API_KEY)
