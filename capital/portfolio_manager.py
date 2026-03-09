"""Portfolio Manager for Solar Swarm experiment buckets.

Manages the 3-bucket capital allocation:
  Exploit:  60% — proven strategies, scaling winners
  Explore:  30% — new 72-hour experiments
  Moonshot: 10% — high-risk, high-reward

Also manages the 72-hour explore protocol lifecycle.
"""

import logging
from datetime import datetime, timedelta
from memory.database import fetch_all, fetch_one, update
from memory.hot_memory import get_budget_used_this_week
import config

logger = logging.getLogger(__name__)


# ── Budget Allocation ─────────────────────────────────────────────────────────

def get_bucket_budgets(weekly_budget: float = None) -> dict:
    """Calculate available budget for each bucket this week.

    Args:
        weekly_budget: Override the default weekly budget

    Returns:
        Dict with exploit, explore, moonshot budget in AUD
    """
    if weekly_budget is None:
        weekly_budget = config.WEEKLY_BUDGET_AUD
    return {
        "exploit": round(weekly_budget * config.BUCKET_EXPLOIT, 2),
        "explore": round(weekly_budget * config.BUCKET_EXPLORE, 2),
        "moonshot": round(weekly_budget * config.BUCKET_MOONSHOT, 2),
        "total": weekly_budget,
    }


def get_bucket_usage() -> dict:
    """Calculate how much has been spent per bucket this week."""
    week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
    rows = fetch_all(
        "SELECT bucket, COALESCE(SUM(budget_allocated), 0) as spent "
        "FROM experiments "
        "WHERE created_at >= ? AND status NOT IN ('rejected','killed') "
        "GROUP BY bucket",
        (week_start,),
    )
    usage = {"exploit": 0.0, "explore": 0.0, "moonshot": 0.0}
    for row in rows:
        bucket = row.get("bucket")
        if bucket in usage:
            usage[bucket] = round(row.get("spent", 0.0), 2)
    return usage


def get_bucket_remaining() -> dict:
    """Calculate remaining budget per bucket."""
    budgets = get_bucket_budgets()
    usage = get_bucket_usage()
    return {
        bucket: round(budgets[bucket] - usage.get(bucket, 0.0), 2)
        for bucket in ["exploit", "explore", "moonshot"]
    }


def assign_bucket(confidence_score: float, devil_score: float, idea_text: str) -> str:
    """Determine which bucket an experiment belongs to.

    Rules:
      - New/unproven → explore
      - High devil score (risky, novel) → moonshot
      - High confidence + proven vertical → exploit

    Args:
        confidence_score: 0–10 confidence rating
        devil_score: 1–10 red team rating (higher = more flaws)
        idea_text: Description of the experiment

    Returns:
        'exploit', 'explore', or 'moonshot'
    """
    if devil_score >= 7 and confidence_score >= 7:
        return "moonshot"
    if confidence_score >= 8 and devil_score < 5:
        return "exploit"
    return "explore"


def can_allocate(bucket: str, amount: float) -> bool:
    """Check if the bucket has enough remaining budget.

    Args:
        bucket: 'exploit', 'explore', or 'moonshot'
        amount: Requested AUD amount

    Returns:
        True if allocation is possible
    """
    remaining = get_bucket_remaining()
    available = remaining.get(bucket, 0.0)
    if available < amount:
        logger.warning(f"[PORTFOLIO] {bucket} bucket insufficient: ${available} < ${amount}")
        return False
    return True


# ── 72-Hour Explore Protocol ──────────────────────────────────────────────────

