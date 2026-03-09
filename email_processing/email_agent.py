"""Email Processing Agent — Read inbound emails and fill the CRM.

Handles emails from two sources:
  1. GHL webhook (GHL forwards email events to POST /webhook/email-received)
  2. Direct IMAP polling (optional — polls a Gmail/Outlook inbox)

For each email:
  - Extracts structured lead data using GPT-4o
  - Creates or updates the GHL contact
  - Scores the lead via qualification_agent
  - Routes the lead (call now / nurture / disqualify)
  - Auto-drafts an AI reply for high-value leads (human reviews before sending)
  - Tags in GHL for pipeline automation
  - Posts Slack notification

Flask routes (registered in main.py):
  POST /webhook/email-received   — GHL email event
  GET  /email/status             — health/status check

Usage:
    from email_processing.email_agent import process_email, start_imap_polling
    process_email({"from": "...", "subject": "...", "body": "..."})
"""

import email
import imaplib
import json
import logging
import threading
import time
from datetime import datetime

import config
from memory.database import insert, fetch_one, get_conn
from memory.cold_ledger import log_event

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION PROMPT
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_EMAIL_PROMPT = """You are analysing an inbound email to an Australian solar company.
Extract all structured information and determine the intent.

Return ONLY valid JSON:
{
  "intent": "quote_request|support_existing|general_inquiry|complaint|not_solar_related",
  "priority": "high|medium|low",
  "name":             "sender's full name or null",
  "email_address":    "sender's email or null",
  "phone":            "phone number mentioned or null",
  "suburb":           "suburb/city mentioned or null",
  "state":            "Australian state code or null",
  "homeowner_status": "owner|renter|unknown",
  "monthly_bill":     <number in AUD or null>,
  "roof_type":        "tile|colorbond|flat|metal|unknown or null",
  "system_size_kw":   <number or null>,
  "interested_in_battery": <true|false|null>,
  "has_ev":           <true|false|null>,
  "urgency":          "immediate|within_week|no_rush|unknown",
  "preferred_contact": "phone|email|either",
  "summary":          "2 sentence summary of the email",
  "draft_reply":      "A professional, warm reply to this email in Australian English, addressing their specific questions. Offer a free site assessment. Keep it under 150 words.",
  "crm_note":         "Internal CRM note summarising key points for the sales team (1-2 sentences)"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EMAIL PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def process_email(email_data: dict, client_id: str = "default") -> dict:
    """Process an inbound email — extract, score, update CRM, notify.

    Args:
        email_data: Dict with from_address, subject, body, to_address, received_at
        client_id: Company client ID (resolved from to_address if possible)

    Returns:
        Processing result dict
    """
    from_addr = email_data.get("from_address") or email_data.get("from", "")
    subject   = email_data.get("subject", "")
    body      = email_data.get("body") or email_data.get("text_body") or email_data.get("html_body", "")
    to_addr   = email_data.get("to_address") or email_data.get("to", "")

    # Resolve client from to_address
    if to_addr:
        client_id = _resolve_client_from_email(to_addr) or client_id

    print(f"[EMAIL AGENT] Processing email from={from_addr} subject='{subject[:60]}'")

    # ── Step 1: Extract structured data
    extracted = _extract_from_email(from_addr, subject, body)

    # ── Step 2: Skip non-solar emails
    if extracted.get("intent") == "not_solar_related":
        print(f"[EMAIL AGENT] Skipping — not solar related: {subject[:40]}")
        return {"processed": False, "reason": "not_solar_related"}

    # ── Step 3: Merge sender info into extracted data
    if not extracted.get("email_address"):
        extracted["email_address"] = from_addr

    # ── Step 4: Find or create lead in DB
    lead_id, ghl_id = _upsert_lead(extracted, client_id, email_data)

    # ── Step 5: Score the lead
    score, action = _score_lead(extracted, lead_id)

    # ── Step 6: Update GHL
    _update_ghl_from_email(ghl_id, extracted, score, action, subject)

    # ── Step 7: Log to email_logs table
    _log_email(from_addr, subject, client_id, lead_id, score, action, extracted)

    # ── Step 8: Notify Slack
    _notify_slack(extracted, score, action, subject, client_id)

    # ── Step 9: Cold ledger
    log_event("EMAIL_LEAD_PROCESSED", json.dumps({
        "from": from_addr,
        "subject": subject[:80],
        "intent": extracted.get("intent"),
        "score": score,
        "action": action,
        "client_id": client_id,
    }), agent_id="email_agent", human_involved=0)

    # ── Step 10: Store draft reply for human review (high value leads)
    draft_reply = extracted.get("draft_reply", "")
    if score and score >= 7 and draft_reply:
        _queue_draft_reply(ghl_id, from_addr, subject, draft_reply)

    print(f"[EMAIL AGENT] Done: score={score} action={action} intent={extracted.get('intent')}")
    return {
        "processed":   True,
        "lead_id":     lead_id,
        "score":       score,
        "action":      action,
        "intent":      extracted.get("intent"),
        "draft_reply": draft_reply,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_from_email(from_addr: str, subject: str, body: str) -> dict:
    """Use GPT-4o to extract structured data from an email.

    Args:
        from_addr: Sender email address
        subject: Email subject
        body: Email body (text or HTML)

    Returns:
        Extracted data dict
    """
    if not config.is_configured():
        return _rule_based_email_extract(from_addr, subject, body)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)

        # Truncate body to keep within token limits
        body_truncated = body[:3000] if len(body) > 3000 else body

        content = f"FROM: {from_addr}\nSUBJECT: {subject}\n\nBODY:\n{body_truncated}"
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_EMAIL_PROMPT},
                {"role": "user",   "content": content},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)

    except json.JSONDecodeError as e:
        logger.error(f"[EMAIL AGENT] JSON parse error: {e}")
        return _rule_based_email_extract(from_addr, subject, body)
    except Exception as e:
        logger.error(f"[EMAIL AGENT] GPT extraction failed: {e}")
        return _rule_based_email_extract(from_addr, subject, body)


def _rule_based_email_extract(from_addr: str, subject: str, body: str) -> dict:
    """Fallback rule-based extraction when OpenAI is unavailable.

    Args:
        from_addr: Sender email
        subject: Email subject
        body: Email body

    Returns:
        Basic extracted data
    """
    text = f"{subject} {body}".lower()
    intent = "general_inquiry"
    if any(w in text for w in ("quote", "price", "cost", "how much", "interest")):
        intent = "quote_request"
    elif any(w in text for w in ("issue", "problem", "not working", "fault")):
        intent = "support_existing"
    elif any(w in text for w in ("complaint", "disappointed", "unhappy")):
        intent = "complaint"

    priority = "high" if intent == "quote_request" else "medium"

    # Try to extract bill amount
    import re
    bill = None
    bill_match = re.search(r'\$(\d+)', body)
    if bill_match:
        bill = float(bill_match.group(1))

    return {
        "intent":           intent,
        "priority":         priority,
        "email_address":    from_addr,
        "name":             None,
        "phone":            None,
        "suburb":           None,
        "state":            None,
        "homeowner_status": "unknown",
        "monthly_bill":     bill,
        "urgency":          "unknown",
        "summary":          f"Email from {from_addr}: {subject[:80]}",
        "draft_reply":      None,
        "crm_note":         f"Email received: {subject[:80]}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CRM OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_lead(extracted: dict, client_id: str, email_data: dict) -> tuple:
    """Find existing lead by email or create a new one.

    Args:
        extracted: GPT-extracted email data
        client_id: Company client ID
        email_data: Original email payload

    Returns:
        Tuple of (lead_db_id, ghl_contact_id)
    """
    email_addr = extracted.get("email_address")
    ghl_id     = None

    # Check local DB
    existing = fetch_one("SELECT id FROM leads WHERE email = ?", (email_addr,)) if email_addr else {}
    db_id    = existing.get("id") if existing else None

    if db_id:
        with get_conn() as conn:
            updates = {k: v for k, v in {
                "name":             extracted.get("name"),
                "phone":            extracted.get("phone"),
                "suburb":           extracted.get("suburb"),
                "state":            extracted.get("state"),
                "homeowner_status": extracted.get("homeowner_status"),
                "monthly_bill":     extracted.get("monthly_bill"),
            }.items() if v is not None}
            if updates:
                assigns = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(f"UPDATE leads SET {assigns} WHERE id = ?", list(updates.values()) + [db_id])
    else:
        db_id = insert("leads", {
            "source":           "manual",
            "name":             extracted.get("name") or email_addr,
            "email":            email_addr,
            "phone":            extracted.get("phone"),
            "suburb":           extracted.get("suburb"),
            "state":            extracted.get("state"),
            "homeowner_status": extracted.get("homeowner_status", "unknown"),
            "monthly_bill":     extracted.get("monthly_bill"),
            "status":           "new",
            "client_account":   client_id,
            "notes":            f"Via email: {extracted.get('crm_note', '')}",
        })

    # Create/update GHL contact
    try:
        from integrations.ghl_client import create_contact, is_configured
        if is_configured() and email_addr:
            result = create_contact({
                "email":      email_addr,
                "firstName":  (extracted.get("name") or "").split()[0] if extracted.get("name") else "",
                "lastName":   " ".join((extracted.get("name") or "").split()[1:]) or "",
                "phone":      extracted.get("phone"),
                "city":       extracted.get("suburb"),
                "state":      extracted.get("state"),
                "source":     "email",
                "tags":       ["email-lead"],
            })
            if result:
                ghl_id = result.get("contact", {}).get("id")
    except Exception as e:
        logger.error(f"[EMAIL AGENT] GHL contact failed: {e}")

    return db_id, ghl_id


def _score_lead(extracted: dict, lead_id: int) -> tuple:
    """Score the email lead.

    Args:
        extracted: Extracted email data
        lead_id: Lead DB ID

    Returns:
        Tuple of (score, action)
    """
    try:
        from agents.qualification_agent import qualify
        lead_data = {
            "name":             extracted.get("name", "Email Lead"),
            "email":            extracted.get("email_address"),
            "homeowner_status": extracted.get("homeowner_status", "unknown"),
            "monthly_bill":     extracted.get("monthly_bill"),
            "state":            extracted.get("state"),
        }
        result = qualify(lead_data, lead_id)
        return result.get("score"), result.get("recommended_action")
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Scoring failed: {e}")
        return None, "nurture"


def _update_ghl_from_email(ghl_id: str, extracted: dict, score, action: str, subject: str):
    """Update GHL contact with email-derived data.

    Args:
        ghl_id: GHL contact ID
        extracted: Extracted data
        score: Lead score
        action: Recommended action
        subject: Email subject
    """
    if not ghl_id:
        return
    try:
        from integrations.ghl_client import update_contact_field, add_contact_tag, is_configured
        if not is_configured():
            return

        if score:
            update_contact_field(ghl_id, "ai_lead_score",         str(score))
            update_contact_field(ghl_id, "ai_recommended_action", action or "")
        if extracted.get("homeowner_status"):
            update_contact_field(ghl_id, "homeowner_status", extracted["homeowner_status"])
        if extracted.get("monthly_bill"):
            update_contact_field(ghl_id, "monthly_electricity_bill", str(extracted["monthly_bill"]))
        if extracted.get("crm_note"):
            update_contact_field(ghl_id, "ai_email_summary", extracted["crm_note"][:500])

        add_contact_tag(ghl_id, "email-inquiry")
        add_contact_tag(ghl_id, f"intent-{extracted.get('intent','unknown')}")
        if score and score >= 7:
            add_contact_tag(ghl_id, "hot-lead")
        if extracted.get("interested_in_battery"):
            add_contact_tag(ghl_id, "battery-interest")

    except Exception as e:
        logger.error(f"[EMAIL AGENT] GHL update failed: {e}")


def _queue_draft_reply(ghl_id: str, to_email: str, subject: str, draft: str):
    """Store the AI-drafted reply for human review before sending.

    Creates a GHL note with the draft so the sales team can review and send.

    Args:
        ghl_id: GHL contact ID
        to_email: Recipient email
        subject: Email subject
        draft: Draft reply text
    """
    try:
        from integrations.ghl_client import update_contact_field, is_configured
        if ghl_id and is_configured():
            update_contact_field(ghl_id, "ai_draft_reply", f"Re: {subject}\n\n{draft}")
        print(f"[EMAIL AGENT] Draft reply queued for {to_email} — review in GHL before sending")
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Draft reply failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def _log_email(from_addr: str, subject: str, client_id: str, lead_id: int, score, action: str, extracted: dict):
    """Log processed email to email_logs table.

    Args:
        from_addr: Sender email
        subject: Email subject
        client_id: Client ID
        lead_id: Lead DB ID
        score: Lead score
        action: Recommended action
        extracted: Extracted data
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO email_logs
                   (from_address, subject, client_id, lead_id, intent, score, action, summary, received_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (from_addr, subject[:200], client_id, lead_id,
                 extracted.get("intent"), score, action,
                 extracted.get("summary", "")[:500],
                 datetime.utcnow().isoformat())
            )
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Log failed: {e}")


