"""Solar Swarm CLI — Command line interface for operating the swarm.

Usage:
  python cli.py swarm-status       — show running experiments, budget, circuit breaker
  python cli.py leads              — last 20 leads with scores
  python cli.py leads --hot        — only score 7+ leads
  python cli.py approve <id>       — approve a pending experiment
  python cli.py reject <id>        — reject a pending experiment
  python cli.py run-general        — manually trigger the General now
  python cli.py retrospective      — generate weekly report now
  python cli.py test-lead          — send a fake solar lead through qualification
  python cli.py test-webhook       — send a fake GHL webhook event
  python cli.py stats              — conversion rates, avg score, pipeline summary
  python cli.py reset-breaker      — reset circuit breaker (requires confirmation)
  python cli.py scout              — run scout agent now (find prospects)
  python cli.py research <query>   — queue a research task manually
  python cli.py opportunities      — show top discovered opportunities
  python cli.py collect            — run data collection cycle now
  python cli.py bus-status         — show message bus queue depths
  python cli.py kg-summary         — show knowledge graph entity counts
  python cli.py ab-tests           — show A/B test results summary
  python cli.py mutate             — run mutation engine now
  python cli.py configure          — interactive API key setup wizard
"""

import sys
import os
import json
from datetime import datetime

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.database import init_db, fetch_all, fetch_one, update
from memory.hot_memory import get_swarm_summary, get_pending_experiments


def cmd_swarm_status():
    """Display current swarm status."""
    print("\n" + "=" * 55)
    print("  SOLAR SWARM — LIVE STATUS")
    print("=" * 55)

    summary = get_swarm_summary()

    cb_level = summary.get("circuit_breaker", "green")
    cb_icons = {"green": "✅ GREEN", "yellow": "⚠️  YELLOW", "orange": "🟠 ORANGE", "red": "🛑 RED"}
    cb_display = cb_icons.get(cb_level, cb_level.upper())

    print(f"\n  Circuit Breaker:    {cb_display}")
    print(f"  Active Experiments: {summary.get('active_experiments', 0)}")
    print(f"  Pending Approval:   {summary.get('pending_approval', 0)}")
    print(f"  Budget Used:        ${summary.get('budget_used_aud', 0):.2f} AUD")
    print(f"  Budget Remaining:   ${summary.get('budget_remaining_aud', 0):.2f} AUD")
    print(f"  Consecutive Fails:  {summary.get('consecutive_failures', 0)}")

    from capital.portfolio_manager import get_portfolio_summary
    portfolio = get_portfolio_summary()
    remaining = portfolio.get("remaining", {})
    print("\n  BUDGET BY BUCKET:")
    for bucket in ["exploit", "explore", "moonshot"]:
        print(f"    {bucket.capitalize():<12} ${remaining.get(bucket, 0):.2f} remaining")

    pending = get_pending_experiments()
    if pending:
        print(f"\n  PENDING APPROVAL ({len(pending)}):")
        for exp in pending[:5]:
            print(f"    #{exp['id']} [{exp.get('confidence_score', 0):.1f}/10] {exp.get('idea_text', '')[:55]}...")
        if len(pending) > 5:
            print(f"    ... and {len(pending) - 5} more")

    print()


def cmd_leads(hot_only: bool = False):
    """Display recent leads with qualification scores."""
    print("\n" + "=" * 55)
    print("  SOLAR LEADS" + (" — HOT ONLY (7+)" if hot_only else " — LAST 20"))
    print("=" * 55)

    if hot_only:
        rows = fetch_all(
            "SELECT * FROM leads WHERE qualification_score >= 7 ORDER BY created_at DESC LIMIT 20"
        )
    else:
        rows = fetch_all("SELECT * FROM leads ORDER BY created_at DESC LIMIT 20")

    if not rows:
        print("\n  No leads found. Run: python cli.py test-lead")
        return

    print(f"\n  {'ID':<4} {'Score':<6} {'Name':<22} {'Action':<12} {'Status':<10} {'Date'}")
    print("  " + "-" * 68)
    for r in rows:
        score = r.get("qualification_score") or 0
        score_str = f"{score:.0f}/10" if score else " N/A "
        icon = "🔥" if score >= 7 else "📋" if score >= 5 else "❌"
        date = (r.get("created_at") or "")[:10]
        print(f"  {r['id']:<4} {icon}{score_str:<4} {str(r.get('name','?')):<22} {str(r.get('recommended_action','?')):<12} {str(r.get('status','?')):<10} {date}")
    print()


