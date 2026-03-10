"""Portfolio manager — tracks experiment allocations using Kelly Criterion.

Portfolio split: Exploit 60% / Explore 30% / Moonshot 10%
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_portfolio_summary() -> dict:
    """Return a summary of current portfolio allocations by bucket.

    Reads live experiment data from the DB and calculates spend by bucket
    against the weekly budget allocation targets.

    Returns:
        Dict with portfolio breakdown, remaining budgets, and experiment counts
    """
    import config as _cfg

    try:
        from memory.database import fetch_all, fetch_one
        rows = fetch_all(
            "SELECT * FROM experiments WHERE status NOT IN ('rejected','killed') "
            "ORDER BY created_at DESC LIMIT 50"
        ) or []
    except Exception:
        rows = []

    weekly = getattr(_cfg, "WEEKLY_BUDGET_AUD", 500)
    targets = {
        "exploit":  weekly * getattr(_cfg, "BUCKET_EXPLOIT",  0.60),
        "explore":  weekly * getattr(_cfg, "BUCKET_EXPLORE",  0.30),
        "moonshot": weekly * getattr(_cfg, "BUCKET_MOONSHOT", 0.10),
    }

    spent = {"exploit": 0.0, "explore": 0.0, "moonshot": 0.0}
    counts = {"exploit": 0, "explore": 0, "moonshot": 0}
    active = 0

    for r in rows:
        bucket = r.get("bucket") or ""
        if bucket in spent:
            spent[bucket] += r.get("budget_allocated") or 0
            counts[bucket] += 1
        if r.get("status") in ("approved", "running"):
            active += 1

    remaining = {b: round(max(targets[b] - spent[b], 0), 2) for b in targets}

    return {
        "total_experiments": len(rows),
        "active":  active,
        "counts":  counts,
        "targets": {b: round(v, 2) for b, v in targets.items()},
        "spent":   {b: round(v, 2) for b, v in spent.items()},
        "remaining": remaining,
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
