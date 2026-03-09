"""Human Gate API — Approve/reject experiments requiring human review.

Flask API on port 5000.

  POST /approve/<experiment_id>  — approve and allocate budget
  POST /reject/<experiment_id>   — reject with reason
  POST /slack/actions            — Slack interactive button handler
  GET  /pending                  — list all awaiting review
  GET  /dashboard                — full swarm status overview
  GET  /health                   — system health check (public)

Authentication:
  All endpoints except /health require:
    Authorization: Bearer <GATE_API_KEY>
  Set GATE_API_KEY in .env. If not set, auth is bypassed with a warning logged.
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from memory.database import update, fetch_all, fetch_one
from memory.hot_memory import get_swarm_summary, get_pending_experiments
from memory.cold_ledger import log_experiment_approved, log_experiment_killed
from capital.circuit_breaker import get_current_level, get_breaker_history, is_halted
from capital.portfolio_manager import get_portfolio_summary
from capital.kelly_engine import calculate_budget
import config

logger = logging.getLogger(__name__)

gate_app = Flask(__name__)

# Security headers on every response
@gate_app.after_request
def _security_headers(response):
    """Attach security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

# Rate limiting — brute force protection on auth endpoints (20/min per IP)
_limiter = Limiter(
    app=gate_app,
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)


