"""Red Team Agent — Devil's advocate for experiment ideas.

Takes any experiment idea and:
  - Generates a devil_score (1-10, higher = more flaws)
  - Identifies top 3 failure modes
  - Auto-downgrades master confidence if devil_score > 6
  - Logs challenges to database

If no OpenAI key is configured, returns a mock response.
"""

import json
import logging
from memory.database import insert
from memory.cold_ledger import log_event
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a ruthless business devil's advocate. Your job is to find every reason
why a business experiment will fail. You score ideas on a scale of 1-10 where:
  1-3 = solid idea, hard to find flaws
  4-6 = moderate concerns worth addressing
  7-10 = serious flaws, likely to fail

Be specific, realistic, and brutal. Focus on market, execution, and financial risks.

Return ONLY valid JSON with this exact structure:
{
  "devil_score": <integer 1-10>,
  "failure_modes": [
    {"rank": 1, "mode": "<title>", "explanation": "<2 sentences>"},
    {"rank": 2, "mode": "<title>", "explanation": "<2 sentences>"},
    {"rank": 3, "mode": "<title>", "explanation": "<2 sentences>"}
  ],
  "summary": "<one paragraph overall assessment>"
}"""


def analyse(idea_text: str, experiment_id: int = None) -> dict:
    """Run red team analysis on an experiment idea.

    Args:
        idea_text: The experiment description to critique
        experiment_id: Optional DB id to link the result

    Returns:
        Dict with devil_score, failure_modes, summary, adjusted_confidence
    """
    print(f"[RED TEAM] Analysing: {idea_text[:80]}...")

    if not config.is_configured():
        logger.warning("[RED TEAM] No OpenAI key — returning mock analysis")
        return _mock_response(idea_text, experiment_id)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Red team this experiment idea:\n\n{idea_text}"},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[RED TEAM] JSON parse error: {e}")
        return _mock_response(idea_text, experiment_id)
    except Exception as e:
        logger.error(f"[RED TEAM] OpenAI error: {e}")
        return _mock_response(idea_text, experiment_id)

    devil_score = result.get("devil_score", 5)
    _save_to_db(experiment_id, idea_text, devil_score, result)

    print(f"[RED TEAM] Devil score: {devil_score}/10")
    for fm in result.get("failure_modes", []):
        print(f"  #{fm['rank']}: {fm['mode']}")

    return result


def adjust_confidence(confidence_score: float, devil_score: int) -> float:
    """Downgrade master confidence if devil score is high.

    If devil_score > 6, reduce confidence by (devil_score - 6) × 0.5 points.

    Args:
        confidence_score: Original confidence score (0-10)
        devil_score: Red team score (1-10)

    Returns:
        Adjusted confidence score
    """
    if devil_score > 6:
        penalty = (devil_score - 6) * 0.5
        adjusted = max(0.0, confidence_score - penalty)
        logger.info(f"[RED TEAM] Confidence adjusted: {confidence_score} → {adjusted} (penalty={penalty})")
        return round(adjusted, 2)
    return confidence_score


def _save_to_db(experiment_id: int, idea_text: str, devil_score: int, result: dict):
    """Persist red team analysis to cold ledger."""
    log_event(
        "RED_TEAM_ANALYSIS",
        {"idea_text": idea_text[:200], "devil_score": devil_score, "result": result},
        experiment_id=experiment_id,
        agent_id="red_team_agent",
    )


def _mock_response(idea_text: str, experiment_id: int) -> dict:
    """Return a deterministic mock response when OpenAI is unavailable."""
    result = {
        "devil_score": 5,
        "failure_modes": [
            {"rank": 1, "mode": "Market Timing", "explanation": "The market may not be ready for this solution yet. Early movers often educate the market at their own expense."},
            {"rank": 2, "mode": "Execution Complexity", "explanation": "The operational requirements may exceed current team capacity. Underestimating setup time is a common failure point."},
            {"rank": 3, "mode": "Unit Economics", "explanation": "Customer acquisition costs may erode margins before scale is reached. The path to profitability needs validation."},
        ],
        "summary": "Moderate risk profile. Proceed with cautious explore budget and clear kill criteria at 72 hours.",
        "mock": True,
    }
    _save_to_db(experiment_id, idea_text, result["devil_score"], result)
    return result
