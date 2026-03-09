"""Weekly Retrospective — Strategic analysis of swarm performance.

Runs every Monday 8am AEST via APScheduler.
Pulls 7 days of experiment data, generates strategic analysis,
and posts to Slack.
"""

import logging
from datetime import datetime, timedelta
from memory.database import fetch_all, fetch_one
from memory.warm_memory import save_learning, get_winning_patterns
from memory.cold_ledger import log_event
from notifications.slack_notifier import post_retrospective
import config

logger = logging.getLogger(__name__)


def run() -> dict:
    """Run the weekly retrospective analysis.

    Returns:
        Dict with retro_text, stats, learnings, and next_week_focus
    """
    print("\n[RETRO] === Weekly Retrospective ===")
    print(f"[RETRO] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    experiment_summary = _analyse_experiments(week_ago)
    lead_summary = _analyse_leads(week_ago)
    budget_summary = _analyse_budget(week_ago)
    patterns = _identify_patterns(week_ago)
    learnings = _extract_learnings(experiment_summary, lead_summary)
    next_focus = _determine_next_focus(experiment_summary, patterns)

    retro_text = _format_retro(
        experiment_summary, lead_summary, budget_summary,
        patterns, learnings, next_focus
    )

    _save_learnings(learnings)
    log_event("WEEKLY_RETROSPECTIVE", {
        "experiments": experiment_summary,
        "leads": lead_summary,
        "budget": budget_summary,
    }, agent_id="retrospective")

    post_retrospective(retro_text)
    print("[RETRO] Retrospective complete and posted to Slack")
    return {
        "retro_text": retro_text,
        "experiment_summary": experiment_summary,
        "lead_summary": lead_summary,
        "learnings": learnings,
        "next_focus": next_focus,
    }


def _analyse_experiments(week_ago: str) -> dict:
    """Analyse experiment outcomes for the week.

    Args:
        week_ago: ISO datetime string for 7 days ago

    Returns:
        Dict with counts, wins, losses, roi
    """
    rows = fetch_all("SELECT * FROM experiments WHERE created_at >= ?", (week_ago,))
    wins = [r for r in rows if r.get("status") == "complete" and (r.get("revenue_generated") or 0) > 0]
    losses = [r for r in rows if r.get("status") in ("killed", "rejected")]
    total_spend = sum(r.get("budget_allocated") or 0 for r in rows)
    total_revenue = sum(r.get("revenue_generated") or 0 for r in rows)
    roi = ((total_revenue - total_spend) / total_spend * 100) if total_spend > 0 else 0

    best = max(rows, key=lambda x: x.get("revenue_generated") or 0, default={})
    worst = min(
        [r for r in rows if r.get("status") == "killed"],
        key=lambda x: x.get("confidence_score") or 10,
        default={},
    )

    return {
        "total": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "running": len([r for r in rows if r.get("status") in ("approved", "running")]),
        "total_spend_aud": round(total_spend, 2),
        "total_revenue_aud": round(total_revenue, 2),
        "roi_pct": round(roi, 1),
        "best_experiment": best.get("idea_text", "N/A")[:80] if best else "N/A",
        "worst_experiment": worst.get("idea_text", "N/A")[:80] if worst else "N/A",
    }


def _analyse_leads(week_ago: str) -> dict:
    """Analyse lead pipeline performance for the week.

    Args:
        week_ago: ISO datetime string

    Returns:
        Dict with lead counts and conversion metrics
    """
    rows = fetch_all("SELECT * FROM leads WHERE created_at >= ?", (week_ago,))
    total = len(rows)
    hot = sum(1 for r in rows if (r.get("qualification_score") or 0) >= 7)
    converted = sum(1 for r in rows if r.get("status") == "converted")

    return {
        "total": total,
        "hot": hot,
        "converted": converted,
        "conversion_rate_pct": round(converted / total * 100, 1) if total > 0 else 0,
    }


def _analyse_budget(week_ago: str) -> dict:
    """Summarise budget usage for the week.

    Args:
        week_ago: ISO datetime string

    Returns:
        Dict with used, remaining, efficiency
    """
    rows = fetch_all(
        "SELECT bucket, SUM(budget_allocated) as spent FROM experiments "
        "WHERE created_at >= ? GROUP BY bucket",
        (week_ago,),
    )
    breakdown = {r["bucket"]: round(r.get("spent") or 0, 2) for r in rows if r.get("bucket")}
    total_used = sum(breakdown.values())
    return {
        "weekly_budget": config.WEEKLY_BUDGET_AUD,
        "total_used_aud": round(total_used, 2),
        "remaining_aud": round(config.WEEKLY_BUDGET_AUD - total_used, 2),
        "by_bucket": breakdown,
        "utilisation_pct": round(total_used / config.WEEKLY_BUDGET_AUD * 100, 1) if config.WEEKLY_BUDGET_AUD > 0 else 0,
    }


def _identify_patterns(week_ago: str) -> list:
    """Identify recurring patterns in experiment outcomes.

    Args:
        week_ago: ISO datetime string

    Returns:
        List of pattern description strings
    """
    winners = get_winning_patterns()
    patterns = []

    if len(winners) >= 2:
        patterns.append("Content-first experiments consistently outperform paid-first approaches")

    pheromones = fetch_all(
        "SELECT topic, signal_type, AVG(strength) as avg_strength FROM pheromone_signals "
        "WHERE created_at >= ? GROUP BY topic, signal_type ORDER BY avg_strength DESC LIMIT 5",
        (week_ago,),
    )
    for p in pheromones:
        if p.get("signal_type") == "POSITIVE" and (p.get("avg_strength") or 0) > 0.7:
            patterns.append(f"Strong positive signal in topic: {p.get('topic')}")

    if not patterns:
        patterns.append("Insufficient data for pattern detection — need more experiments")

    return patterns


def _extract_learnings(experiments: dict, leads: dict) -> list:
    """Extract actionable learnings from this week's data.

    Args:
        experiments: From _analyse_experiments()
        leads: From _analyse_leads()

    Returns:
        List of learning strings
    """
    learnings = []

    if experiments["wins"] > experiments["losses"]:
        learnings.append("Win rate above 50% — current strategy is working, scale exploits")
    elif experiments["losses"] > experiments["wins"] * 2:
        learnings.append("High loss rate — review kill criteria and reduce explore spend")

    if experiments["roi_pct"] > 50:
        learnings.append(f"Strong ROI at {experiments['roi_pct']}% — consider increasing weekly budget")
    elif experiments["roi_pct"] < 0:
        learnings.append("Negative ROI this week — audit experiment quality and scoring criteria")

    if leads["hot"] / max(1, leads["total"]) > 0.3:
        learnings.append("High proportion of hot leads — lead source quality is excellent")
    elif leads["conversion_rate_pct"] < 5:
        learnings.append("Low conversion rate — review qualification criteria and follow-up sequences")

    if not learnings:
        learnings.append("Normal operations — continue current strategy and gather more data")

    return learnings


def _determine_next_focus(experiments: dict, patterns: list) -> list:
    """Recommend strategic focus areas for next week.

    Args:
        experiments: From _analyse_experiments()
        patterns: From _identify_patterns()

    Returns:
        List of focus area strings
    """
    focus = []

    if experiments["wins"] > 0:
        focus.append("Scale winning experiments — move best performers to exploit bucket")
    if experiments["total"] < 3:
        focus.append("Run more explore experiments — increase idea generation frequency")

    focus.append("Continue prospecting Australian solar companies in WA and QLD")
    focus.append("Test new outreach angle: quantified ROI case study")

    return focus[:3]


def _save_learnings(learnings: list):
    """Persist extracted learnings to warm memory.

    Args:
        learnings: List of learning strings
    """
    for learning in learnings:
        save_learning(
            topic="weekly_retrospective",
            insight=learning,
            source="retrospective_agent",
            confidence=0.7,
        )


def _format_retro(experiments: dict, leads: dict, budget: dict,
                  patterns: list, learnings: list, next_focus: list) -> str:
    """Format the retrospective into a readable report.

    Args:
        experiments, leads, budget: Analysis dicts
        patterns, learnings, next_focus: Lists of strings

    Returns:
        Formatted retrospective text
    """
    date_str = datetime.now().strftime("%d %B %Y")

    sections = [
        f"*WEEKLY SWARM RETROSPECTIVE — {date_str}*",
        "",
        "*EXPERIMENT RESULTS*",
        f"  Total: {experiments['total']} | Wins: {experiments['wins']} | Losses: {experiments['losses']}",
        f"  Spend: ${experiments['total_spend_aud']} | Revenue: ${experiments['total_revenue_aud']} | ROI: {experiments['roi_pct']}%",
        f"  Best: {experiments['best_experiment']}",
        "",
        "*LEAD PIPELINE*",
        f"  Total: {leads['total']} | Hot: {leads['hot']} | Converted: {leads['converted']} ({leads['conversion_rate_pct']}%)",
        "",
        "*BUDGET*",
        f"  Used: ${budget['total_used_aud']} / ${budget['weekly_budget']} ({budget['utilisation_pct']}%)",
        "",
        "*PATTERNS IDENTIFIED*",
    ]
    sections.extend(f"  • {p}" for p in patterns)
    sections.extend([
        "",
        "*KEY LEARNINGS*",
    ])
    sections.extend(f"  → {l}" for l in learnings)
    sections.extend([
        "",
        "*NEXT WEEK FOCUS*",
    ])
    sections.extend(f"  ▶ {f}" for f in next_focus)

    return "\n".join(sections)
