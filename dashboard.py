#!/usr/bin/env python3
"""
Solar Swarm Command Centre — Rich Terminal Dashboard

Provides real-time visibility into every layer of the swarm:
  system health, capital allocation, lead pipeline, experiments,
  pheromone signals, message bus, research, A/B tests, cold ledger,
  and the 72-hour explore protocol.

Usage:
    python dashboard.py                      # single snapshot
    python dashboard.py --watch              # live auto-refresh (5s)
    python dashboard.py --watch --interval 10
    python dashboard.py --help
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR & STYLE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

CB_COLOURS = {
    "green":   "bold bright_green",
    "yellow":  "bold yellow",
    "orange":  "bold dark_orange",
    "red":     "bold red",
    "unknown": "dim",
}

CB_ICONS = {
    "green":   "● GREEN",
    "yellow":  "▲ YELLOW",
    "orange":  "◆ ORANGE",
    "red":     "■ RED — HALTED",
    "unknown": "? UNKNOWN",
}

STATUS_COLOURS = {
    "pending":   "yellow",
    "approved":  "cyan",
    "running":   "bright_green",
    "complete":  "green",
    "killed":    "red",
    "rejected":  "dim red",
    "queued":    "yellow",
    "processing":"cyan",
    "failed":    "red",
    "new":       "bright_white",
    "contacted": "cyan",
    "converted": "bright_green",
    "healthy":   "green",
    "degraded":  "yellow",
    "dead":      "red",
}

BUCKET_COLOURS = {
    "exploit":  "bright_green",
    "explore":  "cyan",
    "moonshot": "magenta",
}

SIGNAL_ICONS = {"POSITIVE": "[green]▲[/]", "NEGATIVE": "[red]▼[/]", "NEUTRAL": "[yellow]●[/]"}


def score_colour(score) -> str:
    if score is None:
        return "dim"
    if score >= 7:
        return "bright_green"
    if score >= 5:
        return "yellow"
    return "red"


def bar(value: float, total: float, width: int = 20, colour: str = "green") -> Text:
    """Return a filled progress bar as a Rich Text object."""
    if total <= 0:
        filled = 0
    else:
        filled = min(int((value / total) * width), width)
    empty = width - filled
    t = Text()
    t.append("█" * filled, style=colour)
    t.append("░" * empty, style="dim")
    return t


def mini_bar(value: float, total: float, width: int = 12) -> str:
    """Inline progress bar string."""
    if total <= 0:
        return "░" * width
    filled = min(int((value / total) * width), width)
    return "█" * filled + "░" * (width - filled)


def pct(value, total) -> str:
    if not total:
        return "0.0%"
    return f"{(value / total) * 100:.1f}%"


def age_str(dt_str: str) -> str:
    """Return human-readable age from ISO datetime string."""
    try:
        dt = datetime.fromisoformat(dt_str)
        delta = datetime.now() - dt
        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        if delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        return f"{delta.days}d ago"
    except Exception:
        return dt_str or "—"


def trunc(text: str, n: int) -> str:
    if not text:
        return "—"
    return text[:n] + "…" if len(text) > n else text


# ─────────────────────────────────────────────────────────────────────────────
# DATA LAYER — safe wrappers
# ─────────────────────────────────────────────────────────────────────────────

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def get_data() -> dict:
    """Pull all dashboard data in one pass, returning {} on any failure."""
    try:
        from memory import database as db
        from memory import hot_memory as hm
        from capital import circuit_breaker as cb
        from capital import portfolio_manager as pm
        from bus import message_bus as mb
    except ImportError:
        return {"_error": "Cannot import swarm modules. Run from solar-swarm directory."}

    d = {}
    d["now"] = datetime.now()

    # ── Swarm summary
    d["summary"]            = _safe(hm.get_swarm_summary, {})
    d["cb_level"]           = _safe(cb.get_current_level, "unknown")
    d["cb_history"]         = _safe(lambda: cb.get_breaker_history(10), [])
    d["cb_state"]           = _safe(hm.get_circuit_breaker_state, {})

    # ── Portfolio / capital
    d["portfolio"]          = _safe(pm.get_portfolio_summary, {})

    # ── Experiments
    d["pending_experiments"] = _safe(hm.get_pending_experiments, [])
    d["active_experiments"]  = _safe(hm.get_active_experiments, [])

    d["experiment_stats"]   = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*)                                                  AS total,
            COUNT(CASE WHEN status='complete'  THEN 1 END)           AS wins,
            COUNT(CASE WHEN status='killed'    THEN 1 END)           AS killed,
            COUNT(CASE WHEN status='rejected'  THEN 1 END)           AS rejected,
            AVG(CASE WHEN roi IS NOT NULL THEN roi END)              AS avg_roi,
            SUM(CASE WHEN status='complete' THEN revenue_generated ELSE 0 END) AS total_revenue,
            AVG(confidence_score)                                     AS avg_confidence,
            COUNT(CASE WHEN bucket='exploit'   THEN 1 END)           AS exploit_count,
            COUNT(CASE WHEN bucket='explore'   THEN 1 END)           AS explore_count,
            COUNT(CASE WHEN bucket='moonshot'  THEN 1 END)           AS moonshot_count
        FROM experiments
    """), {})

    d["explore_experiments"] = _safe(lambda: db.fetch_all("""
        SELECT id, idea_text, created_at, budget_allocated, status, confidence_score
        FROM experiments
        WHERE bucket='explore' AND status IN ('approved','running')
        ORDER BY created_at DESC LIMIT 6
    """), [])

    d["budget_history"]     = _safe(lambda: db.fetch_all("""
        SELECT date(created_at) AS day, SUM(budget_allocated) AS spent
        FROM experiments
        WHERE created_at >= date('now', '-7 days')
          AND status NOT IN ('rejected','killed')
        GROUP BY date(created_at)
        ORDER BY day
    """), [])

    # ── Leads
    d["leads_summary"]      = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*)                                                  AS total,
            COUNT(CASE WHEN qualification_score >= 7   THEN 1 END)   AS hot,
            COUNT(CASE WHEN qualification_score >= 5
                        AND qualification_score <  7   THEN 1 END)   AS nurture,
            COUNT(CASE WHEN qualification_score < 5
                        AND qualification_score IS NOT NULL THEN 1 END) AS disqualified,
            COUNT(CASE WHEN status='converted'         THEN 1 END)   AS converted,
            COUNT(CASE WHEN status='contacted'         THEN 1 END)   AS contacted,
            AVG(qualification_score)                                  AS avg_score,
            COUNT(CASE WHEN date(created_at) = date('now') THEN 1 END) AS today
        FROM leads
    """), {})

    d["recent_leads"]       = _safe(lambda: db.fetch_all("""
        SELECT name, phone, suburb, state, qualification_score,
               recommended_action, status, created_at
        FROM leads ORDER BY created_at DESC LIMIT 15
    """), [])

    d["lead_sources"]       = _safe(lambda: db.fetch_all("""
        SELECT source, COUNT(*) AS cnt,
               AVG(qualification_score) AS avg_score
        FROM leads GROUP BY source ORDER BY cnt DESC
    """), [])

    # ── Pheromones
    d["pheromones"]         = _safe(lambda: db.fetch_all("""
        SELECT signal_type, topic, vertical, strength, decay_factor, created_at
        FROM pheromone_signals
        ORDER BY (strength * decay_factor) DESC
        LIMIT 15
    """), [])

    d["pheromone_summary"]  = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*)                                              AS total,
            COUNT(CASE WHEN signal_type='POSITIVE' THEN 1 END)   AS positive,
            COUNT(CASE WHEN signal_type='NEGATIVE' THEN 1 END)   AS negative,
            AVG(strength)                                         AS avg_strength
        FROM pheromone_signals
        WHERE created_at >= date('now', '-7 days')
    """), {})

    # ── Task queue
    d["task_queue_stats"]   = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(CASE WHEN status='queued'   THEN 1 END)   AS queued,
            COUNT(CASE WHEN status='running'  THEN 1 END)   AS running,
            COUNT(CASE WHEN status='complete' THEN 1 END)   AS complete,
            COUNT(CASE WHEN status='failed'   THEN 1 END)   AS failed,
            COUNT(CASE WHEN status='queued' AND tier=1 THEN 1 END) AS tier1_queued,
            COUNT(CASE WHEN status='queued' AND tier=2 THEN 1 END) AS tier2_queued,
            COUNT(CASE WHEN status='queued' AND tier=3 THEN 1 END) AS tier3_queued
        FROM task_queue
    """), {})

    d["recent_tasks"]       = _safe(lambda: db.fetch_all("""
        SELECT job_type, assigned_to, status, priority, tier, completed_at, created_at
        FROM task_queue ORDER BY created_at DESC LIMIT 10
    """), [])

    # ── Message bus
    d["message_bus_queues"] = _safe(lambda: db.fetch_all("""
        SELECT to_queue,
            COUNT(CASE WHEN status='queued'     THEN 1 END) AS queued,
            COUNT(CASE WHEN status='processing' THEN 1 END) AS processing,
            COUNT(CASE WHEN status='complete'   THEN 1 END) AS complete,
            COUNT(CASE WHEN status='failed'     THEN 1 END) AS failed,
            COUNT(CASE WHEN status='expired'    THEN 1 END) AS expired
        FROM message_bus
        GROUP BY to_queue ORDER BY to_queue
    """), [])

    d["bus_summary"]        = _safe(mb.get_bus_summary, {})

    d["recent_messages"]    = _safe(lambda: db.fetch_all("""
        SELECT from_agent, to_queue, msg_type, priority, status, created_at
        FROM message_bus ORDER BY created_at DESC LIMIT 8
    """), [])

    # ── Opportunities
    d["opportunities"]      = _safe(lambda: db.fetch_all("""
        SELECT title, opp_type, overall_score,
               estimated_monthly_revenue_aud, status, source_agent, created_at
        FROM opportunities ORDER BY overall_score DESC LIMIT 10
    """), [])

    d["opp_stats"]          = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN status='active'     THEN 1 END) AS active,
            COUNT(CASE WHEN status='researching'THEN 1 END) AS researching,
            SUM(estimated_monthly_revenue_aud)              AS total_revenue_potential
        FROM opportunities
    """), {})

    # ── Research
    d["research_findings"]  = _safe(lambda: db.fetch_all("""
        SELECT research_type, query, status, confidence,
               opportunities_found, sources_count, created_at
        FROM research_findings ORDER BY created_at DESC LIMIT 10
    """), [])

    d["research_stats"]     = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN status='complete' THEN 1 END) AS complete,
            COUNT(CASE WHEN status='pending'  THEN 1 END) AS pending,
            AVG(confidence) AS avg_confidence,
            SUM(opportunities_found) AS total_opps
        FROM research_findings
    """), {})

    # ── A/B Tests
    d["ab_tests"]           = _safe(lambda: db.fetch_all("""
        SELECT test_id, hypothesis, status,
               variant_a_roi, variant_b_roi, winner, cycles_run, min_cycles,
               variable_changed, created_at
        FROM ab_tests ORDER BY created_at DESC LIMIT 8
    """), [])

    # ── Cold ledger
    d["cold_ledger_recent"] = _safe(lambda: db.fetch_all("""
        SELECT event_type, agent_id, human_involved, event_data, created_at
        FROM cold_ledger ORDER BY created_at DESC LIMIT 12
    """), [])

    d["cold_ledger_stats"]  = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*) AS total_events,
            COUNT(CASE WHEN human_involved=1 THEN 1 END) AS human_events,
            COUNT(DISTINCT event_type) AS unique_types
        FROM cold_ledger
    """), {})

    # ── Knowledge graph
    d["kg_stats"]           = _safe(lambda: db.fetch_one("""
        SELECT
            (SELECT COUNT(*) FROM kg_entities)      AS entities,
            (SELECT COUNT(*) FROM kg_relationships) AS relationships
    """), {})

    # ── Data collection
    d["collection_sources"] = _safe(lambda: db.fetch_all("""
        SELECT name, source_type, health_status, error_count,
               last_collected_at, collection_frequency
        FROM collection_sources ORDER BY health_status, name LIMIT 10
    """), [])

    d["collected_data_stats"] = _safe(lambda: db.fetch_one("""
        SELECT
            COUNT(*) AS total,
            COUNT(CASE WHEN processed=0 THEN 1 END) AS unprocessed,
            AVG(quality_score) AS avg_quality
        FROM collected_data
    """), {})

    # ── Time series (last metric per series)
    d["time_series"]        = _safe(lambda: db.fetch_all("""
        SELECT series_name, value, unit, recorded_at
        FROM time_series
        GROUP BY series_name
        HAVING recorded_at = MAX(recorded_at)
        ORDER BY series_name LIMIT 12
    """), [])

    return d


