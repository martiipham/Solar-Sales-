"""Analytics Agent — Lead pipeline and conversion statistics.

Queries the local SQLite database to compute conversion rates,
average scores, and pipeline breakdown for the CLI stats command
and dashboard reporting.
"""

import logging
from datetime import datetime, timedelta

from memory.database import fetch_one, fetch_all

logger = logging.getLogger(__name__)


def get_conversion_stats() -> dict:
    """Return conversion funnel statistics from the leads table.

    Computes counts by recommended_action and status, plus overall
    conversion rate and average qualification score.

    Returns:
        Dict with total_leads, call_now, nurture, disqualify, converted,
        conversion_rate_pct, avg_qualification_score
    """
    try:
        total  = fetch_one("SELECT COUNT(*) as n FROM leads")
        hot    = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE recommended_action = 'call_now' "
            "OR qualification_score >= 7"
        )
        nurture = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE recommended_action = 'nurture'"
        )
        disqual = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE recommended_action = 'disqualify'"
        )
        conv = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE status = 'converted'"
        )
        avg = fetch_one(
            "SELECT AVG(qualification_score) as a FROM leads "
            "WHERE qualification_score IS NOT NULL"
        )

        total_n = total.get("n", 0) if total else 0
        conv_n  = conv.get("n", 0)  if conv  else 0
        avg_score = round(avg.get("a") or 0, 1) if avg else 0

        return {
            "total_leads":             total_n,
            "call_now":                hot.get("n", 0)     if hot     else 0,
            "nurture":                 nurture.get("n", 0) if nurture else 0,
            "disqualify":              disqual.get("n", 0) if disqual else 0,
            "converted":               conv_n,
            "conversion_rate_pct":     round(conv_n / total_n * 100, 1) if total_n else 0,
            "avg_qualification_score": avg_score,
        }
    except Exception as e:
        logger.error(f"[ANALYTICS] get_conversion_stats failed: {e}")
        return {
            "total_leads": 0, "call_now": 0, "nurture": 0, "disqualify": 0,
            "converted": 0, "conversion_rate_pct": 0, "avg_qualification_score": 0,
        }


def get_weekly_lead_trend() -> list:
    """Return daily lead counts for the past 7 days.

    Returns:
        List of dicts: [{date, count}] ordered oldest first
    """
    try:
        rows = fetch_all(
            "SELECT date(created_at) as day, COUNT(*) as count "
            "FROM leads "
            "WHERE created_at >= date('now', '-7 days') "
            "GROUP BY day ORDER BY day ASC"
        )
        return [{"date": r["day"], "count": r["count"]} for r in rows]
    except Exception as e:
        logger.error(f"[ANALYTICS] get_weekly_lead_trend failed: {e}")
        return []


def get_score_distribution() -> dict:
    """Return lead count broken down by score band.

    Bands: cold (0-4), warm (5-6), hot (7-10)

    Returns:
        Dict with cold, warm, hot counts
    """
    try:
        cold = fetch_one(
            "SELECT COUNT(*) as n FROM leads "
            "WHERE qualification_score < 5 AND qualification_score IS NOT NULL"
        )
        warm = fetch_one(
            "SELECT COUNT(*) as n FROM leads "
            "WHERE qualification_score >= 5 AND qualification_score < 7"
        )
        hot = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE qualification_score >= 7"
        )
        return {
            "cold": cold.get("n", 0) if cold else 0,
            "warm": warm.get("n", 0) if warm else 0,
            "hot":  hot.get("n", 0)  if hot  else 0,
        }
    except Exception as e:
        logger.error(f"[ANALYTICS] get_score_distribution failed: {e}")
        return {"cold": 0, "warm": 0, "hot": 0}
