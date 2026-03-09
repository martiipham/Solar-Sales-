"""Circuit Breaker safety system for Solar Swarm.

Monitors experiment outcomes and budget burn rate.
Triggers automatic halts when thresholds are breached.

Levels:
  Green  — all clear, normal operation
  Yellow — 3 consecutive failures (warning, continue)
  Orange — budget burn > 150% of plan (slowdown)
  Red    — 5 consecutive failures OR single loss > 40% budget → full halt
"""

import logging
from datetime import datetime
from memory.database import insert, update, fetch_one, fetch_all
from memory.hot_memory import get_consecutive_failures, get_budget_used_this_week, get_circuit_breaker_state
from memory.cold_ledger import log_circuit_breaker
import config

logger = logging.getLogger(__name__)


def check_and_trigger(
    consecutive_failures: int = None,
    budget_burn_rate: float = None,
    single_loss_aud: float = None,
) -> dict:
    """Evaluate circuit breaker conditions and trigger if needed.

    Args:
        consecutive_failures: Current streak of failed experiments
        budget_burn_rate: Current spend / planned spend ratio
        single_loss_aud: Loss from a single experiment in AUD

    Returns:
        Dict with level, triggered (bool), reason
    """
    if consecutive_failures is None:
        consecutive_failures = get_consecutive_failures()
    if budget_burn_rate is None:
        budget_used = get_budget_used_this_week()
        planned = config.WEEKLY_BUDGET_AUD / 7 * _days_this_week()
        budget_burn_rate = budget_used / planned if planned > 0 else 1.0

    # Red conditions
    if consecutive_failures >= config.CB_RED_FAILURES:
        return _trigger("red", f"{consecutive_failures} consecutive experiment failures",
                        consecutive_failures, budget_burn_rate)

    if single_loss_aud and single_loss_aud > (config.WEEKLY_BUDGET_AUD * config.CB_RED_LOSS_FRACTION):
        return _trigger("red", f"Single loss ${single_loss_aud:.0f} AUD exceeds 40% of weekly budget",
                        consecutive_failures, budget_burn_rate)

    # Orange condition
    if budget_burn_rate > config.CB_ORANGE_BURN_RATE:
        return _trigger("orange", f"Budget burn rate {budget_burn_rate:.0%} exceeds 150% of plan",
                        consecutive_failures, budget_burn_rate)

    # Yellow condition
    if consecutive_failures >= config.CB_YELLOW_FAILURES:
        return _trigger("yellow", f"{consecutive_failures} consecutive failures — warning",
                        consecutive_failures, budget_burn_rate)

    return {"level": "green", "triggered": False, "reason": "All clear"}


def _trigger(level: str, reason: str, consecutive_failures: int, budget_burn_rate: float) -> dict:
    """Record a circuit breaker event and return the state."""
    existing = get_circuit_breaker_state()
    if existing.get("active") and existing.get("level") == level:
        logger.debug(f"[CB] {level.upper()} already active, skipping re-trigger")
        return {"level": level, "triggered": False, "reason": "Already active", "existing": True}

    log_id = insert("circuit_breaker_log", {
        "level": level,
        "reason": reason,
        "consecutive_failures": consecutive_failures,
        "budget_burn_rate": budget_burn_rate,
    })
    log_circuit_breaker(level, reason, {
        "consecutive_failures": consecutive_failures,
        "budget_burn_rate": budget_burn_rate,
    })

    print(f"\n[CIRCUIT BREAKER] {level.upper()} TRIGGERED: {reason}")
    logger.warning(f"[CB] {level.upper()} triggered: {reason}")
    return {"level": level, "triggered": True, "reason": reason, "log_id": log_id}


def is_halted() -> bool:
    """Return True if the swarm is in a Red halt state."""
    state = get_circuit_breaker_state()
    return state.get("active") and state.get("level") == "red"


def get_current_level() -> str:
    """Return current circuit breaker level (green/yellow/orange/red)."""
    state = get_circuit_breaker_state()
    return state.get("level", "green")


def reset_breaker(resolved_by: str) -> dict:
    """Reset the active circuit breaker (Red only requires confirmation).

    Args:
        resolved_by: Username or agent_id doing the reset

    Returns:
        Dict with success bool and message
    """
    state = get_circuit_breaker_state()
    if not state.get("active"):
        return {"success": False, "message": "No active circuit breaker to reset"}

    update("circuit_breaker_log", state["id"], {
        "resolved_at": datetime.utcnow().isoformat(),
        "resolved_by": resolved_by,
    })
    logger.info(f"[CB] Breaker reset by {resolved_by}")
    print(f"[CIRCUIT BREAKER] Reset by {resolved_by} — resuming normal operation")
    return {"success": True, "message": f"Circuit breaker reset by {resolved_by}"}


def get_breaker_history(limit: int = 20) -> list:
    """Return recent circuit breaker events."""
    return fetch_all(
        "SELECT * FROM circuit_breaker_log ORDER BY triggered_at DESC LIMIT ?",
        (limit,),
    )


def _days_this_week() -> int:
    """Return how many days have elapsed this week (1-7)."""
    return max(1, datetime.utcnow().weekday() + 1)
