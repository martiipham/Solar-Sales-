"""Message Bus — SQLite-backed inter-agent messaging.

Priority levels (lower number = higher priority):
  1 = CRITICAL
  2 = HIGH
  3 = NORMAL
  4 = LOW

Message types: TASK | REPORT | ALERT | ACK | KILL | QUERY | RESPONSE
"""

import json
import logging
from datetime import datetime

from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)


def send(to_agent: str, msg_type: str, payload: dict,
         from_agent: str = "system", priority: int = 3) -> int:
    """Send a message to an agent queue.

    Args:
        to_agent:   Destination agent name (e.g. 'master', 'qualification')
        msg_type:   TASK | REPORT | ALERT | ACK | KILL | QUERY | RESPONSE
        payload:    Message body dict
        from_agent: Sender agent name
        priority:   1 (CRITICAL) – 4 (LOW)

    Returns:
        New message row id
    """
    try:
        msg_id = insert("message_bus", {
            "to_agent":   to_agent,
            "from_agent": from_agent,
            "msg_type":   msg_type,
            "priority":   priority,
            "payload":    json.dumps(payload),
            "status":     "queued",
        })
        logger.debug(f"[BUS] {from_agent}→{to_agent} [{msg_type}] id={msg_id}")
        return msg_id
    except Exception as e:
        logger.error(f"[BUS] send failed: {e}")
        return 0


def receive(to_agent: str, limit: int = 10) -> list:
    """Fetch pending messages for an agent, ordered by priority then created_at.

    Marks fetched messages as 'processing'.

    Args:
        to_agent: Agent name to receive messages for
        limit:    Max messages to fetch

    Returns:
        List of message dicts
    """
    try:
        rows = fetch_all(
            "SELECT * FROM message_bus WHERE to_agent = ? AND status = 'queued' "
            "ORDER BY priority ASC, created_at ASC LIMIT ?",
            (to_agent, limit),
        )
        if rows:
            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" * len(ids))
            with get_conn() as conn:
                conn.execute(
                    f"UPDATE message_bus SET status = 'processing' WHERE id IN ({placeholders})",
                    tuple(ids),
                )
        return rows
    except Exception as e:
        logger.error(f"[BUS] receive failed: {e}")
        return []


def ack(msg_id: int) -> None:
    """Mark a message as complete.

    Args:
        msg_id: Message row id
    """
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE message_bus SET status = 'complete' WHERE id = ?",
                (msg_id,),
            )
    except Exception as e:
        logger.error(f"[BUS] ack failed: {e}")


def fail(msg_id: int, reason: str = "") -> None:
    """Mark a message as failed.

    Args:
        msg_id: Message row id
        reason: Failure description
    """
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE message_bus SET status = 'failed' WHERE id = ?",
                (msg_id,),
            )
    except Exception as e:
        logger.error(f"[BUS] fail failed: {e}")


def purge_expired(max_age_hours: int = 24) -> int:
    """Delete completed and failed messages older than max_age_hours.

    Args:
        max_age_hours: Age threshold

    Returns:
        Number of rows deleted
    """
    try:
        cutoff = (
            datetime.utcnow()
            .replace(microsecond=0)
            .isoformat()
        )
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM message_bus WHERE status IN ('complete','failed') "
                "AND datetime(created_at, ? || ' hours') < ?",
                (str(max_age_hours), cutoff),
            )
            deleted = cur.rowcount
        if deleted:
            logger.info(f"[BUS] Purged {deleted} expired messages")
        return deleted
    except Exception as e:
        logger.error(f"[BUS] purge_expired failed: {e}")
        return 0


def get_bus_summary() -> dict:
    """Return per-queue message counts by status.

    Returns:
        Dict of {to_agent: {queued, processing, complete, failed}}
    """
    try:
        rows = fetch_all(
            "SELECT to_agent, status, COUNT(*) as n "
            "FROM message_bus GROUP BY to_agent, status"
        )
        summary: dict = {}
        for r in rows:
            agent  = r["to_agent"]
            status = r["status"]
            count  = r["n"]
            if agent not in summary:
                summary[agent] = {"queued": 0, "processing": 0, "complete": 0, "failed": 0}
            if status in summary[agent]:
                summary[agent][status] = count
        return summary
    except Exception as e:
        logger.error(f"[BUS] get_bus_summary failed: {e}")
        return {}