# ─────────────────────────────────────────────────────────────────────────────
# PANEL BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def panel_header(d: dict) -> Panel:
    now = d.get("now", datetime.now())
    title = Text()
    title.append("  SOLAR SWARM COMMAND CENTRE  ", style="bold bright_yellow on dark_red")
    title.append(f"  {now.strftime('%A %d %b %Y  %H:%M:%S')}  ", style="bold white")
    title.append("  Perth, WA  ", style="dim")
    return Panel(Align.center(title), style="bright_yellow", box=box.DOUBLE, padding=(0, 1))


def panel_system_health(d: dict) -> Panel:
    s = d.get("summary", {})
    cb = d.get("cb_level", "unknown")
    cb_colour = CB_COLOURS.get(cb, "dim")
    cb_icon   = CB_ICONS.get(cb, "? UNKNOWN")

    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=18)
    t.add_column()

    t.add_row(Text("CIRCUIT BREAKER", style="bold dim"), "")
    t.add_row(Text(cb_icon, style=cb_colour), "")
    t.add_row("", "")
    t.add_row(Text("Active Experiments", style="dim"), Text(str(s.get("active_experiments", "—")), style="bright_white"))
    t.add_row(Text("Pending Approval",   style="dim"), Text(str(s.get("pending_experiments", "—")), style="yellow"))
    t.add_row(Text("Budget Remaining",   style="dim"), Text(f"${s.get('budget_remaining', 0):.0f}", style="bright_green"))
    t.add_row(Text("Budget Used",        style="dim"), Text(f"${s.get('budget_used', 0):.0f}", style="white"))
    t.add_row(Text("Consec. Failures",   style="dim"), Text(str(s.get("consecutive_failures", 0)), style="red" if s.get("consecutive_failures", 0) >= 3 else "white"))

    return Panel(t, title="[bold]SYSTEM HEALTH[/]", border_style=cb_colour, box=box.ROUNDED, padding=(0, 1))