def cmd_approve(experiment_id: int):
    """Approve a pending experiment."""
    exp = fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        print(f"\n  Error: Experiment #{experiment_id} not found")
        return
    if exp.get("status") != "pending":
        print(f"\n  Error: Experiment #{experiment_id} has status '{exp['status']}' — not pending")
        return

    print(f"\n  Experiment #{experiment_id}:")
    print(f"  Idea: {exp.get('idea_text', '')[:70]}...")
    print(f"  Confidence: {exp.get('confidence_score', 0):.1f}/10 | Devil: {exp.get('devil_score', 0):.1f}/10")
    print(f"  Bucket: {exp.get('bucket')} | Kelly: {exp.get('kelly_fraction', 0):.3f}")

    from capital.kelly_engine import calculate_budget
    budget = calculate_budget(exp.get("confidence_score", 5))["budget_aud"]
    print(f"\n  Approving with ${budget:.2f} AUD budget...")

    update("experiments", experiment_id, {
        "status": "approved",
        "budget_allocated": budget,
        "approved_by": "cli",
        "approved_at": datetime.utcnow().isoformat(),
    })

    from memory.cold_ledger import log_experiment_approved
    log_experiment_approved(experiment_id, "cli", budget)
    print(f"  ✅ Experiment #{experiment_id} approved.")


def cmd_reject(experiment_id: int):
    """Reject a pending experiment with a reason."""
    exp = fetch_one("SELECT * FROM experiments WHERE id = ?", (experiment_id,))
    if not exp:
        print(f"\n  Error: Experiment #{experiment_id} not found")
        return

    print(f"\n  Experiment #{experiment_id}: {exp.get('idea_text', '')[:70]}...")
    reason = input("  Rejection reason (or press Enter to skip): ").strip()
    if not reason:
        reason = "Rejected via CLI"

    update("experiments", experiment_id, {
        "status": "rejected",
        "failure_mode": reason,
        "completed_at": datetime.utcnow().isoformat(),
    })
    from memory.cold_ledger import log_experiment_killed
    log_experiment_killed(experiment_id, reason, "cli")
    print(f"  ❌ Experiment #{experiment_id} rejected.")


def cmd_run_general():
    """Manually trigger the General's strategic planning cycle."""
    print("\n  Triggering The General...")
    from agents.master_agent import run
    results = run()
    print(f"\n  General cycle complete. {len(results)} ideas processed.")


def cmd_retrospective():
    """Generate the weekly retrospective now."""
    print("\n  Generating weekly retrospective...")
    from memory.retrospective import run
    result = run()
    print("\n" + "-" * 55)
    print(result.get("retro_text", "No output generated"))
    print("-" * 55)


def cmd_test_lead():
    """Send a fake solar lead through the full qualification pipeline."""
    print("\n" + "=" * 55)
    print("  TEST: Solar Lead Qualification Pipeline")
    print("=" * 55)

    fake_lead = {
        "name": "Test User — Jim Sanderson",
        "phone": "0412 345 678",
        "email": "jim.sanderson@test.com",
        "suburb": "Joondalup",
        "state": "WA",
        "homeowner_status": "owner",
        "monthly_bill": 320,
        "roof_type": "tile",
        "roof_age": 8,
    }

    print(f"\n  Lead data:")
    for k, v in fake_lead.items():
        print(f"    {k}: {v}")

    from memory.database import insert, json_payload
    lead_id = insert("leads", {
        "source": "manual",
        "name": fake_lead["name"],
        "phone": fake_lead["phone"],
        "email": fake_lead["email"],
        "suburb": fake_lead["suburb"],
        "state": fake_lead["state"],
        "homeowner_status": fake_lead["homeowner_status"],
        "monthly_bill": fake_lead["monthly_bill"],
        "roof_type": fake_lead["roof_type"],
        "roof_age": fake_lead["roof_age"],
        "client_account": "test",
    })
    print(f"\n  Lead saved to database (id=#{lead_id})")

    print("\n  Running qualification...")
    from agents.qualification_agent import qualify
    result = qualify(fake_lead, lead_id)

    print(f"\n  RESULT:")
    print(f"    Score:  {result.get('score', 'N/A')}/10")
    print(f"    Action: {result.get('recommended_action', 'N/A')}")
    print(f"    Reason: {result.get('reason', 'N/A')}")

    if result.get("key_signals"):
        print(f"    Signals: {', '.join(result.get('key_signals', []))}")

    print(f"\n  ✅ Test lead pipeline PASSED (lead #{lead_id})")
    return True