def _notify_slack(extracted: dict, score, action: str, subject: str, client_id: str):
    """Post Slack notification for inbound email.

    Args:
        extracted: Extracted data
        score: Lead score
        action: Recommended action
        subject: Email subject
        client_id: Client ID
    """
    try:
        from notifications.slack_notifier import _post
        intent = extracted.get("intent", "unknown")
        if intent == "not_solar_related":
            return

        score_emoji = "🔥" if (score or 0) >= 7 else "📋" if (score or 0) >= 5 else "📧"
        priority    = extracted.get("priority", "medium")
        urgency     = extracted.get("urgency", "unknown")
        name        = extracted.get("name") or extracted.get("email_address", "Unknown")

        msg = (
            f"{score_emoji} *Inbound Email — {intent.replace('_',' ').title()}*\n"
            f"*From:* {name}  |  *Score:* {score}/10\n"
            f"*Subject:* {subject[:60]}\n"
            f"*Priority:* {priority}  |  *Urgency:* {urgency}  |  *Action:* {action}\n"
        )
        if extracted.get("summary"):
            msg += f"*Summary:* _{extracted['summary']}_"
        if action == "call_now":
            msg += "\n*Call this lead now — high value email inquiry!*"

        _post(msg)

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Slack failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# IMAP POLLING (optional — direct inbox reading)
# ─────────────────────────────────────────────────────────────────────────────

