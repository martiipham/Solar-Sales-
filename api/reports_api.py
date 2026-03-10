"""Reports API — monthly performance summary for client dashboard.

Endpoint:
  GET /api/reports/monthly    — current month stats vs prior month
  GET /api/reports/summary    — all-time headline numbers
  GET /api/reports/weekly     — daily breakdown for the past N days (default 30)
"""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from memory.database import fetch_all, fetch_one
from api.auth import require_auth

logger = logging.getLogger(__name__)

reports_bp = Blueprint("reports", __name__)


def _month_bounds(offset: int = 0):
    """Return (start_iso, end_iso) for a given month offset (0=current, -1=prior)."""
    now   = datetime.utcnow()
    year  = now.year
    month = now.month + offset

    # Normalise month overflow
    while month < 1:
        month += 12
        year  -= 1
    while month > 12:
        month -= 12
        year  += 1

    start = datetime(year, month, 1)
    # End = first day of next month
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)

    return start.isoformat(), end.isoformat()


def _call_metrics(since: str, until: str) -> dict:
    """Aggregate call stats for a date window."""
    row = fetch_one(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed, "
        "AVG(duration_seconds) as avg_duration, "
        "AVG(lead_score) as avg_score "
        "FROM call_logs WHERE started_at >= ? AND started_at < ?",
        (since, until),
    )
    d = dict(row) if row else {}

    def fmt(s):
        if not s:
            return "0:00"
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"

    return {
        "calls":        d.get("total") or 0,
        "completed":    d.get("completed") or 0,
        "avg_duration": fmt(d.get("avg_duration")),
        "avg_score":    round(d.get("avg_score") or 0, 1),
    }


def _lead_metrics(since: str, until: str) -> dict:
    """Aggregate lead stats for a date window."""
    row = fetch_one(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='converted' THEN 1 ELSE 0 END) as converted, "
        "SUM(CASE WHEN qualification_score >= 7 THEN 1 ELSE 0 END) as hot, "
        "AVG(qualification_score) as avg_score "
        "FROM leads WHERE created_at >= ? AND created_at < ?",
        (since, until),
    )
    d = dict(row) if row else {}
    total = d.get("total") or 0
    converted = d.get("converted") or 0
    return {
        "total":           total,
        "hot":             d.get("hot") or 0,
        "converted":       converted,
        "conversion_rate": round((converted / total * 100), 1) if total else 0,
        "avg_score":       round(d.get("avg_score") or 0, 1),
    }


