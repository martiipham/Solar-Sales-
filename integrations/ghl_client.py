"""GoHighLevel API Client for Solar Swarm.

Wraps the GHL REST API for contact management, pipeline operations,
SMS sending, and task creation.

All functions handle auth headers automatically.
Returns None on failure (never raises) to keep callers simple.

Rate limiting: A token bucket proactively paces requests to stay under
GHL's API limits (~100 req/10s for sub-accounts), preventing 429 cascades
during bulk operations like CRM sync or batch lead pushes.
"""

import logging
import threading
import time
from datetime import datetime

import api_helpers
import config

logger = logging.getLogger(__name__)

BASE_URL = config.GHL_BASE_URL
HEADERS = {
    "Authorization": f"Bearer {config.GHL_API_KEY}",
    "Content-Type": "application/json",
    "Version": "2021-07-28",
}


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token bucket for proactive GHL API rate limiting.

    Paces requests to stay comfortably under GHL's rate limits rather than
    waiting for 429 responses and relying on exponential backoff.

    Default: 8 requests/second with burst capacity of 15. This stays well
    under GHL's ~100 req/10s sub-account limit while allowing short bursts
    for normal interactive use (voice calls, dashboard).
    """

    def __init__(self, rate: float = 8.0, capacity: int = 15):
        self._rate = rate          # tokens added per second
        self._capacity = capacity  # max burst size
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Block until a token is available or timeout expires.

        Args:
            timeout: Max seconds to wait for a token

        Returns:
            True if token acquired, False if timed out
        """
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                # Calculate wait time until next token
                wait = (1.0 - self._tokens) / self._rate

            if time.monotonic() + wait > deadline:
                logger.warning("[GHL] Rate limiter timeout; request may be delayed")
                return False
            time.sleep(min(wait, 0.25))

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


_rate_limiter = _TokenBucket()


