"""Mutation Engine — Evolves underperforming experiments.

Runs Monday at 22:30 UTC (scheduled in main.py).

What it does:
  1. Finds killed/rejected experiments from the past 30 days
  2. For each failure, uses GPT-4o to generate a mutated/improved variant
  3. Inserts mutations as new 'pending' experiments
  4. Hard-kills experiments that have failed 3+ times without mutation success
  5. Returns summary dict
"""

import json
import logging
from datetime import datetime, timedelta

import config
from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)

# Only mutate experiments that failed in the last N days
LOOKBACK_DAYS = 30
# Max mutations to generate per run
MAX_MUTATIONS = 5
# If an idea has failed N times, kill it permanently
MAX_FAILURES_BEFORE_KILL = 3

MUTATION_PROMPT = """You are a strategy mutation engine for a solar sales AI swarm.

You will be given a failed experiment idea and its failure reason.
Generate ONE mutated variant that addresses the failure mode and is more likely to succeed.

Return a JSON object with:
- idea_text: The improved experiment (1-2 sentences)
- bucket: exploit | explore | moonshot
- confidence_score: 1-10
- mutation_rationale: What you changed and why (1 sentence)

No other text."""


def _get_failed_experiments(days: int = LOOKBACK_DAYS) -> list:
    """Fetch recently failed/killed experiments.

    Args:
        days: Lookback window in days

    Returns:
        List of experiment dicts
    """
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        return fetch_all(
            "SELECT * FROM experiments "
            "WHERE status IN ('killed','rejected') "
            "AND completed_at >= ? "
            "ORDER BY completed_at DESC LIMIT 20",
            (cutoff,),
        )
    except Exception as e:
        logger.error(f"[MUTATION] Failed to fetch experiments: {e}")
        return []


def _count_prior_failures(idea_text: str) -> int:
    """Count how many times a similar idea has been killed.

    Uses a simple keyword match on the first 40 chars of idea_text.

    Args:
        idea_text: The original idea text

    Returns:
        Count of similar failed experiments
    """
    try:
        snippet = idea_text[:40]
        row = fetch_one(
            "SELECT COUNT(*) as n FROM experiments "
            "WHERE idea_text LIKE ? AND status IN ('killed','rejected')",
            (f"%{snippet}%",),
        )
        return row.get("n", 0) if row else 0
    except Exception:
        return 0


def _mutate_with_gpt(idea_text: str, failure_reason: str) -> dict | None:
    """Ask GPT-4o to generate a mutated variant.

    Args:
        idea_text:      Original failed idea
        failure_reason: Why it was killed/rejected

    Returns:
        Mutation dict or None on failure
    """
    if not config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)

        user_msg = (
            f"Failed experiment: {idea_text}\n"
            f"Failure reason: {failure_reason or 'Not specified'}\n\n"
            "Generate one improved mutation."
        )
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": MUTATION_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.8,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.error(f"[MUTATION] GPT call failed: {e}")
        return None


def run() -> dict:
    """Run one mutation cycle.

    Returns:
        Dict with analysed, mutations_created, killed
    """
    print(f"[MUTATION ENGINE] Starting at {datetime.utcnow().isoformat()}")

    failed     = _get_failed_experiments()
    analysed   = len(failed)
    mutations_created = 0
    hard_killed = 0

    for exp in failed[:MAX_MUTATIONS]:
        idea_text      = exp.get("idea_text", "")
        failure_reason = exp.get("failure_mode", "")

        if not idea_text:
            continue

        prior_failures = _count_prior_failures(idea_text)

        # Hard-kill ideas that keep failing
        if prior_failures >= MAX_FAILURES_BEFORE_KILL:
            print(f"[MUTATION ENGINE] Idea hard-killed after {prior_failures} failures: "
                  f"{idea_text[:60]}")
            hard_killed += 1
            continue

        mutation = _mutate_with_gpt(idea_text, failure_reason)
        if not mutation:
            continue

        mutated_text = (mutation.get("idea_text") or "").strip()
        if not mutated_text:
            continue

        bucket = mutation.get("bucket", "explore")
        if bucket not in ("exploit", "explore", "moonshot"):
            bucket = "explore"

        confidence = float(mutation.get("confidence_score") or 5)
        confidence = max(1.0, min(10.0, confidence))

        try:
            exp_id = insert("experiments", {
                "status":           "pending",
                "idea_text":        mutated_text,
                "bucket":           bucket,
                "confidence_score": confidence,
                "failure_mode":     f"Mutation of exp#{exp.get('id')}: "
                                    f"{mutation.get('mutation_rationale','')[:200]}",
            })
            print(f"[MUTATION ENGINE] Mutation #{exp_id} created: {mutated_text[:70]}")
            mutations_created += 1
        except Exception as e:
            logger.error(f"[MUTATION ENGINE] Insert failed: {e}")

    print(
        f"[MUTATION ENGINE] Done — analysed={analysed} "
        f"mutations={mutations_created} killed={hard_killed}"
    )
    return {
        "analysed":          analysed,
        "mutations_created": mutations_created,
        "killed":            hard_killed,
    }
