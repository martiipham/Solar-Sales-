"""Master Agent — Tier 1: The General.

Runs every 6 hours. Responsible for:
  - Generating new experiment ideas using GPT-4o
  - Scoring each idea using 4-component confidence scoring
  - Running red team analysis
  - Routing: auto-proceed / human gate / auto-kill
  - Allocating budget via Kelly Criterion
  - Posting Slack alerts for human gate items

If no OpenAI key is configured, generates mock experiments.
"""

import json
import logging
from datetime import datetime
from memory.database import insert
from memory.hot_memory import get_active_experiments, get_swarm_summary
from memory.warm_memory import get_all_learnings, get_winning_patterns
from memory.cold_ledger import log_experiment_created, log_experiment_killed
from capital.kelly_engine import score_experiment, calculate_budget
from capital.circuit_breaker import is_halted, check_and_trigger
from capital.portfolio_manager import assign_bucket, can_allocate
from agents.red_team_agent import analyse as red_team_analyse, adjust_confidence
from notifications.slack_notifier import alert_human_gate
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a strategic business intelligence engine for an Australian AI automation consultancy.
Your job is to generate high-quality experiment ideas targeting Australian solar SME companies.

Current context:
- Target vertical: Australian solar companies with 5-15 salespeople
- Platform: GoHighLevel CRM
- Revenue model: $1,500-2,000 AUD/month retainer
- Goal: Prove ROI within 72 hours to close new clients

Generate exactly 3 experiment ideas. Each idea should be a concrete, testable action
that could generate leads, prove value, or close a client within 72 hours.

