"""Worker — Tier 3: Stateless task executor.

Workers are spawned on-demand and self-terminate after completing
one task. They are completely stateless — all state is read from
and written to the database.

Workers post pheromone signals on completion.
"""

import logging
import sys
from datetime import datetime
from memory.hot_memory import get_next_task, complete_task, fail_task, post_pheromone
from memory.database import parse_payload
from memory.cold_ledger import log_pheromone_signal
import config

logger = logging.getLogger(__name__)


def run_task(task_id: int = None) -> dict:
    """Pick up and execute one task from the queue, then terminate.

    Args:
        task_id: Specific task id to run, or None to grab next queued

    Returns:
        Dict with task result and pheromone signal posted
    """
    if task_id:
        from memory.database import fetch_one
        task = fetch_one("SELECT * FROM task_queue WHERE id = ?", (task_id,))
    else:
        task = get_next_task()

    if not task:
        print("[WORKER] No tasks available — terminating")
        return {"status": "idle", "message": "No tasks available"}

    task_id = task["id"]
    job_type = task["job_type"]
    context = parse_payload(task.get("context_payload", "{}"))
    experiment_id = context.get("experiment_id")

    print(f"[WORKER] Starting task #{task_id}: {job_type}")

    from memory.database import update
    update("task_queue", task_id, {"status": "running", "assigned_to": "worker"})

    try:
        result = _execute(job_type, context)
        complete_task(task_id, result)

        signal_type = result.get("signal_type", "NEUTRAL")
        topic = result.get("topic", job_type)
        strength = float(result.get("strength", 0.5))

        post_pheromone(signal_type, topic, strength, experiment_id=experiment_id)
        log_pheromone_signal(signal_type, topic, strength, experiment_id)

        print(f"[WORKER] Task #{task_id} complete | Signal: {signal_type} ({strength:.1f})")
        return {"status": "complete", "task_id": task_id, "result": result}

    except Exception as e:
        logger.error(f"[WORKER] Task #{task_id} failed: {e}")
        fail_task(task_id, str(e))
        post_pheromone("NEGATIVE", job_type, 0.3, experiment_id=experiment_id)
        return {"status": "failed", "task_id": task_id, "error": str(e)}


def _execute(job_type: str, context: dict) -> dict:
    """Dispatch task to the correct handler.

    Args:
        job_type: Type of work to perform
        context: Task parameters

    Returns:
        Result dict with output and pheromone data
    """
    handlers = {
        # Research tasks
        "research_prospect": _handle_prospect,
        "research_market": _handle_market,
        # Content tasks
        "content_ad_copy": _handle_ad_copy,
        "content_email": _handle_email,
        "content_linkedin": _handle_linkedin,
        "content_sms": _handle_sms,
        # Solar tasks
        "solar_qualify_lead": _handle_qualify_lead,
        "solar_research_company": _handle_research_company,
        "solar_generate_proposal": _handle_proposal,
        # Generic
        "generic_test": _handle_test,
    }
    handler = handlers.get(job_type, _handle_unknown)
    return handler(context)


def _handle_prospect(context: dict) -> dict:
    """Handle company prospecting tasks."""
    from agents.solar_research_agent import research
    result = research(context.get("company_name", "Unknown"), context.get("suburb", "Perth"))
    return {**result, "signal_type": "POSITIVE" if result.get("score", 0) >= 6 else "NEUTRAL",
            "topic": "solar_prospect", "strength": min(1.0, result.get("score", 5) / 10)}


def _handle_market(context: dict) -> dict:
    """Handle market analysis tasks."""
    return {"analysis": "Market scan complete", "signal_type": "NEUTRAL", "topic": "market", "strength": 0.5}


def _handle_ad_copy(context: dict) -> dict:
    """Handle ad copy generation."""
    from agents.content_agent import _generate_ad_copy
    result = _generate_ad_copy(context)
    return {**result, "signal_type": "POSITIVE", "topic": "content_ads", "strength": 0.6}


def _handle_email(context: dict) -> dict:
    """Handle email sequence generation."""
    from agents.content_agent import _generate_email_sequence
    result = _generate_email_sequence(context)
    return {**result, "signal_type": "POSITIVE", "topic": "content_email", "strength": 0.6}


def _handle_linkedin(context: dict) -> dict:
    """Handle LinkedIn post generation."""
    from agents.content_agent import _generate_linkedin_post
    result = _generate_linkedin_post(context)
    return {**result, "signal_type": "NEUTRAL", "topic": "content_social", "strength": 0.5}


def _handle_sms(context: dict) -> dict:
    """Handle SMS template generation."""
    from agents.content_agent import _generate_sms
    result = _generate_sms(context)
    return {**result, "signal_type": "POSITIVE", "topic": "content_sms", "strength": 0.5}


def _handle_qualify_lead(context: dict) -> dict:
    """Handle lead qualification."""
    from agents.qualification_agent import qualify
    result = qualify(context)
    strength = min(1.0, result.get("score", 5) / 10)
    signal = "POSITIVE" if result.get("score", 0) >= 7 else "NEUTRAL" if result.get("score", 0) >= 5 else "NEGATIVE"
    return {**result, "signal_type": signal, "topic": "lead_quality", "strength": strength}


def _handle_research_company(context: dict) -> dict:
    """Handle solar company research."""
    from agents.solar_research_agent import research
    result = research(context.get("company_name", "Unknown"), context.get("suburb", "Perth"))
    return {**result, "signal_type": "POSITIVE", "topic": "company_research", "strength": 0.6}


def _handle_proposal(context: dict) -> dict:
    """Handle proposal generation."""
    from agents.proposal_agent import generate
    result = generate(
        client_name=context.get("client_name", "Client"),
        pain_points=context.get("pain_points", []),
        current_process=context.get("current_process", ""),
        estimated_leads_per_month=context.get("estimated_leads_per_month", 50),
    )
    return {**result, "signal_type": "POSITIVE", "topic": "proposal", "strength": 0.8}


def _handle_test(context: dict) -> dict:
    """Handle generic test tasks."""
    return {
        "message": "Test task completed successfully",
        "context": context,
        "signal_type": "POSITIVE",
        "topic": "test",
        "strength": 1.0,
    }


def _handle_unknown(context: dict) -> dict:
    """Handle unknown job types gracefully."""
    return {
        "message": "Unknown job type — no handler found",
        "signal_type": "NEUTRAL",
        "topic": "unknown",
        "strength": 0.0,
    }


if __name__ == "__main__":
    task_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_task(task_id)
