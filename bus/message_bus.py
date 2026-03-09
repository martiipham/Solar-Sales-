"""Message Bus — SQLite-backed inter-agent communication for Solar Swarm.

All agents communicate by writing to and reading from this bus.
Every message is logged, auditable, and never deleted.

Message flow:
  sender.post(to_queue, msg_type, payload) → bus (queued)
  receiver.receive(queue_name)             → bus (processing)
  receiver.ack(msg_id)                     → bus (complete)

Priority order: CRITICAL → HIGH → NORMAL → LOW
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from memory.database import get_conn, fetch_all, fetch_one, json_payload, parse_payload

logger = logging.getLogger(__name__)


def post(
    from_agent: str,
    to_queue: str,
    msg_type: str,
    payload: dict,
    priority: str = "NORMAL",
    reply_to: str = None,
    ttl_cycles: int = 3,
    requires_ack: bool = False,
) -> str:
    """Post a message onto the bus for a target queue.

    Args:
        from_agent: Identifier of the sending agent
        to_queue: Name of the destination queue
        msg_type: TASK | REPORT | ALERT | ACK | KILL | QUERY | RESPONSE
        payload: Message data dict
        priority: CRITICAL | HIGH | NORMAL | LOW
        reply_to: msg_id this is a response to
        ttl_cycles: Expire after this many scheduler cycles
        requires_ack: If True, sender expects explicit ACK back

    Returns:
        Unique message id (msg_id)
    """
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO message_bus
               (msg_id, from_agent, to_queue, msg_type, priority,
                payload, reply_to, ttl_cycles, requires_ack, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                msg_id, from_agent, to_queue, msg_type, priority,
                json_payload(payload), reply_to, ttl_cycles,
                1 if requires_ack else 0, "queued",
            ),
        )
    logger.info(f"[BUS] {from_agent} → {to_queue} | {msg_type} | {priority} | {msg_id}")
    return msg_id


def receive(queue_name: str, msg_type: str = None) -> dict:
    """Fetch the highest-priority queued message for a queue.

    Args:
        queue_name: The queue to read from
        msg_type: Optional filter by message type

    Returns:
        Message dict or empty dict if nothing queued
    """
    priority_order = "CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'NORMAL' THEN 3 ELSE 4 END"

    if msg_type:
        row = fetch_one(
            f"SELECT * FROM message_bus WHERE to_queue=? AND msg_type=? AND status='queued' "
            f"ORDER BY {priority_order}, created_at ASC LIMIT 1",
            (queue_name, msg_type),
        )
    else:
        row = fetch_one(
            f"SELECT * FROM message_bus WHERE to_queue=? AND status='queued' "
            f"ORDER BY {priority_order}, created_at ASC LIMIT 1",
            (queue_name,),
        )

    if not row:
        return {}

    with get_conn() as conn:
        conn.execute(
            "UPDATE message_bus SET status='processing' WHERE msg_id=?",
            (row["msg_id"],),
        )

    row["payload"] = parse_payload(row.get("payload", "{}"))
    return dict(row)


def receive_all(queue_name: str, msg_type: str = None, limit: int = 20) -> list:
    """Fetch all queued messages for a queue (drains queue).

    Args:
        queue_name: The queue to drain
        msg_type: Optional filter by message type
        limit: Max messages to return

    Returns:
        List of message dicts
    """
    if msg_type:
        rows = fetch_all(
            "SELECT * FROM message_bus WHERE to_queue=? AND msg_type=? AND status='queued' "
            "ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'NORMAL' THEN 3 ELSE 4 END, created_at ASC LIMIT ?",
            (queue_name, msg_type, limit),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM message_bus WHERE to_queue=? AND status='queued' "
            "ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'NORMAL' THEN 3 ELSE 4 END, created_at ASC LIMIT ?",
            (queue_name, limit),
        )

    ids = [r["msg_id"] for r in rows]
    if ids:
        placeholders = ",".join("?" for _ in ids)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE message_bus SET status='processing' WHERE msg_id IN ({placeholders})",
                ids,
            )

    return [{**r, "payload": parse_payload(r.get("payload", "{}"))} for r in rows]


def complete(msg_id: str):
    """Mark a message as successfully processed."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE message_bus SET status='complete', completed_at=? WHERE msg_id=?",
            (datetime.utcnow().isoformat(), msg_id),
        )


def fail(msg_id: str, reason: str = ""):
    """Mark a message as failed."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE message_bus SET status='failed', completed_at=? WHERE msg_id=?",
            (datetime.utcnow().isoformat(), msg_id),
        )
    logger.warning(f"[BUS] Message {msg_id} failed: {reason}")


def ack(original_msg_id: str, from_agent: str, payload: dict = None) -> str:
    """Send an ACK response to a message that required acknowledgement.

    Args:
        original_msg_id: The msg_id being acknowledged
        from_agent: The acknowledging agent
        payload: Optional response data

    Returns:
        New ACK msg_id
    """
    original = fetch_one(
        "SELECT from_agent, to_queue FROM message_bus WHERE msg_id=?",
        (original_msg_id,),
    )
    if not original:
        return ""

    return post(
        from_agent=from_agent,
        to_queue=original["from_agent"],
        msg_type="ACK",
        payload=payload or {"acked_msg_id": original_msg_id},
        reply_to=original_msg_id,
        requires_ack=False,
    )


def expire_old_messages():
    """Mark messages older than their TTL as expired.

    Called once per scheduler cycle.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=6)).isoformat()
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE message_bus SET status='expired' WHERE status='queued' AND created_at < ?",
            (cutoff,),
        )
    if result.rowcount > 0:
        logger.info(f"[BUS] Expired {result.rowcount} stale messages")


def queue_depth(queue_name: str) -> dict:
    """Return counts of messages in each state for a queue.

    Args:
        queue_name: The queue to inspect

    Returns:
        Dict with queued, processing, complete, failed counts
    """
    rows = fetch_all(
        "SELECT status, COUNT(*) as count FROM message_bus WHERE to_queue=? GROUP BY status",
        (queue_name,),
    )
    result = {"queued": 0, "processing": 0, "complete": 0, "failed": 0, "expired": 0}
    for r in rows:
        result[r["status"]] = r["count"]
    return result


def get_bus_summary() -> dict:
    """High-level bus health summary for the dashboard."""
    rows = fetch_all(
        "SELECT to_queue, status, COUNT(*) as count FROM message_bus "
        "GROUP BY to_queue, status ORDER BY to_queue"
    )
    summary = {}
    for r in rows:
        queue = r["to_queue"]
        if queue not in summary:
            summary[queue] = {}
        summary[queue][r["status"]] = r["count"]
    return summary