def _pct_change(current, prior) -> str:
    """Return formatted percentage change string."""
    if not prior:
        return "+100%" if current else "—"
    change = ((current - prior) / prior) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.0f}%"


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@reports_bp.route("/api/reports/monthly", methods=["GET"])
@require_auth()
def monthly_report():
    """Return current-month performance vs prior month."""
    try:
        curr_start, curr_end = _month_bounds(0)
        prev_start, prev_end = _month_bounds(-1)

        curr_calls = _call_metrics(curr_start, curr_end)
        prev_calls = _call_metrics(prev_start, prev_end)

        curr_leads = _lead_metrics(curr_start, curr_end)
        prev_leads = _lead_metrics(prev_start, prev_end)

        now = datetime.utcnow()

        return jsonify({
            "period": {
                "label": now.strftime("%B %Y"),
                "start": curr_start,
                "end":   curr_end,
            },
            "calls": {
                "current":    curr_calls,
                "prior":      prev_calls,
                "vs_prior":   _pct_change(curr_calls["calls"], prev_calls["calls"]),
            },
            "leads": {
                "current":    curr_leads,
                "prior":      prev_leads,
                "vs_prior":   _pct_change(curr_leads["total"], prev_leads["total"]),
            },
            "highlights": _build_highlights(curr_calls, curr_leads, prev_calls, prev_leads),
        }), 200

    except Exception as e:
        logger.error(f"[REPORTS API] monthly_report error: {e}")
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/api/reports/summary", methods=["GET"])
@require_auth()
def all_time_summary():
    """Return all-time headline numbers for the account."""
    try:
        calls_row = fetch_one(
            "SELECT COUNT(*) as total, AVG(lead_score) as avg_score FROM call_logs"
        )
        leads_row = fetch_one(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN status='converted' THEN 1 ELSE 0 END) as converted "
            "FROM leads"
        )
        # First call date
        first_row = fetch_one(
            "SELECT MIN(started_at) as first FROM call_logs"
        )

        calls_d = dict(calls_row) if calls_row else {}
        leads_d = dict(leads_row) if leads_row else {}
        first_d = dict(first_row) if first_row else {}

        total_calls  = calls_d.get("total") or 0
        total_leads  = leads_d.get("total") or 0
        total_conv   = leads_d.get("converted") or 0

        return jsonify({
            "total_calls":     total_calls,
            "total_leads":     total_leads,
            "total_converted": total_conv,
            "avg_lead_score":  round(calls_d.get("avg_score") or 0, 1),
            "conversion_rate": round((total_conv / total_leads * 100), 1) if total_leads else 0,
            "active_since":    first_d.get("first"),
        }), 200

    except Exception as e:
        logger.error(f"[REPORTS API] summary error: {e}")
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/api/reports/weekly", methods=["GET"])
@require_auth()
def weekly_trend():
    """Return daily call and lead counts for the past N days.

    Query params:
        days: Look-back window in days (default 30, max 90)

    Response:
        days:   list of {date, calls, leads, hot_leads, conversions}
        totals: summed values across the window
    """
    try:
        days = min(int(request.args.get("days", 30)), 90)
    except (TypeError, ValueError):
        days = 30

    try:
        # Build a date series using a recursive CTE so days with zero activity appear
        rows_calls = fetch_all(
            "SELECT date(started_at) AS day, COUNT(*) AS calls "
            "FROM call_logs "
            "WHERE started_at >= date('now', ? || ' days') "
            "GROUP BY day",
            (f"-{days}",),
        )
        rows_leads = fetch_all(
            "SELECT date(created_at) AS day, "
            "COUNT(*) AS leads, "
            "SUM(CASE WHEN qualification_score >= 7 THEN 1 ELSE 0 END) AS hot_leads, "
            "SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) AS conversions "
            "FROM leads "
            "WHERE created_at >= date('now', ? || ' days') "
            "GROUP BY day",
            (f"-{days}",),
        )

        # Index by date for merge
        calls_map = {r["day"]: r["calls"] for r in rows_calls}
        leads_map = {
            r["day"]: {
                "leads": r["leads"],
                "hot_leads": r["hot_leads"] or 0,
                "conversions": r["conversions"] or 0,
            }
            for r in rows_leads
        }

        # Produce full date range
        from datetime import date, timedelta as td
        today = date.today()
        result_days = []
        totals = {"calls": 0, "leads": 0, "hot_leads": 0, "conversions": 0}

        for i in range(days - 1, -1, -1):
            d = (today - td(days=i)).isoformat()
            calls = calls_map.get(d, 0)
            ld    = leads_map.get(d, {"leads": 0, "hot_leads": 0, "conversions": 0})
            result_days.append({
                "date":        d,
                "calls":       calls,
                "leads":       ld["leads"],
                "hot_leads":   ld["hot_leads"],
                "conversions": ld["conversions"],
            })
            totals["calls"]       += calls
            totals["leads"]       += ld["leads"]
            totals["hot_leads"]   += ld["hot_leads"]
            totals["conversions"] += ld["conversions"]

        return jsonify({
            "window_days": days,
            "days":        result_days,
            "totals":      totals,
        }), 200

    except Exception as e:
        logger.error(f"[REPORTS API] weekly_trend error: {e}")
        return jsonify({"error": str(e)}), 500


@reports_bp.route("/api/reports/daily-activity", methods=["GET"])
@require_auth()
def daily_activity():
    """Return last 7 days of call + email + lead counts for the activity chart.

    Response:
        days: list of {day, date, calls, emails, leads}
              where day is a short weekday label (Mon, Tue, …)
    """
    try:
        results = []
        for i in range(6, -1, -1):
            d        = (datetime.utcnow() - timedelta(days=i)).date()
            date_str = d.isoformat()

            calls_row  = fetch_one("SELECT COUNT(*) AS n FROM call_logs WHERE DATE(started_at)  = ?", (date_str,))
            emails_row = fetch_one("SELECT COUNT(*) AS n FROM emails    WHERE DATE(received_at) = ?", (date_str,))
            leads_row  = fetch_one("SELECT COUNT(*) AS n FROM leads     WHERE DATE(created_at)  = ?", (date_str,))

            results.append({
                "day":    d.strftime("%a"),
                "date":   date_str,
                "calls":  (calls_row  or {}).get("n", 0),
                "emails": (emails_row or {}).get("n", 0),
                "leads":  (leads_row  or {}).get("n", 0),
            })

        return jsonify({"days": results}), 200

    except Exception as e:
        logger.error(f"[REPORTS] daily_activity error: {e}")
        return jsonify({"days": []}), 500


def _build_highlights(curr_calls, curr_leads, prev_calls, prev_leads) -> list:
    """Build a list of highlight bullet points comparing current vs prior month."""
    highlights = []

    call_diff = curr_calls["calls"] - prev_calls["calls"]
    if call_diff > 0:
        highlights.append(f"{call_diff} more calls handled than last month")
    elif call_diff < 0:
        highlights.append(f"{abs(call_diff)} fewer calls than last month")

    lead_diff = curr_leads["total"] - prev_leads["total"]
    if lead_diff > 0:
        highlights.append(f"{lead_diff} more leads qualified this month")

    if curr_leads["conversion_rate"] > prev_leads["conversion_rate"]:
        delta = curr_leads["conversion_rate"] - prev_leads["conversion_rate"]
        highlights.append(f"Conversion rate up {delta:.1f}% vs last month")

    if curr_leads["hot"] > 0:
        highlights.append(f"{curr_leads['hot']} hot leads scored 7+ this month")

    if not highlights:
        highlights.append("Keep going — your AI receptionist is active and handling calls")

    return highlights
