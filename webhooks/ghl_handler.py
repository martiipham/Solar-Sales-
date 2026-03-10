"""GHL Webhook Server — Receives native events from GoHighLevel.

Flask server on port 5001.

Routes:
  POST /webhook/ghl          — unified GHL native event handler
  POST /webhook/new-lead     — legacy: new contact created in GHL
  POST /webhook/call-complete — legacy: voice call completed
  POST /webhook/form-submit  — legacy: solar quote form submitted
  POST /webhook/stage-change — legacy: pipeline stage updated
  GET  /health               — returns 200 OK

Native GHL event types handled via /webhook/ghl:
  ContactCreated / contact.created    → upsert to local leads table
  OpportunityStatusChanged            → update local lead status
  InboundMessage                      → route to email_agent (email) or log (SMS)
  All events                          → log to agent_run_log
"""

import hashlib
import hmac
import logging
from datetime import datetime
from flask import Flask, request, jsonify

from memory.database import get_conn, fetch_one, insert, json_payload
from agents.qualification_agent import qualify
import config

logger = logging.getLogger(__name__)

ghl_app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY HEADERS
# ─────────────────────────────────────────────────────────────────────────────

@ghl_app.after_request
def _security_headers(response):
    """Attach security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _verify_ghl_signature(req) -> bool:
    """Verify GHL webhook HMAC-SHA256 signature.

    If GHL_WEBHOOK_SECRET is not set, allows the request through with a warning
    so existing setups without a secret keep working.

    Args:
        req: Flask request object

    Returns:
        True if signature is valid or no secret is configured
    """
    if not config.GHL_WEBHOOK_SECRET:
        logger.warning("[GHL WEBHOOK] GHL_WEBHOOK_SECRET not set — skipping signature check")
        return True

    sig = req.headers.get("X-GHL-Signature", "")
    if not sig:
        return False

    expected = hmac.new(
        config.GHL_WEBHOOK_SECRET.encode(),
        req.get_data(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, sig)


def _log_agent_run(event_type: str, status: str, notes: str = ""):
    """Log a webhook event to the agent_run_log table.

    Args:
        event_type: GHL event type string (e.g. 'ContactCreated')
        status: 'ok' or 'error'
        notes: Optional extra context (truncated to 500 chars)
    """
    try:
        insert("agent_run_log", {
            "job_id": f"ghl_webhook_{event_type}",
            "status": status,
            "notes":  (notes or "")[:500],
        })
    except Exception as e:
        logger.error(f"[GHL WEBHOOK] agent_run_log write failed: {e}")


def _safe_like(value: str) -> str:
    """Escape LIKE special characters to prevent SQL wildcard injection.

    Args:
        value: Raw string to use inside a LIKE pattern

    Returns:
        Escaped string safe for: WHERE col LIKE '%' || ? || '%' ESCAPE '\\'
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_number(value) -> float | None:
    """Safely parse a number from a string or numeric value.

    Args:
        value: Any value to parse

    Returns:
        Float or None
    """
    if value is None:
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _extract_lead_data(data: dict) -> dict:
    """Extract standardised lead fields from a GHL webhook payload.

    Handles both the legacy custom format and GHL native event payloads.

    Args:
        data: Raw GHL webhook payload

    Returns:
        Standardised lead dict
    """
    name = (
        data.get("full_name")
        or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        or data.get("name", "Unknown")
    )
    # customField may be a dict (legacy) or a list of {id, value} (native)
    cf = data.get("customField") or data.get("customFields") or {}
    if isinstance(cf, list):
        cf = {item.get("id", ""): item.get("value", "") for item in cf}

    return {
        "name":             name,
        "phone":            data.get("phone") or data.get("phoneRaw"),
        "email":            data.get("email"),
        "suburb":           data.get("suburb") or data.get("city"),
        "state":            data.get("state"),
        "homeowner_status": data.get("homeowner_status") or cf.get("homeowner_status"),
        "monthly_bill":     _parse_number(data.get("monthly_bill") or cf.get("monthly_bill")),
        "roof_type":        data.get("roof_type") or cf.get("roof_type"),
        "roof_age":         _parse_number(data.get("roof_age") or cf.get("roof_age")),
        "pipeline_stage":   data.get("pipelineStage") or data.get("pipeline_stage"),
        "client_account":   data.get("locationId") or data.get("client_account", "default"),
    }