def panel_capital(d: dict) -> Panel:
    import config
    weekly = float(config.WEEKLY_BUDGET_AUD or 500)
    p = d.get("portfolio", {})
    buckets   = p.get("buckets", {})
    remaining = p.get("remaining", {})

    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=9)
    t.add_column(min_width=14)
    t.add_column(min_width=8)
    t.add_column()

    t.add_row(Text("Bucket", style="bold dim"), Text("Used / Total", style="bold dim"), Text("Remaining", style="bold dim"), "")

    for bucket, colour in BUCKET_COLOURS.items():
        used  = buckets.get(bucket, 0) or 0
        alloc = weekly * {"exploit": 0.60, "explore": 0.30, "moonshot": 0.10}[bucket]
        rem   = remaining.get(bucket, alloc - used)
        b = bar(used, alloc, width=12, colour=colour)
        t.add_row(
            Text(bucket.capitalize(), style=f"bold {colour}"),
            Text(f"${used:.0f} / ${alloc:.0f}"),
            Text(f"${rem:.0f}", style=colour),
            b,
        )

    t.add_row("", "", "", "")
    used_total = sum(buckets.get(k, 0) or 0 for k in BUCKET_COLOURS)
    t.add_row(
        Text("Weekly", style="bold"),
        Text(f"${used_total:.0f} / ${weekly:.0f}"),
        Text(pct(used_total, weekly), style="dim"),
        bar(used_total, weekly, width=12, colour="bright_yellow"),
    )

    # 7-day spend sparkline
    history = d.get("budget_history", [])
    if history:
        amounts = [h.get("spent", 0) or 0 for h in history]
        max_amt = max(amounts) if amounts else 1
        blocks  = " ".join("▁▂▃▄▅▆▇█"[min(int(a / max_amt * 7), 7)] for a in amounts)
        t.add_row("", Text(f"7d: {blocks}", style="dim"), "", "")

    return Panel(t, title="[bold]CAPITAL ALLOCATION[/]", border_style="bright_yellow", box=box.ROUNDED, padding=(0, 1))


