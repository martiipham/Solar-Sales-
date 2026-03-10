"""Opportunity Store — Lifecycle management for discovered prospects.

Wraps the opportunities table (created in database.py).

Statuses: discovered → actioned → won | lost
"""

import logging
from datetime import datetime

from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)


def add(title: str, opp_type: str, effort: str = "medium",
        impact: str = "medium", priority_score: float = 5.0,
        source: str = "", notes: str = "") -> int:
    """Insert a new opportunity into the store.

    Args:
        title:          Short description
        opp_type:       Category (e.g. 'solar_lead', 'partnership', 'content')
        effort:         low | medium | high
        impact:         low | medium | high
        priority_score: 0-10 float used for ranking
        source:         Where it was found
        notes:          Free-text notes

    Returns:
        New row id
    """
    try:
        opp_id = insert("opportunities", {
            "title":          title,
            "opp_type":       opp_type,
            "status":         "discovered",
            "effort":         effort,
            "impact":         impact,
            "priority_score": priority_score,
            "source":         source,
            "notes":          notes,
        })
        print(f"[OPP STORE] Added: {title[:60]} (id={opp_id} score={priority_score})")
        return opp_id
    except Exception as e:
        logger.error(f"[OPP STORE] add failed: {e}")
        return 0


def get_top(limit: int = 10, status: str = "discovered") -> list:
    """Return top opportunities ordered by priority_score descending.

    Args:
        limit:  Max rows to return
        status: Filter by status (default 'discovered')

    Returns:
        List of opportunity dicts
    """
    try:
        if status:
            return fetch_all(
                "SELECT * FROM opportunities WHERE status = ? "
                "ORDER BY priority_score DESC LIMIT ?",
                (status, limit),
            )
        return fetch_all(
            "SELECT * FROM opportunities ORDER BY priority_score DESC LIMIT ?",
            (limit,),
        )
    except Exception as e:
        logger.error(f"[OPP STORE] get_top failed: {e}")
        return []


def get_summary() -> dict:
    """Return opportunity counts grouped by status.

    Returns:
        Dict with by_status counts and total
    """
    try:
        rows = fetch_all(
            "SELECT status, COUNT(*) as n FROM opportunities GROUP BY status"
        )
        by_status = {r["status"]: r["n"] for r in rows}
        return {
            "by_status": by_status,
            "total":     sum(by_status.values()),
        }
    except Exception as e:
        logger.error(f"[OPP STORE] get_summary failed: {e}")
        return {"by_status": {}, "total": 0}


def action(opp_id: int, notes: str = "") -> bool:
    """Mark an opportunity as actioned (being pursued).

    Args:
        opp_id: Row id
        notes:  Optional action notes

    Returns:
        True on success
    """
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE opportunities SET status = 'actioned', notes = notes || ? "
                "WHERE id = ?",
                (f" | Actioned {datetime.utcnow().date()}: {notes}", opp_id),
            )
        return True
    except Exception as e:
        logger.error(f"[OPP STORE] action failed: {e}")
        return False


def close(opp_id: int, outcome: str = "won", notes: str = "") -> bool:
    """Close an opportunity as won or lost.

    Args:
        opp_id:  Row id
        outcome: 'won' or 'lost'
        notes:   Closing notes

    Returns:
        True on success
    """
    try:
        status = "won" if outcome == "won" else "lost"
        with get_conn() as conn:
            conn.execute(
                "UPDATE opportunities SET status = ?, notes = notes || ? WHERE id = ?",
                (status, f" | Closed {outcome} {datetime.utcnow().date()}: {notes}", opp_id),
            )
        return True
    except Exception as e:
        logger.error(f"[OPP STORE] close failed: {e}")
        return False
