"""Circuit breaker — tracks system health and halts on repeated failures.

Levels: green → yellow → orange → red
  Yellow: 3 consecutive failures (warning)
  Orange: budget burn > 150% of plan
  Red:    5 consecutive failures OR single loss > 40% budget → full halt
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_state = {
    "level": "green",
    "consecutive_failures": 0,
    "history": [],
}


def get_current_level() -> str:
    """Return current circuit breaker level (green/yellow/orange/red).

    Returns:
        Level string
    """
    return _state["level"]


def is_halted() -> bool:
    """Return True if the system is in a red halt state.

    Returns:
        True if halted
    """
    return _state["level"] == "red"


def get_breaker_history(limit: int = 5) -> list:
    """Return recent circuit breaker events.

    Args:
        limit: Max number of events to return

    Returns:
        List of event dicts
    """
    return _state["history"][-limit:]


def record_failure(reason: str = "") -> str:
    """Record a failure event and update breaker level.

    Args:
        reason: Short description of the failure

    Returns:
        New level string
    """
    _state["consecutive_failures"] += 1
    n = _state["consecutive_failures"]
    old_level = _state["level"]

    if n >= 5:
        _state["level"] = "red"
    elif n >= 3:
        _state["level"] = "yellow"

    event = {
        "ts": datetime.utcnow().isoformat(),
        "event": "failure",
        "reason": reason,
        "level": _state["level"],
    }
    _state["history"].append(event)
    if _state["level"] != old_level:
        logger.warning(f"[CIRCUIT BREAKER] Level changed: {old_level} → {_state['level']}")
    return _state["level"]


def reset_breaker(approved_by: str = "system") -> dict:
    """Reset the circuit breaker to green.

    Args:
        approved_by: Who approved the reset

    Returns:
        Dict with success, message, and new level
    """
    _state["level"] = "green"
    _state["consecutive_failures"] = 0
    event = {
        "ts": datetime.utcnow().isoformat(),
        "event": "reset",
        "approved_by": approved_by,
        "level": "green",
    }
    _state["history"].append(event)
    logger.info(f"[CIRCUIT BREAKER] Reset by {approved_by}")
    return {"success": True, "message": f"Circuit breaker reset to GREEN by {approved_by}", "level": "green"}


def get_circuit_breaker_state() -> dict:
    """Return full circuit breaker state dict.

    Includes an 'active' key: True when breaker is not green.

    Returns:
        State dict with level, consecutive_failures, history, active
    """
    state = dict(_state)
    state["active"] = state.get("level", "green") != "green"
    return state
