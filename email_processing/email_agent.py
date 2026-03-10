"""Email Processing Agent — classify, score, draft, and route inbound emails.

Handles emails from two sources:
  1. GHL webhook (POST /webhook/email-received wired in main.py)
  2. Direct IMAP polling (optional — set IMAP_HOST/USER/PASS in .env)

For each email:
  a) Classify: NEW_ENQUIRY | QUOTE_REQUEST | COMPLAINT | BOOKING_REQUEST | SPAM | OTHER
  b) Extract: sender name, phone, suburb, system size interest, urgency signals
  c) Score urgency 1-10
  d) Draft a GPT-4o reply matching company tone, answering their question,
     ending with a CTA to book a free assessment, signed off as
     "The [Company Name] Team"
  e) urgency >= 8  → auto-send via GHL + Slack alert
     urgency 5-7   → queue draft for human-gate approval
     urgency < 5 or SPAM → log and discard

Usage:
    from email_processing.email_agent import process_email
    process_email({"from": "...", "subject": "...", "body": "..."})
"""

import email
import email.utils
import imaplib
import json
import logging
import re
import threading
import time
from datetime import datetime

import config
from memory.database import insert, fetch_one, update, get_conn

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# ENSURE EMAILS TABLE EXISTS (owned by this module)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_emails_table():
    """Create the emails table if it does not already exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at     TEXT DEFAULT (datetime('now')),
                from_email      TEXT NOT NULL,
                from_name       TEXT,
                subject         TEXT,
                body            TEXT,
                classification  TEXT
                    CHECK(classification IN (
                        'NEW_ENQUIRY','QUOTE_REQUEST','COMPLAINT',
                        'BOOKING_REQUEST','SPAM','OTHER')),
                urgency_score   INTEGER DEFAULT 0,
                draft_reply     TEXT,
                status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','sent','discarded')),
                ghl_contact_id  TEXT
            )
        """)


# Run once on import
_ensure_emails_table()


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION + EXTRACTION PROMPT
# ─────────────────────────────────────────────────────────────────────────────

_CLASSIFY_PROMPT = """You are processing an inbound email for an Australian solar company.

Analyse the email and return ONLY valid JSON with these fields:

{
  "classification": "NEW_ENQUIRY|QUOTE_REQUEST|COMPLAINT|BOOKING_REQUEST|SPAM|OTHER",
  "urgency_score": <integer 1-10>,
  "urgency_signals": ["list of phrases signalling urgency"],
  "from_name": "sender full name or null",
  "phone": "phone number if mentioned or null",
  "suburb": "suburb or city mentioned or null",
  "system_size_kw": <number or null>,
  "battery_interest": <true|false|null>,
  "summary": "one sentence describing the email"
}

Urgency scoring guide:
  9-10: Ready to buy now, requesting immediate callback, very time-sensitive
  7-8:  Actively comparing quotes, clear intent to proceed soon
  5-6:  Interested but no specific timeline
  3-4:  Early research, no clear intent
  1-2:  Spam, completely off-topic, or bot

Classification guide:
  NEW_ENQUIRY    — first contact, general interest in solar
  QUOTE_REQUEST  — asking for a price or quote
  COMPLAINT      — unhappy with existing installation or service
  BOOKING_REQUEST— wants to book a site visit or assessment
  SPAM           — marketing, unsolicited, bot
  OTHER          — anything else that is solar-related
"""