def cmd_test_webhook():
    """Send a fake GHL webhook event and process it."""
    print("\n  Sending fake GHL webhook event...")

    fake_payload = {
        "full_name": "Test Webhook — Sarah Chen",
        "phone": "0487 654 321",
        "email": "sarah.chen@test.com",
        "suburb": "Subiaco",
        "state": "WA",
        "homeowner_status": "owner",
        "monthly_bill": "250",
        "roof_type": "colorbond",
        "roof_age": "5",
        "locationId": "test-location",
    }

    from webhooks.ghl_handler import _extract_lead_data
    lead_data = _extract_lead_data(fake_payload)

    from memory.database import insert, json_payload
    lead_id = insert("leads", {
        "source": "ghl_webhook",
        "name": lead_data.get("name"),
        "phone": lead_data.get("phone"),
        "email": lead_data.get("email"),
        "suburb": lead_data.get("suburb"),
        "state": lead_data.get("state"),
        "homeowner_status": lead_data.get("homeowner_status"),
        "monthly_bill": lead_data.get("monthly_bill"),
        "roof_type": lead_data.get("roof_type"),
        "roof_age": lead_data.get("roof_age"),
        "client_account": "test",
        "notes": json_payload(fake_payload),
    })

    from agents.qualification_agent import qualify
    result = qualify(lead_data, lead_id)

    print(f"  Webhook processed: lead #{lead_id} | Score: {result.get('score')}/10 | Action: {result.get('recommended_action')}")
    print(f"  ✅ Webhook test complete.")


def cmd_stats():
    """Show conversion rates, average scores, and pipeline summary."""
    print("\n" + "=" * 55)
    print("  SOLAR SWARM — PIPELINE STATISTICS")
    print("=" * 55)

    from agents.analytics_agent import get_conversion_stats
    stats = get_conversion_stats()

    if stats.get("total_leads", 0) == 0:
        print("\n  No leads in database yet.")
        print("  Run: python cli.py test-lead")
        return

    print(f"\n  LEAD PIPELINE:")
    print(f"    Total leads:     {stats['total_leads']}")
    print(f"    Call now (hot):  {stats['call_now']}")
    print(f"    Nurture:         {stats['nurture']}")
    print(f"    Disqualified:    {stats['disqualify']}")
    print(f"    Converted:       {stats['converted']}")
    print(f"    Conversion rate: {stats['conversion_rate_pct']}%")
    print(f"    Avg lead score:  {stats['avg_qualification_score']}/10")

    print(f"\n  EXPERIMENT PIPELINE:")
    exp_rows = fetch_all("SELECT status, COUNT(*) as count FROM experiments GROUP BY status")
    for r in exp_rows:
        print(f"    {r['status']:<12}: {r['count']}")

    print()


def cmd_reset_breaker():
    """Reset the circuit breaker (Red level requires confirmation)."""
    from capital.circuit_breaker import get_circuit_breaker_state, reset_breaker
    state = get_circuit_breaker_state()

    if not state.get("active"):
        print("\n  No active circuit breaker to reset.")
        return

    level = state.get("level", "unknown")
    print(f"\n  Active circuit breaker: {level.upper()}")
    print(f"  Reason: {state.get('reason', 'unknown')}")

    if level == "red":
        print("\n  ⚠️  WARNING: Red circuit breaker halts ALL experiments.")
        confirm = input("  Type 'RESET' to confirm: ").strip()
        if confirm != "RESET":
            print("  Reset cancelled.")
            return

    result = reset_breaker("cli")
    if result["success"]:
        print(f"  ✅ {result['message']}")
    else:
        print(f"  ❌ {result['message']}")


