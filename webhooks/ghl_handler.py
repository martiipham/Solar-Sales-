"""GHL Webhook Server — Receives events from GoHighLevel.

Flask server on port 5001. Handles:
  POST /webhook/new-lead       — new contact in GHL
  POST /webhook/call-complete  — voice AI call finished
  POST /webhook/form-submit    — solar quote form submitted
  POST /webhook/stage-change   — pipeline stage updated
  GET  /health                 — returns 200 OK
"""

import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from memory.database import insert, json_payload
from agents.qualification_agent import qualify
import config

logger = logging.getLogger(__name__)

ghl_app = Flask(__name__)


@ghl_app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "ghl-webhooks", "timestamp": datetime.utcnow().isoformat()}), 200


@ghl_app.route("/webhook/new-lead", methods=["POST"])
def new_lead():
    """Handle a new contact/lead arriving in GHL.

    Expects JSON body with contact data from GHL webhook.
    Saves lead to database and triggers qualification.
    """
    try:
        data = request.get_json(force=True) or {}
        print(f"[GHL WEBHOOK] New lead received: {data.get('full_name', data.get('name', 'Unknown'))}")

        lead_data = _extract_lead_data(data)
        lead_id = insert("leads", {
            "source": "ghl_webhook",
            "name": lead_data.get("name"),
            "phone": lead_data.get("phone"),
            "email": lead_data.get("email"),
            "suburb": lead_data.get("suburb"),
            "state": lead_data.get("state"),
            "homeowner_status": lead_data.get("homeowner_status"),
            "monthly_bill": lead_data.get("monthly_bill"),
            "roof_type": lead_data.get("roof_type"),
            "roof_age": lead_data.get("roof_age"),
            "pipeline_stage": lead_data.get("pipeline_stage", "new"),
            "client_account": lead_data.get("client_account", "default"),
            "notes": json_payload(data),
        })

        result = qualify(lead_data, lead_id)
        return jsonify({"status": "processed", "lead_id": lead_id, "score": result.get("score")}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] new-lead error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@ghl_app.route("/webhook/call-complete", methods=["POST"])
def call_complete():
    """Handle a completed voice AI call event from GHL.

    Updates lead status and pipeline stage based on call outcome.
    """
    try:
        data = request.get_json(force=True) or {}
        contact_id = data.get("contactId") or data.get("contact_id")
        outcome = data.get("outcome", "unknown")
        print(f"[GHL WEBHOOK] Call complete: contact={contact_id} outcome={outcome}")

        from memory.database import get_conn
        with get_conn() as conn:
            conn.execute(
                "UPDATE leads SET contacted_at = ?, status = ?, notes = notes || ? WHERE phone = ?",
                (
                    datetime.utcnow().isoformat(),
                    "contacted",
                    f" | Call outcome: {outcome}",
                    data.get("phone", ""),
                ),
            )

        return jsonify({"status": "processed", "contact_id": contact_id, "outcome": outcome}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] call-complete error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@ghl_app.route("/webhook/form-submit", methods=["POST"])
def form_submit():
    """Handle a solar quote form submission.

    Processes richer lead data including roof, bill, and homeowner info.
    """
    try:
        data = request.get_json(force=True) or {}
        print(f"[GHL WEBHOOK] Form submitted: {data.get('name', 'Unknown')}")

        lead_data = _extract_form_data(data)
        lead_id = insert("leads", {
            "source": "form",
            "name": lead_data.get("name"),
            "phone": lead_data.get("phone"),
            "email": lead_data.get("email"),
            "suburb": lead_data.get("suburb"),
            "state": lead_data.get("state"),
            "homeowner_status": lead_data.get("homeowner_status"),
            "monthly_bill": lead_data.get("monthly_bill"),
            "roof_type": lead_data.get("roof_type"),
            "roof_age": lead_data.get("roof_age"),
            "client_account": lead_data.get("client_account", "default"),
            "notes": json_payload(data),
        })

        result = qualify(lead_data, lead_id)
        return jsonify({"status": "processed", "lead_id": lead_id, "score": result.get("score")}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] form-submit error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@ghl_app.route("/webhook/stage-change", methods=["POST"])
def stage_change():
    """Handle a pipeline stage change event from GHL.

    Updates the lead record to reflect the new pipeline position.
    """
    try:
        data = request.get_json(force=True) or {}
        contact_id = data.get("contactId") or data.get("contact_id")
        new_stage = data.get("newStage") or data.get("stage")
        print(f"[GHL WEBHOOK] Stage change: contact={contact_id} → {new_stage}")

        from memory.database import get_conn
        with get_conn() as conn:
            conn.execute(
                "UPDATE leads SET pipeline_stage = ? WHERE notes LIKE ?",
                (new_stage, f"%{contact_id}%"),
            )

        if new_stage and "convert" in new_stage.lower():
            from memory.database import get_conn as gc
            with gc() as conn:
                conn.execute(
                    "UPDATE leads SET status = 'converted', converted_at = ? WHERE notes LIKE ?",
                    (datetime.utcnow().isoformat(), f"%{contact_id}%"),
                )

        return jsonify({"status": "processed", "contact_id": contact_id, "new_stage": new_stage}), 200

    except Exception as e:
        logger.error(f"[GHL WEBHOOK] stage-change error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def _extract_lead_data(data: dict) -> dict:
    """Extract standardised lead fields from a GHL webhook payload.

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
    return {
        "name": name,
        "phone": data.get("phone") or data.get("phoneRaw"),
        "email": data.get("email"),
        "suburb": data.get("suburb") or data.get("city"),
        "state": data.get("state"),
        "homeowner_status": data.get("homeowner_status") or data.get("customField", {}).get("homeowner_status"),
        "monthly_bill": _parse_number(data.get("monthly_bill") or data.get("customField", {}).get("monthly_bill")),
        "roof_type": data.get("roof_type") or data.get("customField", {}).get("roof_type"),
        "roof_age": _parse_number(data.get("roof_age") or data.get("customField", {}).get("roof_age")),
        "pipeline_stage": data.get("pipelineStage") or data.get("pipeline_stage"),
        "client_account": data.get("locationId") or data.get("client_account", "default"),
    }


def _extract_form_data(data: dict) -> dict:
    """Extract lead data specifically from form submission payloads.

    Args:
        data: Form submission payload

    Returns:
        Standardised lead dict
    """
    base = _extract_lead_data(data)
    base["homeowner_status"] = data.get("homeowner") or base["homeowner_status"]
    base["monthly_bill"] = _parse_number(data.get("electricity_bill") or data.get("bill")) or base["monthly_bill"]
    base["roof_type"] = data.get("roof") or base["roof_type"]
    return base


def _parse_number(value) -> float | None:
    """Safely parse a number from a string or number value.

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