_DRAFT_PROMPT = """You are a friendly but professional solar consultant replying on behalf of {company_name}.

Write a reply email to {from_name} who sent: "{summary}"

Requirements:
- Warm, professional Australian English (not American)
- Directly answer their specific question or acknowledge their request
- Include a clear CTA to book a free solar assessment
- Keep it under 160 words
- Sign off as "The {company_name} Team"
- Do NOT include a subject line — body only

Previous thread context (newest first):
{thread_context}
"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def process_email(email_data: dict, client_id: str = "default") -> dict:
    """Process one inbound email end-to-end.

    Args:
        email_data: Dict with keys: from_address (or from), subject, body
                    (also accepts text_body, html_body, to_address/to)
        client_id:  Solar company client ID; resolved from to_address if possible

    Returns:
        Result dict with keys: processed, email_id, classification,
        urgency_score, status, draft_reply
    """
    from_addr = email_data.get("from_address") or email_data.get("from", "")
    subject   = email_data.get("subject", "")
    body      = (email_data.get("body")
                 or email_data.get("text_body")
                 or email_data.get("html_body", ""))
    to_addr   = email_data.get("to_address") or email_data.get("to", "")

    if to_addr:
        client_id = _resolve_client_from_email(to_addr) or client_id

    # ── 0. Check master kill-switch
    try:
        from api.settings_api import get_setting
        if get_setting("email.agent_enabled", "true") != "true":
            print("[EMAIL AGENT] Disabled via settings — skipping")
            return {"processed": False, "reason": "email agent disabled"}
    except Exception:
        pass  # settings not yet available — allow through

    print(f"[EMAIL AGENT] Processing from={from_addr} subject='{subject[:60]}'")

    # ── 1. Classify & extract
    extracted = _classify_and_extract(from_addr, subject, body)
    classification = extracted.get("classification", "OTHER")
    urgency        = int(extracted.get("urgency_score", 1))

    # ── 2. Discard immediately based on settings
    try:
        from api.settings_api import get_setting as _gs
        _auto_discard_spam = _gs("email.auto_discard_spam", "true") == "true"
    except Exception:
        _auto_discard_spam = True

    if (_auto_discard_spam and classification == "SPAM") or urgency < 5:
        email_id = _save_email(
            from_addr, extracted.get("from_name"), subject, body,
            classification, urgency, draft_reply=None,
            status="discarded", ghl_contact_id=None,
        )
        print(f"[EMAIL AGENT] Discarded — class={classification} urgency={urgency}")
        return {"processed": True, "email_id": email_id,
                "classification": classification, "urgency_score": urgency,
                "status": "discarded", "draft_reply": None}

    # ── 3. Fetch company info and thread context
    company_name  = _get_company_name(client_id)
    ghl_contact_id = _resolve_ghl_contact(from_addr)
    thread_context = _get_thread_context(ghl_contact_id)

    # ── 4. Draft reply
    try:
        from api.settings_api import get_setting as _gs
        _custom_prompt = _gs("email.reply_prompt", "") or ""
    except Exception:
        _custom_prompt = ""

    draft = _draft_reply(
        company_name=company_name,
        from_name=extracted.get("from_name") or from_addr,
        summary=extracted.get("summary") or subject,
        thread_context=thread_context,
        custom_instructions=_custom_prompt,
    )

    # ── 5. Persist to emails table (initially pending)
    email_id = _save_email(
        from_addr, extracted.get("from_name"), subject, body,
        classification, urgency, draft_reply=draft,
        status="pending", ghl_contact_id=ghl_contact_id,
    )

    # ── 6. Route by urgency + settings
    try:
        from api.settings_api import get_setting as _gs
        _auto_send_on  = _gs("email.auto_send_enabled", "false") == "true"
        _auto_threshold = int(_gs("email.auto_send_threshold", "9") or "9")
    except Exception:
        _auto_send_on, _auto_threshold = False, 9

    if _auto_send_on and urgency >= _auto_threshold:
        _auto_send(email_id, from_addr, subject, draft, ghl_contact_id)
        _notify_auto_sent(from_addr, subject, classification, urgency, draft)
        status = "sent"
    else:
        # Queue for human review
        _notify_draft_for_approval(email_id, subject, from_addr, classification, urgency, draft)
        status = "pending"

    # Update status in DB
    update("emails", email_id, {"status": status})

    print(f"[EMAIL AGENT] Done email_id={email_id} class={classification} "
          f"urgency={urgency} status={status}")
    return {
        "processed":      True,
        "email_id":       email_id,
        "classification": classification,
        "urgency_score":  urgency,
        "status":         status,
        "draft_reply":    draft,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION & EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _classify_and_extract(from_addr: str, subject: str, body: str) -> dict:
    """Use GPT-4o to classify the email and extract key fields.

    Args:
        from_addr: Sender email
        subject:   Email subject
        body:      Email body text

    Returns:
        Extracted data dict; falls back to rule-based if GPT unavailable
    """
    if not config.is_configured():
        return _rule_based_classify(from_addr, subject, body)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        content = f"FROM: {from_addr}\nSUBJECT: {subject}\n\nBODY:\n{body[:3000]}"
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFY_PROMPT},
                {"role": "user",   "content": content},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)

    except json.JSONDecodeError as e:
        logger.error(f"[EMAIL AGENT] JSON parse error in classify: {e}")
        return _rule_based_classify(from_addr, subject, body)
    except Exception as e:
        logger.error(f"[EMAIL AGENT] GPT classify failed: {e}")
        return _rule_based_classify(from_addr, subject, body)


def _rule_based_classify(from_addr: str, subject: str, body: str) -> dict:
    """Fallback rule-based classifier used when OpenAI is unavailable.

    Args:
        from_addr: Sender email
        subject:   Email subject
        body:      Email body

    Returns:
        Basic classification dict
    """
    text = f"{subject} {body}".lower()

    if any(w in text for w in ("unsubscribe", "click here", "dear valued", "winner")):
        return {"classification": "SPAM", "urgency_score": 1,
                "urgency_signals": [], "from_name": None,
                "phone": None, "suburb": None, "summary": subject[:80]}

    if any(w in text for w in ("book", "schedule", "appointment", "site visit")):
        classification, urgency = "BOOKING_REQUEST", 7
    elif any(w in text for w in ("quote", "price", "cost", "how much")):
        classification, urgency = "QUOTE_REQUEST", 6
    elif any(w in text for w in ("complaint", "unhappy", "disappointed", "issue", "problem")):
        classification, urgency = "COMPLAINT", 6
    elif any(w in text for w in ("interested", "enquire", "enquiry", "information")):
        classification, urgency = "NEW_ENQUIRY", 5
    else:
        classification, urgency = "OTHER", 4

    phone_match = re.search(r'(\b04\d{8}\b|\b\+?61\s?4\d{2}\s?\d{3}\s?\d{3}\b)', body)
    phone = phone_match.group(0) if phone_match else None

    return {
        "classification": classification,
        "urgency_score":  urgency,
        "urgency_signals": [],
        "from_name":      None,
        "phone":          phone,
        "suburb":         None,
        "system_size_kw": None,
        "battery_interest": None,
        "summary":        f"Email from {from_addr}: {subject[:80]}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT REPLY
# ─────────────────────────────────────────────────────────────────────────────

def _draft_reply(company_name: str, from_name: str, summary: str,
                 thread_context: str = "", custom_instructions: str = "") -> str:
    """Generate a GPT-4o reply draft matching the company's tone.

    Args:
        company_name:   Solar company display name
        from_name:      Sender name for personalisation
        summary:        One-line summary of their email
        thread_context: Prior thread messages for context

    Returns:
        Draft reply body text
    """
    if not config.is_configured():
        return _fallback_draft(company_name, from_name)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        extra = f"\n\nAdditional instructions: {custom_instructions}" if custom_instructions else ""
        prompt = _DRAFT_PROMPT.format(
            company_name=company_name,
            from_name=from_name,
            summary=summary,
            thread_context=thread_context or "No prior messages.",
        ) + extra
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=350,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[EMAIL AGENT] Draft reply failed: {e}")
        return _fallback_draft(company_name, from_name)


def _fallback_draft(company_name: str, from_name: str) -> str:
    """Static fallback reply when GPT is unavailable.

    Args:
        company_name: Solar company name
        from_name:    Sender's name

    Returns:
        Generic reply string
    """
    return (
        f"Hi {from_name},\n\n"
        "Thank you for reaching out to us! We'd love to help you explore your "
        "solar options.\n\n"
        "To get started, we'd like to offer you a free, no-obligation solar "
        "assessment at your property. One of our specialists will assess your "
        "roof, review your electricity usage, and give you a personalised "
        "recommendation.\n\n"
        "Reply to this email or call us to book your free assessment today.\n\n"
        f"The {company_name} Team"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-SEND (urgency >= 8)
# ─────────────────────────────────────────────────────────────────────────────

def _auto_send(email_id: int, to_email: str, subject: str,
               draft: str, ghl_contact_id: str | None):
    """Send the draft reply automatically via GHL and log the result.

    Args:
        email_id:       DB row id in emails table
        to_email:       Recipient email
        subject:        Original email subject (used to form Re: subject)
        draft:          Draft reply body
        ghl_contact_id: GHL contact ID (may be None)
    """
    try:
        from email_processing.email_sender import send_via_ghl
        result = send_via_ghl(to_email, f"Re: {subject}", draft)
        if result:
            print(f"[EMAIL AGENT] Auto-sent reply to {to_email} (email_id={email_id})")
        else:
            logger.error(f"[EMAIL AGENT] Auto-send failed for email_id={email_id}")
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Auto-send error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _notify_auto_sent(from_email: str, subject: str, classification: str,
                      urgency: int, draft: str):
    """Post a Slack alert when a reply was automatically sent.

    Args:
        from_email:     Sender email
        subject:        Email subject
        classification: Classified intent
        urgency:        Urgency score
        draft:          The reply that was sent
    """
    try:
        from notifications.slack_notifier import _post, _block
        msg = (
            f"*🚀 Email Auto-Replied* (urgency {urgency}/10)\n"
            f"*From:* {from_email}\n"
            f"*Subject:* {subject[:80]}\n"
            f"*Classification:* {classification}\n"
            f"*Sent reply preview:* _{draft[:200]}..._"
        )
        _post({"blocks": [_block(msg)]})
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Slack auto-sent notify failed: {e}")


def _notify_draft_for_approval(email_id: int, subject: str, from_email: str,
                                classification: str, urgency: int, draft: str):
    """Send Slack notification with approve/discard buttons for the draft.

    Args:
        email_id:       DB row id for the email
        subject:        Email subject
        from_email:     Sender email
        classification: Classified intent
        urgency:        Urgency score
        draft:          Drafted reply text
    """
    try:
        from notifications.slack_notifier import notify_email_draft
        notify_email_draft(
            email_id=email_id,
            subject=subject,
            from_email=from_email,
            classification=classification,
            urgency=urgency,
            draft_preview=draft[:300],
        )
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Slack draft notify failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _save_email(from_email: str, from_name: str | None, subject: str,
                body: str, classification: str, urgency_score: int,
                draft_reply: str | None, status: str,
                ghl_contact_id: str | None) -> int:
    """Persist an inbound email record to the emails table.

    Args:
        from_email:     Sender email address
        from_name:      Sender name (may be None)
        subject:        Email subject
        body:           Email body (truncated to 10000 chars for storage)
        classification: One of the 6 classification values
        urgency_score:  Integer 1-10
        draft_reply:    AI-drafted reply text or None
        status:         pending | sent | discarded
        ghl_contact_id: GHL contact ID or None

    Returns:
        New row id
    """
    return insert("emails", {
        "from_email":     from_email,
        "from_name":      from_name,
        "subject":        subject[:200] if subject else "",
        "body":           body[:10000] if body else "",
        "classification": classification,
        "urgency_score":  urgency_score,
        "draft_reply":    draft_reply,
        "status":         status,
        "ghl_contact_id": ghl_contact_id,
    })


# ─────────────────────────────────────────────────────────────────────────────
# GHL / CRM HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_ghl_contact(from_email: str) -> str | None:
    """Fetch or create a GHL contact for the sender.

    Args:
        from_email: Sender email address

    Returns:
        GHL contact ID or None
    """
    try:
        from integrations.ghl_client import create_contact, is_configured
        if not is_configured():
            return None
        result = create_contact({
            "email":  from_email,
            "source": "email",
            "tags":   ["email-lead"],
        })
        return result.get("contact", {}).get("id") if result else None
    except Exception as e:
        logger.error(f"[EMAIL AGENT] GHL contact failed: {e}")
        return None


def _get_thread_context(ghl_contact_id: str | None) -> str:
    """Return the last 5 email messages as formatted context text.

    Args:
        ghl_contact_id: GHL contact ID or None

    Returns:
        Formatted string with prior messages, or empty string
    """
    if not ghl_contact_id:
        return ""
    try:
        from email_processing.email_sender import get_thread_history
        messages = get_thread_history(ghl_contact_id, limit=5)
        if not messages:
            return ""
        lines = []
        for m in messages:
            direction = "↓ Inbound" if m.get("direction") == "inbound" else "↑ Outbound"
            body_snippet = (m.get("body") or m.get("text") or "")[:150]
            lines.append(f"{direction}: {body_snippet}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[EMAIL AGENT] Thread context failed: {e}")
        return ""


def _get_company_name(client_id: str) -> str:
    """Fetch the display name for a solar company client.

    Args:
        client_id: Client ID string

    Returns:
        Company name string (falls back to 'Your Solar Team')
    """
    try:
        row = fetch_one(
            "SELECT company_name, name FROM company_profiles WHERE client_id = ?",
            (client_id,),
        )
        return row.get("company_name") or row.get("name") or "Your Solar Team"
    except Exception:
        return "Your Solar Team"


def _resolve_client_from_email(to_address: str) -> str | None:
    """Resolve client_id from the email address the message was sent to.

    Args:
        to_address: The recipient email address

    Returns:
        client_id or None
    """
    try:
        row = fetch_one(
            "SELECT client_id FROM company_profiles WHERE email = ? AND active = 1",
            (to_address,),
        )
        return row.get("client_id") if row else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# IMAP POLLING (optional — polls a direct inbox)
# ─────────────────────────────────────────────────────────────────────────────

def start_imap_polling(interval_seconds: int = 120):
    """Start background thread that polls the configured IMAP inbox.

    Only starts if IMAP_HOST, IMAP_USER, IMAP_PASS are configured.

    Args:
        interval_seconds: How often to check in seconds (default 2 min)
    """
    if not all([config.IMAP_HOST, config.IMAP_USER, config.IMAP_PASS]):
        print("[EMAIL AGENT] IMAP not configured — skipping inbox polling")
        return

    def _poll():
        print(f"[EMAIL AGENT] IMAP polling started — every {interval_seconds}s")
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
    """Connect to IMAP and process all unread messages."""
    host      = config.IMAP_HOST
    user      = config.IMAP_USER
    password  = config.IMAP_PASS
    folder    = config.IMAP_FOLDER
    client_id = config.DEFAULT_CLIENT_ID

    mail = imaplib.IMAP4_SSL(host)
    mail.login(user, password)
    mail.select(folder)

    _, msgs = mail.search(None, "UNSEEN")
    msg_ids = msgs[0].split()
    if not msg_ids:
        mail.logout()
        return

    print(f"[EMAIL AGENT] {len(msg_ids)} unread email(s) found via IMAP")
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
            }, client_id=client_id)

            mail.store(msg_id, "+FLAGS", "\\Seen")

        except Exception as e:
            logger.error(f"[EMAIL AGENT] IMAP msg {msg_id} error: {e}")

    mail.logout()


def _extract_email_body(msg) -> str:
    """Extract plain text body from an email.Message object.

    Args:
        msg: email.Message object

    Returns:
        Plain text body string
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return ""
