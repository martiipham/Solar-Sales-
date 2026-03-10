"""Dashboard API — Live data feed for the swarm-board React app.

CORS-enabled Flask app served on PORT_DASHBOARD_API (default 5003).
The React board polls these endpoints every 30 seconds to show live
CRM data, swarm metrics, and experiment status without needing direct
DB access in the browser.

Endpoints:
  GET /api/health              — service health + CRM connection status
  GET /api/crm/status          — which CRM is active and configured
  GET /api/crm/pipeline        — pipeline stages with contact counts
  GET /api/crm/contacts        — recent contacts from cache
  GET /api/crm/metrics         — conversion funnel metrics
  GET /api/swarm/summary       — hot memory swarm overview
  GET /api/swarm/experiments   — recent experiments (filterable by status)
  GET /api/swarm/leads         — recent leads from DB
  GET /api/board/state         — board-state.json + live DB overlay
"""

import json
import logging
import os
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
from memory.database import fetch_all, fetch_one

logger = logging.getLogger(__name__)

dashboard_app = Flask(__name__)

# CORS: allow Vite dev server + any configured FRONTEND_URL
_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",   # vite preview
]
_frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if _frontend_url and _frontend_url not in _cors_origins:
    _cors_origins.append(_frontend_url)

CORS(dashboard_app, origins=_cors_origins, supports_credentials=True)

# Rate limiting — 20 requests/minute per IP on all endpoints
_dash_storage_uri = config.REDIS_URL if config.REDIS_URL else "memory://"
_limiter = Limiter(
    app=dashboard_app,
    key_func=get_remote_address,
    default_limits=["20 per minute"],
    storage_uri=_dash_storage_uri,
)