def panel_lead_pipeline(d: dict) -> Panel:
    ls = d.get("leads_summary", {})
    total      = ls.get("total", 0) or 0
    hot        = ls.get("hot", 0) or 0
    nurture    = ls.get("nurture", 0) or 0
    disq       = ls.get("disqualified", 0) or 0
    converted  = ls.get("converted", 0) or 0
    contacted  = ls.get("contacted", 0) or 0
    avg_score  = ls.get("avg_score") or 0.0
    today      = ls.get("today", 0) or 0

    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=16)
    t.add_column(min_width=6)
    t.add_column()

    def row(label, value, colour="white", extra=""):
        t.add_row(Text(label, style="dim"), Text(str(value), style=f"bold {colour}"), Text(extra, style="dim"))

    row("Total Leads",     total,     "bright_white")
    row("Hot (score 7+)",  hot,       "bright_green",  f"({pct(hot, total)})")
    row("Nurture (5-6)",   nurture,   "yellow",        f"({pct(nurture, total)})")
    row("Disqualified",    disq,      "red",           f"({pct(disq, total)})")
    row("Contacted",       contacted, "cyan")
    row("Converted",       converted, "bright_green",  f"({pct(converted, total)})")
    row("Avg Score",       f"{avg_score:.1f}", score_colour(avg_score))
    row("Today",           today,     "bright_yellow")

    # Conversion funnel bar
    if total > 0:
        t.add_row("", "", "")
        t.add_row(Text("Funnel", style="bold dim"), bar(hot, total, 16, "bright_green"), Text(f"hot: {pct(hot, total)}", style="dim"))

    return Panel(t, title="[bold]LEAD PIPELINE[/]", border_style="bright_green", box=box.ROUNDED, padding=(0, 1))


def panel_agent_activity(d: dict) -> Panel:
    tq = d.get("task_queue_stats", {})
    bs = d.get("bus_summary", {})

    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=16)
    t.add_column()

    t.add_row(Text("TASK QUEUE", style="bold dim"), "")
    t.add_row(Text("Queued",   style="dim"), Text(str(tq.get("queued",  0)), style="yellow"))
    t.add_row(Text("Running",  style="dim"), Text(str(tq.get("running", 0)), style="cyan"))
    t.add_row(Text("Complete", style="dim"), Text(str(tq.get("complete",0)), style="green"))
    t.add_row(Text("Failed",   style="dim"), Text(str(tq.get("failed",  0)), style="red"))

    t.add_row(Text("Tier 1 Queue",style="dim"), Text(str(tq.get("tier1_queued",0)), style="magenta"))
    t.add_row(Text("Tier 2 Queue",style="dim"), Text(str(tq.get("tier2_queued",0)), style="cyan"))
    t.add_row(Text("Tier 3 Queue",style="dim"), Text(str(tq.get("tier3_queued",0)), style="white"))

    t.add_row("", "")
    t.add_row(Text("MESSAGE BUS", style="bold dim"), "")
    if isinstance(bs, dict):
        t.add_row(Text("Total Msgs",  style="dim"), Text(str(bs.get("total", "—")), style="white"))
        t.add_row(Text("Pending",     style="dim"), Text(str(bs.get("queued","—")), style="yellow"))
        t.add_row(Text("Failed",      style="dim"), Text(str(bs.get("failed","—")), style="red"))
    else:
        t.add_row(Text("Bus OK", style="dim"), Text("—", style="dim"))

    return Panel(t, title="[bold]AGENT ACTIVITY[/]", border_style="cyan", box=box.ROUNDED, padding=(0, 1))


