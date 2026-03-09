"""Onboarding API — guided setup wizard for new solar company clients.

Tracks completion of each onboarding step in app_settings.
Steps:
  1. company    — Basic company info
  2. crm        — GHL API key + location ID
  3. voice      — Retell agent ID + phone number
  4. knowledge  — Confirm KB has been filled in
  5. complete   — Mark onboarding done

Endpoints:
  GET  /api/onboarding/status            — check which steps are done
  POST /api/onboarding/company           — save company info (step 1)
  POST /api/onboarding/crm               — save CRM credentials (step 2)
  POST /api/onboarding/voice             — save voice AI config (step 3)
  POST /api/onboarding/knowledge         — mark KB step done (step 4)
  POST /api/onboarding/complete          — mark fully onboarded
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, g

from memory.database import fetch_one, get_conn
from api.auth import require_auth

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint("onboarding", __name__)

STEPS = ["company", "crm", "voice", "knowledge", "complete"]


def _get_setting(key: str, client_id: str = "global") -> str | None:
    """Fetch a setting value from app_settings."""
    row = fetch_one(
        "SELECT value FROM app_settings WHERE key = ? AND category = ?",
        (key, f"onboarding_{client_id}"),
    )
    return dict(row)["value"] if row else None


def _set_setting(key: str, value: str, client_id: str = "global"):
    """Upsert a setting value in app_settings."""
    category = f"onboarding_{client_id}"
    existing = fetch_one(
        "SELECT id FROM app_settings WHERE key = ? AND category = ?",
        (key, category),
    )
    with get_conn() as conn:
        if existing:
            conn.execute(
                "UPDATE app_settings SET value = ?, updated_at = ? WHERE key = ? AND category = ?",
                (value, datetime.utcnow().isoformat(), key, category),
            )
        else:
            conn.execute(
                "INSERT INTO app_settings (key, value, category, description) VALUES (?,?,?,?)",
                (key, value, category, f"Onboarding step: {key}"),
            )


def _build_status(client_id: str) -> dict:
    """Build the onboarding status dict for a client."""
    completed_steps = {}
    for step in STEPS:
        val = _get_setting(f"step_{step}", client_id)
        completed_steps[step] = val == "done"

    all_done = all(completed_steps[s] for s in STEPS)
    next_step = next((s for s in STEPS if not completed_steps[s]), None)

    return {
        "client_id":       client_id,
        "steps":           completed_steps,
        "is_complete":     all_done,
        "next_step":       next_step,
        "percent_done":    round(sum(1 for v in completed_steps.values() if v) / len(STEPS) * 100),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@onboarding_bp.route("/api/onboarding/status", methods=["GET"])
@require_auth()
def onboarding_status():
    """Return which onboarding steps are complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        return jsonify(_build_status(client_id)), 200
    except Exception as e:
        logger.error(f"[ONBOARDING] status error: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/api/onboarding/company", methods=["POST"])
@require_auth()
def onboarding_company():
    """Save company info and mark step 1 complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        data = request.get_json(force=True) or {}

        # Upsert into company_profiles
        allowed = [
            "company_name", "abn", "phone", "email", "website",
            "service_areas", "years_in_business", "num_installers", "certifications",
        ]
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields.get("company_name"):
            return jsonify({"error": "company_name is required"}), 400

        fields["updated_at"] = datetime.utcnow().isoformat()
        existing = fetch_one(
            "SELECT id FROM company_profiles WHERE client_id = ?", (client_id,)
        )
        with get_conn() as conn:
            if existing:
                assigns = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(
                    f"UPDATE company_profiles SET {assigns} WHERE client_id = ?",
                    list(fields.values()) + [client_id],
                )
            else:
                fields["client_id"] = client_id
                cols = ", ".join(fields.keys())
                ph   = ", ".join("?" for _ in fields)
                conn.execute(
                    f"INSERT INTO company_profiles ({cols}) VALUES ({ph})",
                    list(fields.values()),
                )

        _set_setting("step_company", "done", client_id)
        return jsonify({"ok": True, "status": _build_status(client_id)}), 200

    except Exception as e:
        logger.error(f"[ONBOARDING] company step error: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/api/onboarding/crm", methods=["POST"])
@require_auth()
def onboarding_crm():
    """Save GHL API key and location ID, mark step 2 complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        data = request.get_json(force=True) or {}
        ghl_api_key     = (data.get("ghl_api_key") or "").strip()
        ghl_location_id = (data.get("ghl_location_id") or "").strip()

        if not ghl_api_key or not ghl_location_id:
            return jsonify({"error": "ghl_api_key and ghl_location_id are required"}), 400

        # Store in app_settings — NOT in plain config (keys masked in response)
        category = f"crm_{client_id}"
        with get_conn() as conn:
            for key, val in [("ghl_api_key", ghl_api_key), ("ghl_location_id", ghl_location_id)]:
                existing = fetch_one(
                    "SELECT id FROM app_settings WHERE key = ? AND category = ?",
                    (key, category),
                )
                if existing:
                    conn.execute(
                        "UPDATE app_settings SET value = ? WHERE key = ? AND category = ?",
                        (val, key, category),
                    )
                else:
                    conn.execute(
                        "INSERT INTO app_settings (key, value, category, description) VALUES (?,?,?,?)",
                        (key, val, category, f"CRM credential for {client_id}"),
                    )

        # Update company profile with location ID
        with get_conn() as conn:
            conn.execute(
                "UPDATE company_profiles SET ghl_location_id = ? WHERE client_id = ?",
                (ghl_location_id, client_id),
            )

        _set_setting("step_crm", "done", client_id)
        return jsonify({"ok": True, "status": _build_status(client_id)}), 200

    except Exception as e:
        logger.error(f"[ONBOARDING] crm step error: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/api/onboarding/voice", methods=["POST"])
@require_auth()
def onboarding_voice():
    """Save Retell agent ID and phone number, mark step 3 complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        data = request.get_json(force=True) or {}
        retell_agent_id = (data.get("retell_agent_id") or "").strip()
        phone           = (data.get("phone") or "").strip()

        if not retell_agent_id or not phone:
            return jsonify({"error": "retell_agent_id and phone are required"}), 400

        with get_conn() as conn:
            conn.execute(
                "UPDATE company_profiles SET retell_agent_id = ?, phone = ? WHERE client_id = ?",
                (retell_agent_id, phone, client_id),
            )

        _set_setting("step_voice", "done", client_id)
        return jsonify({"ok": True, "status": _build_status(client_id)}), 200

    except Exception as e:
        logger.error(f"[ONBOARDING] voice step error: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/api/onboarding/knowledge", methods=["POST"])
@require_auth()
def onboarding_knowledge():
    """Mark the knowledge base step as complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        _set_setting("step_knowledge", "done", client_id)
        return jsonify({"ok": True, "status": _build_status(client_id)}), 200
    except Exception as e:
        logger.error(f"[ONBOARDING] knowledge step error: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/api/onboarding/complete", methods=["POST"])
@require_auth()
def onboarding_complete():
    """Mark onboarding fully complete."""
    user = g.user
    client_id = user.get("client_id") or "global"
    try:
        _set_setting("step_complete", "done", client_id)
        status = _build_status(client_id)
        return jsonify({"ok": True, "status": status, "message": "Onboarding complete — your AI receptionist is live!"}), 200
    except Exception as e:
        logger.error(f"[ONBOARDING] complete step error: {e}")
        return jsonify({"error": str(e)}), 500
