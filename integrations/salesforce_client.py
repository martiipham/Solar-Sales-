"""Salesforce CRM Client for SolarAdmin AI.

Wraps the Salesforce REST API for contact management, opportunity pipeline
operations, note creation, and task management.

Authentication uses OAuth 2.0 Username-Password flow, with automatic
token refresh on 401 responses.

All functions handle auth automatically.
Returns None on failure (never raises) to keep callers simple.
"""

import logging
import threading
import time
from typing import Any

import api_helpers
import config

logger = logging.getLogger(__name__)

LOGIN_URL = "https://login.salesforce.com/services/oauth2/token"
API_VERSION = "v59.0"

# Auth state (module-level, thread-safe)
_auth_lock = threading.Lock()
_access_token: str = ""
_instance_url: str = ""
_token_expiry: float = 0


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

def _authenticate() -> bool:
    """Authenticate with Salesforce using OAuth 2.0 Username-Password flow.

    Returns:
        True if authenticated successfully
    """
    global _access_token, _instance_url, _token_expiry

    if not all([config.SALESFORCE_USERNAME, config.SALESFORCE_PASSWORD,
                config.SALESFORCE_CLIENT_ID, config.SALESFORCE_CLIENT_SECRET]):
        logger.warning("[SALESFORCE] Incomplete credentials; skipping auth")
        return False

    try:
        resp = api_helpers.request_with_retry("POST", LOGIN_URL, data={
            "grant_type": "password",
            "client_id": config.SALESFORCE_CLIENT_ID,
            "client_secret": config.SALESFORCE_CLIENT_SECRET,
            "username": config.SALESFORCE_USERNAME,
            "password": f"{config.SALESFORCE_PASSWORD}{config.SALESFORCE_SECURITY_TOKEN}",
        }, timeout=15)

        if resp.status_code != 200:
            logger.error("[SALESFORCE] Auth failed: HTTP %d: %s", resp.status_code, resp.text[:200])
            return False

        data = resp.json()
        with _auth_lock:
            _access_token = data["access_token"]
            _instance_url = data["instance_url"]
            _token_expiry = time.monotonic() + 7200  # Refresh every 2 hours
        logger.info("[SALESFORCE] Authenticated successfully")
        return True
    except Exception as e:
        logger.error("[SALESFORCE] Auth error: %s", e)
        return False