def panel_active_experiments(d: dict) -> Panel:
    exps = d.get("active_experiments", [])
    es   = d.get("experiment_stats", {})

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("ID",     width=4,  style="dim")
    t.add_column("Idea",   width=32)
    t.add_column("Bucket", width=9)
    t.add_column("Conf",   width=6)
    t.add_column("Budget", width=8)
    t.add_column("Status", width=10)
    t.add_column("Age",    width=10, style="dim")

    for e in exps[:8]:
        bucket  = e.get("bucket", "—")
        conf    = e.get("confidence_score")
        status  = e.get("status", "—")
        t.add_row(
            str(e.get("id", "?")),
            trunc(e.get("idea_text", ""), 32),
            Text(bucket.capitalize(), style=BUCKET_COLOURS.get(bucket, "white")),
            Text(f"{conf:.1f}" if conf else "—", style=score_colour(conf)),
            f"${e.get('budget_allocated', 0):.0f}",
            Text(status, style=STATUS_COLOURS.get(status, "white")),
            age_str(e.get("created_at", "")),
        )

    if not exps:
        t.add_row("—", "[dim]No active experiments[/]", "", "", "", "", "")

    # Stats footer
    footer = Text()
    footer.append(f"  All-time: {es.get('total','—')} total  ", style="dim")
    footer.append(f"✓ {es.get('wins',0)} wins  ", style="green")
    footer.append(f"✗ {es.get('killed',0)} killed  ", style="red")
    if es.get("avg_roi"):
        footer.append(f"Avg ROI: {es.get('avg_roi',0):.1f}x  ", style="bright_yellow")
    if es.get("total_revenue"):
        footer.append(f"Revenue: ${es.get('total_revenue',0):.0f}  ", style="bright_green")

    from rich.console import Group
    return Panel(Group(t, footer), title="[bold]ACTIVE EXPERIMENTS[/]", border_style="green", box=box.ROUNDED)


def panel_pending_experiments(d: dict) -> Panel:
    exps = d.get("pending_experiments", [])

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("ID",     width=4,  style="dim")
    t.add_column("Idea",   width=36)
    t.add_column("Conf",   width=6)
    t.add_column("Devil",  width=6)
    t.add_column("Budget", width=8)
    t.add_column("Age",    width=10, style="dim")

    for e in exps[:8]:
        conf  = e.get("confidence_score")
        devil = e.get("devil_score")
        t.add_row(
            str(e.get("id", "?")),
            trunc(e.get("idea_text", ""), 36),
            Text(f"{conf:.1f}" if conf else "—", style=score_colour(conf)),
            Text(f"{devil:.1f}" if devil else "—", style="red" if devil and devil > 6 else "green"),
            f"${e.get('budget_allocated', 0):.0f}",
            age_str(e.get("created_at", "")),
        )

    if not exps:
        t.add_row("—", "[dim]No experiments awaiting approval[/]", "", "", "", "")

    return Panel(t, title=f"[bold yellow]PENDING APPROVAL ({len(exps)})[/]", border_style="yellow", box=box.ROUNDED)


def panel_recent_leads(d: dict) -> Panel:
    leads = d.get("recent_leads", [])
    sources = d.get("lead_sources", [])

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Name",    width=16)
    t.add_column("Suburb",  width=14)
    t.add_column("Score",   width=6)
    t.add_column("Action",  width=12)
    t.add_column("Status",  width=10)
    t.add_column("When",    width=10, style="dim")

    for l in leads:
        score  = l.get("qualification_score")
        action = l.get("recommended_action", "—") or "—"
        status = l.get("status", "—")
        t.add_row(
            trunc(l.get("name", "Unknown"), 16),
            trunc(l.get("suburb", "—") or "—", 14),
            Text(f"{score:.1f}" if score else "—", style=score_colour(score)),
            Text(action, style="bright_green" if action == "call_now" else "yellow" if action == "nurture" else "dim"),
            Text(status, style=STATUS_COLOURS.get(status, "white")),
            age_str(l.get("created_at", "")),
        )

    if not leads:
        t.add_row("[dim]No leads yet[/]", "", "", "", "", "")

    # Source breakdown
    source_line = Text("  Sources: ", style="dim")
    for s in sources:
        source_line.append(f"{s.get('source','?')}: {s.get('cnt',0)}  ", style="dim")

    from rich.console import Group
    return Panel(Group(t, source_line), title="[bold]RECENT LEADS[/]", border_style="bright_green", box=box.ROUNDED)


def panel_pheromones(d: dict) -> Panel:
    signals = d.get("pheromones", [])
    ps      = d.get("pheromone_summary", {})

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("",       width=2)
    t.add_column("Topic",  width=20)
    t.add_column("Vert",   width=10)
    t.add_column("Str",    width=5)
    t.add_column("Signal", width=18)
    t.add_column("When",   width=10, style="dim")

    for s in signals:
        stype    = s.get("signal_type", "NEUTRAL")
        strength = s.get("strength", 0.5) or 0
        decay    = s.get("decay_factor", 1.0) or 1.0
        eff      = strength * decay
        icon     = SIGNAL_ICONS.get(stype, "●")
        colour   = "green" if stype == "POSITIVE" else "red" if stype == "NEGATIVE" else "yellow"
        b = Text()
        filled = min(int(eff * 16), 16)
        b.append("█" * filled, style=colour)
        b.append("░" * (16 - filled), style="dim")

        t.add_row(
            icon,
            trunc(s.get("topic", "—"), 20),
            trunc(s.get("vertical", "—") or "—", 10),
            Text(f"{strength:.1f}", style=colour),
            b,
            age_str(s.get("created_at", "")),
        )

    if not signals:
        t.add_row("", "[dim]No pheromone signals yet[/]", "", "", "", "")

    footer = Text(f"  7d: +{ps.get('positive',0)} positive  -{ps.get('negative',0)} negative  avg: {ps.get('avg_strength',0):.2f}", style="dim")
    from rich.console import Group
    return Panel(Group(t, footer), title="[bold]PHEROMONE SIGNALS[/]", border_style="magenta", box=box.ROUNDED)