def start_imap_polling(interval_seconds: int = 120):
    """Start background thread that polls the configured IMAP inbox.

    Only starts if IMAP_HOST, IMAP_USER, IMAP_PASS are configured.
    Processes all unread emails in the inbox.

    Args:
        interval_seconds: How often to check (default: 2 minutes)
    """
    if not all([config.get("IMAP_HOST"), config.get("IMAP_USER"), config.get("IMAP_PASS")]):
        print("[EMAIL AGENT] IMAP not configured — skipping inbox polling (set IMAP_HOST/USER/PASS in .env)")
        return

    def _poll():
        print(f"[EMAIL AGENT] IMAP polling started — checking every {interval_seconds}s")
        while True:
            try:
                _check_imap_inbox()
            except Exception as e:
                logger.error(f"[EMAIL AGENT] IMAP poll error: {e}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_poll, daemon=True, name="IMAPPoller")
    thread.start()
    print("[EMAIL AGENT] IMAP polling thread started")


def _check_imap_inbox():
    """Connect to IMAP inbox and process all unread emails."""
    host     = config.get("IMAP_HOST", "imap.gmail.com")
    user     = config.get("IMAP_USER", "")
    password = config.get("IMAP_PASS", "")
    folder   = config.get("IMAP_FOLDER", "INBOX")
    client_id = config.get("DEFAULT_CLIENT_ID", "default")

    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select(folder)

        _, msgs = mail.search(None, "UNSEEN")
        msg_ids = msgs[0].split()

        if not msg_ids:
            return

        print(f"[EMAIL AGENT] {len(msg_ids)} unread emails found")

        for msg_id in msg_ids:
            try:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw_email   = msg_data[0][1]
                msg         = email.message_from_bytes(raw_email)

                from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                subject   = msg.get("Subject", "")
                body      = _extract_email_body(msg)

                process_email({
                    "from_address": from_addr,
                    "subject":      subject,
                    "body":         body,
                    "received_at":  msg.get("Date", ""),
                }, client_id=client_id)

                # Mark as read
                mail.store(msg_id, "+FLAGS", "\\Seen")

            except Exception as e:
                logger.error(f"[EMAIL AGENT] Error processing msg {msg_id}: {e}")

        mail.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"[EMAIL AGENT] IMAP auth error: {e}")


def _extract_email_body(msg) -> str:
    """Extract plain text body from an email.Message object.

    Args:
        msg: email.Message object

    Returns:
        Plain text body string
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except Exception:
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            body = ""
    return body


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_client_from_email(to_address: str) -> str | None:
    """Resolve client_id from the email address the message was sent to.

    Each solar company client can have their own forwarding email address.

    Args:
        to_address: Email address the message was sent to

    Returns:
        client_id or None
    """
    try:
        row = fetch_one(
            "SELECT client_id FROM company_profiles WHERE email = ? AND active = 1",
            (to_address,)
        )
        return row.get("client_id") if row else None
    except Exception:
        return None
