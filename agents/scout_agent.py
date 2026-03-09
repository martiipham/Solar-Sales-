"""Scout Agent — Autonomous prospect hunter for Solar Swarm.

The scout proactively discovers new Australian solar companies that are
likely to need CRM automation. It fuses signals from the knowledge graph,
data collection pipeline, and social monitoring to surface ranked prospects
and post them to the research queue for deep profiling.

Runs daily at 08:00 UTC via APScheduler.
"""

import json
import logging
from datetime import datetime
from memory.database import fetch_all, get_conn, json_payload
from storage import opportunity_store, knowledge_graph
from bus import message_bus
import config

logger = logging.getLogger(__name__)

# States that make a solar company a hot prospect
HOT_SIGNALS = ["hiring", "scaling", "crm", "manual process", "follow up", "new office"]
MIN_PROSPECT_SCORE = 5.0


def run() -> dict:
    """Execute one scout cycle — discover, score, and queue prospects.

    Returns:
        {prospects_found, queued_for_research, opportunities_saved}
    """
    print("[SCOUT] Starting prospect hunt")

    candidates = _gather_candidates()
    print(f"[SCOUT] {len(candidates)} raw candidates")

    scored = [_score_candidate(c) for c in candidates]
    hot = [c for c in scored if c["scout_score"] >= MIN_PROSPECT_SCORE]
    hot.sort(key=lambda x: x["scout_score"], reverse=True)

    queued = _queue_for_research(hot[:10])  # top 10 per cycle
    saved = _save_opportunities(hot[:5])    # top 5 as opportunities

    _emit_pheromone(len(hot))

    print(f"[SCOUT] Done — found={len(hot)} queued={queued} opps={saved}")
    return {"prospects_found": len(hot), "queued_for_research": queued, "opportunities_saved": saved}


def _gather_candidates() -> list:
    """Pull candidate companies from all data sources."""
    candidates = []

    # From web scraper (installer registry)
    installer_rows = fetch_all(
        """SELECT data FROM collected_data
           WHERE source_type='web_scrape' AND data_type='solar_installer'
           AND collected_at >= datetime('now', '-2 days')
           LIMIT 50""",
    )
    for row in installer_rows:
        try:
            data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            candidates.append({"company_name": data.get("company_name", ""), "source": "installer_registry",
                                "state": data.get("state", ""), "signals": []})
        except Exception:
            pass

    # From social signals (high/medium strength)
    social_rows = fetch_all(
        """SELECT data FROM collected_data
           WHERE source_type='social'
           AND collected_at >= datetime('now', '-1 day')
           LIMIT 30""",
    )
    for row in social_rows:
        try:
            data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            if data.get("signal_strength") in ("high", "medium") and data.get("company"):
                keywords = data.get("keyword_hits", [])
                candidates.append({"company_name": data.get("company", ""),
                                    "source": "social_signal",
                                    "signals": keywords,
                                    "social_text": data.get("text", "")[:200]})
        except Exception:
            pass

    # From knowledge graph — companies not yet fully researched
    kg_companies = knowledge_graph.search_entities("company", limit=20)
    for ent in kg_companies:
        props = ent.get("properties", {})
        if not props.get("research_complete"):
            candidates.append({"company_name": ent["name"], "source": "knowledge_graph",
                                "signals": props.get("signals", []), "entity_id": ent["entity_id"]})

    return candidates


def _score_candidate(candidate: dict) -> dict:
    """Score a candidate on prospect quality (0–10)."""
    score = 0.0
    signals = candidate.get("signals", [])

    # Base score by source
    score += {"installer_registry": 3.0, "social_signal": 5.0, "knowledge_graph": 4.0}.get(
        candidate.get("source", ""), 2.0
    )

    # Bonus for hot signals
    hot_hits = [s for s in signals if any(h in s.lower() for h in HOT_SIGNALS)]
    score += len(hot_hits) * 1.5

    # Bonus for social signal strength
    if candidate.get("source") == "social_signal" and "hiring" in signals:
        score += 2.0

    # Check if already in GHL pipeline (deduct to avoid double-handling)
    if _already_in_pipeline(candidate["company_name"]):
        score -= 3.0

    return {**candidate, "scout_score": min(round(score, 2), 10.0)}


def _already_in_pipeline(company_name: str) -> bool:
    """Check if the company is already tracked as a lead or contact."""
    if not company_name:
        return False
    rows = fetch_all(
        "SELECT id FROM leads WHERE LOWER(company) LIKE ? LIMIT 1",
        (f"%{company_name.lower()[:20]}%",),
    )
    return bool(rows)


def _queue_for_research(prospects: list) -> int:
    """Post top prospects to the research queue for deep profiling."""
    queued = 0
    for p in prospects:
        company = p.get("company_name", "")
        if not company:
            continue
        message_bus.post(
            from_agent="scout_agent",
            to_queue="research_queue",
            msg_type="TASK",
            payload={"research_type": "prospect", "query": company, "scout_score": p["scout_score"]},
            priority="HIGH" if p["scout_score"] >= 7 else "NORMAL",
        )
        queued += 1
    return queued


def _save_opportunities(prospects: list) -> int:
    """Persist top prospects as opportunities in the opportunity store."""
    saved = 0
    for p in prospects:
        company = p.get("company_name", "")
        if not company:
            continue
        opportunity_store.save(
            title=f"Prospect: {company}",
            description=f"Solar company identified via {p['source']}. "
                        f"Scout score: {p['scout_score']}. Signals: {p.get('signals', [])}",
            opp_type="prospect",
            effort="medium",
            impact="high" if p["scout_score"] >= 7 else "medium",
            confidence=round(p["scout_score"] / 10, 2),
            source="scout_agent",
            metadata=p,
        )
        saved += 1
    return saved


def _emit_pheromone(hot_count: int):
    """Emit pheromone signal to reinforce scouting if results are good."""
    if hot_count >= 5:
        try:
            from memory.hot_memory import post_pheromone
            post_pheromone("prospect_found", topic="scout_found_prospects", strength=min(hot_count / 10, 1.0))
        except Exception as e:
            logger.error(f"[SCOUT] Pheromone error: {e}")
