"""Mutation Engine — Evolves underperforming strategies for Solar Swarm.

Analyses experiments and A/B tests, identifies losers, generates
mutated variants using GPT-4o, and submits them back into the experiment
queue with new Kelly budget allocations.

Runs weekly during retrospective (Monday 22:00 UTC).
"""

import json
import logging
from datetime import datetime
from memory.database import fetch_all, json_payload
from memory.hot_memory import get_active_experiments, post_pheromone
from memory.cold_ledger import log_event
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an experiment mutation specialist for an AI automation agency.
You receive underperforming strategy experiments and generate improved variants.

Given a failing experiment, produce 2 mutated variants that:
1. Address the identified failure reason
2. Preserve what was working
3. Test a single changed variable (scientific mutation)
4. Are executable by an AI agent without human help where possible

Return ONLY valid JSON:
{
  "mutations": [
    {
      "name": "<experiment name>",
      "hypothesis": "<what we're testing>",
      "changes_from_parent": ["<specific change>"],
      "expected_improvement": "<why this will work better>",
      "confidence": <0.0-1.0>,
      "estimated_revenue": <AUD integer>,
      "risk_level": "low|medium|high"
    }
  ],
  "kill_recommendation": <true/false>,
  "kill_reason": "<why to kill if applicable>"
}"""


def run() -> dict:
    """Identify underperforming experiments and generate mutations.

    Returns:
        {analysed, mutations_created, killed}
    """
    print("[MUTATION ENGINE] Analysing experiment performance")

    losers = _find_underperformers()
    print(f"[MUTATION ENGINE] Found {len(losers)} underperforming experiments")

    mutations_created = killed = 0

    for exp in losers:
        result = _mutate(exp)
        if result.get("kill_recommendation"):
            _kill_experiment(exp)
            killed += 1
        else:
            _submit_mutations(result.get("mutations", []), exp)
            mutations_created += len(result.get("mutations", []))

    _record_retrospective(len(losers), mutations_created, killed)

    print(f"[MUTATION ENGINE] Done — analysed={len(losers)} mutated={mutations_created} killed={killed}")
    return {"analysed": len(losers), "mutations_created": mutations_created, "killed": killed}


def _find_underperformers() -> list:
    """Fetch experiments with score < 5 or 3+ consecutive failures."""
    rows = fetch_all(
        """SELECT * FROM experiments
           WHERE status='active'
           AND (score < 5.0 OR consecutive_failures >= 3)
           ORDER BY score ASC LIMIT 5"""
    )
    return [dict(r) for r in rows]


def _mutate(experiment: dict) -> dict:
    """Use GPT-4o to generate mutated variants of a failing experiment."""
    if not config.is_configured():
        return _mock_mutation(experiment)

    prompt = (
        f"Experiment: {experiment.get('name', 'unknown')}\n"
        f"Hypothesis: {experiment.get('hypothesis', '')}\n"
        f"Score: {experiment.get('score', 0)}\n"
        f"Failures: {experiment.get('consecutive_failures', 0)}\n"
        f"Notes: {experiment.get('notes', '')}\n\n"
        "Generate 2 mutations that fix the failure mode."
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        logger.error(f"[MUTATION ENGINE] GPT error: {e}")
        return _mock_mutation(experiment)


def _submit_mutations(mutations: list, parent: dict):
    """Insert mutated experiments into the experiments queue."""
    from memory.database import get_conn
    for mut in mutations:
        exp_id = f"exp_{__import__('uuid').uuid4().hex[:10]}"
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO experiments
                       (experiment_id, name, hypothesis, parent_id, status,
                        confidence, estimated_revenue, risk_level, created_at)
                       VALUES (?,?,?,?,'queued',?,?,?,?)""",
                    (exp_id, mut["name"], mut["hypothesis"],
                     parent.get("experiment_id"),
                     mut.get("confidence", 0.5),
                     mut.get("estimated_revenue", 0),
                     mut.get("risk_level", "medium"),
                     datetime.utcnow().isoformat()),
                )
            logger.info(f"[MUTATION ENGINE] Submitted mutation: {mut['name']}")
        except Exception as e:
            logger.error(f"[MUTATION ENGINE] Submit error: {e}")


def _kill_experiment(experiment: dict):
    """Mark a fatally underperforming experiment as killed."""
    from memory.database import get_conn
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE experiments SET status='killed', updated_at=? WHERE experiment_id=?",
                (datetime.utcnow().isoformat(), experiment.get("experiment_id")),
            )
        log_event("EXPERIMENT_KILLED", experiment, agent_id="mutation_engine")
        post_pheromone("strategy_killed", topic=experiment.get("name", "unknown"), strength=0.1)
    except Exception as e:
        logger.error(f"[MUTATION ENGINE] Kill error: {e}")


def _record_retrospective(analysed: int, mutated: int, killed: int):
    """Log the mutation cycle outcome to the cold ledger."""
    log_event("MUTATION_CYCLE", {
        "analysed": analysed, "mutated": mutated, "killed": killed,
        "timestamp": datetime.utcnow().isoformat(),
    }, agent_id="mutation_engine")


def _mock_mutation(experiment: dict) -> dict:
    """Return mock mutation when OpenAI unavailable."""
    return {
        "mutations": [
            {
                "name": f"{experiment.get('name', 'Experiment')} v2 — Faster Follow-up",
                "hypothesis": "Calling within 5 minutes instead of 30 will increase conversion",
                "changes_from_parent": ["Reduce SMS-to-call delay from 30min to 5min"],
                "expected_improvement": "Industry data shows 5min callback = 9x higher connect rate",
                "confidence": 0.72,
                "estimated_revenue": 3000,
                "risk_level": "low",
            }
        ],
        "kill_recommendation": False,
        "kill_reason": "",
    }
