"""Solar Swarm — Main Orchestrator.

Starts the complete system:
  - APScheduler: General runs every 6 hours
  - APScheduler: Retrospective every Monday 8am AEST
  - APScheduler: Pheromone decay every 24 hours
  - APScheduler: Department heads run daily
  - APScheduler: Scout agent daily at 08:00 UTC
  - APScheduler: Data collection every 4 hours
  - APScheduler: Research engine daily at 06:00 UTC
  - APScheduler: Pipeline processor every 4 hours (after collection)
  - APScheduler: A/B test evaluator daily at 10:00 UTC
  - APScheduler: Message bus expiry every 6 hours
  - Flask: Human Gate API on port 5000
  - Flask: GHL Webhook server on port 5001

Usage:
  python main.py
"""

import sys
import os
import logging
import threading
from datetime import datetime, timedelta

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from memory.database import init_db

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def setup_scheduler():
    """Configure and return the APScheduler with all jobs.

    Returns:
        Configured BlockingScheduler instance (not yet started)
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = BackgroundScheduler(timezone="UTC")

    # The General — every 6 hours
    scheduler.add_job(
        _run_general,
        trigger=IntervalTrigger(hours=6),
        id="general",
        name="The General (Tier 1)",
        replace_existing=True,
        max_instances=1,
    )

    # Department Heads — daily at 9am UTC (7pm AEST)
    scheduler.add_job(
        _run_department_heads,
        trigger=CronTrigger(hour=9, minute=0),
        id="department_heads",
        name="Department Heads (Tier 2)",
        replace_existing=True,
        max_instances=1,
    )

    # Weekly Retrospective — Monday 22:00 UTC = Tuesday 8am AEST
    scheduler.add_job(
        _run_retrospective,
        trigger=CronTrigger(day_of_week="mon", hour=22, minute=0),
        id="retrospective",
        name="Weekly Retrospective",
        replace_existing=True,
        max_instances=1,
    )

    # Pheromone decay — daily at midnight UTC
    scheduler.add_job(
        _run_pheromone_decay,
        trigger=CronTrigger(hour=0, minute=0),
        id="pheromone_decay",
        name="Pheromone Decay",
        replace_existing=True,
        max_instances=1,
    )

    # Scout Agent — daily at 08:00 UTC
    scheduler.add_job(
        _run_scout,
        trigger=CronTrigger(hour=8, minute=0),
        id="scout_agent",
        name="Scout Agent (Prospect Hunter)",
        replace_existing=True,
        max_instances=1,
    )

    # Research Engine — daily at 06:00 UTC (before scout so KG is fresh)
    scheduler.add_job(
        _run_research_engine,
        trigger=CronTrigger(hour=6, minute=0),
        id="research_engine",
        name="Research Engine",
        replace_existing=True,
        max_instances=1,
    )

    # Data Collection — every 4 hours
    scheduler.add_job(
        _run_data_collection,
        trigger=IntervalTrigger(hours=4),
        id="data_collection",
        name="Data Collection Engine",
        replace_existing=True,
        max_instances=1,
    )

    # Pipeline Processor — every 4 hours (30 min after collection)
    pipeline_start = datetime.utcnow() + timedelta(minutes=30)
    scheduler.add_job(
        _run_pipeline,
        trigger=IntervalTrigger(hours=4, start_date=pipeline_start),
        id="pipeline_processor",
        name="Pipeline Processor",
        replace_existing=True,
        max_instances=1,
    )

    # A/B Test Evaluator — daily at 10:00 UTC
    scheduler.add_job(
        _run_ab_evaluator,
        trigger=CronTrigger(hour=10, minute=0),
        id="ab_evaluator",
        name="A/B Test Evaluator",
        replace_existing=True,
        max_instances=1,
    )

    # Mutation Engine — Monday retrospective (runs after retrospective)
    scheduler.add_job(
        _run_mutation_engine,
        trigger=CronTrigger(day_of_week="mon", hour=22, minute=30),
        id="mutation_engine",
        name="Mutation Engine",
        replace_existing=True,
        max_instances=1,
    )

    # Message Bus Expiry — every 6 hours
    scheduler.add_job(
        _run_bus_expiry,
        trigger=IntervalTrigger(hours=6),
        id="bus_expiry",
        name="Message Bus Expiry",
        replace_existing=True,
        max_instances=1,
    )

    # Explore Monitor — every 2 hours (drives 72-hour explore lifecycle)
    scheduler.add_job(
        _run_explore_monitor,
        trigger=IntervalTrigger(hours=2),
        id="explore_monitor",
        name="72-Hour Explore Protocol Monitor",
        replace_existing=True,
        max_instances=1,
    )

    # CRM Sync — every 30 minutes (feeds dashboard board with live CRM data)
    scheduler.add_job(
        _run_crm_sync,
        trigger=IntervalTrigger(minutes=30),
        id="crm_sync",
        name="CRM Data Sync",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler


def _agent_enabled(agent_id: str) -> bool:
    """Check if an agent is enabled in the settings table.

    Returns True by default if no config exists for this agent.

    Args:
        agent_id: Agent identifier matching the frontend catalogue
    """
    try:
        from memory.database import fetch_one
        import json as _json
        row = fetch_one("SELECT value FROM settings WHERE key = 'agent_config'")
        if row:
            cfg = _json.loads(row["value"])
            return cfg.get(agent_id, True)
    except Exception:
        pass
    return True


def _log_agent_run(job_id: str, status: str = "ok", notes: str = ""):
    """Write a run record to agent_run_log for dashboard display.

    Args:
        job_id: Scheduler job identifier
        status: 'ok' or 'error'
        notes:  Optional short message
    """
    try:
        from memory.database import insert
        insert("agent_run_log", {"job_id": job_id, "status": status, "notes": notes})
    except Exception:
        pass


def _run_general():
    """Scheduled job: run The General's strategic planning cycle."""
    if not _agent_enabled("general"):
        logger.info("[SCHEDULER] General skipped — disabled in agent config")
        return
    try:
        from agents.master_agent import run
        run()
        _log_agent_run("general")
    except Exception as e:
        logger.error(f"[SCHEDULER] General failed: {e}")
        _log_agent_run("general", "error", str(e)[:200])


