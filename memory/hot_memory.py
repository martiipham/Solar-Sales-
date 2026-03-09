"""Hot Memory — Active state queries for Solar Swarm.

Sub-second access to live experiment state, task queues,
pheromone signals, and current circuit breaker status.
"""

import logging
from datetime import datetime, timedelta
from memory.database import fetch_one, fetch_all, update, insert, json_payload
import config

logger = logging.getLogger(__name__)


# ── Experiments ──────────────────────────────────────────────────────────────

def get_active_experiments() -> list:
    """Return all experiments currently running or approved."""
    return fetch_all(
        "SELECT * FROM experiments WHERE status IN ('approved','running') ORDER BY created_at DESC"
    )


def get_pending_experiments() -> list:
    """Return all experiments awaiting human approval."""
    return fetch_all(
        "SELECT * FROM experiments WHERE status = 'pending' ORDER BY confidence_score DESC"
    )


def get_experiment(experiment_id: int) -> dict:
    """Fetch a single experiment by id."""
    return fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))


def update_experiment_status(experiment_id: int, status: str, extra: dict = None):
    """Update experiment status and optional extra fields."""
    data = {"status": status}
    if extra:
        data.update(extra)
    update("experiments", experiment_id, data)
    logger.info(f"[HOT] Experiment {experiment_id} -> {status}")


def get_budget_used_this_week() -> float:
    """Calculate total budget allocated this week."""
    week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
    row = fetch_one(
        "SELECT COALESCE(SUM(budget_allocated), 0) as total FROM experiments "
        "WHERE created_at >= ? AND status NOT IN ('rejected','killed')",
        (week_start,),
    )
    return row.get("total", 0.0)


def get_consecutive_failures() -> int:
    """Count the current streak of consecutive failed experiments."""
    rows = fetch_all(
        "SELECT status FROM experiments ORDER BY completed_at DESC LIMIT 10"
    )
    count = 0
    for row in rows:
        if row["status"] in ("killed", "rejected"):
            count += 1
        else:
            break
    return count


# ── Task Queue ───────────────────────────────────────────────────────────────

def enqueue_task(job_type: str, context: dict, priority: int = 5, tier: int = 3) -> int:
    """Add a task to the queue and return its id."""
    task_id = insert("task_queue", {
        "job_type": job_type,
        "priority": priority,
        "context_payload": json_payload(context),
        "tier": tier,
        "status": "queued",
    })
    logger.info(f"[HOT] Task queued: {job_type} (id={task_id})")
    return task_id


def get_next_task(tier: int = None) -> dict:
    """Fetch the highest-priority queued task, optionally filtered by tier."""
    if tier:
        return fetch_one(
            "SELECT * FROM task_queue WHERE status='queued' AND tier=? ORDER BY priority ASC, created_at ASC LIMIT 1",
            (tier,),
        )
    return fetch_one(
        "SELECT * FROM task_queue WHERE status='queued' ORDER BY priority ASC, created_at ASC LIMIT 1"
    )


def complete_task(task_id: int, output: dict):
    """Mark a task complete with its output payload."""
    update("task_queue", task_id, {
        "status": "complete",
        "output": json_payload(output),
        "completed_at": datetime.utcnow().isoformat(),
    })


def fail_task(task_id: int, reason: str):
    """Mark a task as failed."""
    update("task_queue", task_id, {
        "status": "failed",
        "output": json_payload({"error": reason}),
        "completed_at": datetime.utcnow().isoformat(),
    })


# ── Pheromone Signals ────────────────────────────────────────────────────────

def post_pheromone(signal_type: str, topic: str, strength: float,
                   vertical: str = None, channel: str = None, experiment_id: int = None) -> int:
    """Post a pheromone signal from a worker."""
    signal_id = insert("pheromone_signals", {
        "signal_type": signal_type,
        "topic": topic,
        "strength": strength,
        "vertical": vertical,
        "channel": channel,
        "experiment_id": experiment_id,
        "decay_factor": 1.0,
    })
    logger.info(f"[PHEROMONE] {signal_type} | {topic} | strength={strength}")
    return signal_id


def get_active_pheromones(topic: str = None) -> list:
    """Get pheromone signals with non-zero weight."""
    if topic:
        return fetch_all(
            "SELECT * FROM pheromone_signals WHERE topic = ? AND decay_factor > 0.01 ORDER BY created_at DESC",
            (topic,),
        )
    return fetch_all(
        "SELECT * FROM pheromone_signals WHERE decay_factor > 0.01 ORDER BY strength DESC LIMIT 50"
    )


def apply_pheromone_decay():
    """Apply daily decay to all pheromone signals older than 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=config.PHEROMONE_DECAY_DAYS)).isoformat()
    from memory.database import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE pheromone_signals SET decay_factor = decay_factor * ? "
            "WHERE created_at < ? AND decay_factor > 0.01",
            (1.0 - config.PHEROMONE_DECAY_RATE, cutoff),
        )
    logger.info("[PHEROMONE] Decay applied to signals older than 7 days")


# ── Circuit Breaker ──────────────────────────────────────────────────────────

def get_circuit_breaker_state() -> dict:
    """Return the current (most recent active) circuit breaker state."""
    row = fetch_one(
        "SELECT * FROM circuit_breaker_log WHERE resolved_at IS NULL ORDER BY triggered_at DESC LIMIT 1"
    )
    if not row:
        return {"level": "green", "active": False}
    return {**row, "active": True}


def get_swarm_summary() -> dict:
    """Return a high-level summary of the swarm for the dashboard."""
    active = fetch_all("SELECT * FROM experiments WHERE status IN ('approved','running')")
    pending = fetch_all("SELECT * FROM experiments WHERE status = 'pending'")
    budget_used = get_budget_used_this_week()
    budget_remaining = config.WEEKLY_BUDGET_AUD - budget_used
    failures = get_consecutive_failures()
    cb = get_circuit_breaker_state()
    return {
        "active_experiments": len(active),
        "pending_approval": len(pending),
        "budget_used_aud": round(budget_used, 2),
        "budget_remaining_aud": round(budget_remaining, 2),
        "consecutive_failures": failures,
        "circuit_breaker": cb.get("level", "green"),
    }