def cmd_scout():
    """Run the scout agent now to find new solar company prospects."""
    print("\n  Running scout agent...")
    from agents.scout_agent import run
    result = run()
    print(f"\n  Prospects found:       {result['prospects_found']}")
    print(f"  Queued for research:   {result['queued_for_research']}")
    print(f"  Opportunities saved:   {result['opportunities_saved']}")


def cmd_research(query: str):
    """Queue a manual research task and run the engine immediately."""
    print(f"\n  Queuing research: {query}")
    from research.orchestrator import queue_research, run
    research_id = queue_research("market", query, requested_by="cli", priority="HIGH")
    print(f"  Research queued: {research_id}")
    print("  Running research engine...")
    result = run(max_tasks=1)
    print(f"  Done — completed={result.get('completed', 0)} opportunities={result.get('opportunities_found', 0)}")


def cmd_opportunities(limit: int = 10):
    """Show top discovered opportunities ranked by priority score."""
    print("\n" + "=" * 55)
    print("  TOP OPPORTUNITIES")
    print("=" * 55)
    from storage.opportunity_store import get_top, get_summary
    summary = get_summary()
    by_status = summary.get("by_status", {})
    print(f"\n  Total: {sum(by_status.values())} | "
          f"Discovered: {by_status.get('discovered', 0)} | "
          f"Actioned: {by_status.get('actioned', 0)} | "
          f"Won: {by_status.get('won', 0)}")
    opps = get_top(limit=limit)
    if not opps:
        print("\n  No opportunities yet. Run: python cli.py scout")
        return
    print(f"\n  {'Score':<7} {'Type':<12} {'Effort':<8} {'Impact':<8} Title")
    print("  " + "-" * 60)
    for o in opps:
        print(f"  {o['priority_score']:<7.2f} {o['opp_type']:<12} {o['effort']:<8} {o['impact']:<8} {o['title'][:35]}")
    print()


def cmd_collect():
    """Run data collection cycle now."""
    print("\n  Running data collection cycle...")
    from data_collection.orchestrator import run
    result = run()
    print(f"\n  Sources run:   {result['sources_run']}")
    print(f"  Records:       {result['collected']}")
    print(f"  New signals:   {result['new_signals']}")
    print(f"  Failed:        {result['failed']}")
    print("\n  Running pipeline processor...")
    from data_collection.pipeline.processor import process_batch
    pr = process_batch(since_minutes=30)
    print(f"  Processed: {pr['processed']} | Deduped: {pr['deduplicated']} | Signals posted: {pr['signals_posted']}")


def cmd_bus_status():
    """Show message bus queue depths across all agents."""
    print("\n" + "=" * 55)
    print("  MESSAGE BUS STATUS")
    print("=" * 55)
    from bus.message_bus import get_bus_summary
    summary = get_bus_summary()
    if not summary:
        print("\n  No messages on bus yet.")
        return
    print(f"\n  {'Queue':<25} {'Queued':<8} {'Processing':<12} {'Complete':<10} {'Failed'}")
    print("  " + "-" * 60)
    for queue, counts in sorted(summary.items()):
        print(f"  {queue:<25} {counts.get('queued', 0):<8} {counts.get('processing', 0):<12} "
              f"{counts.get('complete', 0):<10} {counts.get('failed', 0)}")
    print()


def cmd_kg_summary():
    """Show knowledge graph entity and relationship counts."""
    print("\n" + "=" * 55)
    print("  KNOWLEDGE GRAPH SUMMARY")
    print("=" * 55)
    from storage.knowledge_graph import get_graph_summary
    summary = get_graph_summary()
    print("\n  ENTITIES:")
    for etype, count in summary.get("entities", {}).items():
        print(f"    {etype:<15} {count}")
    print("\n  RELATIONSHIPS:")
    for rtype, count in summary.get("relationships", {}).items():
        print(f"    {rtype:<20} {count}")
    print()