def _run_department_heads():
    """Scheduled job: run all Tier 2 department heads."""
    job = "department_heads"
    try:
        from agents.research_agent import run as research_run
        from agents.content_agent import run as content_run
        from agents.analytics_agent import run as analytics_run
        if _agent_enabled("research"):
            research_run()
        if _agent_enabled("content"):
            content_run()
        if _agent_enabled("analytics"):
            analytics_run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Department heads failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_retrospective():
    """Scheduled job: run the weekly retrospective."""
    job = "retrospective"
    if not _agent_enabled("retro"):
        logger.info("[SCHEDULER] Retrospective skipped — disabled")
        return
    try:
        from memory.retrospective import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Retrospective failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_pheromone_decay():
    """Scheduled job: apply pheromone signal decay."""
    try:
        from memory.hot_memory import apply_pheromone_decay
        apply_pheromone_decay()
        _log_agent_run("pheromone_decay")
    except Exception as e:
        logger.error(f"[SCHEDULER] Pheromone decay failed: {e}")
        _log_agent_run("pheromone_decay", "error", str(e)[:200])


def _run_scout():
    """Scheduled job: scout agent hunts for new solar company prospects."""
    job = "scout_agent"
    if not _agent_enabled("scout"):
        logger.info("[SCHEDULER] Scout skipped — disabled")
        return
    try:
        from agents.scout_agent import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Scout agent failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_research_engine():
    """Scheduled job: research engine processes queued research tasks."""
    job = "research_engine"
    if not _agent_enabled("research_engine"):
        logger.info("[SCHEDULER] Research engine skipped — disabled")
        return
    try:
        from research.orchestrator import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Research engine failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_data_collection():
    """Scheduled job: data collection engine gathers fresh market data."""
    job = "data_collection"
    if not _agent_enabled("data_collection"):
        logger.info("[SCHEDULER] Data collection skipped — disabled")
        return
    try:
        from data_collection.orchestrator import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Data collection failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_pipeline():
    """Scheduled job: pipeline processor normalises and routes collected data."""
    job = "pipeline_processor"
    if not _agent_enabled("pipeline"):
        logger.info("[SCHEDULER] Pipeline processor skipped — disabled")
        return
    try:
        from data_collection.pipeline.processor import process_batch
        process_batch(since_minutes=260)  # covers 4h interval + buffer
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Pipeline processor failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_ab_evaluator():
    """Scheduled job: A/B test evaluator checks running tests for winners."""
    job = "ab_evaluator"
    if not _agent_enabled("abtester"):
        logger.info("[SCHEDULER] A/B evaluator skipped — disabled")
        return
    try:
        from agents.ab_tester import evaluate_tests
        evaluate_tests()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] A/B evaluator failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_mutation_engine():
    """Scheduled job: mutation engine evolves underperforming strategies."""
    job = "mutation_engine"
    if not _agent_enabled("mutation"):
        logger.info("[SCHEDULER] Mutation engine skipped — disabled")
        return
    try:
        from agents.mutation_engine import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Mutation engine failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_explore_monitor():
    """Scheduled job: monitor 72-hour explore experiment lifecycle."""
    job = "explore_monitor"
    try:
        from capital.portfolio_manager import run_explore_monitor
        run_explore_monitor()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Explore monitor failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_bus_expiry():
    """Scheduled job: expire stale messages on the message bus."""
    try:
        from bus.message_bus import expire_old_messages
        expire_old_messages()
        _log_agent_run("bus_expiry")
    except Exception as e:
        logger.error(f"[SCHEDULER] Bus expiry failed: {e}")
        _log_agent_run("bus_expiry", "error", str(e)[:200])