def _request(method: str, endpoint: str, data: dict = None) -> dict | None:
    """Make an authenticated request to the GHL API.

    Proactively rate-limited via token bucket to prevent 429 cascades
    during bulk operations.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        endpoint: API endpoint path (e.g. '/contacts/123')
        data: Request body dict for POST/PUT/PATCH

    Returns:
        Response JSON dict or None on failure
    """
    if not config.GHL_API_KEY:
        logger.warning("[GHL] No API key configured; skipping GHL call")
        return None
    _rate_limiter.acquire()
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = api_helpers.request_with_retry(method, url, headers=HEADERS, json=data, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json()
        logger.error(f"[GHL] {method} {endpoint} -> HTTP {resp.status_code}: {resp.text[:200]}")
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


def find_contact_by_phone(phone: str) -> dict | None:
    """Search for a contact by phone number.

    Args:
        phone: Phone number in E.164 format (e.g. +61412345678)

    Returns:
        Contact dict or None if not found
    """
    result = _request("GET", f"/contacts/search/duplicate?phone={phone}")
    return result.get("contact") if result else None


def get_contacts(location_id: str | None = None, limit: int = 100) -> list:
    """Fetch contacts from GHL, sorted by most recently updated.

    Args:
        location_id: GHL location ID (defaults to config value)
        limit: Max contacts to return

    Returns:
        List of contact dicts
    """
    loc = location_id or config.GHL_LOCATION_ID
    result = _request(
        "GET",
        f"/contacts/?locationId={loc}&limit={limit}&sortBy=dateUpdated&sortOrder=desc",
    )
    if result:
        return result.get("contacts", [])
    return []


def update_contact(contact_id: str, data: dict, location_id: str | None = None) -> dict | None:
    """Update a contact record with a full data dict.

    Args:
        contact_id: GHL contact ID
        data: Dict of fields to update (name, email, phone, customFields, etc.)
        location_id: GHL location ID (defaults to config value)

    Returns:
        Updated contact dict or None
    """
    loc = location_id or config.GHL_LOCATION_ID
    payload = {"locationId": loc, **data}
    result = _request("PUT", f"/contacts/{contact_id}", payload)
    if result:
        print(f"[GHL] Contact updated: {contact_id}")
    return result


def add_note(contact_id: str, note_text: str, location_id: str | None = None) -> dict | None:
    """Add a note to a GHL contact record.

    Args:
        contact_id: GHL contact ID
        note_text: Note body text
        location_id: GHL location ID (defaults to config value)

    Returns:
        Created note dict or None
    """
    loc = location_id or config.GHL_LOCATION_ID
    result = _request("POST", f"/contacts/{contact_id}/notes", {
        "body":       note_text,
        "locationId": loc,
    })
    if result:
        print(f"[GHL] Note added to contact {contact_id}: {note_text[:50]}")
    return result


def create_opportunity(
    contact_id: str,
    pipeline_id: str,
    stage_id: str,
    value: float = 0,
    location_id: str | None = None,
) -> dict | None:
    """Create an opportunity (deal) in a GHL pipeline for a contact.

    Args:
        contact_id: GHL contact ID
        pipeline_id: GHL pipeline ID
        stage_id: GHL pipeline stage ID
        value: Monetary value of the opportunity (AUD)
        location_id: GHL location ID (defaults to config value)

    Returns:
        Created opportunity dict or None
    """
    loc = location_id or config.GHL_LOCATION_ID
    result = _request("POST", "/opportunities/", {
        "locationId":      loc,
        "pipelineId":      pipeline_id,
        "pipelineStageId": stage_id,
        "contactId":       contact_id,
        "name":            f"Solar Lead — {datetime.utcnow().strftime('%Y-%m-%d')}",
        "status":          "open",
        "monetaryValue":   value,
    })
    if result:
        opp_id = result.get("opportunity", {}).get("id", "unknown")
        print(f"[GHL] Opportunity created: {opp_id} for contact {contact_id}")
    return result


def get_conversations(contact_id: str, location_id: str | None = None) -> list:
    """Fetch email and SMS conversation history for a contact.

    Args:
        contact_id: GHL contact ID
        location_id: GHL location ID (defaults to config value)

    Returns:
        List of conversation dicts
    """
    loc = location_id or config.GHL_LOCATION_ID
    result = _request("GET", f"/conversations/?locationId={loc}&contactId={contact_id}")
    if result:
        return result.get("conversations", [])
    return []


def is_configured() -> bool:
    """Check if GHL API credentials are properly configured.

    Returns:
        True if API key and location ID are set
    """
    return bool(config.GHL_API_KEY and config.GHL_LOCATION_ID)


# ─────────────────────────────────────────────────────────────────────────────
# GHLClient CLASS — object-oriented wrapper for convenience
# ─────────────────────────────────────────────────────────────────────────────

class GHLClient:
    """Object-oriented GHL API client.

    Wraps all module-level functions so callers can instantiate with
    custom credentials and use methods with explicit location_id signatures.

    Usage:
        client = GHLClient()
        contacts = client.get_contacts(limit=50)
        client.add_note(contact_id, "AI score: 8/10")
    """

    def __init__(self, api_key: str | None = None, location_id: str | None = None):
        """Initialise the GHL client.

        Args:
            api_key: GHL API key (defaults to config.GHL_API_KEY)
            location_id: GHL location ID (defaults to config.GHL_LOCATION_ID)
        """
        self.api_key     = api_key     or config.GHL_API_KEY
        self.location_id = location_id or config.GHL_LOCATION_ID

    def get_contacts(self, location_id: str | None = None, limit: int = 100) -> list:
        """Fetch contacts from GHL sorted by most recently updated.

        Args:
            location_id: Override location ID
            limit: Max contacts to return

        Returns:
            List of contact dicts
        """
        return get_contacts(location_id or self.location_id, limit)

    def create_contact(self, location_id: str | None = None, data: dict | None = None) -> dict | None:
        """Create a new contact in GHL.

        Args:
            location_id: Override location ID
            data: Contact data dict

        Returns:
            Created contact dict or None
        """
        payload = {"locationId": location_id or self.location_id, **(data or {})}
        return create_contact(payload)

    def update_contact(self, contact_id: str, data: dict, location_id: str | None = None) -> dict | None:
        """Update a contact with a full data dict.

        Args:
            contact_id: GHL contact ID
            data: Fields to update
            location_id: Override location ID

        Returns:
            Updated contact dict or None
        """
        return update_contact(contact_id, data, location_id or self.location_id)

    def add_note(self, contact_id: str, note_text: str, location_id: str | None = None) -> dict | None:
        """Add a note to a GHL contact.

        Args:
            contact_id: GHL contact ID
            note_text: Note body
            location_id: Override location ID

        Returns:
            Created note dict or None
        """
        return add_note(contact_id, note_text, location_id or self.location_id)

    def create_opportunity(
        self,
        contact_id: str,
        pipeline_id: str,
        stage_id: str,
        value: float = 0,
        location_id: str | None = None,
    ) -> dict | None:
        """Create an opportunity in a GHL pipeline.

        Args:
            contact_id: GHL contact ID
            pipeline_id: Pipeline ID
            stage_id: Stage ID
            value: Monetary value (AUD)
            location_id: Override location ID

        Returns:
            Created opportunity dict or None
        """
        return create_opportunity(
            contact_id, pipeline_id, stage_id, value,
            location_id or self.location_id,
        )

    def send_sms(self, location_id: str | None = None, contact_id: str | None = None, message: str = "") -> dict | None:
        """Send an SMS to a GHL contact.

        Args:
            location_id: Override location ID
            contact_id: GHL contact ID
            message: SMS text

        Returns:
            Result dict or None
        """
        return send_sms(contact_id or "", message)

    def get_conversations(self, contact_id: str, location_id: str | None = None) -> list:
        """Fetch conversation history for a contact.

        Args:
            contact_id: GHL contact ID
            location_id: Override location ID

        Returns:
            List of conversation dicts
        """
        return get_conversations(contact_id, location_id or self.location_id)

    def is_configured(self) -> bool:
        """Check if this client has credentials configured.

        Returns:
            True if both api_key and location_id are set
        """
        return bool(self.api_key and self.location_id)
