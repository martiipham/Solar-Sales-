"""Calls API — voice call logs, transcripts, and performance stats.

Endpoints:
  GET /api/calls              — paginated call list (filterable)
  GET /api/calls/stats        — today / this week / all time counts + rates
  GET /api/calls/<call_id>    — single call with full transcript
"""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from memory.database import fetch_all, fetch_one
from api.auth import require_auth

logger = logging.getLogger(__name__)

calls_bp = Blueprint("calls", __name__)


def _fmt_duration(seconds) -> str:
    """Format seconds into mm:ss string."""
    if not seconds:
        return "0:00"
    try:
        s = int(seconds)
        return f"{s // 60}:{s % 60:02d}"
    except Exception:
        return "0:00"


def _parse_transcript(raw) -> list:
    """Parse transcript_text field — stored as JSON string or list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []


def _row_to_call(row) -> dict:
    """Convert a DB row to a clean call dict for the API."""
    d = dict(row)
    d["duration_fmt"] = _fmt_duration(d.get("duration_seconds"))
    d["transcript"] = _parse_transcript(d.get("transcript_text"))
    d.pop("transcript_text", None)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@calls_bp.route("/api/calls", methods=["GET"])
@require_auth()
def list_calls():
    """Return paginated call log, optionally filtered by date range or status."""
    try:
        limit  = min(int(request.args.get("limit", 20)), 100)
        offset = int(request.args.get("offset", 0))
        status = request.args.get("status")          # e.g. "completed", "failed"
        since  = request.args.get("since")           # ISO date string

        clauses = []
        params  = []

        if status:
            clauses.append("status = ?")
            params.append(status)

        if since:
            clauses.append("started_at >= ?")
            params.append(since)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"""
            SELECT call_id, client_id, from_phone, to_phone, agent_id,
                   status, duration_seconds, recording_url, lead_score, started_at,
                   transcript_text
            FROM call_logs
            {where}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        rows = fetch_all(query, tuple(params))
        calls = [_row_to_call(r) for r in rows]

        # Total count for pagination
        count_query = f"SELECT COUNT(*) as cnt FROM call_logs {where}"
        count_row = fetch_one(count_query, tuple(params[:-2]))
        total = dict(count_row).get("cnt", 0) if count_row else 0

        return jsonify({"calls": calls, "total": total, "limit": limit, "offset": offset}), 200

    except Exception as e:
        logger.error(f"[CALLS API] list_calls error: {e}")
        return jsonify({"error": str(e), "calls": []}), 500


@calls_bp.route("/api/calls/stats", methods=["GET"])
@require_auth()
def call_stats():
    """Return aggregated call performance stats for the dashboard."""
    try:
        now   = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()

        def _counts(since_iso: str) -> dict:
            row = fetch_one(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed, "
                "AVG(duration_seconds) as avg_duration, "
                "AVG(lead_score) as avg_score "
                "FROM call_logs WHERE started_at >= ?",
                (since_iso,)
            )
            return dict(row) if row else {}

        today_row = fetch_one(
            "SELECT COUNT(*) as cnt FROM call_logs WHERE started_at >= ?",
            (today,)
        )

        week  = _counts(week_ago)
        month = _counts(month_ago)

        # Booking rate: leads with status 'called' or 'converted' / total calls
        booked_row = fetch_one(
            "SELECT COUNT(*) as cnt FROM leads WHERE status IN ('called','converted') "
            "AND created_at >= ?",
            (week_ago,)
        )
        booked = dict(booked_row).get("cnt", 0) if booked_row else 0
        total_week_calls = week.get("total") or 1
        booking_rate = round((booked / total_week_calls) * 100, 1)

        return jsonify({
            "today": {
                "calls": dict(today_row).get("cnt", 0) if today_row else 0,
            },
            "this_week": {
                "calls":        week.get("total") or 0,
                "completed":    week.get("completed") or 0,
                "avg_duration": _fmt_duration(week.get("avg_duration")),
                "avg_score":    round(week.get("avg_score") or 0, 1),
                "booking_rate": booking_rate,
            },
            "this_month": {
                "calls":     month.get("total") or 0,
                "completed": month.get("completed") or 0,
            },
        }), 200

    except Exception as e:
        logger.error(f"[CALLS API] call_stats error: {e}")
        return jsonify({"error": str(e)}), 500


@calls_bp.route("/api/calls/<call_id>", methods=["GET"])
@require_auth()
def get_call(call_id: str):
    """Return full call detail including parsed transcript."""
    try:
        row = fetch_one(
            "SELECT * FROM call_logs WHERE call_id = ?",
            (call_id,)
        )
        if not row:
            return jsonify({"error": "Call not found"}), 404

        return jsonify({"call": _row_to_call(row)}), 200

    except Exception as e:
        logger.error(f"[CALLS API] get_call error: {e}")
        return jsonify({"error": str(e)}), 500
