"""Research Orchestrator — Manages the research engine for Solar Swarm.

Runs on a daily schedule. Responsibilities:
  - Reads the research queue from the database
  - Prioritises tasks: CRITICAL → HIGH → NORMAL → LOW
  - Dispatches to specialist sub-agents based on research type
  - Collects findings and dispatches to Synthesis Agent
  - Writes actionable insights to opportunities table
  - Posts pheromone signals for strong market findings

Research types:
  market     → solar market demand, pricing, trends in Australia
  competitive → competitor CRM/automation products targeting solar
  prospect   → deep research on a specific solar company
  technical  → tools/APIs/integrations for building automations
  validation → verify a hypothesis before committing budget
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from memory.database import insert, fetch_all, fetch_one, update, json_payload
from memory.cold_ledger import log_event
from memory.hot_memory import post_pheromone
import config

logger = logging.getLogger(__name__)

QUEUES = {
    "market": "research.market",
    "competitive": "research.competitive",
    "prospect": "research.prospect",
    "technical": "research.technical",
    "validation": "research.validation",
}


def run(max_tasks: int = 5) -> dict:
    """Run the research engine's daily cycle.

    Args:
        max_tasks: Maximum research tasks to process this cycle

    Returns:
        Dict with tasks_processed, opportunities_found, findings_stored
    """
    print(f"\n[RESEARCH ENGINE] === Daily Research Cycle ===")
    print(f"[RESEARCH ENGINE] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    tasks_processed = 0
    opportunities_found = 0

    _queue_routine_research()

    pending = fetch_all(
        "SELECT * FROM research_findings WHERE status='pending' "
        "ORDER BY CASE "
        "  WHEN requested_by='orchestrator' THEN 1 "
        "  WHEN requested_by='scout' THEN 2 "
        "  ELSE 3 END, created_at ASC LIMIT ?",
        (max_tasks,),
    )

    for task in pending:
        research_id = task["research_id"]
        research_type = task["research_type"]
        query = task["query"]

        print(f"[RESEARCH ENGINE] Processing: [{research_type.upper()}] {query[:60]}")

        _mark_in_progress(research_id)

        try:
            findings = _dispatch(research_type, query, task)

            if findings:
                synthesised = _synthesise(research_id, query, findings, research_type)
                _store_findings(research_id, synthesised)

                opps = synthesised.get("opportunities", [])
                for opp in opps:
                    _save_opportunity(opp, research_id)
                    opportunities_found += 1

                if synthesised.get("pheromone_signal"):
                    sig = synthesised["pheromone_signal"]
                    post_pheromone(
                        signal_type=sig["type"],
                        topic=sig["topic"],
                        strength=sig["strength"],
                        vertical="solar_australia",
                    )

                tasks_processed += 1
            else:
                _mark_failed(research_id, "No findings returned from sub-agent")

        except Exception as e:
            logger.error(f"[RESEARCH ENGINE] Task {research_id} failed: {e}")
            _mark_failed(research_id, str(e))

    result = {
        "tasks_processed": tasks_processed,
        "opportunities_found": opportunities_found,
        "cycle_at": datetime.utcnow().isoformat(),
    }
    log_event("RESEARCH_CYCLE", result, agent_id="research_orchestrator")
    print(f"[RESEARCH ENGINE] Cycle complete — processed={tasks_processed}, opps={opportunities_found}")
    return result


def queue_research(
    research_type: str,
    query: str,
    requested_by: str = "system",
    priority: str = "NORMAL",
) -> str:
    """Queue a research task for the engine to process.

    Args:
        research_type: market | competitive | prospect | technical | validation
        query: The research question or target
        requested_by: Which agent requested this
        priority: CRITICAL | HIGH | NORMAL | LOW

    Returns:
        research_id string
    """
    research_id = f"res_{uuid.uuid4().hex[:10]}"
    ttl_map = {"CRITICAL": 1, "HIGH": 2, "NORMAL": 7, "LOW": 14}
    expires_at = (datetime.utcnow() + timedelta(days=ttl_map.get(priority, 7))).isoformat()

    insert("research_findings", {
        "research_id": research_id,
        "research_type": research_type,
        "query": query,
        "requested_by": requested_by,
        "status": "pending",
        "expires_at": expires_at,
    })

    print(f"[RESEARCH ENGINE] Queued [{research_type}] {query[:60]} (id={research_id})")
    return research_id


def get_finding(research_id: str) -> dict:
    """Retrieve a completed research finding by id."""
    row = fetch_one(
        "SELECT * FROM research_findings WHERE research_id=?",
        (research_id,),
    )
    if not row:
        return {}
    from memory.database import parse_payload
    row["findings"] = parse_payload(row.get("findings", "{}"))
    return dict(row)


# ── Private helpers ──────────────────────────────────────────────────────────

def _dispatch(research_type: str, query: str, task: dict) -> dict:
    """Route research task to the correct sub-agent.

    Args:
        research_type: Type of research
        query: Research question
        task: Full task row from DB

    Returns:
        Raw findings dict from sub-agent
    """
    from memory.database import parse_payload
    context = parse_payload(task.get("findings", "{}"))

    if research_type == "market":
        from research.agents.market_research import run as market_run
        return market_run(query, context)
    elif research_type == "competitive":
        from research.agents.competitive_intel import run as comp_run
        return comp_run(query, context)
    elif research_type == "prospect":
        from research.agents.prospect_researcher import run as prospect_run
        return prospect_run(query, context)
    elif research_type == "technical":
        from research.agents.technical_research import run as tech_run
        return tech_run(query, context)
    elif research_type == "validation":
        from research.agents.market_research import run as market_run
        return market_run(query, context)
    else:
        raise ValueError(f"Unknown research type: {research_type}")


def _synthesise(research_id: str, query: str, findings: dict, research_type: str) -> dict:
    """Run synthesis on raw findings to extract structured insights.

    Args:
        research_id: The research task id
        query: Original research question
        findings: Raw findings from sub-agent
        research_type: Type of research

    Returns:
        Synthesised output with confidence, opportunities, recommendations
    """
    from research.agents.synthesis import run as synth_run
    return synth_run(research_id, query, findings, research_type)


def _store_findings(research_id: str, synthesised: dict):
    """Write completed findings back to the database."""
    update("research_findings", None, {})  # We use research_id, not id
    with __import__("memory.database", fromlist=["get_conn"]).get_conn() as conn:
        conn.execute(
            "UPDATE research_findings SET status='complete', findings=?, "
            "confidence=?, sources_count=?, opportunities_found=?, completed_at=? "
            "WHERE research_id=?",
            (
                json_payload(synthesised),
                synthesised.get("confidence", 0.0),
                synthesised.get("sources_count", 0),
                len(synthesised.get("opportunities", [])),
                datetime.utcnow().isoformat(),
                research_id,
            ),
        )


def _save_opportunity(opp: dict, research_id: str):
    """Persist a discovered opportunity to the opportunities table."""
    opp_id = f"opp_{uuid.uuid4().hex[:10]}"
    insert("opportunities", {
        "opportunity_id": opp_id,
        "opp_type": opp.get("type", "market"),
        "title": opp.get("title", "Untitled opportunity"),
        "description": opp.get("description", ""),
        "estimated_monthly_revenue_aud": opp.get("estimated_monthly_revenue_aud", 0),
        "effort_score": opp.get("effort_score", 5.0),
        "speed_score": opp.get("speed_score", 5.0),
        "risk_score": opp.get("risk_score", 5.0),
        "overall_score": opp.get("overall_score", 0.0),
        "source_agent": "research_engine",
        "research_id": research_id,
        "evidence": json_payload(opp.get("evidence", {})),
    })
    print(f"[RESEARCH ENGINE] Opportunity saved: {opp.get('title', '')[:50]}")


def _mark_in_progress(research_id: str):
    """Update status to in_progress."""
    with __import__("memory.database", fromlist=["get_conn"]).get_conn() as conn:
        conn.execute(
            "UPDATE research_findings SET status='in_progress' WHERE research_id=?",
            (research_id,),
        )


def _mark_failed(research_id: str, reason: str):
    """Update status to failed with reason."""
    with __import__("memory.database", fromlist=["get_conn"]).get_conn() as conn:
        conn.execute(
            "UPDATE research_findings SET status='failed', findings=? WHERE research_id=?",
            (json_payload({"error": reason}), research_id),
        )


def _queue_routine_research():
    """Queue standard daily research tasks if none pending."""
    pending_count = fetch_one(
        "SELECT COUNT(*) as count FROM research_findings WHERE status='pending'",
    ).get("count", 0)

    if pending_count == 0:
        queue_research(
            "market",
            "Australian solar SME market trends and demand signals this week",
            requested_by="system",
            priority="NORMAL",
        )
        queue_research(
            "competitive",
            "CRM automation providers targeting Australian solar companies — pricing and gaps",
            requested_by="system",
            priority="NORMAL",
        )
        print("[RESEARCH ENGINE] Queued 2 routine daily research tasks")
