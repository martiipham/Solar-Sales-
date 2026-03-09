"""A/B Tester — Runs and evaluates split tests for Solar Swarm strategies.

Manages A/B test lifecycle: create → assign variants → collect results →
determine winner → emit pheromone to reinforce winning strategies.
Integrates with GoHighLevel to track variant performance.
"""

import json
import logging
import uuid
from datetime import datetime
from memory.database import get_conn, fetch_all, fetch_one, json_payload, parse_payload
from memory.hot_memory import post_pheromone

logger = logging.getLogger(__name__)

MIN_SAMPLE_SIZE = 30   # minimum leads per variant before evaluating
SIGNIFICANCE_THRESHOLD = 0.05  # p-value for statistical significance (simplified)


def create_test(
    name: str,
    hypothesis: str,
    variant_a: dict,
    variant_b: dict,
    metric: str = "conversion_rate",
    experiment_id: str = None,
) -> str:
    """Register a new A/B test.

    Args:
        name: Human-readable test name
        hypothesis: What we expect to happen
        variant_a: Control variant config
        variant_b: Treatment variant config
        metric: Primary metric to optimise (conversion_rate|reply_rate|booking_rate)
        experiment_id: Optional parent experiment

    Returns:
        test_id
    """
    test_id = f"abt_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ab_tests
               (test_id, name, hypothesis, variant_a, variant_b,
                metric, experiment_id, status, created_at)
               VALUES (?,?,?,?,?,?,?,'running',?)""",
            (test_id, name, hypothesis,
             json_payload(variant_a), json_payload(variant_b),
             metric, experiment_id, datetime.utcnow().isoformat()),
        )
    print(f"[A/B TESTER] Created test: {name} ({test_id})")
    return test_id


def record_event(test_id: str, variant: str, event_type: str, value: float = 1.0):
    """Record an event (impression, click, conversion) for a test variant.

    Args:
        test_id: The A/B test
        variant: 'a' or 'b'
        event_type: impression|reply|booking|conversion
        value: Numeric value (default 1.0)
    """
    try:
        with get_conn() as conn:
            conn.execute(
                f"""UPDATE ab_tests
                    SET {variant}_{event_type}s = COALESCE({variant}_{event_type}s, 0) + ?
                    WHERE test_id=?""",
                (value, test_id),
            )
    except Exception as e:
        logger.error(f"[A/B TESTER] Record event error: {e}")


def evaluate_tests() -> dict:
    """Check all running tests and declare winners where possible.

    Returns:
        {evaluated, winners_found, tests_extended}
    """
    print("[A/B TESTER] Evaluating running tests")
    running = fetch_all("SELECT * FROM ab_tests WHERE status='running'")

    evaluated = winners_found = extended = 0

    for test in running:
        result = _evaluate_single(dict(test))
        evaluated += 1

        if result["status"] == "winner":
            _declare_winner(test["test_id"], result["winner"], result)
            winners_found += 1
        elif result["status"] == "needs_more_data":
            extended += 1

    print(f"[A/B TESTER] evaluated={evaluated} winners={winners_found} extended={extended}")
    return {"evaluated": evaluated, "winners_found": winners_found, "tests_extended": extended}


def _evaluate_single(test: dict) -> dict:
    """Determine if a test has a winner or needs more data."""
    metric = test.get("metric", "conversion_rate")
    prefix = metric.split("_")[0]  # "conversion" → "conversion"

    a_impressions = test.get("a_impressions", 0) or 0
    b_impressions = test.get("b_impressions", 0) or 0
    a_conversions = test.get(f"a_{prefix}s", 0) or 0
    b_conversions = test.get(f"b_{prefix}s", 0) or 0

    if a_impressions < MIN_SAMPLE_SIZE or b_impressions < MIN_SAMPLE_SIZE:
        return {"status": "needs_more_data", "winner": None,
                "a_rate": 0, "b_rate": 0, "lift": 0}

    a_rate = a_conversions / a_impressions if a_impressions else 0
    b_rate = b_conversions / b_impressions if b_impressions else 0
    lift = ((b_rate - a_rate) / a_rate * 100) if a_rate else 0

    if abs(lift) < 10:  # less than 10% lift = no meaningful difference
        winner = "no_winner"
    elif b_rate > a_rate:
        winner = "b"
    else:
        winner = "a"

    return {"status": "winner", "winner": winner, "a_rate": round(a_rate, 4),
            "b_rate": round(b_rate, 4), "lift": round(lift, 2)}


def _declare_winner(test_id: str, winner: str, stats: dict):
    """Mark test complete and emit pheromone for winning variant."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE ab_tests
               SET status='complete', winner=?, winner_stats=?, completed_at=?
               WHERE test_id=?""",
            (winner, json_payload(stats), datetime.utcnow().isoformat(), test_id),
        )

    if winner not in ("a", "b"):
        return  # no winner to reinforce

    test = fetch_one("SELECT name FROM ab_tests WHERE test_id=?", (test_id,))
    test_name = test["name"] if test else test_id
    signal_name = f"ab_winner_{test_name}_{winner}".replace(" ", "_")[:50]
    post_pheromone(signal_type="ab_winner", topic=signal_name, strength=0.8)
    logger.info(f"[A/B TESTER] Winner declared: {test_name} → variant {winner} (lift {stats['lift']}%)")


def get_summary() -> dict:
    """Return A/B test status summary for dashboard."""
    rows = fetch_all("SELECT status, COUNT(*) as count FROM ab_tests GROUP BY status")
    return {r["status"]: r["count"] for r in rows}
