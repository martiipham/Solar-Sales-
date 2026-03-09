"""Opportunity Store — Manages discovered opportunities for Solar Swarm.

Stores, scores, retrieves, and tracks actionable opportunities surfaced
by the research engine, data collection pipeline, and scout agents.
Opportunities flow from discovered → queued → actioned → won|lost.
"""

import logging
import uuid
from datetime import datetime
from memory.database import get_conn, fetch_all, fetch_one, json_payload, parse_payload

logger = logging.getLogger(__name__)


def save(
    title: str,
    description: str,
    opp_type: str,
    effort: str,
    impact: str,
    confidence: float,
    source: str = "research",
    metadata: dict = None,
) -> str:
    """Save a new opportunity.

    Args:
        title: Short opportunity title
        description: What to do and why
        opp_type: prospect|strategy|product|partnership|content
        effort: low|medium|high
        impact: low|medium|high
        confidence: 0.0–1.0
        source: Which agent/engine discovered this
        metadata: Any extra data (company info, signals, etc.)

    Returns:
        opp_id
    """
    opp_id = f"opp_{uuid.uuid4().hex[:10]}"
    impact_score = {"low": 3, "medium": 6, "high": 9}.get(impact, 5)
    effort_score = {"low": 1, "medium": 2, "high": 3}.get(effort, 2)
    priority_score = round((impact_score / effort_score) * confidence, 2)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO opportunities
               (opp_id, title, description, opp_type, effort, impact,
                confidence, priority_score, source, status, metadata, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,'discovered',?,?)""",
            (opp_id, title, description, opp_type, effort, impact,
             confidence, priority_score, source,
             json_payload(metadata or {}),
             datetime.utcnow().isoformat()),
        )

    logger.info(f"[OPP STORE] Saved: {title} (score={priority_score})")
    return opp_id


def get_top(limit: int = 10, opp_type: str = None, status: str = "discovered") -> list:
    """Retrieve top opportunities sorted by priority score.

    Args:
        limit: Max opportunities to return
        opp_type: Optional type filter
        status: discovered|queued|actioned|won|lost

    Returns:
        List of opportunity dicts
    """
    if opp_type:
        rows = fetch_all(
            """SELECT * FROM opportunities WHERE status=? AND opp_type=?
               ORDER BY priority_score DESC LIMIT ?""",
            (status, opp_type, limit),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM opportunities WHERE status=? ORDER BY priority_score DESC LIMIT ?",
            (status, limit),
        )
    return [{**dict(r), "metadata": parse_payload(r.get("metadata", "{}"))} for r in rows]


def update_status(opp_id: str, status: str, notes: str = "") -> bool:
    """Move an opportunity through its lifecycle.

    Args:
        opp_id: Opportunity to update
        status: New status: queued|actioned|won|lost
        notes: Optional context for the status change

    Returns:
        True if updated, False if not found
    """
    existing = fetch_one("SELECT opp_id FROM opportunities WHERE opp_id=?", (opp_id,))
    if not existing:
        return False

    with get_conn() as conn:
        conn.execute(
            "UPDATE opportunities SET status=?, notes=?, updated_at=? WHERE opp_id=?",
            (status, notes, datetime.utcnow().isoformat(), opp_id),
        )
    logger.info(f"[OPP STORE] {opp_id} → {status}")
    return True


def get_summary() -> dict:
    """Return opportunity counts by status and type for dashboard."""
    status_rows = fetch_all(
        "SELECT status, COUNT(*) as count FROM opportunities GROUP BY status"
    )
    type_rows = fetch_all(
        "SELECT opp_type, COUNT(*) as count, AVG(confidence) as avg_conf "
        "FROM opportunities WHERE status='discovered' GROUP BY opp_type"
    )
    return {
        "by_status": {r["status"]: r["count"] for r in status_rows},
        "by_type": {
            r["opp_type"]: {"count": r["count"], "avg_confidence": round(r["avg_conf"] or 0, 2)}
            for r in type_rows
        },
    }


def mark_duplicate(opp_id: str, duplicate_of: str):
    """Flag an opportunity as a duplicate of an existing one."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE opportunities SET status='lost', notes=? WHERE opp_id=?",
            (f"duplicate of {duplicate_of}", opp_id),
        )