def panel_explore_protocol(d: dict) -> Panel:
    exps = d.get("explore_experiments", [])

    PHASES = [
        (0,  12, "Asset Creation"),
        (12, 24, "Distribution"),
        (24, 48, "Observation"),
        (48, 60, "Decision Point"),
        (60, 72, "Final Assessment"),
    ]

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("ID",      width=4,  style="dim")
    t.add_column("Idea",    width=28)
    t.add_column("Phase",   width=18)
    t.add_column("Elapsed", width=10)
    t.add_column("72h Bar", width=20)
    t.add_column("Budget",  width=8)

    for e in exps:
        try:
            created = datetime.fromisoformat(e.get("created_at", ""))
            elapsed = (datetime.now() - created).total_seconds() / 3600
        except Exception:
            elapsed = 0

        # Determine phase
        phase_label = "Expired"
        phase_colour = "red"
        for start, end, label in PHASES:
            if start <= elapsed < end:
                phase_label  = label
                phase_colour = "cyan" if elapsed < 48 else "yellow" if elapsed < 60 else "bright_green"
                break

        elapsed_bar = Text()
        filled = min(int((elapsed / 72) * 20), 20)
        elapsed_bar.append("█" * filled, style=phase_colour)
        elapsed_bar.append("░" * (20 - filled), style="dim")

        t.add_row(
            str(e.get("id", "?")),
            trunc(e.get("idea_text", ""), 28),
            Text(phase_label, style=f"bold {phase_colour}"),
            Text(f"{elapsed:.1f}h", style="dim"),
            elapsed_bar,
            f"${e.get('budget_allocated', 0):.0f}",
        )

    if not exps:
        t.add_row("—", "[dim]No active explore experiments[/]", "", "", "", "")

    legend = Text("  Phases: ", style="dim")
    for _, _, label in PHASES:
        legend.append(f"{label}  ", style="dim")
    from rich.console import Group
    return Panel(Group(t, legend), title="[bold cyan]72-HOUR EXPLORE PROTOCOL[/]", border_style="cyan", box=box.ROUNDED)


def panel_message_bus(d: dict) -> Panel:
    queues  = d.get("message_bus_queues", [])
    msgs    = d.get("recent_messages", [])

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Queue",      width=16)
    t.add_column("Queued",     width=7)
    t.add_column("Processing", width=11)
    t.add_column("Complete",   width=9)
    t.add_column("Failed",     width=7)
    t.add_column("Expired",    width=8)

    for q in queues:
        failed  = q.get("failed", 0) or 0
        expired = q.get("expired", 0) or 0
        t.add_row(
            Text(q.get("to_queue", "?"), style="bold"),
            Text(str(q.get("queued", 0)),      style="yellow"),
            Text(str(q.get("processing", 0)),  style="cyan"),
            Text(str(q.get("complete", 0)),    style="green"),
            Text(str(failed),  style="red"  if failed  > 0 else "dim"),
            Text(str(expired), style="dim"),
        )

    if not queues:
        t.add_row("[dim]No message bus data yet[/]", "", "", "", "", "")

    # Recent messages
    rt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    rt.add_column(width=12, style="dim")
    rt.add_column(width=12)
    rt.add_column(width=10)
    rt.add_column(width=8)
    rt.add_column(width=10, style="dim")

    for m in msgs[:5]:
        status = m.get("status", "—")
        t.add_row(
            Text(m.get("from_agent", "?"), style="dim"),
            Text(f"→ {m.get('to_queue','?')}"),
            Text(m.get("msg_type", "?"), style="cyan"),
            Text(m.get("priority", "?"), style="yellow" if m.get("priority") in ("CRITICAL","HIGH") else "dim"),
            Text(status, style=STATUS_COLOURS.get(status, "white")),
        )

    from rich.console import Group
    return Panel(Group(t), title="[bold]MESSAGE BUS QUEUES[/]", border_style="cyan", box=box.ROUNDED)


def panel_cold_ledger(d: dict) -> Panel:
    events = d.get("cold_ledger_recent", [])
    stats  = d.get("cold_ledger_stats", {})

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Event Type",  width=28)
    t.add_column("Agent",       width=14, style="dim")
    t.add_column("Human",       width=7)
    t.add_column("When",        width=12, style="dim")

    for e in events:
        human = e.get("human_involved", 0)
        t.add_row(
            Text(e.get("event_type", "—"), style="bold dim"),
            trunc(e.get("agent_id", "—") or "—", 14),
            Text("YES", style="bright_yellow") if human else Text("auto", style="dim"),
            age_str(e.get("created_at", "")),
        )

    if not events:
        t.add_row("[dim]No ledger entries yet[/]", "", "", "")

    footer = Text(f"  Total: {stats.get('total_events','—')} events  |  Human: {stats.get('human_events','—')}  |  Types: {stats.get('unique_types','—')}", style="dim")
    from rich.console import Group
    return Panel(Group(t, footer), title="[bold]COLD LEDGER (Immutable)[/]", border_style="dim", box=box.ROUNDED)