Return ONLY valid JSON:
{
  "experiments": [
    {
      "idea_text": "<specific experiment description>",
      "vertical": "solar_australia",
      "market_signal": <0-10>,
      "competitive_gap": <0-10>,
      "execution_speed": <0-10>,
      "revenue_path": <0-10>,
      "rationale": "<one sentence why>"
    }
  ]
}"""


def run() -> list:
    """Run the General's strategic planning cycle.

    Returns:
        List of experiment dicts that were created/routed
    """
    print("\n[GENERAL] === Strategic Planning Cycle ===")
    print(f"[GENERAL] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    if is_halted():
        print("[GENERAL] Circuit breaker RED — planning cycle suspended")
        return []

    summary = get_swarm_summary()
    print(f"[GENERAL] Active experiments: {summary['active_experiments']} | Budget remaining: ${summary['budget_remaining_aud']}")

    ideas = _generate_ideas()
    results = []

    for idea_data in ideas:
        result = _process_idea(idea_data)
        if result:
            results.append(result)

    check_and_trigger()
    print(f"[GENERAL] Cycle complete. Processed {len(results)} ideas.")
    return results


def _generate_ideas() -> list:
    """Use GPT-4o to generate experiment ideas."""
    if not config.is_configured():
        logger.warning("[GENERAL] No OpenAI key — returning mock ideas")
        return _mock_ideas()

    learnings = get_all_learnings()
    patterns = get_winning_patterns()
    context = f"Past learnings: {len(learnings)} entries. Winning patterns: {len(patterns)} experiments."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate 3 experiment ideas. Context: {context}"},
            ],
            temperature=0.8,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        return data.get("experiments", [])
    except Exception as e:
        logger.error(f"[GENERAL] OpenAI error: {e}")
        return _mock_ideas()


def _process_idea(idea_data: dict) -> dict:
    """Score, red-team, route, and record a single experiment idea.

    Args:
        idea_data: Dict with idea_text, scores, vertical

    Returns:
        Dict with experiment_id, routing, budget or None
    """
    idea_text = idea_data.get("idea_text", "")
    print(f"\n[GENERAL] Evaluating: {idea_text[:70]}...")

    scored = score_experiment(
        market_signal=idea_data.get("market_signal", 5),
        competitive_gap=idea_data.get("competitive_gap", 5),
        execution_speed=idea_data.get("execution_speed", 5),
        revenue_path=idea_data.get("revenue_path", 5),
    )
    confidence = scored["confidence_score"]
    print(f"[GENERAL] Confidence: {confidence}/10 → {scored['routing']}")

    if scored["routing"] == "auto_kill":
        print(f"[GENERAL] Auto-killed: confidence {confidence} < {config.CONFIDENCE_AUTO_KILL}")
        exp_id = insert("experiments", {
            "idea_text": idea_text,
            "vertical": idea_data.get("vertical", "solar_australia"),
            "confidence_score": confidence,
            "status": "killed",
            "failure_mode": "Low confidence score — auto-killed by General",
        })
        log_experiment_killed(exp_id, f"Auto-kill: confidence={confidence}", "master_agent")
        return None

    red_result = red_team_analyse(idea_text)
    devil_score = red_result.get("devil_score", 5)
    adjusted_confidence = adjust_confidence(confidence, devil_score)

    if adjusted_confidence < config.CONFIDENCE_AUTO_KILL:
        print(f"[GENERAL] Auto-killed after red team: confidence dropped to {adjusted_confidence}")
        exp_id = insert("experiments", {
            "idea_text": idea_text,
            "vertical": idea_data.get("vertical", "solar_australia"),
            "confidence_score": adjusted_confidence,
            "devil_score": devil_score,
            "status": "killed",
            "failure_mode": f"Red team downgrade: devil_score={devil_score}",
        })
        log_experiment_killed(exp_id, f"Red team kill: devil_score={devil_score}", "master_agent")
        return None

    budget_info = calculate_budget(adjusted_confidence)
    bucket = assign_bucket(adjusted_confidence, devil_score, idea_text)

    if not can_allocate(bucket, budget_info["budget_aud"]):
        print(f"[GENERAL] Insufficient budget in {bucket} bucket — skipping")
        return None

    status = "approved" if adjusted_confidence > config.CONFIDENCE_AUTO_PROCEED else "pending"
    exp_id = insert("experiments", {
        "idea_text": idea_text,
        "vertical": idea_data.get("vertical", "solar_australia"),
        "bucket": bucket,
        "confidence_score": adjusted_confidence,
        "devil_score": devil_score,
        "kelly_fraction": budget_info["kelly_fraction"],
        "budget_allocated": budget_info["budget_aud"] if status == "approved" else 0,
        "status": status,
        "approved_by": "auto" if status == "approved" else None,
        "approved_at": datetime.utcnow().isoformat() if status == "approved" else None,
    })
    log_experiment_created(exp_id, idea_text, adjusted_confidence, "master_agent")

    if status == "pending":
        print(f"[GENERAL] → Human gate required (id=#{exp_id})")
        alert_human_gate(exp_id, idea_text, adjusted_confidence, budget_info["budget_aud"])
    else:
        print(f"[GENERAL] → Auto-approved (id=#{exp_id}, budget=${budget_info['budget_aud']})")

    return {
        "experiment_id": exp_id,
        "idea_text": idea_text,
        "confidence_score": adjusted_confidence,
        "devil_score": devil_score,
        "status": status,
        "bucket": bucket,
        "budget_aud": budget_info["budget_aud"],
    }


def _mock_ideas() -> list:
    """Return mock experiment ideas when OpenAI is unavailable."""
    return [
        {
            "idea_text": "Create a 72-hour Facebook ad campaign targeting solar company owners in Perth with a 'We fill your CRM while you sleep' angle, linking to a VSL landing page",
            "vertical": "solar_australia",
            "market_signal": 7.5,
            "competitive_gap": 6.5,
            "execution_speed": 8.0,
            "revenue_path": 7.0,
            "rationale": "Direct paid acquisition with clear ICP targeting",
        },
        {
            "idea_text": "Cold email sequence to 50 solar SMEs in WA offering a free 'Lead Response Audit' — showing how many leads they lose due to slow follow-up",
            "vertical": "solar_australia",
            "market_signal": 8.0,
            "competitive_gap": 7.0,
            "execution_speed": 7.5,
            "revenue_path": 6.5,
            "rationale": "Pain-based outreach with quantifiable value prop",
        },
        {
            "idea_text": "LinkedIn outreach to solar company directors offering a 30-day pilot: AI voice calls all missed leads within 5 minutes, guaranteed",
            "vertical": "solar_australia",
            "market_signal": 7.0,
            "competitive_gap": 8.0,
            "execution_speed": 6.0,
            "revenue_path": 8.0,
            "rationale": "High-value guarantee reduces buyer risk",
        },
    ]