# Security headers on every response
@dashboard_app.after_request
def _security_headers(response):
    """Attach security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@dashboard_app.before_request
def _check_auth():
    """Require JWT auth on all endpoints except /api/health, auth routes, and preflight.

    Exempt paths:
      /api/health         — public liveness probe
      /api/auth/*         — login / logout / token endpoints must be unauthenticated
      OPTIONS             — CORS preflight must pass through
    """
    if request.method == "OPTIONS":
        return None
    if request.path == "/api/health" or request.path.startswith("/api/auth/"):
        return None

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": "Authentication required"}), 401

    token = header[7:]
    try:
        # Reuse the JWT secret and token-hash helper from auth module
        from api.auth import _JWT_SECRET, _hash_token
        import jwt as _jwt
        _jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Revocation check — guard against logged-out tokens
    from api.auth import _hash_token as _ht
    rev_row = fetch_one(
        "SELECT revoked FROM auth_tokens WHERE token_hash = ?", (_ht(token),)
    )
    if not rev_row or rev_row.get("revoked"):
        return jsonify({"error": "Session revoked — please log in again"}), 401


# ── Register feature blueprints ───────────────────────────────────────────────
def _register_blueprints():
    """Register auth, users, settings, company, API key, and feature blueprints."""
    try:
        from api.auth import auth_bp, seed_owner
        from api.users_api import users_bp
        from api.settings_api import settings_bp, seed_settings
        from api.company_api import company_bp
        from api.apikeys_api import apikeys_bp
        from api.calls_api import calls_bp
        from api.kb_api import kb_bp
        from api.reports_api import reports_bp
        from api.onboarding_api import onboarding_bp
        from api.emails_api import emails_bp

        dashboard_app.register_blueprint(auth_bp)
        dashboard_app.register_blueprint(users_bp)
        dashboard_app.register_blueprint(settings_bp)
        dashboard_app.register_blueprint(company_bp)
        dashboard_app.register_blueprint(apikeys_bp)
        dashboard_app.register_blueprint(calls_bp)
        dashboard_app.register_blueprint(kb_bp)
        dashboard_app.register_blueprint(reports_bp)
        dashboard_app.register_blueprint(onboarding_bp)
        dashboard_app.register_blueprint(emails_bp)

        # Seed defaults on startup
        seed_owner()
        seed_settings()

        # Ensure KB tables exist before any API request hits them
        from knowledge.company_kb import init_kb_tables
        init_kb_tables()

        logger.info("[DASH API] All blueprints registered.")
    except Exception as e:
        logger.error(f"[DASH API] Blueprint registration failed: {e}")

_register_blueprints()

# Path to board-state.json in project root /public/
BOARD_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public",
    "board-state.json",
)


def _read_board_state() -> dict:
    """Read board-state.json from disk, returning {} on any error."""
    try:
        with open(BOARD_STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


# ── Health ───────────────────────────────────────────────────────────────────

@dashboard_app.route("/api/health", methods=["GET"])
def health():
    """Service health check with CRM connection status."""
    try:
        from integrations.crm_router import status as crm_status
        crm = crm_status()
    except Exception:
        crm = {"active": "none", "ghl": False, "hubspot": False, "salesforce": False}

    return jsonify({
        "status": "ok",
        "service": "dashboard-api",
        "crm": crm,
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


# ── Support message ──────────────────────────────────────────────────────────

@dashboard_app.route("/api/support/message", methods=["POST"])
def support_message():
    """Accept a support message from the client portal and forward to Slack.

    Request body:
        message: str — the client's message text
    """
    try:
        data = request.get_json(force=True) or {}
        msg  = str(data.get("message", "")).strip()[:1000]
        if not msg:
            return jsonify({"error": "message required"}), 400

        from notifications.slack_notifier import post_message
        post_message(f"*Support message from client portal:*\n{msg}")
        logger.info("[DASH API] Support message forwarded to Slack")
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"[DASH API] support_message error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ── Agent config endpoints ────────────────────────────────────────────────────

@dashboard_app.route("/api/agents/config", methods=["GET"])
def agents_config_get():
    """Return per-agent enabled/disabled state and last scheduler run times.

    Response:
        agents:   { agent_id: bool } — enabled state for each agent
        schedule: { job_id: { last_run, next_run, running } }
    """
    try:
        # Read agent enabled state from settings table
        row = fetch_one("SELECT value FROM settings WHERE key = 'agent_config'")
        agents = json.loads(row["value"]) if row else {}

        # Read scheduler run log (last_run per job_id)
        runs = fetch_all(
            "SELECT job_id, MAX(ran_at) AS last_run FROM agent_run_log GROUP BY job_id"
        )
        schedule = {r["job_id"]: {"last_run": r["last_run"], "running": False} for r in runs}

        return jsonify({"agents": agents, "schedule": schedule}), 200
    except Exception as e:
        logger.error(f"[DASH API] agents_config_get error: {e}")
        return jsonify({"agents": {}, "schedule": {}}), 200


@dashboard_app.route("/api/agents/config", methods=["PATCH"])
def agents_config_patch():
    """Enable or disable a single agent by ID.

    Request body:
        agent_id: str — agent identifier (e.g. 'scout', 'general')
        enabled:  bool

    Persists to the settings table under key 'agent_config'.
    """
    try:
        data     = request.get_json(force=True) or {}
        agent_id = str(data.get("agent_id", ""))[:50]
        enabled  = bool(data.get("enabled", True))

        if not agent_id:
            return jsonify({"error": "agent_id required"}), 400

        # Read existing config
        row        = fetch_one("SELECT value FROM settings WHERE key = 'agent_config'")
        agent_cfg  = json.loads(row["value"]) if row else {}
        agent_cfg[agent_id] = enabled

        # Upsert back
        from memory.database import get_conn
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("agent_config", json.dumps(agent_cfg)),
            )

        logger.info(f"[DASH API] Agent '{agent_id}' set to enabled={enabled}")
        return jsonify({"agent_id": agent_id, "enabled": enabled}), 200
    except Exception as e:
        logger.error(f"[DASH API] agents_config_patch error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ── CRM endpoints ─────────────────────────────────────────────────────────────

@dashboard_app.route("/api/crm/status", methods=["GET"])
def crm_status_endpoint():
    """Return which CRM is active and all configured integrations."""
    try:
        from integrations.crm_router import status as crm_status, active_crm, all_configured_crms
        return jsonify({
            "active": active_crm(),
            "configured": all_configured_crms(),
            "detail": crm_status(),
        }), 200
    except Exception as e:
        logger.error(f"[DASH API] crm/status error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@dashboard_app.route("/api/crm/pipeline", methods=["GET"])
def crm_pipeline():
    """Return pipeline stages with contact counts.

    Serves from SQLite cache (written by crm_sync every 30 min).
    Falls back to a live CRM call if the cache is empty.
    """
    try:
        rows = fetch_all(
            "SELECT cache_key, cache_value, cached_at FROM crm_cache "
            "WHERE cache_key LIKE 'pipeline_%' ORDER BY cached_at DESC LIMIT 100"
        )
        if rows:
            seen = {}
            for r in rows:
                if r["cache_key"] not in seen:
                    seen[r["cache_key"]] = json.loads(r["cache_value"])
            return jsonify({
                "source": "cache",
                "stages": list(seen.values()),
                "cached_at": rows[0]["cached_at"],
            }), 200

        # No cache — try live
        from integrations.crm_router import get_pipeline_stages, active_crm
        pipeline_id = config.get("GHL_PIPELINE_ID", "")
        stages = get_pipeline_stages(pipeline_id)
        return jsonify({"source": "live", "stages": stages, "crm": active_crm()}), 200

    except Exception as e:
        logger.error(f"[DASH API] crm/pipeline error: {e}")
        return jsonify({"error": "Internal server error", "stages": []}), 500


@dashboard_app.route("/api/crm/contacts", methods=["GET"])
def crm_contacts():
    """Return recent contacts from the cache table."""
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
        rows = fetch_all(
            "SELECT cache_key, cache_value, cached_at FROM crm_cache "
            "WHERE cache_key LIKE 'contact_%' ORDER BY cached_at DESC LIMIT ?",
            (limit,),
        )
        contacts = [json.loads(r["cache_value"]) for r in rows]
        return jsonify({"contacts": contacts, "count": len(contacts)}), 200
    except Exception as e:
        logger.error(f"[DASH API] crm/contacts error: {e}")
        return jsonify({"error": "Internal server error", "contacts": []}), 500


@dashboard_app.route("/api/crm/metrics", methods=["GET"])
def crm_metrics():
    """Return conversion funnel metrics from the cache."""
    try:
        row = fetch_one(
            "SELECT cache_value FROM crm_cache "
            "WHERE cache_key = 'metrics_summary' ORDER BY cached_at DESC LIMIT 1"
        )
        if row:
            return jsonify({"source": "cache", "metrics": json.loads(row["cache_value"])}), 200

        return jsonify({
            "source": "empty",
            "metrics": {
                "total_contacts": 0,
                "new_this_week": 0,
                "pipeline_stages": [],
                "conversion_rate": 0,
                "synced_at": None,
            },
        }), 200
    except Exception as e:
        logger.error(f"[DASH API] crm/metrics error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ── Swarm endpoints ───────────────────────────────────────────────────────────

@dashboard_app.route("/api/swarm/summary", methods=["GET"])
def swarm_summary():
    """Return the swarm hot memory summary."""
    try:
        from memory.hot_memory import get_swarm_summary
        return jsonify(get_swarm_summary()), 200
    except Exception as e:
        logger.error(f"[DASH API] swarm/summary error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@dashboard_app.route("/api/swarm/experiments", methods=["GET"])
def swarm_experiments():
    """Return recent experiments, optionally filtered by status."""
    try:
        status_filter = request.args.get("status")
        limit = min(int(request.args.get("limit", 15)), 200)
        if status_filter:
            rows = fetch_all(
                "SELECT * FROM experiments WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit),
            )
        else:
            rows = fetch_all(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        return jsonify({"experiments": [dict(r) for r in rows], "count": len(rows)}), 200
    except Exception as e:
        logger.error(f"[DASH API] swarm/experiments error: {e}")
        return jsonify({"error": "Internal server error", "experiments": []}), 500


@dashboard_app.route("/api/swarm/leads", methods=["GET"])
def swarm_leads():
    """Return recent leads from the database."""
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
        rows = fetch_all(
            "SELECT id, name, qualification_score, recommended_action, status, created_at "
            "FROM leads ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return jsonify({"leads": [dict(r) for r in rows], "count": len(rows)}), 200
    except Exception as e:
        logger.error(f"[DASH API] swarm/leads error: {e}")
        return jsonify({"error": "Internal server error", "leads": []}), 500


@dashboard_app.route("/api/swarm/circuit-breaker", methods=["GET"])
def circuit_breaker():
    """Return current circuit breaker state."""
    try:
        from capital.circuit_breaker import get_current_level, is_halted
        return jsonify({
            "level": get_current_level(),
            "halted": is_halted(),
        }), 200
    except Exception as e:
        logger.error(f"[DASH API] circuit-breaker error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ── Voice status ─────────────────────────────────────────────────────────────

@dashboard_app.route("/api/voice/status", methods=["GET"])
def voice_status():
    """Return whether the voice AI is configured and active."""
    try:
        retell_ok = bool(config.get("RETELL_API_KEY", ""))
        eleven_ok = bool(config.get("ELEVENLABS_API_KEY", ""))
        agent_row = fetch_one(
            "SELECT retell_agent_id FROM company_profiles "
            "WHERE retell_agent_id IS NOT NULL LIMIT 1"
        )
        has_agent = bool(agent_row)
        status = "live" if (retell_ok and has_agent) else "needs_setup" if retell_ok else "offline"
        return jsonify({
            "status":      status,
            "retell":      retell_ok,
            "elevenlabs":  eleven_ok,
            "agent_ready": has_agent,
        }), 200
    except Exception as e:
        logger.error(f"[DASH API] voice/status error: {e}")
        return jsonify({"status": "offline", "error": "Internal server error"}), 500


# ── Dashboard summary ────────────────────────────────────────────────────────

@dashboard_app.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """Return today's aggregated KPI metrics for the dashboard overview.

    Response fields:
        calls_today, emails_today, leads_today, hot_leads,
        proposals_sent, crm_last_sync, contacts_total,
        calls_this_week, pending_approvals
    """
    try:
        today = datetime.utcnow().date().isoformat()

        calls_today_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM call_logs WHERE DATE(started_at) = ?", (today,)
        )
        emails_today_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM email_logs WHERE DATE(received_at) = ?", (today,)
        )
        leads_today_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM leads WHERE DATE(created_at) = ?", (today,)
        )
        hot_leads_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM leads WHERE qualification_score >= 8"
        )
        proposals_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM proposals WHERE DATE(created_at) = ?", (today,)
        )
        calls_week_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM call_logs "
            "WHERE started_at >= datetime('now', '-7 days')"
        )
        pending_approvals_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM email_logs WHERE draft_reply_queued = 1"
        )
        crm_sync_row = fetch_one(
            "SELECT cached_at FROM crm_cache ORDER BY cached_at DESC LIMIT 1"
        )
        contacts_row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM crm_cache WHERE cache_key LIKE 'contact_%'"
        )

        return jsonify({
            "calls_today":       (calls_today_row or {}).get("cnt", 0),
            "emails_today":      (emails_today_row or {}).get("cnt", 0),
            "leads_today":       (leads_today_row or {}).get("cnt", 0),
            "hot_leads":         (hot_leads_row or {}).get("cnt", 0),
            "proposals_sent":    (proposals_row or {}).get("cnt", 0),
            "crm_last_sync":     (crm_sync_row or {}).get("cached_at"),
            "contacts_total":    (contacts_row or {}).get("cnt", 0),
            "calls_this_week":   (calls_week_row or {}).get("cnt", 0),
            "pending_approvals": (pending_approvals_row or {}).get("cnt", 0),
        }), 200
    except Exception as e:
        logger.error(f"[DASH API] dashboard/summary error: {e}")
        return jsonify({
            "calls_today": 0, "emails_today": 0, "leads_today": 0,
            "hot_leads": 0, "proposals_sent": 0, "crm_last_sync": None,
            "contacts_total": 0, "calls_this_week": 0, "pending_approvals": 0,
        }), 200


# ── Leads list ────────────────────────────────────────────────────────────────

@dashboard_app.route("/api/leads", methods=["GET"])
def leads_list():
    """Return recent leads from the database.

    Query params:
        limit (int, default 20, max 200)
    """
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
        rows = fetch_all(
            "SELECT id, name, phone, email, suburb, state, qualification_score, "
            "score_reason, recommended_action, status, created_at "
            "FROM leads ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return jsonify({"leads": rows, "count": len(rows)}), 200
    except Exception as e:
        logger.error(f"[DASH API] leads error: {e}")
        return jsonify({"error": "Internal server error", "leads": []}), 500


# ── Agent status (alias of /api/agents/config) ────────────────────────────────

@dashboard_app.route("/api/agents/status", methods=["GET"])
def agents_status_get():
    """Return per-agent enabled/disabled state — alias of /api/agents/config."""
    return agents_config_get()


@dashboard_app.route("/api/agents/status", methods=["PATCH"])
def agents_status_patch():
    """Enable or disable a single agent — alias of /api/agents/config PATCH."""
    return agents_config_patch()


# ── Board state ───────────────────────────────────────────────────────────────

@dashboard_app.route("/api/board/state", methods=["GET"])
def board_state():
    """Return board-state.json merged with live DB experiment and lead counts."""
    try:
        state = _read_board_state()

        exp_rows = fetch_all(
            "SELECT status, COUNT(*) as cnt FROM experiments GROUP BY status"
        )
        exp_counts = {r["status"]: r["cnt"] for r in exp_rows}

        lead_row = fetch_one("SELECT COUNT(*) as cnt FROM leads")
        lead_count = (dict(lead_row) if lead_row else {}).get("cnt", 0)

        ab_row = fetch_one(
            "SELECT COUNT(*) as cnt FROM ab_tests WHERE status = 'running'"
        )
        ab_running = (dict(ab_row) if ab_row else {}).get("cnt", 0)

        state["liveStats"] = {
            "experiments": exp_counts,
            "totalLeads": lead_count,
            "abTestsRunning": ab_running,
            "generatedAt": datetime.utcnow().isoformat(),
        }
        return jsonify(state), 200
    except Exception as e:
        logger.error(f"[DASH API] board/state error: {e}")
        return jsonify(_read_board_state()), 200
