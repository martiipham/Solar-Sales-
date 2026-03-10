"""Settings API — read and write runtime application settings.

Settings are stored in app_settings (SQLite) and override .env values at
runtime. They are seeded with sensible defaults on first startup.

Blueprint: settings_bp
  GET   /api/settings          — return all settings grouped by category
  PATCH /api/settings          — update one or more settings by key
"""

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from api.auth import require_auth
from memory.database import fetch_all, fetch_one, get_conn

logger = logging.getLogger(__name__)
settings_bp = Blueprint("settings", __name__)

# Default settings seeded on first startup
DEFAULTS = [
    # Budget
    ("budget.weekly_aud",          "500",   "budget",    "Weekly spend budget in AUD"),
    ("budget.max_single_bet_pct",  "0.25",  "budget",    "Max single experiment as % of budget (Kelly cap)"),
    # Confidence routing
    ("confidence.auto_proceed",    "8.5",   "confidence","Score above this → auto-approve experiment"),
    ("confidence.human_gate",      "5.0",   "confidence","Score above this → send to human gate"),
    ("confidence.auto_kill",       "5.0",   "confidence","Score below this → auto-kill experiment"),
    # Kelly
    ("kelly.fractional",           "0.25",  "capital",   "Fractional Kelly multiplier (0.25 = 25%)"),
    # Circuit breaker
    ("breaker.yellow_failures",    "3",     "circuit",   "Consecutive failures to trigger Yellow alert"),
    ("breaker.orange_burn_rate",   "1.5",   "circuit",   "Budget burn rate multiplier to trigger Orange"),
    ("breaker.red_failures",       "5",     "circuit",   "Consecutive failures to trigger Red (full halt)"),
    ("breaker.red_single_loss_pct","0.4",   "circuit",   "Single loss as % of budget to trigger Red"),
    # Portfolio allocation
    ("portfolio.exploit_pct",      "0.60",  "portfolio", "% of budget allocated to exploit bucket"),
    ("portfolio.explore_pct",      "0.30",  "portfolio", "% of budget allocated to explore bucket"),
    ("portfolio.moonshot_pct",     "0.10",  "portfolio", "% of budget allocated to moonshot bucket"),
    # Scheduler toggles
    ("schedule.general_hours",     "6",     "schedule",  "How often The General runs (hours)"),
    ("schedule.scout_time_utc",    "08:00", "schedule",  "Daily UTC time the Scout runs"),
    ("schedule.research_time_utc", "06:00", "schedule",  "Daily UTC time the Research engine runs"),
    # CRM
    ("crm.sync_interval_min",      "30",    "crm",       "CRM cache refresh interval in minutes"),
    ("crm.active",                 "ghl",   "crm",       "Active CRM: ghl | hubspot | salesforce"),
    # Notifications
    ("notify.slack_enabled",       "true",  "notify",    "Send Slack alerts for approvals/failures"),
    ("notify.email_enabled",       "false", "notify",    "Send email digests (requires SMTP config)"),
    # Email processing
    ("email.agent_enabled",        "true",  "email",     "Master on/off switch for inbound email processing"),
    ("email.auto_send_enabled",    "false", "email",     "Auto-send AI replies without human approval"),
    ("email.auto_send_threshold",  "9",     "email",     "Urgency score (1-10) required to trigger auto-send (only when auto-send is on)"),
    ("email.auto_discard_spam",    "true",  "email",     "Automatically discard emails classified as SPAM without showing in queue"),
    ("email.imap_poll_interval",   "120",   "email",     "Seconds between IMAP inbox checks. Set to 0 to disable polling"),
    ("email.reply_prompt",         "",      "email",     "Custom AI instructions for drafting replies — tone, sign-off, what to mention"),
]


def seed_settings():
    """Insert default settings rows that don't already exist."""
    with get_conn() as conn:
        for key, value, category, description in DEFAULTS:
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value, category, description) "
                "VALUES (?, ?, ?, ?)",
                (key, value, category, description)
            )
    logger.info("[SETTINGS] Defaults seeded.")


def get_setting(key: str, fallback=None):
    """Read a single setting value from the DB (or fallback if missing)."""
    row = fetch_one("SELECT value FROM app_settings WHERE key = ?", (key,))
    return row.get("value", fallback) if row else fallback


@settings_bp.route("/api/settings", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def list_settings():
    """Return all settings grouped by category."""
    rows = fetch_all(
        "SELECT key, value, category, description, updated_at "
        "FROM app_settings ORDER BY category, key"
    )
    grouped = {}
    for r in rows:
        cat = r["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "key": r["key"],
            "value": r["value"],
            "description": r["description"],
            "updated_at": r["updated_at"],
        })
    return jsonify({"settings": grouped}), 200


@settings_bp.route("/api/settings", methods=["PATCH"])
@require_auth(roles=["owner", "admin"])
def update_settings():
    """Update one or more settings. Body: { "key": "new_value", ... }"""
    data = request.get_json() or {}
    if not data:
        return jsonify({"error": "No settings provided"}), 400

    now = datetime.utcnow().isoformat()
    updated = []
    try:
        with get_conn() as conn:
            for key, value in data.items():
                conn.execute(
                    "UPDATE app_settings SET value = ?, updated_at = ? WHERE key = ?",
                    (str(value), now, key)
                )
                if conn.execute(
                    "SELECT changes()"
                ).fetchone()[0] > 0:
                    updated.append(key)
    except Exception as e:
        logger.error(f"[SETTINGS] update error: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "updated": updated}), 200