def _run_crm_sync():
    """Scheduled job: pull live CRM data into SQLite cache and update board-state.json."""
    job = "crm_sync"
    if not _agent_enabled("crm_sync"):
        return
    try:
        from api.crm_sync import run
        run()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] CRM sync failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def start_dashboard_api(port: int):
    """Start the Dashboard API Flask server in a daemon thread.

    Serves CORS-enabled endpoints for the swarm-board React app.

    Args:
        port: Port number to listen on
    """
    from api.dashboard_api import dashboard_app
    dashboard_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start_human_gate(port: int):
    """Start the Human Gate Flask API in a daemon thread.

    Args:
        port: Port number to listen on
    """
    from api.human_gate import gate_app
    gate_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start_ghl_webhooks(port: int):
    """Start the GHL Webhook Flask server in a daemon thread.

    Args:
        port: Port number to listen on
    """
    from webhooks.ghl_handler import ghl_app
    ghl_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start_voice_webhook(port: int):
    """Start the Voice AI + Email webhook server in a daemon thread.

    Handles:
      POST /voice/call-started        — Retell call initialisation
      POST /voice/response            — Retell custom LLM endpoint
      POST /voice/post-call           — Post-call transcript processing
      POST /voice/elevenlabs/response — ElevenLabs alternative
      POST /webhook/email-received    — GHL email forwarding
      GET  /voice/health              — Health check

    Args:
        port: Port number to listen on
    """
    from voice.call_handler import voice_app
    from flask import request, jsonify
    from email_processing.email_agent import process_email

    @voice_app.route("/webhook/email-received", methods=["POST"])
    def email_received():
        """GHL email webhook — forward inbound emails for AI processing."""
        try:
            data      = request.get_json(force=True) or {}
            client_id = data.get("locationId") or config.DEFAULT_CLIENT_ID
            result    = process_email({
                "from_address": data.get("from") or data.get("sender"),
                "to_address":   data.get("to")   or data.get("recipient"),
                "subject":      data.get("subject", ""),
                "body":         data.get("body")  or data.get("message", ""),
                "received_at":  data.get("date",  ""),
            }, client_id=client_id)
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"[EMAIL WEBHOOK] Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    voice_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def print_banner():
    """Print the startup banner with service information."""
    print("\n" + "=" * 60)
    print("  SOLAR SWARM — AUTONOMOUS AGENT SYSTEM")
    print("  By Martin Pham | Perth, Australia")
    print("=" * 60)
    print(f"\n  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n  SERVICES:")
    print(f"    Human Gate API:   http://localhost:{config.PORT_HUMAN_GATE}")
    print(f"    GHL Webhooks:     http://localhost:{config.PORT_GHL_WEBHOOKS}")
    print(f"    Voice AI Webhook: http://localhost:{config.PORT_VOICE_WEBHOOK}")
    print(f"    Dashboard API:    http://localhost:{config.PORT_DASHBOARD_API}  ← swarm-board feed")
    print(f"\n  SCHEDULER:")
    print(f"    The General:      Every 6 hours")
    print(f"    Dept Heads:       Daily 9:00 UTC")
    print(f"    Retrospective:    Monday 22:00 UTC (Tue 8am AEST)")
    print(f"    Pheromone Decay:  Daily midnight UTC")
    print(f"\n  CONFIG:")
    print(f"    Weekly Budget:    ${config.WEEKLY_BUDGET_AUD} AUD")
    print(f"    OpenAI:           {'✅ Configured' if config.is_configured() else '⚠️  Not configured (add to .env)'}")
    print(f"    GHL:              {'✅ Configured' if config.GHL_API_KEY else '⚠️  Not configured'}")
    print(f"    Slack:            {'✅ Configured' if config.SLACK_WEBHOOK_URL else '⚠️  Not configured'}")
    print(f"    Retell AI:        {'✅ Configured' if config.retell_configured() else '⚠️  Not configured'}")
    print(f"    ElevenLabs:       {'✅ Configured' if config.elevenlabs_configured() else '⚠️  Not configured'}")
    print(f"\n  Press Ctrl+C to stop\n")
    print("=" * 60 + "\n")


