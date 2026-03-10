"""Cold ledger — append-only event log.

Writes events to a JSON-lines file so nothing is ever overwritten.
All functions are safe to call; failures are logged but never raised.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cold_ledger.jsonl")


def _append(entry: dict) -> None:
    """Append a single JSON entry to the ledger file.

    Args:
        entry: Dict to serialise and append
    """
    try:
        entry["ts"] = datetime.utcnow().isoformat()
        with open(_LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.error(f"[COLD LEDGER] Write failed: {exc}")


def log_event(event_type: str, data: dict = None) -> None:
    """Append a generic event to the cold ledger.

    Args:
        event_type: Short string label (e.g. 'call_completed')
        data: Optional payload dict
    """
    _append({"type": event_type, "data": data or {}})


def log_lead_qualified(lead_data: dict) -> None:
    """Record a lead qualification event.

    Args:
        lead_data: Dict with lead details (name, score, etc.)
    """
    _append({"type": "lead_qualified", "data": lead_data})


def log_experiment_approved(experiment_id: str) -> None:
    """Record that an experiment was approved by a human operator.

    Args:
        experiment_id: Unique experiment identifier
    """
    _append({"type": "experiment_approved", "experiment_id": experiment_id})


def log_experiment_killed(experiment_id: str) -> None:
    """Record that an experiment was killed by a human operator.

    Args:
        experiment_id: Unique experiment identifier
    """
    _append({"type": "experiment_killed", "experiment_id": experiment_id})
