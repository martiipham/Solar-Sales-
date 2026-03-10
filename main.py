"""Solar Admin AI — Main Orchestrator.

Starts the complete system:
  - Flask: Human Gate API on port 5000
  - Flask: GHL Webhook server on port 5001
  - Flask: Voice AI Webhook on port 5002
  - Flask: Dashboard API on port 5003
  - APScheduler: CRM sync every 30 minutes
  - APScheduler: Lead qualification check every 60 minutes

Usage:
  python main.py
"""

import sys
import os
import logging
import threading

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
    """Configure and return the APScheduler with MVP jobs.

    Returns:
        Configured BackgroundScheduler instance (not yet started)
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = BackgroundScheduler(timezone="UTC")

    # CRM Sync — every 30 minutes
    scheduler.add_job(
        _run_crm_sync,
        trigger=IntervalTrigger(minutes=30),
        id="crm_sync",
        name="CRM Data Sync",
        replace_existing=True,
        max_instances=1,
    )

    # Lead Qualification Check — every 60 minutes
    scheduler.add_job(
        _run_lead_check,
        trigger=IntervalTrigger(minutes=60),
        id="lead_check",
        name="Lead Qualification Check",
        replace_existing=True,
        max_instances=1,
    )

    # Health Monitor — every 5 minutes
    scheduler.add_job(
        _run_health_check,
        trigger=IntervalTrigger(minutes=5),
        id="health_monitor",
        name="Service Health Monitor",
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


def _run_health_check():
    """Scheduled job: check all service health endpoints and alert on failure."""
    job = "health_monitor"
    if not _agent_enabled("health_monitor"):
        return
    try:
        from monitor.health_monitor import run_health_check
        run_health_check()
        _log_agent_run(job)
    except Exception as e:
        logger.error(f"[SCHEDULER] Health check failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def _run_crm_sync():
    """Scheduled job: pull live CRM data into SQLite cache."""
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


def _run_lead_check():
    """Scheduled job: qualify any leads that haven't been scored yet."""
    job = "lead_check"
    if not _agent_enabled("qualification"):
        return
    try:
        from memory.database import fetch_all
        from agents.qualification_agent import qualify
        rows = fetch_all(
            "SELECT id, name, email, suburb, state, monthly_bill, homeowner_status "
            "FROM leads WHERE qualification_score IS NULL ORDER BY created_at DESC LIMIT 20"
        )
        for row in rows:
            lead_data = dict(row)
            lead_id = lead_data.pop("id")
            qualify(lead_data, lead_id)
        _log_agent_run(job, notes=f"Qualified {len(rows)} leads")
    except Exception as e:
        logger.error(f"[SCHEDULER] Lead check failed: {e}")
        _log_agent_run(job, "error", str(e)[:200])


def start_dashboard_api(port: int):
    """Start the Dashboard API Flask server in a daemon thread.

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
    from datetime import datetime
    print("\n" + "=" * 60)
    print("  SOLAR ADMIN AI")
    print("  By Martin Pham | Perth, Australia")
    print("=" * 60)
    print(f"\n  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n  SERVICES:")
    print(f"    Human Gate API:   http://localhost:{config.PORT_HUMAN_GATE}")
    print(f"    GHL Webhooks:     http://localhost:{config.PORT_GHL_WEBHOOKS}")
    print(f"    Voice AI Webhook: http://localhost:{config.PORT_VOICE_WEBHOOK}")
    print(f"    Dashboard API:    http://localhost:{config.PORT_DASHBOARD_API}")
    print(f"\n  SCHEDULER:")
    print(f"    CRM Sync:         Every 30 minutes")
    print(f"    Lead Check:       Every 60 minutes")
    print(f"    Health Monitor:   Every 5 minutes")
    print(f"\n  CONFIG:")
    print(f"    OpenAI:           {'OK' if config.is_configured() else 'NOT SET'}")
    print(f"    GHL:              {'OK' if config.GHL_API_KEY else 'NOT SET'}")
    print(f"    Slack:            {'OK' if config.SLACK_WEBHOOK_URL else 'NOT SET'}")
    print(f"    Retell AI:        {'OK' if config.retell_configured() else 'NOT SET'}")
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

    # Seed knowledge base
    try:
        from knowledge.company_kb import init_demo_client
        init_demo_client()
    except Exception as e:
        logger.error(f"[MAIN] KB init failed: {e}")

    # Start IMAP polling if configured
    try:
        from email_processing.email_agent import start_imap_polling
        start_imap_polling(interval_seconds=120)
    except Exception as e:
        logger.error(f"[MAIN] IMAP polling start failed: {e}")

    # Start scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    print("[MAIN] Scheduler started — CRM sync every 30min, lead check every 60min, health check every 5min")

    # Keep main thread alive
    try:
        import time
        while True:
            time.sleep(60)
            logger.debug("[MAIN] Heartbeat — all services running")
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown requested — stopping scheduler...")
        scheduler.shutdown()
        print("[MAIN] Solar Admin AI stopped.")


if __name__ == "__main__":
    main()
