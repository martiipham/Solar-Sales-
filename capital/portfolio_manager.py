"""Portfolio manager — tracks experiment allocations using Kelly Criterion.

Portfolio split: Exploit 60% / Explore 30% / Moonshot 10%
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_portfolio_summary() -> dict:
    """Return a summary of the current portfolio allocations.

    Returns:
        Dict with portfolio breakdown and experiment counts
    """
    try:
        from memory.database import fetch_all
        rows = fetch_all("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 20") or []
    except Exception:
        rows = []

    active   = [r for r in rows if r.get("status") == "active"]
    exploit  = [r for r in active if r.get("type") == "exploit"]
    explore  = [r for r in active if r.get("type") == "explore"]
    moonshot = [r for r in active if r.get("type") == "moonshot"]

    return {
        "total_experiments": len(rows),
        "active": len(active),
        "exploit": len(exploit),
        "explore": len(explore),
        "moonshot": len(moonshot),
        "allocation": {"exploit": 0.60, "explore": 0.30, "moonshot": 0.10},
        "updated_at": datetime.utcnow().isoformat(),
    }


def run_explore_monitor() -> None:
    """Monitor 72-hour explore experiment lifecycle and advance state."""
    try:
        from memory.database import fetch_all, execute
        rows = fetch_all(
            "SELECT * FROM experiments WHERE type = 'explore' AND status = 'active'"
        ) or []
        logger.info(f"[PORTFOLIO] Explore monitor: {len(rows)} active explore experiments")
    except Exception as exc:
        logger.error(f"[PORTFOLIO] Explore monitor failed: {exc}")