def _upsert_lead_from_contact(contact: dict) -> int | None:
    """Insert or update a local lead from a GHL contact dict.

    Matches on phone first, then email.

    Args:
        contact: GHL contact dict from a native event payload

    Returns:
        Lead DB id or None on failure
    """
    lead_data = _extract_lead_data(contact)
    phone = lead_data.get("phone") or ""
    email = lead_data.get("email") or ""
    now   = datetime.utcnow().isoformat()

    existing = None
    if phone:
        existing = fetch_one("SELECT id FROM leads WHERE phone = ? LIMIT 1", (phone,))
    if not existing and email:
        existing = fetch_one("SELECT id FROM leads WHERE email = ? LIMIT 1", (email,))

    if existing:
        db_id = existing.get("id")
        with get_conn() as conn:
            conn.execute(
                """UPDATE leads SET
                   name   = COALESCE(?, name),
                   email  = COALESCE(?, email),
                   suburb = COALESCE(?, suburb),
                   state  = COALESCE(?, state)
                   WHERE id = ?""",
                (
                    lead_data.get("name") or None,
                    email or None,
                    lead_data.get("suburb") or None,
                    lead_data.get("state") or None,
                    db_id,
                ),
            )
        return db_id

    return insert("leads", {
        "source":           "ghl_webhook",
        "name":             lead_data.get("name"),
        "phone":            phone or None,
        "email":            email or None,
        "suburb":           lead_data.get("suburb"),
        "state":            lead_data.get("state"),
        "homeowner_status": lead_data.get("homeowner_status"),
        "monthly_bill":     lead_data.get("monthly_bill"),
        "roof_type":        lead_data.get("roof_type"),
        "pipeline_stage":   lead_data.get("pipeline_stage"),
        "status":           "new",
        "client_account":   lead_data.get("client_account", "default"),
        "notes":            f"Created via GHL webhook at {now}",
    })


# ─────────────────────────────────────────────────────────────────────────────
# NATIVE EVENT HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def _handle_contact_created(data: dict):
    """Handle ContactCreated — upsert contact to local leads table.

    Args:
        data: Full GHL event payload
    """
    contact = data.get("contact") or data
    db_id   = _upsert_lead_from_contact(contact)
    name    = contact.get("name") or contact.get("firstName", "Unknown")
    print(f"[GHL WEBHOOK] ContactCreated: {name} → lead db_id={db_id}")
    _log_agent_run("ContactCreated", "ok", f"lead_id={db_id} name={name}")


def _handle_opportunity_status_changed(data: dict):
    """Handle OpportunityStatusChanged — update local lead status.

    Args:
        data: Full GHL event payload
    """
    opp        = data.get("opportunity") or data
    status     = opp.get("status", "")
    contact_id = opp.get("contactId") or opp.get("contact_id") or ""
    opp_id     = opp.get("id", "unknown")

    status_map = {
        "won":       "converted",
        "lost":      "not_interested",
        "open":      "contacted",
        "abandoned": "not_interested",
    }
    local_status = status_map.get(status.lower(), "contacted")

    if contact_id:
        safe_id = _safe_like(str(contact_id))
        with get_conn() as conn:
            conn.execute(
                r"UPDATE leads SET status = ?, pipeline_stage = ? "
                r"WHERE notes LIKE ? ESCAPE '\'",
                (local_status, status, f"%{safe_id}%"),
            )
            if local_status == "converted":
                conn.execute(
                    r"UPDATE leads SET converted_at = ? "
                    r"WHERE notes LIKE ? ESCAPE '\'",
                    (datetime.utcnow().isoformat(), f"%{safe_id}%"),
                )

    print(f"[GHL WEBHOOK] OpportunityStatusChanged: opp={opp_id} {status} → {local_status}")
    _log_agent_run("OpportunityStatusChanged", "ok",
                   f"opp_id={opp_id} contact={contact_id} status={status}")