def main():
    """Initialise the database, start all services, and run the scheduler."""
    print_banner()
    init_db()

    # Start Flask servers in daemon threads
    gate_thread = threading.Thread(
        target=start_human_gate,
        args=(config.PORT_HUMAN_GATE,),
        daemon=True,
        name="HumanGateAPI",
    )
    webhook_thread = threading.Thread(
        target=start_ghl_webhooks,
        args=(config.PORT_GHL_WEBHOOKS,),
        daemon=True,
        name="GHLWebhooks",
    )
    voice_thread = threading.Thread(
        target=start_voice_webhook,
        args=(config.PORT_VOICE_WEBHOOK,),
        daemon=True,
        name="VoiceAIWebhook",
    )
    dashboard_thread = threading.Thread(
        target=start_dashboard_api,
        args=(config.PORT_DASHBOARD_API,),
        daemon=True,
        name="DashboardAPI",
    )
    gate_thread.start()
    webhook_thread.start()
    voice_thread.start()
    dashboard_thread.start()
    print(f"[MAIN] Human Gate API running on port {config.PORT_HUMAN_GATE}")
    print(f"[MAIN] GHL Webhook server running on port {config.PORT_GHL_WEBHOOKS}")
    print(f"[MAIN] Voice AI webhook running on port {config.PORT_VOICE_WEBHOOK}")
    print(f"[MAIN] Dashboard API running on port {config.PORT_DASHBOARD_API}")

    # Seed knowledge base + start IMAP polling if configured
    try:
        from knowledge.company_kb import init_demo_client
        init_demo_client()
    except Exception as e:
        logger.error(f"[MAIN] KB init failed: {e}")

    try:
        from email_processing.email_agent import start_imap_polling
        start_imap_polling(interval_seconds=120)
    except Exception as e:
        logger.error(f"[MAIN] IMAP polling start failed: {e}")

    # Start scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    print("[MAIN] Scheduler started — all jobs active")

    # Run The General immediately on startup
    print("[MAIN] Running initial General cycle...")
    _run_general()

    # Keep main thread alive
    try:
        import time
        while True:
            time.sleep(60)
            logger.debug("[MAIN] Heartbeat — all services running")
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown requested — stopping scheduler...")
        scheduler.shutdown()
        print("[MAIN] Solar Swarm stopped.")


if __name__ == "__main__":
    main()