def _ensure_auth() -> bool:
    """Ensure we have a valid access token, refreshing if needed."""
    with _auth_lock:
        if _access_token and time.monotonic() < _token_expiry:
            return True
    return _authenticate()


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json",
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token bucket for Salesforce API rate limiting.

    Salesforce limits vary by edition (typically 15,000/day for Enterprise).
    Default: 5 requests/second with burst capacity of 10.
    """

    def __init__(self, rate: float = 5.0, capacity: int = 10):
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
                logger.warning("[SALESFORCE] Rate limiter timeout")
                return False
            time.sleep(min(wait, 0.25))

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now


_rate_limiter = _TokenBucket()


def _request(method: str, endpoint: str, data: dict = None, params: dict = None,
             retry_auth: bool = True) -> dict | None:
    """Make an authenticated request to the Salesforce REST API.

    Automatically refreshes auth token on 401 responses (once).

    Args:
        method: HTTP method
        endpoint: API endpoint path (e.g. '/sobjects/Contact/001xx')
        data: Request body dict
        params: Query parameters
        retry_auth: Whether to retry with fresh auth on 401

    Returns:
        Response JSON dict or None on failure
    """
    if not _ensure_auth():
        return None
    _rate_limiter.acquire()
    try:
        url = f"{_instance_url}/services/data/{API_VERSION}{endpoint}"
        kwargs = {"headers": _headers(), "timeout": 15}
        if data is not None:
            kwargs["json"] = data
        if params is not None:
            kwargs["params"] = params
        resp = api_helpers.request_with_retry(method, url, **kwargs)

        if resp.status_code == 401 and retry_auth:
            logger.info("[SALESFORCE] Token expired, re-authenticating")
            if _authenticate():
                return _request(method, endpoint, data, params, retry_auth=False)
            return None

        if resp.status_code in (200, 201):
            return resp.json()

        # Salesforce returns 204 for successful deletes/updates with no body
        if resp.status_code == 204:
            return {"success": True}

        logger.error("[SALESFORCE] %s %s -> HTTP %d: %s", method, endpoint, resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        logger.error("[SALESFORCE] Request failed: %s", e)
        return None


def _soql(query: str) -> list:
    """Execute a SOQL query.

    Args:
        query: SOQL query string

    Returns:
        List of record dicts
    """
    result = _request("GET", "/query", params={"q": query})
    if result:
        return result.get("records", [])
    return []


# ── Contact Operations ─────────────────────────────────────────────────────

def get_contact(contact_id: str) -> dict | None:
    """Fetch a contact by Salesforce ID.

    Args:
        contact_id: Salesforce Contact ID (18-char)

    Returns:
        Contact record dict or None
    """
    result = _request("GET", f"/sobjects/Contact/{contact_id}")
    if result:
        logger.info("[SALESFORCE] Got contact: %s", contact_id)
    return result


def create_contact(data: dict) -> dict | None:
    """Create a new contact in Salesforce.

    Args:
        data: Dict with keys like name/firstname/lastname, email, phone.
              Automatically maps generic keys to Salesforce field names.

    Returns:
        Created contact dict with 'id' key, or None
    """
    fields = _map_contact_input(data)
    result = _request("POST", "/sobjects/Contact", fields)
    if result:
        logger.info("[SALESFORCE] Contact created: %s", result.get("id", "unknown"))
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a single field on a Salesforce contact.

    Args:
        contact_id: Salesforce Contact ID
        field: Salesforce field API name (e.g. 'Email', 'Phone')
        value: New value

    Returns:
        Success dict or None
    """
    result = _request("PATCH", f"/sobjects/Contact/{contact_id}", {field: value})
    if result:
        logger.info("[SALESFORCE] Updated contact %s: %s=%s", contact_id, field, value)
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a Salesforce contact via a custom field.

    Salesforce doesn't have native tags on contacts. Uses a custom
    text field 'Tags__c' with semicolon-separated values.

    Args:
        contact_id: Salesforce Contact ID
        tag: Tag string to add

    Returns:
        Updated contact dict or None
    """
    existing = get_contact(contact_id)
    if not existing:
        return None
    current_tags = existing.get("Tags__c", "") or ""
    tag_list = [t.strip() for t in current_tags.split(";") if t.strip()]
    if tag not in tag_list:
        tag_list.append(tag)
    return update_contact_field(contact_id, "Tags__c", ";".join(tag_list))


# ── Pipeline / Opportunity Operations ──────────────────────────────────────

def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move a contact's most recent opportunity to a new stage.

    Args:
        contact_id: Salesforce Contact ID
        stage_id: Target StageName value (e.g. 'Qualification', 'Proposal')

    Returns:
        Success dict or None
    """
    opps = _soql(
        f"SELECT Id FROM Opportunity WHERE ContactId = '{_safe(contact_id)}' "
        "ORDER BY CreatedDate DESC LIMIT 1"
    )
    if not opps:
        logger.warning("[SALESFORCE] No opportunities for contact %s", contact_id)
        return None
    opp_id = opps[0]["Id"]
    result = _request("PATCH", f"/sobjects/Opportunity/{opp_id}", {"StageName": stage_id})
    if result:
        logger.info("[SALESFORCE] Opportunity %s moved to stage %s", opp_id, stage_id)
    return result


def get_pipeline_stages(pipeline_id: str = "") -> list:
    """Get all opportunity stage values from Salesforce.

    Args:
        pipeline_id: Ignored — Salesforce stages are global picklist values

    Returns:
        List of stage dicts with 'value', 'label', 'active' keys
    """
    result = _request("GET", "/sobjects/Opportunity/describe")
    if not result:
        return []
    for field in result.get("fields", []):
        if field.get("name") == "StageName":
            return [{"value": pv["value"], "label": pv["label"], "active": pv["active"]}
                    for pv in field.get("picklistValues", [])]
    return []