def _handle_inbound_message(data: dict):
    """Handle InboundMessage — route emails to email_agent, log SMS.

    Args:
        data: Full GHL event payload
    """
    msg_type  = (data.get("messageType") or data.get("type", "")).lower()
    from_addr = data.get("from") or data.get("email") or ""
    subject   = data.get("subject") or ""
    body      = data.get("body") or data.get("message") or ""
    conv_id   = data.get("conversationId", "")

    if msg_type == "email":
        try:
            from email_processing.email_agent import process_email
            process_email({
                "from":    from_addr,
                "subject": subject,
                "body":    body,
                "source":  "ghl_inbound",
            })
            print(f"[GHL WEBHOOK] InboundMessage (email) → email_agent: {from_addr}")
            _log_agent_run("InboundMessage_Email", "ok",
                           f"from={from_addr} subject={subject[:80]}")
        except Exception as e:
            logger.error(f"[GHL WEBHOOK] email_agent routing failed: {e}")
            _log_agent_run("InboundMessage_Email", "error", str(e)[:200])
    else:
        print(f"[GHL WEBHOOK] InboundMessage (SMS) from {from_addr}: {body[:80]}")
        _log_agent_run("InboundMessage_SMS", "ok",
                       f"from={from_addr} conv={conv_id} body={body[:120]}")


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED NATIVE WEBHOOK ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@ghl_app.route("/webhook/ghl", methods=["POST"])
def ghl_event():
    """Unified GHL native event handler.

    GHL sends all native events to a single URL. This route reads the
    event type field and dispatches to the correct handler.
    All events are logged to agent_run_log regardless of type.
    """
    if not _verify_ghl_signature(request):
        logger.warning("[GHL WEBHOOK] /webhook/ghl: invalid signature")
        return jsonify({"error": "Invalid signature"}), 401

    try:
        data       = request.get_json(force=True) or {}
        event_type = (
            data.get("type")
            or data.get("event")
            or data.get("eventType")
            or "unknown"
        )
        print(f"[GHL WEBHOOK] Native event: {event_type}")

        # Normalise to lowercase without separators for matching
        et = event_type.lower().replace(".", "").replace("_", "")

        if et == "contactcreated":
            _handle_contact_created(data)
        elif et == "opportunitystatuschanged":
            _handle_opportunity_status_changed(data)
        elif et == "inboundmessage":
            _handle_inbound_message(data)
        else:
            logger.info(f"[GHL WEBHOOK] Unhandled event type: {event_type}")
            _log_agent_run(event_type, "ok", "Unhandled — logged only")

        return jsonify({"status": "processed", "event": event_type}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] /webhook/ghl error: {e}")
        _log_agent_run("unknown", "error", str(e)[:200])
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@ghl_app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status":    "ok",
        "service":   "ghl-webhooks",
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@ghl_app.route("/webhook/new-lead", methods=["POST"])
def new_lead():
    """Handle a new contact/lead arriving in GHL (legacy format).

    Saves lead to database and triggers qualification.
    Logs result to agent_run_log.
    """
    if not _verify_ghl_signature(request):
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data      = request.get_json(force=True) or {}
        lead_data = _extract_lead_data(data)
        print(f"[GHL WEBHOOK] New lead: {lead_data.get('name', 'Unknown')}")

        lead_id = insert("leads", {
            "source":           "ghl_webhook",
            "name":             lead_data.get("name"),
            "phone":            lead_data.get("phone"),
            "email":            lead_data.get("email"),
            "suburb":           lead_data.get("suburb"),
            "state":            lead_data.get("state"),
            "homeowner_status": lead_data.get("homeowner_status"),
            "monthly_bill":     lead_data.get("monthly_bill"),
            "roof_type":        lead_data.get("roof_type"),
            "roof_age":         lead_data.get("roof_age"),
            "pipeline_stage":   lead_data.get("pipeline_stage", "new"),
            "client_account":   lead_data.get("client_account", "default"),
            "notes":            json_payload(data),
        })

        result = qualify(lead_data, lead_id)
        _log_agent_run("new_lead", "ok", f"lead_id={lead_id} score={result.get('score')}")
        return jsonify({"status": "processed", "lead_id": lead_id,
                        "score": result.get("score")}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] new-lead error: {e}")
        _log_agent_run("new_lead", "error", str(e)[:200])
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@ghl_app.route("/webhook/call-complete", methods=["POST"])
def call_complete():
    """Handle a completed voice AI call event from GHL (legacy).

    Updates lead status based on call outcome.
    Logs result to agent_run_log.
    """
    if not _verify_ghl_signature(request):
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data       = request.get_json(force=True) or {}
        contact_id = data.get("contactId") or data.get("contact_id")
        outcome    = data.get("outcome", "unknown")
        print(f"[GHL WEBHOOK] Call complete: contact={contact_id} outcome={outcome}")

        with get_conn() as conn:
            conn.execute(
                "UPDATE leads SET contacted_at = ?, status = ?, notes = notes || ? "
                "WHERE phone = ?",
                (
                    datetime.utcnow().isoformat(),
                    "contacted",
                    f" | Call outcome: {outcome}",
                    data.get("phone", ""),
                ),
            )

        _log_agent_run("call_complete", "ok", f"contact={contact_id} outcome={outcome}")
        return jsonify({"status": "processed", "contact_id": contact_id,
                        "outcome": outcome}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] call-complete error: {e}")
        _log_agent_run("call_complete", "error", str(e)[:200])
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@ghl_app.route("/webhook/form-submit", methods=["POST"])
def form_submit():
    """Handle a solar quote form submission (legacy).

    Processes lead data with richer fields (roof, bill, homeowner).
    Logs result to agent_run_log.
    """
    if not _verify_ghl_signature(request):
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data      = request.get_json(force=True) or {}
        lead_data = _extract_lead_data(data)
        lead_data["homeowner_status"] = (
            data.get("homeowner") or lead_data["homeowner_status"]
        )
        lead_data["monthly_bill"] = (
            _parse_number(data.get("electricity_bill") or data.get("bill"))
            or lead_data["monthly_bill"]
        )
        lead_data["roof_type"] = data.get("roof") or lead_data["roof_type"]
        print(f"[GHL WEBHOOK] Form submit: {lead_data.get('name', 'Unknown')}")

        lead_id = insert("leads", {
            "source":           "form",
            "name":             lead_data.get("name"),
            "phone":            lead_data.get("phone"),
            "email":            lead_data.get("email"),
            "suburb":           lead_data.get("suburb"),
            "state":            lead_data.get("state"),
            "homeowner_status": lead_data.get("homeowner_status"),
            "monthly_bill":     lead_data.get("monthly_bill"),
            "roof_type":        lead_data.get("roof_type"),
            "roof_age":         lead_data.get("roof_age"),
            "client_account":   lead_data.get("client_account", "default"),
            "notes":            json_payload(data),
        })

        result = qualify(lead_data, lead_id)
        _log_agent_run("form_submit", "ok", f"lead_id={lead_id} score={result.get('score')}")
        return jsonify({"status": "processed", "lead_id": lead_id,
                        "score": result.get("score")}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] form-submit error: {e}")
        _log_agent_run("form_submit", "error", str(e)[:200])
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@ghl_app.route("/webhook/stage-change", methods=["POST"])
def stage_change():
    """Handle a pipeline stage change event from GHL (legacy).

    Updates the lead pipeline_stage to reflect the new position.
    Logs result to agent_run_log.
    """
    if not _verify_ghl_signature(request):
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data       = request.get_json(force=True) or {}
        contact_id = data.get("contactId") or data.get("contact_id")
        new_stage  = data.get("newStage") or data.get("stage")
        print(f"[GHL WEBHOOK] Stage change: contact={contact_id} → {new_stage}")

        safe_id = _safe_like(str(contact_id or ""))
        with get_conn() as conn:
            conn.execute(
                r"UPDATE leads SET pipeline_stage = ? WHERE notes LIKE ? ESCAPE '\'",
                (new_stage, f"%{safe_id}%"),
            )
            if new_stage and "convert" in new_stage.lower():
                conn.execute(
                    r"UPDATE leads SET status = 'converted', converted_at = ? "
                    r"WHERE notes LIKE ? ESCAPE '\'",
                    (datetime.utcnow().isoformat(), f"%{safe_id}%"),
                )

        _log_agent_run("stage_change", "ok",
                       f"contact={contact_id} new_stage={new_stage}")
        return jsonify({"status": "processed", "contact_id": contact_id,
                        "new_stage": new_stage}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] stage-change error: {e}")
        _log_agent_run("stage_change", "error", str(e)[:200])
        return jsonify({"status": "error", "message": "Internal server error"}), 500