def get_explore_phase(experiment_id: int) -> dict:
    """Determine the current phase of a 72-hour explore experiment.

    Phases:
      0-12h:  asset_creation
      12-24h: distribution
      24-48h: signal_observation
      48-60h: decision_point
      60-72h: final_assessment
      >72h:   expired

    Args:
        experiment_id: Database id of the experiment

    Returns:
        Dict with phase, hours_elapsed, hours_remaining, action
    """
    exp = fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp or exp.get("bucket") != "explore":
        return {"phase": "not_explore", "action": "n/a"}

    approved_at_str = exp.get("approved_at") or exp.get("created_at")
    try:
        approved_at = datetime.fromisoformat(approved_at_str)
    except Exception:
        approved_at = datetime.utcnow()

    hours_elapsed = (datetime.utcnow() - approved_at).total_seconds() / 3600
    hours_remaining = max(0, config.EXPLORE_TOTAL_HOURS - hours_elapsed)

    if hours_elapsed < 12:
        phase = "asset_creation"
        action = "Build assets — landing page, copy, creatives"
    elif hours_elapsed < 24:
        phase = "distribution"
        action = "Minimum viable distribution — organic channels only"
    elif hours_elapsed < 48:
        phase = "signal_observation"
        action = "Observe metrics — CTR, engagement, enquiries"
    elif hours_elapsed < 60:
        phase = "decision_point"
        action = "Evaluate CTR — if >2% activate paid spend"
    elif hours_elapsed < 72:
        phase = "final_assessment"
        action = "Final call — promote to exploit or kill and log"
    else:
        phase = "expired"
        action = "Kill experiment — log learnings immediately"

    return {
        "phase": phase,
        "hours_elapsed": round(hours_elapsed, 1),
        "hours_remaining": round(hours_remaining, 1),
        "action": action,
    }


def activate_paid_spend(experiment_id: int) -> bool:
    """Unlock paid spend for an explore experiment that hit the CTR threshold.

    Called by run_explore_monitor() at the decision_point phase when
    CTR >= config.EXPLORE_CTR_THRESHOLD (default 2%).

    Args:
        experiment_id: Database id of the explore experiment

    Returns:
        True if activation succeeded
    """
    from memory.database import get_conn
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE experiments SET paid_spend_activated=1, explore_phase='paid_active' WHERE id=?",
                (experiment_id,),
            )
        print(f"[PORTFOLIO] Paid spend activated for experiment #{experiment_id}")
        return True
    except Exception as e:
        logger.error(f"[PORTFOLIO] activate_paid_spend failed: {e}")
        return False