# ─────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _require_api_key(f):
    """Decorator: require Bearer token matching GATE_API_KEY.

    If GATE_API_KEY is not configured, logs a warning but allows through
    (so local dev without a key still works). In production always set the key.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not config.GATE_API_KEY:
            logger.warning("[HUMAN GATE] GATE_API_KEY not set — endpoint is unprotected")
            return f(*args, **kwargs)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != config.GATE_API_KEY:
            logger.warning(f"[HUMAN GATE] Unauthorised request to {request.path} from {request.remote_addr}")
            return jsonify({"error": "Unauthorised"}), 401
        return f(*args, **kwargs)
    return decorated


def _verify_slack_signature(req) -> bool:
    """Verify Slack request signature using signing secret.

    Args:
        req: Flask request object

    Returns:
        True only if signature is cryptographically valid.
        Always False (hard block) when SLACK_SIGNING_SECRET is not configured.
    """
    if not config.SLACK_SIGNING_SECRET:
        logger.warning("[HUMAN GATE] SLACK_SIGNING_SECRET not set — rejecting Slack action")
        return False

    slack_signature = req.headers.get("X-Slack-Signature", "")
    timestamp = req.headers.get("X-Slack-Request-Timestamp", "")

    # Reject requests older than 5 minutes (replay attack protection)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except (ValueError, TypeError):
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    expected = "v0=" + hmac.new(
        config.SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, slack_signature)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@gate_app.route("/health", methods=["GET"])
def health():
    """System health check (public — no auth required)."""
    return jsonify({
        "status": "ok",
        "service": "human-gate",
        "circuit_breaker": get_current_level(),
        "halted": is_halted(),
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


@gate_app.route("/approve/<int:experiment_id>", methods=["POST"])
@_limiter.limit("20 per minute")
@_require_api_key
def approve(experiment_id: int):
    """Approve an experiment and allocate budget.

    Args:
        experiment_id: Database id of the experiment

    Request body (optional JSON):
        approved_by: Name of approver (default: 'human')
    """
    try:
        data = request.get_json(force=True) or {}
        approved_by = str(data.get("approved_by", "human"))[:64]  # length-cap input
        result = _approve(experiment_id, approved_by=approved_by)
        if "error" in result:
            return jsonify(result), 404 if "not found" in result["error"] else 400
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"[HUMAN GATE] Approve error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/reject/<int:experiment_id>", methods=["POST"])
@_limiter.limit("20 per minute")
@_require_api_key
def reject(experiment_id: int):
    """Reject an experiment with a reason.

    Args:
        experiment_id: Database id of the experiment

    Request body (optional JSON):
        reason: Why rejected
        rejected_by: Who rejected it
    """
    try:
        data = request.get_json(force=True) or {}
        reason = str(data.get("reason", "Rejected by human reviewer"))[:500]
        rejected_by = str(data.get("rejected_by", "human"))[:64]
        result = _reject(experiment_id, rejected_by=rejected_by, reason=reason)
        if "error" in result:
            return jsonify(result), 404 if "not found" in result["error"] else 400
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"[HUMAN GATE] Reject error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/pending", methods=["GET"])
@_require_api_key
def pending():
    """List all experiments awaiting human review."""
    try:
        experiments = get_pending_experiments()
        return jsonify({
            "count": len(experiments),
            "experiments": experiments,
        }), 200
    except Exception as e:
        logger.error(f"[HUMAN GATE] Pending error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/dashboard", methods=["GET"])
@_require_api_key
def dashboard():
    """Full swarm status overview."""
    try:
        summary = get_swarm_summary()
        portfolio = get_portfolio_summary()
        pending_exps = get_pending_experiments()
        active_exps = fetch_all("SELECT * FROM experiments WHERE status IN ('approved','running') ORDER BY created_at DESC LIMIT 10")
        recent_leads = fetch_all("SELECT id, name, qualification_score, recommended_action, status, created_at FROM leads ORDER BY created_at DESC LIMIT 10")
        cb_history = get_breaker_history(5)

        return jsonify({
            "swarm": summary,
            "portfolio": portfolio,
            "pending_experiments": pending_exps,
            "active_experiments": active_exps,
            "recent_leads": recent_leads,
            "circuit_breaker_history": cb_history,
            "generated_at": datetime.utcnow().isoformat(),
        }), 200

    except Exception as e:
        logger.error(f"[HUMAN GATE] Dashboard error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/costs", methods=["GET"])
@_require_api_key
def costs():
    """API usage and cost dashboard.

    Query params:
        days: Look-back period in days (default 7)
        client_id: Optional — filter by client
        call_id: Optional — cost for a single call
    """
    try:
        from tracking.cost_tracker import (
            get_cost_summary, get_daily_costs, get_call_cost,
            get_client_costs, get_projected_monthly_cost,
        )
        days      = min(int(request.args.get("days", 7)), 365)
        call_id   = request.args.get("call_id")
        client_id = request.args.get("client_id")

        if call_id:
            return jsonify(get_call_cost(call_id)), 200

        if client_id:
            return jsonify(get_client_costs(client_id, days=days)), 200

        return jsonify({
            "summary":    get_cost_summary(days=days),
            "daily":      get_daily_costs(days=days),
            "projection": get_projected_monthly_cost(),
        }), 200

    except Exception as e:
        logger.error(f"[HUMAN GATE] Costs error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/experiments", methods=["GET"])
@_require_api_key
def list_experiments():
    """List recent experiments with optional status filter."""
    try:
        status = request.args.get("status")
        limit  = min(int(request.args.get("limit", 20)), 100)  # cap at 100
        if status:
            rows = fetch_all(
                "SELECT * FROM experiments WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            rows = fetch_all("SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,))
        return jsonify({"experiments": rows, "count": len(rows)}), 200
    except Exception as e:
        logger.error(f"[HUMAN GATE] List experiments error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/approve-breaker", methods=["POST"])
@_require_api_key
def approve_breaker_reset():
    """Approve a circuit breaker reset (Red level requires this endpoint).

    Request body:
        approved_by: Who is resetting the breaker
    """
    try:
        data = request.get_json(force=True) or {}
        approved_by = str(data.get("approved_by", "human"))[:64]

        from capital.circuit_breaker import reset_breaker
        result = reset_breaker(approved_by)
        return jsonify(result), 200 if result["success"] else 400

    except Exception as e:
        logger.error(f"[HUMAN GATE] Breaker reset error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@gate_app.route("/slack/actions", methods=["POST"])
def slack_actions():
    """Handle Slack interactive button callbacks (approve/reject experiment).

    Slack sends a form-encoded 'payload' field containing JSON.
    Responds with an updated message replacing the buttons with confirmation text.
    """
    if not _verify_slack_signature(request):
        logger.warning("[HUMAN GATE] Slack signature verification failed")
        return jsonify({"error": "Invalid signature"}), 403

    try:
        raw_payload = request.form.get("payload", "{}")
        payload = json.loads(raw_payload)

        actions = payload.get("actions", [])
        if not actions:
            return jsonify({"error": "No actions in payload"}), 400

        action_id = actions[0].get("action_id", "")
        response_url = payload.get("response_url", "")

        # Parse action: approve_experiment_42 or reject_experiment_42
        if action_id.startswith("approve_experiment_"):
            experiment_id = int(action_id.split("_")[-1])
            result = _approve(experiment_id, approved_by="slack")
            status_text = f"✅ Experiment #{experiment_id} *approved* via Slack."
        elif action_id.startswith("reject_experiment_"):
            experiment_id = int(action_id.split("_")[-1])
            result = _reject(experiment_id, rejected_by="slack", reason="Rejected via Slack button")
            status_text = f"❌ Experiment #{experiment_id} *rejected* via Slack."
        else:
            return jsonify({"error": "Unknown action"}), 400

        # Replace the original message buttons with confirmation text
        if response_url and response_url.startswith("https://hooks.slack.com/"):
            import requests as req_lib
            req_lib.post(response_url, json={
                "replace_original": True,
                "text": status_text,
            }, timeout=5)

        return jsonify({"status": "ok", "result": result}), 200

    except Exception as e:
        logger.error(f"[HUMAN GATE] Slack actions error: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _approve(experiment_id: int, approved_by: str = "human") -> dict:
    """Internal approve logic shared by REST endpoint and Slack handler.

    Args:
        experiment_id: Database id
        approved_by: Identifier for the approver

    Returns:
        Result dict
    """
    exp = fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        return {"error": f"Experiment #{experiment_id} not found"}
    if exp.get("status") != "pending":
        return {"error": f"Experiment #{experiment_id} is not pending"}

    budget_info = calculate_budget(exp.get("confidence_score", 5))
    budget = budget_info["budget_aud"]

    update("experiments", experiment_id, {
        "status": "approved",
        "budget_allocated": budget,
        "approved_by": approved_by,
        "approved_at": datetime.utcnow().isoformat(),
    })
    log_experiment_approved(experiment_id, approved_by, budget)
    print(f"[HUMAN GATE] Experiment #{experiment_id} approved by {approved_by} (${budget} AUD)")
    return {"status": "approved", "experiment_id": experiment_id, "budget_allocated_aud": budget}


def _reject(experiment_id: int, rejected_by: str = "human", reason: str = "Rejected by human reviewer") -> dict:
    """Internal reject logic shared by REST endpoint and Slack handler.

    Args:
        experiment_id: Database id
        rejected_by: Identifier for the rejector
        reason: Rejection reason

    Returns:
        Result dict
    """
    exp = fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        return {"error": f"Experiment #{experiment_id} not found"}
    if exp.get("status") not in ("pending", "approved"):
        return {"error": f"Cannot reject experiment with status: {exp.get('status')}"}

    update("experiments", experiment_id, {
        "status": "rejected",
        "failure_mode": reason,
        "completed_at": datetime.utcnow().isoformat(),
    })
    log_experiment_killed(experiment_id, reason, rejected_by)
    print(f"[HUMAN GATE] Experiment #{experiment_id} rejected by {rejected_by}: {reason}")
    return {"status": "rejected", "experiment_id": experiment_id, "reason": reason}