def create_opportunity(contact_id: str, stage_name: str = "Prospecting",
                       value: float = 0, name: str = "") -> dict | None:
    """Create an opportunity linked to a contact.

    Args:
        contact_id: Salesforce Contact ID
        stage_name: Initial stage name
        value: Monetary value (AUD)
        name: Opportunity name (auto-generated if empty)

    Returns:
        Created opportunity dict or None
    """
    from datetime import datetime, timedelta
    opp_name = name or f"Solar Lead — {datetime.utcnow().strftime('%Y-%m-%d')}"
    close_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
    result = _request("POST", "/sobjects/Opportunity", {
        "Name": opp_name,
        "StageName": stage_name,
        "Amount": value,
        "CloseDate": close_date,
        "ContactId": contact_id,
    })
    if result:
        logger.info("[SALESFORCE] Opportunity created: %s for contact %s", result.get("id"), contact_id)
    return result


# ── Task Operations ────────────────────────────────────────────────────────

def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a task associated with a contact.

    Args:
        contact_id: Salesforce Contact ID
        title: Task subject
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Created task dict or None
    """
    result = _request("POST", "/sobjects/Task", {
        "Subject": title,
        "WhoId": contact_id,
        "ActivityDate": due_date,
        "Status": "Not Started",
        "Priority": "Normal",
    })
    if result:
        logger.info("[SALESFORCE] Task created for %s: %s", contact_id, title)
    return result


# ── Notes ──────────────────────────────────────────────────────────────────

def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a note (ContentNote) linked to a Salesforce contact.

    Args:
        contact_id: Salesforce Contact ID
        note_body: Note text

    Returns:
        Created note dict or None
    """
    import base64
    # Salesforce ContentNote requires base64-encoded body
    encoded_body = base64.b64encode(note_body.encode("utf-8")).decode("utf-8")
    note = _request("POST", "/sobjects/ContentNote", {
        "Title": f"AI Note — {time.strftime('%Y-%m-%d %H:%M')}",
        "Content": encoded_body,
    })
    if note:
        note_id = note.get("id")
        _request("POST", "/sobjects/ContentDocumentLink", {
            "ContentDocumentId": note_id,
            "LinkedEntityId": contact_id,
            "ShareType": "V",
        })
        logger.info("[SALESFORCE] Note added to contact %s", contact_id)
    return note


# ── Search ─────────────────────────────────────────────────────────────────

def find_contact_by_phone(phone: str) -> dict | None:
    """Search for a contact by phone number.

    Args:
        phone: Phone number in E.164 format

    Returns:
        Contact dict or None
    """
    records = _soql(
        f"SELECT Id, FirstName, LastName, Email, Phone, MailingCity, MailingState "
        f"FROM Contact WHERE Phone = '{_safe(phone)}' LIMIT 1"
    )
    return records[0] if records else None


def get_contacts(limit: int = 100) -> list:
    """Fetch recently modified contacts.

    Args:
        limit: Max contacts to return

    Returns:
        List of contact dicts
    """
    return _soql(
        f"SELECT Id, FirstName, LastName, Email, Phone, MailingCity, MailingState "
        f"FROM Contact ORDER BY LastModifiedDate DESC LIMIT {min(limit, 200)}"
    )


# ── Status ─────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Check if Salesforce credentials are configured."""
    return bool(config.SALESFORCE_USERNAME and config.SALESFORCE_CLIENT_ID)


# ── Internal helpers ───────────────────────────────────────────────────────

def _safe(value: str) -> str:
    """Escape a string for safe use in SOQL queries.

    Prevents SOQL injection by escaping single quotes.
    """
    return str(value).replace("'", "\\'")


def _map_contact_input(data: dict) -> dict:
    """Map generic contact data to Salesforce field names."""
    fields = {}
    if "name" in data:
        parts = data["name"].strip().split(" ", 1)
        fields["FirstName"] = parts[0]
        fields["LastName"] = parts[1] if len(parts) > 1 else parts[0]
    if "firstname" in data:
        fields["FirstName"] = data["firstname"]
    if "lastname" in data:
        fields["LastName"] = data["lastname"]
    if "email" in data:
        fields["Email"] = data["email"]
    if "phone" in data:
        fields["Phone"] = data["phone"]
    # LastName is required in Salesforce
    if "LastName" not in fields:
        fields["LastName"] = "Unknown"
    # Pass through any Salesforce-native field names (capitalized)
    for key in data:
        if key[0].isupper() and key not in fields:
            fields[key] = data[key]
    return fields