def run_explore_monitor() -> dict:
    """Check all running explore experiments and take phase-appropriate actions.

    Runs every 2 hours via APScheduler. For each active explore experiment:
      - Determines the current phase using get_explore_phase()
      - Logs phase transitions to the cold ledger
      - At decision_point: checks CTR and activates paid spend if >= threshold
      - At expired: auto-kills the experiment and emits a pheromone signal

    Returns:
        Summary dict: {checked, killed, paid_activated, alerts_sent}
    """
    from memory.database import fetch_all, get_conn
    from memory.hot_memory import post_pheromone
    from memory.cold_ledger import log_experiment_approved, log_experiment_killed
    from notifications import slack_notifier
    from storage.time_series import record_metric

    print("[EXPLORE MONITOR] Checking active explore experiments")

    running = fetch_all(
        "SELECT * FROM experiments WHERE bucket='explore' AND status IN ('approved','running')"
    )

    checked = killed = paid_activated = alerts_sent = 0

    for exp in running:
        exp_id = exp["id"]
        idea = exp.get("idea_text", f"Experiment #{exp_id}")[:60]
        phase_info = get_explore_phase(exp_id)
        phase = phase_info.get("phase", "unknown")
        hours = phase_info.get("hours_elapsed", 0)
        current_phase = exp.get("explore_phase", "")

        # Record phase in DB only when it changes
        if phase != current_phase and phase not in ("not_explore", "unknown"):
            with get_conn() as conn:
                conn.execute(
                    "UPDATE experiments SET explore_phase=? WHERE id=?",
                    (phase, exp_id),
                )

        checked += 1

        # ── EXPIRED — auto-kill ──────────────────────────────────────────────
        if phase == "expired":
            with get_conn() as conn:
                conn.execute(
                    "UPDATE experiments SET status='killed', completed_at=datetime('now'), "
                    "failure_mode='72hr explore window expired — auto-killed' WHERE id=?",
                    (exp_id,),
                )
            log_experiment_killed(exp_id, "72hr explore expired", "explore_monitor")
            post_pheromone(
                signal_type="NEGATIVE", topic=f"explore_expired_{exp_id}",
                strength=0.3, channel="explore_monitor", experiment_id=exp_id,
            )
            try:
                slack_notifier.post_message(
                    f"⏰ *Explore Experiment Expired & Auto-Killed*\n"
                    f"*#{exp_id}:* {idea}\n"
                    f"*Hours elapsed:* {hours:.1f}h / 72h window closed.\n"
                    f"Learnings logged. Mutation engine will generate variants Monday."
                )
            except Exception:
                pass
            killed += 1
            continue

        # ── DECISION POINT — check CTR, activate paid spend if threshold met ─
        if phase == "decision_point":
            ctr_row = fetch_all(
                "SELECT value FROM time_series WHERE series_name='ctr' AND entity_id=? "
                "ORDER BY recorded_at DESC LIMIT 1",
                (str(exp_id),),
            )
            ctr = ctr_row[0]["value"] if ctr_row else 0.0

            if ctr >= config.EXPLORE_CTR_THRESHOLD and not exp.get("paid_spend_activated"):
                if activate_paid_spend(exp_id):
                    paid_activated += 1
                    try:
                        slack_notifier.post_message(
                            f"🚀 *Paid Spend Activated — Explore Experiment*\n"
                            f"*#{exp_id}:* {idea}\n"
                            f"*CTR:* {ctr:.1%} ≥ {config.EXPLORE_CTR_THRESHOLD:.0%} threshold met.\n"
                            f"Paid distribution now unlocked. Monitor spend closely."
                        )
                        alerts_sent += 1
                    except Exception:
                        pass
            elif current_phase != "decision_point":
                # First time entering decision_point — notify
                try:
                    slack_notifier.post_message(
                        f"🔎 *Explore Decision Point Reached*\n"
                        f"*#{exp_id}:* {idea}\n"
                        f"*CTR:* {ctr:.1%} (threshold: {config.EXPLORE_CTR_THRESHOLD:.0%})\n"
                        f"{'✅ Paid spend will activate shortly.' if ctr >= config.EXPLORE_CTR_THRESHOLD else '❌ CTR below threshold — organic only, final assessment in 12h.'}"
                    )
                    alerts_sent += 1
                except Exception:
                    pass

        # ── PHASE TRANSITION NOTIFICATIONS ───────────────────────────────────
        elif phase != current_phase:
            phase_labels = {
                "asset_creation": "🔨 Asset Creation (0–12h)",
                "distribution": "📢 Distribution (12–24h)",
                "signal_observation": "👁 Signal Observation (24–48h)",
                "final_assessment": "🏁 Final Assessment (60–72h)",
            }
            label = phase_labels.get(phase, phase)
            if phase in phase_labels:
                try:
                    slack_notifier.post_message(
                        f"📍 *Explore Phase Update*\n"
                        f"*#{exp_id}:* {idea}\n"
                        f"*Phase:* {label}\n"
                        f"*Action:* {phase_info.get('action', '')}\n"
                        f"*Time remaining:* {phase_info.get('hours_remaining', 0):.1f}h"
                    )
                    alerts_sent += 1
                except Exception:
                    pass

        # Record phase metric to time series
        try:
            record_metric(f"explore_phase_{exp_id}", hours, unit="hours", entity_id=str(exp_id))
        except Exception:
            pass

    print(f"[EXPLORE MONITOR] checked={checked} killed={killed} paid_activated={paid_activated} alerts={alerts_sent}")
    return {"checked": checked, "killed": killed, "paid_activated": paid_activated, "alerts_sent": alerts_sent}


def get_portfolio_summary() -> dict:
    """Return full portfolio status for dashboard display."""
    budgets = get_bucket_budgets()
    usage = get_bucket_usage()
    remaining = get_bucket_remaining()

    active = fetch_all("SELECT bucket, COUNT(*) as count FROM experiments WHERE status IN ('approved','running') GROUP BY bucket")
    counts = {row["bucket"]: row["count"] for row in active}

    return {
        "budgets": budgets,
        "usage": usage,
        "remaining": remaining,
        "active_counts": counts,
        "weekly_budget": config.WEEKLY_BUDGET_AUD,
    }
