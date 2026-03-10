"""Kelly engine — fractional Kelly Criterion budget allocation.

f* = (bp - q) / b, using 25% fractional Kelly.
"""

import logging
import config

logger = logging.getLogger(__name__)

FRACTIONAL_KELLY = 0.25


def calculate_budget(confidence_score: float, weekly_budget: float = None) -> dict:
    """Calculate recommended budget allocation using fractional Kelly.

    Args:
        confidence_score: Float 0–10 from agent confidence scoring
        weekly_budget: Override weekly budget in AUD (defaults to config)

    Returns:
        Dict with recommended_aud, kelly_fraction, confidence_score
    """
    if weekly_budget is None:
        weekly_budget = getattr(config, "WEEKLY_BUDGET_AUD", 500)

    # Normalise confidence to 0–1
    p = min(max(confidence_score / 10.0, 0.01), 0.99)
    q = 1.0 - p
    b = 1.0  # 1:1 payoff assumption

    kelly_f = (b * p - q) / b
    kelly_f = max(kelly_f, 0.0)
    fractional = kelly_f * FRACTIONAL_KELLY

    recommended = round(weekly_budget * fractional, 2)

    return {
        "confidence_score": confidence_score,
        "kelly_fraction": round(fractional, 4),
        "recommended_aud": recommended,
        "weekly_budget_aud": weekly_budget,
    }
