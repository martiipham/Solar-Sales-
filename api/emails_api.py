"""Emails API — queue management for inbound email processing.

Blueprint: emails_bp
  GET  /api/emails              — list emails with filters, sorted by urgency
  GET  /api/emails/stats        — pending/sent/today counts (used for nav badge)
  GET  /api/emails/<id>         — single email with full body
  POST /api/emails/bulk-discard — discard multiple pending emails
  POST /gate/email-approve      — approve, edit, or discard a pending draft
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from api.auth import require_auth
from memory.database import fetch_all, fetch_one, get_conn

logger = logging.getLogger(__name__)
emails_bp = Blueprint("emails", __name__)


@emails_bp.route("/api/emails", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def list_emails():
    """List emails with optional filters, sorted urgency desc then received_at desc.

    Query params:
        status:         pending | sent | discarded | all (default all)
        classification: filter by classification value
        urgency_min:    minimum urgency score (int, default 0)
        limit:          max rows returned (default 50, max 200)
        offset:         pagination offset (default 0)
        search:         search from_email, from_name, subject
    """
    status         = request.args.get("status", "")
    classification = request.args.get("classification", "")
    search         = request.args.get("search", "").strip()
    try:
        urgency_min = int(request.args.get("urgency_min", 0))
        limit       = min(int(request.args.get("limit", 50)), 200)
        offset      = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numeric parameter"}), 400

    conditions, params = [], []

    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)
    if classification:
        conditions.append("classification = ?")
        params.append(classification)
    if urgency_min > 0:
        conditions.append("urgency_score >= ?")
        params.append(urgency_min)
    if search:
        conditions.append("(from_email LIKE ? OR from_name LIKE ? OR subject LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like]

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        count_row = fetch_one(f"SELECT COUNT(*) AS n FROM emails {where}", tuple(params))
        total     = count_row.get("n", 0) if count_row else 0

        rows = fetch_all(
            f"""SELECT id, received_at, from_email, from_name, subject,
                       classification, urgency_score, draft_reply, status
                FROM emails {where}
                ORDER BY
                    CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                    urgency_score DESC,
                    received_at DESC
                LIMIT ? OFFSET ?""",
            tuple(params + [limit, offset]),
        )
        return jsonify({"emails": rows, "total": total, "limit": limit, "offset": offset}), 200

    except Exception as e:
        logger.error(f"[EMAILS API] list_emails error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route("/api/emails/stats", methods=["GET"])
@require_auth(roles=["owner", "admin", "client"])
def email_stats():
    """Return quick stats used for the sidebar badge and header KPIs."""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        pending         = fetch_one("SELECT COUNT(*) AS n FROM emails WHERE status = 'pending'")
        sent            = fetch_one("SELECT COUNT(*) AS n FROM emails WHERE status = 'sent'")
        today_total     = fetch_one(
            "SELECT COUNT(*) AS n FROM emails WHERE date(received_at) = ?", (today,))
        today_pending   = fetch_one(
            "SELECT COUNT(*) AS n FROM emails WHERE status = 'pending' AND date(received_at) = ?",
            (today,))
        discarded_today = fetch_one(
            "SELECT COUNT(*) AS n FROM emails WHERE status = 'discarded' AND date(received_at) = ?",
            (today,))

        return jsonify({
            "pending":         pending.get("n", 0)         if pending         else 0,
            "sent":            sent.get("n", 0)            if sent            else 0,
            "today_total":     today_total.get("n", 0)     if today_total     else 0,
            "today_pending":   today_pending.get("n", 0)   if today_pending   else 0,
            "discarded_today": discarded_today.get("n", 0) if discarded_today else 0,
        }), 200

    except Exception as e:
        logger.error(f"[EMAILS API] stats error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route("/api/emails/<int:email_id>", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def get_email(email_id: int):
    """Return a single email including full body.

    Args:
        email_id: Row id in the emails table
    """
    try:
        row = fetch_one("SELECT * FROM emails WHERE id = ?", (email_id,))
        if not row:
            return jsonify({"error": f"Email #{email_id} not found"}), 404
        return jsonify({"email": row}), 200
    except Exception as e:
        logger.error(f"[EMAILS API] get_email error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route("/gate/email-approve", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def email_approve():
    """Approve, edit, or discard a pending email draft.

    This endpoint is proxied from the React frontend via Vite's /gate/* proxy rule
    which targets the Dashboard API. Auth is handled by the before_request JWT guard.

    Request body:
        email_id:    int  — id in the emails table
        action:      str  — "send" | "edit" | "discard"
        edited_body: str  — required when action is "edit"
    """
    try:
        data = request.get_json(force=True) or {}

        try:
            email_id = int(data.get("email_id", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "email_id must be an integer"}), 400

        action      = str(data.get("action", "")).strip()
        edited_body = str(data.get("edited_body", "")).strip()

        if not email_id or action not in ("send", "edit", "discard"):
            return jsonify({"error": "email_id and action (send|edit|discard) required"}), 400

        from memory.database import update
        row = fetch_one("SELECT * FROM emails WHERE id = ?", (email_id,))
        if not row:
            return jsonify({"error": f"Email #{email_id} not found"}), 404
        if row.get("status") != "pending":
            return jsonify({"error": f"Email #{email_id} is not pending (status={row.get('status')})"}), 400

        if action == "discard":
            update("emails", email_id, {"status": "discarded"})
            logger.info(f"[EMAILS API] Email #{email_id} discarded")
            return jsonify({"status": "discarded", "email_id": email_id}), 200

        body_to_send = edited_body if action == "edit" and edited_body else row.get("draft_reply", "")
        if not body_to_send:
            return jsonify({"error": "No body to send"}), 400

        if action == "edit":
            update("emails", email_id, {"draft_reply": body_to_send})

        result = _send_email_draft(row, body_to_send)
        if result:
            update("emails", email_id, {"status": "sent"})
            logger.info(f"[EMAILS API] Email #{email_id} sent")
            return jsonify({"status": "sent", "email_id": email_id}), 200
        else:
            return jsonify({"error": "Send failed — check logs"}), 500

    except Exception as e:
        logger.error(f"[EMAILS API] email_approve error: {e}")
        return jsonify({"error": "Internal server error"}), 500


def _send_email_draft(row: dict, body: str) -> bool:
    """Send a draft email reply via GHL.

    Args:
        row:  Row dict from the emails table
        body: Email body to send

    Returns:
        True on success, False on failure
    """
    try:
        from email_processing.email_sender import send_via_ghl
        subject = f"Re: {row.get('subject', '')}"
        result  = send_via_ghl(
            to_email    = row.get("from_email", ""),
            subject     = subject,
            body        = body,
            location_id = None,
        )
        return result is not None
    except Exception as e:
        logger.error(f"[EMAILS API] _send_email_draft failed: {e}")
        return False


@emails_bp.route("/api/emails/bulk-discard", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def bulk_discard():
    """Discard multiple pending emails in one request.

    Request body:
        ids: list of integer email IDs to discard
    """
    try:
        data = request.get_json(force=True) or {}
        raw_ids = data.get("ids", [])
        if not raw_ids or not isinstance(raw_ids, list):
            return jsonify({"error": "ids array required"}), 400

        ids = []
        for i in raw_ids:
            try:
                ids.append(int(i))
            except (TypeError, ValueError):
                pass

        if not ids:
            return jsonify({"error": "No valid integer ids"}), 400

        with get_conn() as conn:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"UPDATE emails SET status = 'discarded' WHERE id IN ({placeholders}) AND status = 'pending'",
                tuple(ids),
            )
            affected = cursor.rowcount

        print(f"[EMAILS API] Bulk discarded {affected} email(s)")
        return jsonify({"ok": True, "discarded": affected}), 200

    except Exception as e:
        logger.error(f"[EMAILS API] bulk_discard error: {e}")
        return jsonify({"error": "Internal server error"}), 500
