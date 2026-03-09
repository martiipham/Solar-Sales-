"""GoHighLevel API Client for Solar Swarm.

Wraps the GHL REST API for contact management, pipeline operations,
SMS sending, and task creation.

All functions handle auth headers automatically.
Returns None on failure (never raises) to keep callers simple.
"""

import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)

BASE_URL = config.GHL_BASE_URL
HEADERS = {
    "Authorization": f"Bearer {config.GHL_API_KEY}",
    "Content-Type": "application/json",
    "Version": "2021-07-28",
}


def _request(method: str, endpoint: str, data: dict = None) -> dict | None:
    """Make an authenticated request to the GHL API.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        endpoint: API endpoint path (e.g. '/contacts/123')
        data: Request body dict for POST/PUT/PATCH

    Returns:
        Response JSON dict or None on failure
    """
    if not config.GHL_API_KEY:
        logger.warning("[GHL] No API key configured — skipping GHL call")
        return None
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = requests.request(method, url, headers=HEADERS, json=data, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.error(f"[GHL] {method} {endpoint} → HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[GHL] Request failed: {e}")
        return None


def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact record from GHL.

    Args:
        contact_id: GHL contact id

    Returns:
        Contact dict or None
    """
    result = _request("GET", f"/contacts/{contact_id}")
    if result:
        print(f"[GHL] Got contact: {contact_id}")
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a custom field on a GHL contact.

    Args:
        contact_id: GHL contact id
        field: Field key name
        value: New field value

    Returns:
        Updated contact dict or None
    """
    result = _request("PUT", f"/contacts/{contact_id}", {"customField": {field: value}})
    if result:
        print(f"[GHL] Updated contact {contact_id}: {field}={value}")
    return result


def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a contact to a specific pipeline stage.

    Args:
        contact_id: GHL contact id
        stage_id: Target pipeline stage id

    Returns:
        Result dict or None
    """
    result = _request("POST", f"/contacts/{contact_id}/pipeline-stage", {
        "pipelineStageId": stage_id,
        "locationId": config.GHL_LOCATION_ID,
    })
    if result:
        print(f"[GHL] Contact {contact_id} moved to stage {stage_id}")
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a GHL contact.

    Args:
        contact_id: GHL contact id
        tag: Tag string to add

    Returns:
        Result dict or None
    """
    result = _request("POST", f"/contacts/{contact_id}/tags", {"tags": [tag]})
    if result:
        print(f"[GHL] Tag '{tag}' added to contact {contact_id}")
    return result


def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a task in GHL associated with a contact.

    Args:
        contact_id: GHL contact id
        title: Task description
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    result = _request("POST", "/tasks/", {
        "title": title,
        "contactId": contact_id,
        "dueDate": due_date,
        "status": "incomplete",
        "locationId": config.GHL_LOCATION_ID,
    })
    if result:
        print(f"[GHL] Task created for {contact_id}: {title}")
    return result


def send_sms(contact_id: str, message: str) -> dict | None:
    """Send an SMS to a GHL contact via the conversations API.

    Args:
        contact_id: GHL contact id
        message: SMS message text

    Returns:
        Message result dict or None
    """
    result = _request("POST", "/conversations/messages", {
        "type": "SMS",
        "contactId": contact_id,
        "message": message,
        "locationId": config.GHL_LOCATION_ID,
    })
    if result:
        print(f"[GHL] SMS sent to contact {contact_id}: {message[:50]}...")
    return result


def create_contact(data: dict) -> dict | None:
    """Create a new contact in GHL.

    Args:
        data: Dict with name, phone, email, tags, customFields etc.

    Returns:
        Created contact dict or None
    """
    payload = {
        "locationId": config.GHL_LOCATION_ID,
        **data,
    }
    result = _request("POST", "/contacts/", payload)
    if result:
        contact_id = result.get("contact", {}).get("id", "unknown")
        print(f"[GHL] Contact created: {contact_id}")
    return result


def get_pipeline_stages(pipeline_id: str) -> list:
    """Get all stages for a pipeline.

    Args:
        pipeline_id: GHL pipeline id

    Returns:
        List of stage dicts or empty list
    """
    result = _request("GET", f"/opportunities/pipelines/{pipeline_id}")
    if not result:
        return []
    return result.get("stages", [])


def is_configured() -> bool:
    """Check if GHL API credentials are properly configured.

    Returns:
        True if API key and location ID are set
    """
    return bool(config.GHL_API_KEY and config.GHL_LOCATION_ID)