def cmd_ab_tests():
    """Show A/B test status summary."""
    print("\n" + "=" * 55)
    print("  A/B TEST SUMMARY")
    print("=" * 55)
    from agents.ab_tester import get_summary
    from memory.database import fetch_all
    summary = get_summary()
    print(f"\n  Running:   {summary.get('running', 0)}")
    print(f"  Complete:  {summary.get('complete', 0)}")
    rows = fetch_all(
        "SELECT name, winner, winner_stats FROM ab_tests WHERE status='complete' ORDER BY completed_at DESC LIMIT 5"
    )
    if rows:
        print("\n  RECENT WINNERS:")
        for r in rows:
            stats = json.loads(r["winner_stats"]) if r.get("winner_stats") else {}
            lift = stats.get("lift", 0)
            print(f"    {r['name'][:40]:<40} winner=Variant {str(r.get('winner','?')).upper()} lift={lift}%")
    print()


def cmd_configure():
    """Interactive wizard to set API keys and save them to .env."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    # Load existing values
    current = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    current[k.strip()] = v.strip()

    def mask(val):
        """Mask key value for display."""
        if not val:
            return ""
        return val[:4] + "…" + val[-4:] if len(val) > 8 else "****"

    def ask(env_key, label, required=False):
        """Prompt for a value, returning existing if user presses Enter."""
        cur  = current.get(env_key, "")
        hint = f" [{mask(cur)}]" if cur else " [not set]"
        tag  = " (REQUIRED)" if required else " (optional)"
        try:
            val = input(f"  {label}{tag}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return cur
        return val if val else cur

    print("\n" + "=" * 55)
    print("  SOLAR SWARM — API CONFIGURATION WIZARD")
    print("  Press Enter to keep the existing value.")
    print("=" * 55)

    print("\n── REQUIRED ───────────────────────────────────────────")
    current["OPENAI_API_KEY"]  = ask("OPENAI_API_KEY",  "OpenAI API Key",      required=True)
    current["GHL_API_KEY"]     = ask("GHL_API_KEY",     "GoHighLevel API Key", required=True)
    current["GHL_LOCATION_ID"] = ask("GHL_LOCATION_ID", "GHL Location ID",     required=True)

    print("\n── SLACK ──────────────────────────────────────────────")
    current["SLACK_WEBHOOK_URL"]     = ask("SLACK_WEBHOOK_URL",     "Slack Incoming Webhook URL")
    current["SLACK_BOT_TOKEN"]       = ask("SLACK_BOT_TOKEN",       "Slack Bot Token (xoxb-...)")
    current["SLACK_DEFAULT_CHANNEL"] = ask("SLACK_DEFAULT_CHANNEL", "Slack Default Channel")
    current["SLACK_SIGNING_SECRET"]  = ask("SLACK_SIGNING_SECRET",  "Slack Signing Secret")

    print("\n── VOICE AI ───────────────────────────────────────────")
    current["RETELL_API_KEY"]          = ask("RETELL_API_KEY",          "Retell AI API Key")
    current["RETELL_DEFAULT_VOICE_ID"] = ask("RETELL_DEFAULT_VOICE_ID", "Retell Default Voice ID")
    current["ELEVENLABS_API_KEY"]      = ask("ELEVENLABS_API_KEY",      "ElevenLabs API Key")
    current["VOICE_WEBHOOK_BASE_URL"]  = ask("VOICE_WEBHOOK_BASE_URL",  "Voice Webhook Base URL")
    current["TRANSFER_PHONE"]          = ask("TRANSFER_PHONE",          "Transfer Phone (+61...)")

    print("\n── GHL EXTRAS ─────────────────────────────────────────")
    current["GHL_PIPELINE_ID"] = ask("GHL_PIPELINE_ID", "GHL Pipeline ID")

    print("\n── EMAIL (IMAP) ───────────────────────────────────────")
    current["IMAP_HOST"] = ask("IMAP_HOST", "IMAP Host (e.g. imap.gmail.com)")
    current["IMAP_USER"] = ask("IMAP_USER", "IMAP Username")
    current["IMAP_PASS"] = ask("IMAP_PASS", "IMAP Password")

    print("\n── BUDGET & PORTS ─────────────────────────────────────")
    current["WEEKLY_BUDGET_AUD"]  = ask("WEEKLY_BUDGET_AUD",  "Weekly Budget AUD")
    current["PORT_HUMAN_GATE"]    = ask("PORT_HUMAN_GATE",    "Port: Human Gate")
    current["PORT_GHL_WEBHOOKS"]  = ask("PORT_GHL_WEBHOOKS",  "Port: GHL Webhooks")
    current["PORT_VOICE_WEBHOOK"] = ask("PORT_VOICE_WEBHOOK", "Port: Voice Webhook")
    current["PORT_DASHBOARD_API"] = ask("PORT_DASHBOARD_API", "Port: Dashboard API")
    current["DATABASE_PATH"]      = ask("DATABASE_PATH",      "Database Path")
    current["LOG_LEVEL"]          = ask("LOG_LEVEL",          "Log Level (INFO/DEBUG)")

    # Write structured .env file
    sections = [
        ("OpenAI",          ["OPENAI_API_KEY", "OPENAI_MODEL"]),
        ("GoHighLevel",     ["GHL_API_KEY", "GHL_LOCATION_ID", "GHL_PIPELINE_ID"]),
        ("Slack",           ["SLACK_WEBHOOK_URL", "SLACK_BOT_TOKEN", "SLACK_DEFAULT_CHANNEL", "SLACK_SIGNING_SECRET"]),
        ("Voice AI",        ["RETELL_API_KEY", "RETELL_DEFAULT_VOICE_ID", "ELEVENLABS_API_KEY",
                             "ELEVENLABS_DEFAULT_VOICE", "VOICE_WEBHOOK_BASE_URL", "TRANSFER_PHONE", "DEFAULT_CLIENT_ID"]),
        ("Email (IMAP)",    ["IMAP_HOST", "IMAP_USER", "IMAP_PASS", "IMAP_FOLDER"]),
        ("HubSpot",         ["HUBSPOT_API_KEY"]),
        ("Budget & Ports",  ["WEEKLY_BUDGET_AUD", "PORT_HUMAN_GATE", "PORT_GHL_WEBHOOKS",
                             "PORT_VOICE_WEBHOOK", "PORT_DASHBOARD_API"]),
        ("Database",        ["DATABASE_PATH", "LOG_LEVEL"]),
    ]

    lines = [
        "# Solar Swarm — Environment Variables\n",
        f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "# NEVER commit this file to version control\n\n",
    ]
    for title, keys in sections:
        lines.append(f"# {title}\n")
        for k in keys:
            lines.append(f"{k}={current.get(k, '')}\n")
        lines.append("\n")

    with open(env_path, "w") as f:
        f.writelines(lines)

    print(f"\n  ✓ Saved to {env_path}")
    print("  Run: python dashboard.py  to verify configuration status\n")


def cmd_mutate():
    """Run the mutation engine now to evolve underperforming strategies."""
    print("\n  Running mutation engine...")
    from agents.mutation_engine import run
    result = run()
    print(f"\n  Analysed:          {result['analysed']}")
    print(f"  Mutations created: {result['mutations_created']}")
    print(f"  Killed:            {result['killed']}")


def main():
    """Parse CLI arguments and dispatch to the correct command."""
    init_db()

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "swarm-status":
        cmd_swarm_status()
    elif cmd == "leads":
        hot_only = "--hot" in args
        cmd_leads(hot_only)
    elif cmd == "approve" and len(args) >= 2:
        cmd_approve(int(args[1]))
    elif cmd == "reject" and len(args) >= 2:
        cmd_reject(int(args[1]))
    elif cmd == "run-general":
        cmd_run_general()
    elif cmd == "retrospective":
        cmd_retrospective()
    elif cmd == "test-lead":
        success = cmd_test_lead()
        sys.exit(0 if success else 1)
    elif cmd == "test-webhook":
        cmd_test_webhook()
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "reset-breaker":
        cmd_reset_breaker()
    elif cmd == "scout":
        cmd_scout()
    elif cmd == "research" and len(args) >= 2:
        cmd_research(" ".join(args[1:]))
    elif cmd == "opportunities":
        cmd_opportunities()
    elif cmd == "collect":
        cmd_collect()
    elif cmd == "bus-status":
        cmd_bus_status()
    elif cmd == "kg-summary":
        cmd_kg_summary()
    elif cmd == "ab-tests":
        cmd_ab_tests()
    elif cmd == "mutate":
        cmd_mutate()
    elif cmd == "configure":
        cmd_configure()
    else:
        print(f"\n  Unknown command: '{cmd}'")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
