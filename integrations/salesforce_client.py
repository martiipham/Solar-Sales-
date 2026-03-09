"""Salesforce CRM API Client for Solar Swarm.

Uses the Salesforce REST API with OAuth2 username-password flow.
Wraps Lead, Contact, Opportunity, Task, and Note operations.

All functions return None on failure (never raises) to keep callers simple.
Requires SALESFORCE_USERNAME, SALESFORCE_PASSWORD, SALESFORCE_SECURITY_TOKEN,
SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET in environment.
"""

import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)

# Salesforce login endpoint — use test.salesforce.com for sandbox
LOGIN_URL = "https://login.salesforce.com/services/oauth2/token"

# Module-level token cache (refreshed on expiry)
_access_token: str = ""
_instance_url: str = ""


def _authenticate() -> bool:
    """Obtain an OAuth2 access token via username-password flow.

    Stores token and instance URL in module-level cache.

    Returns:
        True if authentication succeeded
    """
    global _access_token, _instance_url
    if not config.SALESFORCE_USERNAME:
        logger.warning("[SALESFORCE] Credentials not configured — skipping auth")
        return False
    try:
        resp = requests.post(LOGIN_URL, data={
            "grant_type": "password",
            "client_id": config.SALESFORCE_CLIENT_ID,
            "client_secret": config.SALESFORCE_CLIENT_SECRET,
            "username": config.SALESFORCE_USERNAME,
            "password": config.SALESFORCE_PASSWORD + config.SALESFORCE_SECURITY_TOKEN,
        }, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            _access_token = data["access_token"]
            _instance_url = data["instance_url"]
            print("[SALESFORCE] Authenticated successfully")
            return True
        logger.error(f"[SALESFORCE] Auth failed: HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"[SALESFORCE] Auth exception: {e}")
        return False


def _headers() -> dict:
    """Build authenticated Salesforce request headers."""
    return {
        "Authorization": f"Bearer {_access_token}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, data: dict = None, params: dict = None) -> dict | None:
    """Make an authenticated request to the Salesforce REST API.

    Automatically re-authenticates once if token has expired (401).

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        path: API path (e.g. '/services/data/v57.0/sobjects/Contact/003...')
        data: Request body dict
        params: Query string parameters

    Returns:
        Response JSON dict, empty dict on 204, or None on failure
    """
    global _access_token
    if not _access_token:
        if not _authenticate():
            return None

    def _do_request():
        url = f"{_instance_url}{path}"
        return requests.request(method, url, headers=_headers(), json=data, params=params, timeout=15)

    try:
        resp = _do_request()
        if resp.status_code == 401:
            # Token expired — re-authenticate once
            if _authenticate():
                resp = _do_request()
            else:
                return None
        if resp.status_code in (200, 201):
            return resp.json()
        if resp.status_code == 204:
            return {}
        logger.error(f"[SALESFORCE] {method} {path} → HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[SALESFORCE] Request failed: {e}")
        return None


def _soql(query: str) -> list:
    """Execute a SOQL query and return records.

    Args:
        query: SOQL query string

    Returns:
        List of record dicts or empty list
    """
    result = _request("GET", "/services/data/v57.0/query", params={"q": query})
    if not result:
        return []
    return result.get("records", [])


API_BASE = "/services/data/v57.0/sobjects"


def get_contact(contact_id: str) -> dict | None:
    """Fetch a Contact record from Salesforce.

    Args:
        contact_id: Salesforce Contact id (18-char)

    Returns:
        Contact dict or None
    """
    result = _request("GET", f"{API_BASE}/Contact/{contact_id}")
    if result:
        print(f"[SALESFORCE] Got contact: {contact_id}")
    return result


def get_contact_by_email(email: str) -> dict | None:
    """Search for a Contact by email address.

    Args:
        email: Contact's email address

    Returns:
        Contact dict or None
    """
    records = _soql(f"SELECT Id, FirstName, LastName, Email, Phone, Account.Name FROM Contact WHERE Email = '{email}' LIMIT 1")
    return records[0] if records else None


def create_contact(data: dict) -> dict | None:
    """Create a new Contact in Salesforce.

    Args:
        data: Dict with LastName (required), FirstName, Email, Phone, AccountId, etc.

    Returns:
        Dict with 'id' of created contact, or None
    """
    result = _request("POST", f"{API_BASE}/Contact", data=data)
    if result:
        print(f"[SALESFORCE] Contact created: {result.get('id', 'unknown')}")
    return result


def update_contact_field(contact_id: str, field: str, value) -> dict | None:
    """Update a field on a Salesforce Contact.

    Args:
        contact_id: Salesforce Contact id
        field: API field name (e.g. 'LeadSource')
        value: New field value

    Returns:
        Empty dict on success, None on failure (PATCH returns 204)
    """
    result = _request("PATCH", f"{API_BASE}/Contact/{contact_id}", data={field: value})
    if result is not None:
        print(f"[SALESFORCE] Updated contact {contact_id}: {field}={value}")
    return result


def add_contact_tag(contact_id: str, tag: str) -> dict | None:
    """Add a tag to a Salesforce Contact via a custom Tags__c field.

    Requires a custom multi-select picklist field named 'Tags__c' on Contact.

    Args:
        contact_id: Salesforce Contact id
        tag: Tag string to add

    Returns:
        Empty dict on success, None on failure
    """
    current = get_contact(contact_id)
    existing = current.get("Tags__c", "") if current else ""
    tags = set(filter(None, existing.split(";"))) if existing else set()
    tags.add(tag)
    result = update_contact_field(contact_id, "Tags__c", ";".join(tags))
    if result is not None:
        print(f"[SALESFORCE] Tag '{tag}' added to contact {contact_id}")
    return result


def move_pipeline_stage(contact_id: str, stage_id: str) -> dict | None:
    """Move an Opportunity linked to a contact to a specific stage.

    Finds the first open Opportunity associated with the contact's Account
    and updates its StageName.

    Args:
        contact_id: Salesforce Contact id
        stage_id: Target StageName string (e.g. 'Proposal/Price Quote')

    Returns:
        Empty dict on success, None on failure
    """
    records = _soql(
        f"SELECT Id FROM Opportunity WHERE AccountId IN "
        f"(SELECT AccountId FROM Contact WHERE Id = '{contact_id}') "
        f"AND IsClosed = false ORDER BY CreatedDate DESC LIMIT 1"
    )
    if not records:
        logger.warning(f"[SALESFORCE] No open opportunity found for contact {contact_id}")
        return None
    opp_id = records[0]["Id"]
    result = _request("PATCH", f"{API_BASE}/Opportunity/{opp_id}", data={"StageName": stage_id})
    if result is not None:
        print(f"[SALESFORCE] Opportunity {opp_id} moved to stage '{stage_id}'")
    return result


def create_task(contact_id: str, title: str, due_date: str) -> dict | None:
    """Create a Task in Salesforce associated with a Contact.

    Args:
        contact_id: Salesforce Contact id (WhoId)
        title: Task subject
        due_date: Due date in ISO format (YYYY-MM-DD)

    Returns:
        Dict with 'id' of created task, or None
    """
    result = _request("POST", f"{API_BASE}/Task", data={
        "Subject": title,
        "WhoId": contact_id,
        "ActivityDate": due_date,
        "Status": "Not Started",
        "Priority": "Normal",
    })
    if result:
        print(f"[SALESFORCE] Task created for contact {contact_id}: {title}")
    return result


def add_note(contact_id: str, note_body: str) -> dict | None:
    """Add a Note to a Salesforce Contact.

    Args:
        contact_id: Salesforce Contact id (ParentId)
        note_body: Note text content

    Returns:
        Dict with 'id' of created note, or None
    """
    result = _request("POST", f"{API_BASE}/Note", data={
        "ParentId": contact_id,
        "Title": f"Solar Swarm Note — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "Body": note_body,
    })
    if result:
        print(f"[SALESFORCE] Note added to contact {contact_id}")
    return result


def get_pipeline_stages(pipeline_id: str = None) -> list:
    """Get all Opportunity stage names from Salesforce picklist.

    Args:
        pipeline_id: Unused (Salesforce stages are global) — kept for interface parity

    Returns:
        List of stage name strings or empty list
    """
    result = _request("GET", "/services/data/v57.0/ui-api/object-info/Opportunity/picklist-values/012000000000000AAA")
    if not result:
        return []
    stage_values = result.get("picklistFieldValues", {}).get("StageName", {}).get("values", [])
    return [{"id": s["value"], "label": s["label"]} for s in stage_values]


def is_configured() -> bool:
    """Check if Salesforce credentials are properly configured.

    Returns:
        True if username and client credentials are all set
    """
    return bool(
        config.SALESFORCE_USERNAME
        and config.SALESFORCE_CLIENT_ID
        and config.SALESFORCE_CLIENT_SECRET
    )
