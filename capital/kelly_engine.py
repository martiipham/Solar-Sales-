"""Kelly Criterion capital allocation engine for Solar Swarm.

Implements 25% Fractional Kelly to size experiment budgets
with a hard cap of 25% of weekly budget per experiment.

Kelly formula: f* = (bp - q) / b
  b = odds (expected ROI ratio)
  p = probability of win
  q = probability of loss (1 - p)
Fractional Kelly: f_actual = f* × 0.25
"""

import logging
import config

logger = logging.getLogger(__name__)


def kelly_fraction(win_probability: float, win_multiplier: float) -> float:
    """Calculate the raw Kelly fraction for a bet.

    Args:
        win_probability: Probability of winning (0.0–1.0)
        win_multiplier: Ratio of profit to stake (e.g. 2.0 = double your money)

    Returns:
        Kelly fraction (0.0–1.0), clamped to [0, 1]
    """
    if win_multiplier <= 0 or win_probability <= 0:
        return 0.0
    p = win_probability
    q = 1.0 - p
    b = win_multiplier
    f_star = (b * p - q) / b
    return max(0.0, min(1.0, f_star))


def fractional_kelly(win_probability: float, win_multiplier: float) -> float:
    """Apply 25% fractional Kelly to reduce variance.

    Args:
        win_probability: Probability of winning (0.0–1.0)
        win_multiplier: Expected ROI multiplier

    Returns:
        Fractional Kelly fraction, clamped to KELLY_MAX_SINGLE
    """
    f_star = kelly_fraction(win_probability, win_multiplier)
    f_fractional = f_star * config.KELLY_FRACTION
    f_capped = min(f_fractional, config.KELLY_MAX_SINGLE)
    logger.debug(f"[KELLY] f*={f_star:.3f} fractional={f_fractional:.3f} capped={f_capped:.3f}")
    return f_capped


def confidence_to_probability(confidence_score: float) -> float:
    """Convert a 0–10 confidence score to a win probability estimate.

    Uses a sigmoid-style mapping:
      score 5  → ~35% win probability
      score 7  → ~55% win probability
      score 9  → ~75% win probability
    """
    normalised = confidence_score / 10.0
    probability = 0.2 + (normalised * 0.65)
    return min(0.90, max(0.10, probability))


def calculate_budget(
    confidence_score: float,
    weekly_budget: float = None,
    win_multiplier: float = 3.0,
) -> dict:
    """Calculate the recommended budget for an experiment.

    Args:
        confidence_score: 0–10 confidence rating from scoring
        weekly_budget: Total weekly budget (defaults to config)
        win_multiplier: Expected payoff ratio (default 3x)

    Returns:
        Dict with kelly_fraction, budget_aud, pct_of_weekly
    """
    if weekly_budget is None:
        weekly_budget = config.WEEKLY_BUDGET_AUD

    p = confidence_to_probability(confidence_score)
    f = fractional_kelly(p, win_multiplier)
    budget = f * weekly_budget
    hard_cap = weekly_budget * config.KELLY_MAX_SINGLE

    budget = min(budget, hard_cap)
    budget = round(budget, 2)

    result = {
        "kelly_fraction": round(f, 4),
        "win_probability": round(p, 3),
        "budget_aud": budget,
        "pct_of_weekly": round(budget / weekly_budget * 100, 1),
        "hard_cap_applied": budget == hard_cap,
    }
    logger.info(f"[KELLY] score={confidence_score} → ${budget} AUD ({result['pct_of_weekly']}%)")
    return result


def score_experiment(
    market_signal: float,
    competitive_gap: float,
    execution_speed: float,
    revenue_path: float,
) -> dict:
    """Calculate the 4-component confidence score for an experiment.

    Each component is rated 0–10 and averaged.

    Args:
        market_signal: Evidence of demand (0-10)
        competitive_gap: Underserved opportunity (0-10)
        execution_speed: How fast testable, 72hr threshold (0-10)
        revenue_path: Clear line to cash (0-10)

    Returns:
        Dict with individual scores and final confidence_score
    """
    scores = {
        "market_signal": market_signal,
        "competitive_gap": competitive_gap,
        "execution_speed": execution_speed,
        "revenue_path": revenue_path,
    }
    confidence = sum(scores.values()) / len(scores)

    if confidence > config.CONFIDENCE_AUTO_PROCEED:
        routing = "auto_proceed"
    elif confidence >= config.CONFIDENCE_AUTO_KILL:
        routing = "human_gate"
    else:
        routing = "auto_kill"

    return {
        **scores,
        "confidence_score": round(confidence, 2),
        "routing": routing,
    }
