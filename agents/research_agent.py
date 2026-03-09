"""Research Agent — Tier 2: Department Head for research operations.

Runs daily. Manages the research task queue:
  - Solar company prospecting
  - Market intelligence gathering
  - Competitor analysis
  - Pheromone signal synthesis

Spawns Tier 3 workers for individual research tasks.
"""

import logging
from datetime import datetime
from memory.hot_memory import get_next_task, enqueue_task, complete_task, fail_task, post_pheromone
from memory.database import fetch_all, parse_payload
from memory.cold_ledger import log_event
import config

logger = logging.getLogger(__name__)


def run(max_tasks: int = 5) -> dict:
    """Run the research department's daily task processing cycle.

    Args:
        max_tasks: Maximum number of tasks to process in this run

    Returns:
        Dict with tasks_processed, tasks_failed, signals_posted
    """
    print(f"\n[RESEARCH HEAD] === Daily Research Cycle ===")
    print(f"[RESEARCH HEAD] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    processed = 0
    failed = 0
    signals = 0

    for _ in range(max_tasks):
        task = get_next_task(tier=3)
        if not task or task.get("job_type", "").split("_")[0] != "research":
            break

        task_id = task["id"]
        job_type = task["job_type"]
        context = parse_payload(task.get("context_payload", "{}"))

        print(f"[RESEARCH HEAD] Processing task #{task_id}: {job_type}")

        try:
            result = _dispatch_task(job_type, context)
            complete_task(task_id, result)
            processed += 1

            if result.get("signal_type"):
                post_pheromone(
                    signal_type=result["signal_type"],
                    topic=result.get("topic", job_type),
                    strength=result.get("strength", 0.5),
                    vertical="solar_australia",
                )
                signals += 1

        except Exception as e:
            logger.error(f"[RESEARCH HEAD] Task #{task_id} failed: {e}")
            fail_task(task_id, str(e))
            failed += 1

    _queue_routine_research()

    result = {"tasks_processed": processed, "tasks_failed": failed, "signals_posted": signals}
    log_event("RESEARCH_CYCLE", result, agent_id="research_agent")
    print(f"[RESEARCH HEAD] Cycle complete: {result}")
    return result


def _dispatch_task(job_type: str, context: dict) -> dict:
    """Route a task to the appropriate handler.

    Args:
        job_type: The type of research task
        context: Task-specific parameters

    Returns:
        Result dict with output and optional pheromone data
    """
    handlers = {
        "research_prospect": _prospect_company,
        "research_market": _analyse_market,
        "research_competitor": _analyse_competitor,
    }
    handler = handlers.get(job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job_type}")
    return handler(context)


def _prospect_company(context: dict) -> dict:
    """Prospect a solar company for outreach.

    Args:
        context: Dict with company_name, suburb

    Returns:
        Dict with research results and pheromone signal
    """
    from agents.solar_research_agent import research as solar_research
    company_name = context.get("company_name", "Unknown")
    suburb = context.get("suburb", "Perth")
    print(f"[RESEARCH HEAD] Prospecting: {company_name}, {suburb}")
    result = solar_research(company_name, suburb)
    result["signal_type"] = "POSITIVE" if result.get("score", 0) >= 6 else "NEUTRAL"
    result["topic"] = "solar_prospecting"
    result["strength"] = min(1.0, result.get("score", 5) / 10.0)
    return result


def _analyse_market(context: dict) -> dict:
    """Analyse market signals for a vertical.

    Args:
        context: Dict with vertical, keywords

    Returns:
        Dict with market analysis and pheromone signal
    """
    vertical = context.get("vertical", "solar_australia")
    print(f"[RESEARCH HEAD] Analysing market: {vertical}")
    return {
        "vertical": vertical,
        "analysis": "Market analysis placeholder — configure OpenAI for live analysis",
        "signal_type": "NEUTRAL",
        "topic": "market_analysis",
        "strength": 0.5,
    }


def _analyse_competitor(context: dict) -> dict:
    """Research a competitor in the solar automation space.

    Args:
        context: Dict with competitor_name

    Returns:
        Dict with competitive intel and pheromone signal
    """
    competitor = context.get("competitor_name", "Unknown")
    print(f"[RESEARCH HEAD] Competitor analysis: {competitor}")
    return {
        "competitor": competitor,
        "gaps": ["No AI-powered follow-up", "Manual lead qualification", "No 24/7 response"],
        "signal_type": "POSITIVE",
        "topic": "competitive_gap",
        "strength": 0.7,
    }


def _queue_routine_research():
    """Queue standard daily research tasks if queue is empty."""
    pending = fetch_all("SELECT COUNT(*) as count FROM task_queue WHERE status='queued' AND job_type LIKE 'research_%'")
    count = pending[0].get("count", 0) if pending else 0
    if count == 0:
        enqueue_task("research_market", {"vertical": "solar_australia"}, priority=7, tier=3)
        print("[RESEARCH HEAD] Queued routine market analysis task")


def queue_prospect(company_name: str, suburb: str) -> int:
    """Queue a company prospecting task.

    Args:
        company_name: Solar company name
        suburb: Location suburb

    Returns:
        Task id
    """
    return enqueue_task(
        "research_prospect",
        {"company_name": company_name, "suburb": suburb},
        priority=3,
        tier=3,
    )
