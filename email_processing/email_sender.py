"""Email Sender — sends emails via GoHighLevel Conversations API.

Functions:
    send_via_ghl(to_email, subject, body, location_id) → sends email via GHL
    get_thread_history(contact_id) → returns last 5 emails for context
"""

import logging

import api_helpers
import config

logger = logging.getLogger(__name__)

_BASE_URL = config.GHL_BASE_URL
_HEADERS = {
    "Authorization": f"Bearer {config.GHL_API_KEY}",
    "Content-Type": "application/json",
    "Version": "2021-07-28",
}


def send_via_ghl(to_email: str, subject: str, body: str, location_id: str = None) -> dict | None:
    """Send an email via GHL Conversations API.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body (plain text)
        location_id: GHL location ID (defaults to config.GHL_LOCATION_ID)

    Returns:
        GHL API response dict, or None on failure
    """
    if not config.GHL_API_KEY:
        logger.warning("[EMAIL SENDER] GHL not configured — cannot send email")
        return None

    loc_id = location_id or config.GHL_LOCATION_ID
    contact_id = _resolve_contact_by_email(to_email)

    payload = {
        "type": "Email",
        "locationId": loc_id,
        "emailTo": to_email,
        "subject": subject,
        "body": body,
    }
    if contact_id:
        payload["contactId"] = contact_id

    try:
        resp = api_helpers.post(
            f"{_BASE_URL}/conversations/messages",
            headers=_HEADERS,
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            print(f"[EMAIL SENDER] Email sent to {to_email}: {subject[:60]}")
            return resp.json()
        logger.error(f"[EMAIL SENDER] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[EMAIL SENDER] Failed to send email: {e}")
        return None


def get_thread_history(contact_id: str, limit: int = 5) -> list:
    """Fetch the last N email messages from a GHL conversation thread.

    Args:
        contact_id: GHL contact ID
        limit: Max messages to return (default 5)

    Returns:
        List of message dicts (may be empty if not configured or no history)
    """
    if not config.GHL_API_KEY or not contact_id:
        return []

    try:
        convo_id = _get_conversation_id(contact_id)
        if not convo_id:
            return []

        resp = api_helpers.get(
            f"{_BASE_URL}/conversations/{convo_id}/messages",
            headers=_HEADERS,
            params={"limit": limit * 2},  # fetch extra, filter to email only
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"[EMAIL SENDER] Messages HTTP {resp.status_code}")
            return []

        messages = resp.json().get("messages", {}).get("messages", [])
        email_msgs = [m for m in messages if m.get("messageType") in ("Email", "EMAIL")]
        return email_msgs[:limit]

    except Exception as e:
        logger.error(f"[EMAIL SENDER] Thread history failed: {e}")
        return []


def _get_conversation_id(contact_id: str) -> str | None:
    """Retrieve the GHL conversation ID for a contact.

    Args:
        contact_id: GHL contact ID

    Returns:
        Conversation ID string or None
    """
    try:
        resp = api_helpers.get(
            f"{_BASE_URL}/conversations/search",
            headers=_HEADERS,
            params={"locationId": config.GHL_LOCATION_ID, "contactId": contact_id},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        conversations = resp.json().get("conversations", [])
        return conversations[0].get("id") if conversations else None
    except Exception as e:
        logger.error(f"[EMAIL SENDER] Conversation lookup failed: {e}")
        return None


def _resolve_contact_by_email(email: str) -> str | None:
    """Look up GHL contact ID by email address.

    Args:
        email: Email address to search

    Returns:
        GHL contact ID or None
    """
    if not config.GHL_API_KEY or not email:
        return None
    try:
        resp = api_helpers.get(
            f"{_BASE_URL}/contacts/",
            headers=_HEADERS,
            params={"locationId": config.GHL_LOCATION_ID, "query": email},
            timeout=10,
        )
        if resp.status_code == 200:
            contacts = resp.json().get("contacts", [])
            return contacts[0].get("id") if contacts else None
        return None
    except Exception as e:
        logger.error(f"[EMAIL SENDER] Contact lookup failed: {e}")
        return None