def panel_opportunities(d: dict) -> Panel:
    opps  = d.get("opportunities", [])
    stats = d.get("opp_stats", {})

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Title",       width=30)
    t.add_column("Type",        width=12)
    t.add_column("Score",       width=7)
    t.add_column("$/month",     width=10)
    t.add_column("Status",      width=12)
    t.add_column("Source",      width=14, style="dim")

    for o in opps:
        score  = o.get("overall_score", 0) or 0
        rev    = o.get("estimated_monthly_revenue_aud", 0) or 0
        status = o.get("status", "—")
        t.add_row(
            trunc(o.get("title", ""), 30),
            Text(o.get("opp_type", "—"), style="dim"),
            Text(f"{score:.1f}", style=score_colour(score)),
            Text(f"${rev:.0f}" if rev else "—", style="bright_green" if rev > 1000 else "white"),
            Text(status, style=STATUS_COLOURS.get(status, "white")),
            trunc(o.get("source_agent", "—") or "—", 14),
        )

    if not opps:
        t.add_row("[dim]No opportunities yet — research agents will populate this[/]", "", "", "", "", "")

    pot = stats.get("total_revenue_potential", 0) or 0
    footer = Text(f"  Total: {stats.get('total','—')}  |  Active: {stats.get('active','—')}  |  Potential: ${pot:.0f}/mo", style="dim")
    from rich.console import Group
    return Panel(Group(t, footer), title="[bold bright_yellow]OPPORTUNITY PIPELINE[/]", border_style="bright_yellow", box=box.ROUNDED)


def panel_research(d: dict) -> Panel:
    findings = d.get("research_findings", [])
    stats    = d.get("research_stats", {})

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Type",   width=18)
    t.add_column("Query",  width=30)
    t.add_column("Status", width=12)
    t.add_column("Conf",   width=6)
    t.add_column("Opps",   width=6)
    t.add_column("Srcs",   width=6)
    t.add_column("When",   width=10, style="dim")

    for f in findings:
        status = f.get("status", "—")
        conf   = f.get("confidence")
        t.add_row(
            Text(f.get("research_type", "—"), style="dim"),
            trunc(f.get("query", "—"), 30),
            Text(status, style=STATUS_COLOURS.get(status, "white")),
            Text(f"{conf:.1f}" if conf else "—", style=score_colour(conf * 10 if conf else None)),
            Text(str(f.get("opportunities_found", 0)), style="bright_yellow"),
            Text(str(f.get("sources_count", 0)), style="dim"),
            age_str(f.get("created_at", "")),
        )

    if not findings:
        t.add_row("[dim]No research findings yet[/]", "", "", "", "", "", "")

    footer = Text(
        f"  Total: {stats.get('total','—')}  |  Complete: {stats.get('complete','—')}  |  "
        f"Avg Conf: {stats.get('avg_confidence') or 0:.2f}  |  "
        f"Opps found: {stats.get('total_opps','—')}",
        style="dim"
    )
    from rich.console import Group
    return Panel(Group(t, footer), title="[bold]RESEARCH FINDINGS[/]", border_style="magenta", box=box.ROUNDED)


def panel_ab_tests(d: dict) -> Panel:
    tests = d.get("ab_tests", [])

    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", padding=(0, 1))
    t.add_column("Test ID",    width=18, style="dim")
    t.add_column("Hypothesis", width=32)
    t.add_column("Variable",   width=16)
    t.add_column("A ROI",      width=8)
    t.add_column("B ROI",      width=8)
    t.add_column("Winner",     width=8)
    t.add_column("Cycles",     width=8)
    t.add_column("Status",     width=12)

    for test in tests:
        status  = test.get("status", "—")
        winner  = test.get("winner")
        a_roi   = test.get("variant_a_roi")
        b_roi   = test.get("variant_b_roi")
        cycles  = test.get("cycles_run", 0) or 0
        min_c   = test.get("min_cycles", 3) or 3

        winner_text = Text(winner.upper() if winner else "—", style="bright_green" if winner else "dim")
        t.add_row(
            trunc(test.get("test_id", "—"), 18),
            trunc(test.get("hypothesis", "—"), 32),
            trunc(test.get("variable_changed", "—") or "—", 16),
            Text(f"{a_roi:.1f}x" if a_roi else "—", style="cyan"),
            Text(f"{b_roi:.1f}x" if b_roi else "—", style="cyan"),
            winner_text,
            Text(f"{cycles}/{min_c}", style="bright_yellow" if cycles >= min_c else "dim"),
            Text(status, style=STATUS_COLOURS.get(status, "white")),
        )

    if not tests:
        t.add_row("[dim]No A/B tests yet[/]", "", "", "", "", "", "", "")

    return Panel(t, title="[bold]A/B TESTS[/]", border_style="cyan", box=box.ROUNDED)


