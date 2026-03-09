"""Analytics Agent — Tier 2: Department Head for analytics operations.

Runs daily. Manages:
  - Experiment performance tracking
  - Lead conversion analytics
  - Budget burn rate monitoring
  - Pheromone signal synthesis from data
  - Circuit breaker health checks
"""

import logging
from datetime import datetime, timedelta
from memory.hot_memory import get_active_experiments, get_budget_used_this_week, get_consecutive_failures
from memory.database import fetch_all, fetch_one
from memory.cold_ledger import log_event
from capital.circuit_breaker import check_and_trigger
import config

logger = logging.getLogger(__name__)


def run() -> dict:
    """Run the analytics department's daily cycle.

    Returns:
        Dict with analytics summary
    """
    print(f"\n[ANALYTICS HEAD] === Daily Analytics Cycle ===")
    print(f"[ANALYTICS HEAD] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    lead_stats = _analyse_leads()
    experiment_stats = _analyse_experiments()
    budget_stats = _analyse_budget()
    cb_result = _check_circuit_breakers(budget_stats)

    summary = {
        "leads": lead_stats,
        "experiments": experiment_stats,
        "budget": budget_stats,
        "circuit_breaker": cb_result,
        "generated_at": datetime.utcnow().isoformat(),
    }

    log_event("ANALYTICS_CYCLE", summary, agent_id="analytics_agent")
    _print_summary(summary)
    return summary


def _analyse_leads() -> dict:
    """Analyse lead pipeline metrics for the last 7 days.

    Returns:
        Dict with total, qualified, contacted, converted counts and rates
    """
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    rows = fetch_all(
        "SELECT status, qualification_score, recommended_action FROM leads WHERE created_at >= ?",
        (week_ago,),
    )
    total = len(rows)
    qualified = sum(1 for r in rows if (r.get("qualification_score") or 0) >= 5)
    hot = sum(1 for r in rows if (r.get("qualification_score") or 0) >= 7)
    converted = sum(1 for r in rows if r.get("status") == "converted")
    avg_score = (
        sum(r.get("qualification_score") or 0 for r in rows) / total
        if total > 0 else 0
    )
    return {
        "total_7d": total,
        "qualified": qualified,
        "hot_leads": hot,
        "converted": converted,
        "conversion_rate": round(converted / total * 100, 1) if total > 0 else 0,
        "avg_score": round(avg_score, 1),
    }


def _analyse_experiments() -> dict:
    """Analyse experiment outcomes and track success rate.

    Returns:
        Dict with total, complete, killed, running, success_rate
    """
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    rows = fetch_all(
        "SELECT status, revenue_generated, budget_allocated FROM experiments WHERE created_at >= ?",
        (week_ago,),
    )
    total = len(rows)
    complete = sum(1 for r in rows if r.get("status") == "complete")
    killed = sum(1 for r in rows if r.get("status") in ("killed", "rejected"))
    running = sum(1 for r in rows if r.get("status") in ("approved", "running"))
    total_revenue = sum(r.get("revenue_generated") or 0 for r in rows)
    total_spent = sum(r.get("budget_allocated") or 0 for r in rows)

    return {
        "total_7d": total,
        "complete": complete,
        "killed": killed,
        "running": running,
        "success_rate": round(complete / (complete + killed) * 100, 1) if (complete + killed) > 0 else 0,
        "total_revenue_aud": round(total_revenue, 2),
        "total_spent_aud": round(total_spent, 2),
        "roi": round((total_revenue - total_spent) / total_spent * 100, 1) if total_spent > 0 else 0,
    }


def _analyse_budget() -> dict:
    """Calculate budget burn rate against weekly plan.

    Returns:
        Dict with used, remaining, burn_rate, on_track
    """
    days_elapsed = max(1, datetime.utcnow().weekday() + 1)
    planned_daily = config.WEEKLY_BUDGET_AUD / 7
    planned_to_date = planned_daily * days_elapsed
    actual_used = get_budget_used_this_week()
    burn_rate = actual_used / planned_to_date if planned_to_date > 0 else 1.0

    return {
        "weekly_budget_aud": config.WEEKLY_BUDGET_AUD,
        "used_aud": round(actual_used, 2),
        "remaining_aud": round(config.WEEKLY_BUDGET_AUD - actual_used, 2),
        "planned_to_date_aud": round(planned_to_date, 2),
        "burn_rate": round(burn_rate, 2),
        "on_track": burn_rate <= 1.1,
    }


def _check_circuit_breakers(budget_stats: dict) -> dict:
    """Evaluate and trigger circuit breakers based on current data.

    Args:
        budget_stats: From _analyse_budget()

    Returns:
        Circuit breaker check result
    """
    consecutive = get_consecutive_failures()
    burn_rate = budget_stats.get("burn_rate", 1.0)
    result = check_and_trigger(
        consecutive_failures=consecutive,
        budget_burn_rate=burn_rate,
    )
    return result


def _print_summary(summary: dict):
    """Print analytics summary to console."""
    leads = summary["leads"]
    exps = summary["experiments"]
    budget = summary["budget"]
    print(f"[ANALYTICS HEAD] Leads 7d: {leads['total_7d']} total | {leads['hot_leads']} hot | {leads['conversion_rate']}% converted")
    print(f"[ANALYTICS HEAD] Experiments: {exps['running']} running | {exps['success_rate']}% success rate | ROI: {exps['roi']}%")
    print(f"[ANALYTICS HEAD] Budget: ${budget['used_aud']} used / ${budget['weekly_budget_aud']} | Burn rate: {budget['burn_rate']:.0%}")


def get_conversion_stats() -> dict:
    """Get overall lead conversion statistics.

    Returns:
        Dict with pipeline breakdown and key metrics
    """
    rows = fetch_all("SELECT recommended_action, status, qualification_score FROM leads")
    total = len(rows)
    if total == 0:
        return {"total_leads": 0, "message": "No leads yet"}

    call_now = sum(1 for r in rows if r.get("recommended_action") == "call_now")
    nurture = sum(1 for r in rows if r.get("recommended_action") == "nurture")
    disqualify = sum(1 for r in rows if r.get("recommended_action") == "disqualify")
    converted = sum(1 for r in rows if r.get("status") == "converted")
    avg_score = sum(r.get("qualification_score") or 0 for r in rows) / total

    return {
        "total_leads": total,
        "call_now": call_now,
        "nurture": nurture,
        "disqualify": disqualify,
        "converted": converted,
        "conversion_rate_pct": round(converted / total * 100, 1),
        "avg_qualification_score": round(avg_score, 1),
    }
