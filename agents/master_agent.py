"""Master Agent (The General) — Tier 1 strategic planning cycle.

Runs every 6 hours (scheduled in main.py).

What it does:
  1. Reads the swarm summary (budget, circuit breaker, active experiments)
  2. Reads recent lead pipeline stats
  3. Calls GPT-4o with a strategic prompt to generate new experiment ideas
  4. Inserts ideas as 'pending' experiments for human approval
  5. Returns list of ideas created this cycle
"""

import json
import logging
from datetime import datetime

import config
from memory.database import fetch_all, fetch_one, insert
from memory.hot_memory import get_swarm_summary, get_consecutive_failures

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are The General — the strategic AI director of a solar sales automation swarm.

Your role is to generate high-value experiment ideas that will grow revenue for Australian solar SMEs
using AI automation. Each idea should be specific, actionable, and measurable.

Focus areas:
- Lead qualification improvements (better scoring, faster response)
- Voice AI optimisation (better scripts, objection handling)
- CRM automation (GHL workflows, pipeline velocity)
- Email/SMS follow-up sequences
- Proposal generation improvements
- New lead sources or partnerships

For each idea, specify:
- idea_text: Clear description of the experiment (1-2 sentences)
- bucket: exploit | explore | moonshot
- confidence_score: 1-10 (how confident are you this will work?)
- rationale: Brief reason (1 sentence)

Return a JSON array of 3-5 experiment ideas. No other text."""


def _get_context() -> dict:
    """Collect context data for the strategic prompt.

    Returns:
        Dict with swarm summary, lead stats, and recent experiments
    """
    try:
        summary = get_swarm_summary()
    except Exception:
        summary = {}

    try:
        total = fetch_one("SELECT COUNT(*) as n FROM leads")
        hot   = fetch_one("SELECT COUNT(*) as n FROM leads WHERE qualification_score >= 7")
        conv  = fetch_one("SELECT COUNT(*) as n FROM leads WHERE status = 'converted'")
        lead_stats = {
            "total":     total.get("n", 0) if total else 0,
            "hot":       hot.get("n", 0)   if hot   else 0,
            "converted": conv.get("n", 0)  if conv  else 0,
        }
    except Exception:
        lead_stats = {}

    try:
        recent_exps = fetch_all(
            "SELECT idea_text, status, confidence_score FROM experiments "
            "ORDER BY created_at DESC LIMIT 5"
        )
    except Exception:
        recent_exps = []

    try:
        calls_today = fetch_one(
            "SELECT COUNT(*) as n FROM call_logs WHERE date(started_at) = date('now')"
        )
        call_count = calls_today.get("n", 0) if calls_today else 0
    except Exception:
        call_count = 0

    return {
        "swarm": summary,
        "leads": lead_stats,
        "calls_today": call_count,
        "recent_experiments": recent_exps,
        "weekly_budget_aud": config.WEEKLY_BUDGET_AUD,
        "cb_level": summary.get("circuit_breaker", "green"),
        "consecutive_failures": get_consecutive_failures(),
    }


def _call_gpt(context: dict) -> list:
    """Call GPT-4o to generate experiment ideas.

    Args:
        context: Swarm context dict from _get_context()

    Returns:
        List of idea dicts from GPT-4o
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)

        user_msg = f"""Current swarm state:
- Circuit breaker: {context['cb_level']}
- Weekly budget: ${context['weekly_budget_aud']} AUD
- Active experiments: {context['swarm'].get('active_experiments', 0)}
- Consecutive failures: {context['consecutive_failures']}
- Total leads: {context['leads'].get('total', 0)}
- Hot leads (7+): {context['leads'].get('hot', 0)}
- Converted: {context['leads'].get('converted', 0)}
- Calls today: {context['calls_today']}

Recent experiments (last 5):
{json.dumps(context['recent_experiments'], indent=2)}

Generate 3-5 new experiment ideas to grow solar sales AI performance.
Return a JSON array only."""

        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        # GPT sometimes wraps in a key
        if isinstance(parsed, dict):
            for key in ("ideas", "experiments", "items", "results"):
                if key in parsed:
                    parsed = parsed[key]
                    break
        return parsed if isinstance(parsed, list) else []

    except Exception as e:
        logger.error(f"[MASTER AGENT] GPT call failed: {e}")
        return []


def run() -> list:
    """Run one strategic planning cycle.

    Skips if circuit breaker is red or GPT is not configured.

    Returns:
        List of idea dicts that were inserted as pending experiments
    """
    print(f"[MASTER AGENT] Strategic cycle starting at {datetime.utcnow().isoformat()}")

    if not config.OPENAI_API_KEY:
        print("[MASTER AGENT] OpenAI not configured — skipping")
        return []

    # Don't generate new ideas when the system is in a red halt
    cb = get_swarm_summary().get("circuit_breaker", "green")
    if cb == "red":
        print("[MASTER AGENT] Circuit breaker RED — skipping idea generation")
        return []

    context = _get_context()
    ideas   = _call_gpt(context)

    if not ideas:
        print("[MASTER AGENT] No ideas generated this cycle")
        return []

    created = []
    for idea in ideas:
        if not isinstance(idea, dict):
            continue
        idea_text = (idea.get("idea_text") or idea.get("description") or "").strip()
        if not idea_text:
            continue

        bucket = idea.get("bucket", "explore")
        if bucket not in ("exploit", "explore", "moonshot"):
            bucket = "explore"

        confidence = float(idea.get("confidence_score") or 5)
        confidence = max(1.0, min(10.0, confidence))

        try:
            exp_id = insert("experiments", {
                "status":           "pending",
                "idea_text":        idea_text,
                "bucket":           bucket,
                "confidence_score": confidence,
            })
            created.append({"id": exp_id, "idea_text": idea_text, "bucket": bucket,
                            "confidence_score": confidence})
            print(f"[MASTER AGENT] Idea queued #{exp_id} [{bucket} {confidence:.0f}/10]: "
                  f"{idea_text[:70]}")
        except Exception as e:
            logger.error(f"[MASTER AGENT] Failed to insert idea: {e}")

    print(f"[MASTER AGENT] Cycle complete — {len(created)} ideas queued for approval")
    return created