def panel_knowledge_graph(d: dict) -> Panel:
    kg = d.get("kg_stats", {})
    ts = d.get("time_series", [])
    cl = d.get("collection_sources", [])
    cd = d.get("collected_data_stats", {})

    t = Table.grid(padding=(0, 2))
    t.add_column(min_width=22)
    t.add_column(min_width=22)
    t.add_column()

    t.add_row(
        Text("KNOWLEDGE GRAPH", style="bold dim"),
        Text("DATA COLLECTION", style="bold dim"),
        Text("TIME SERIES METRICS", style="bold dim"),
    )
    t.add_row(
        Text(f"Entities:       {kg.get('entities', 0)}", style="white"),
        Text(f"Sources:        {len(cl)}", style="white"),
        Text(f"Series tracked: {len(ts)}", style="white"),
    )
    t.add_row(
        Text(f"Relationships:  {kg.get('relationships', 0)}", style="white"),
        Text(f"Records total:  {cd.get('total', 0)}", style="white"),
        "",
    )
    t.add_row(
        "",
        Text(f"Unprocessed:    {cd.get('unprocessed', 0)}", style="yellow" if (cd.get("unprocessed") or 0) > 0 else "dim"),
        "",
    )

    # Data sources health
    if cl:
        for src in cl[:4]:
            health = src.get("health_status", "healthy")
            t.add_row(
                "",
                Text(f"  {src.get('name','?')[:16]}: {health}", style=STATUS_COLOURS.get(health, "white")),
                "",
            )

    # Time series recent values
    for ts_row in ts[:4]:
        t.add_row(
            "",
            "",
            Text(f"  {ts_row.get('series_name','?')[:18]}: {ts_row.get('value',0):.2f} {ts_row.get('unit','') or ''}", style="dim"),
        )

    return Panel(t, title="[bold]KNOWLEDGE GRAPH  |  DATA COLLECTION  |  TIME SERIES[/]", border_style="dim", box=box.ROUNDED, padding=(0, 1))


def panel_footer(d: dict, interval: int = 5, watch: bool = False) -> Panel:
    now = d.get("now", datetime.now())
    t = Text()
    t.append(f"  Last refresh: {now.strftime('%H:%M:%S')}  ", style="dim")
    if watch:
        t.append(f"  Auto-refresh: every {interval}s  ", style="dim")
    t.append("  [q] Quit  [r] Refresh  ", style="dim")
    t.append("  CLI: python cli.py swarm-status  ", style="dim")
    t.append("  API: http://localhost:5000/dashboard  ", style="dim")
    return Panel(t, style="dim", box=box.HORIZONTALS, padding=(0, 0))


# ─────────────────────────────────────────────────────────────────────────────
# FULL RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render(d: dict, interval: int = 5, watch: bool = False) -> None:
    """Print the entire dashboard to the console."""
    if "_error" in d:
        console.print(Panel(Text(d["_error"], style="bold red"), title="ERROR", border_style="red"))
        return

    from rich.console import Group

    console.print(panel_header(d))

    # ── Row 1: Status cards (4 columns)
    console.print(Columns([
        panel_system_health(d),
        panel_capital(d),
        panel_lead_pipeline(d),
        panel_agent_activity(d),
    ], equal=True, expand=True))

    # ── Row 2: Experiments side-by-side
    console.print(Columns([
        panel_active_experiments(d),
        panel_pending_experiments(d),
    ], equal=True, expand=True))

    # ── Row 3: Leads + Pheromones
    console.print(Columns([
        panel_recent_leads(d),
        panel_pheromones(d),
    ], equal=True, expand=True))

    # ── Row 4: 72hr Explore Protocol (full width)
    console.print(panel_explore_protocol(d))

    # ── Row 5: Message Bus + Cold Ledger
    console.print(Columns([
        panel_message_bus(d),
        panel_cold_ledger(d),
    ], equal=True, expand=True))

    # ── Row 6: Opportunities + Research
    console.print(Columns([
        panel_opportunities(d),
        panel_research(d),
    ], equal=True, expand=True))

    # ── Row 7: A/B Tests (full width)
    console.print(panel_ab_tests(d))

    # ── Row 8: Knowledge Graph + Data Collection + Time Series
    console.print(panel_knowledge_graph(d))

    # ── Footer
    console.print(panel_footer(d, interval=interval, watch=watch))


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Solar Swarm Command Centre — Rich Terminal Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dashboard.py                     # single snapshot
  python dashboard.py --watch             # auto-refresh every 5 seconds
  python dashboard.py --watch --interval 10
        """,
    )
    parser.add_argument("--watch",    action="store_true", help="Auto-refresh mode")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    if args.watch:
        console.print(f"[dim]Solar Swarm Command Centre — live mode (refresh every {args.interval}s) — Ctrl+C to exit[/]")
        try:
            while True:
                console.clear()
                d = get_data()
                render(d, interval=args.interval, watch=True)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/]")
    else:
        d = get_data()
        render(d, interval=args.interval, watch=False)


if __name__ == "__main__":
    main()
