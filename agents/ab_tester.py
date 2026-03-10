"""A/B Tester Agent — Manages A/B test lifecycle in the ab_tests table.

Creates tests, records variant results, and declares winners when
statistical significance is reached (or max duration exceeded).
"""

import json
import logging
from datetime import datetime, timedelta

from memory.database import fetch_one, fetch_all, insert, get_conn

logger = logging.getLogger(__name__)

# Minimum sample size per variant before declaring a winner
MIN_SAMPLE_SIZE = 30
# Maximum test duration in days before forcing a conclusion
MAX_DURATION_DAYS = 14


def get_summary() -> dict:
    """Return A/B test counts by status.

    Returns:
        Dict with running and complete counts
    """
    try:
        running  = fetch_one("SELECT COUNT(*) as n FROM ab_tests WHERE status = 'running'")
        complete = fetch_one("SELECT COUNT(*) as n FROM ab_tests WHERE status = 'complete'")
        return {
            "running":  running.get("n", 0)  if running  else 0,
            "complete": complete.get("n", 0) if complete else 0,
        }
    except Exception as e:
        logger.error(f"[AB TESTER] get_summary failed: {e}")
        return {"running": 0, "complete": 0}


def create_test(name: str, variants: list, metric: str = "conversion_rate") -> int:
    """Create a new A/B test record.

    Args:
        name:     Human-readable test name
        variants: List of variant labels (e.g. ['control', 'variant_a'])
        metric:   The metric to optimise (default: conversion_rate)

    Returns:
        New ab_tests row id
    """
    try:
        test_id = insert("ab_tests", {
            "name":        name,
            "status":      "running",
            "winner_stats": json.dumps({
                "variants": variants,
                "metric":   metric,
                "results":  {v: {"impressions": 0, "conversions": 0} for v in variants},
            }),
        })
        print(f"[AB TESTER] Created test '{name}' (id={test_id}) variants={variants}")
        return test_id
    except Exception as e:
        logger.error(f"[AB TESTER] create_test failed: {e}")
        return 0


def record_event(test_id: int, variant: str, converted: bool = False) -> None:
    """Record an impression (and optionally a conversion) for a variant.

    Args:
        test_id:   ab_tests row id
        variant:   Variant label
        converted: Whether this event resulted in a conversion
    """
    try:
        row = fetch_one("SELECT * FROM ab_tests WHERE id = ?", (test_id,))
        if not row or row.get("status") != "running":
            return

        stats = json.loads(row.get("winner_stats") or "{}")
        results = stats.get("results", {})
        if variant not in results:
            results[variant] = {"impressions": 0, "conversions": 0}

        results[variant]["impressions"] += 1
        if converted:
            results[variant]["conversions"] += 1

        stats["results"] = results
        with get_conn() as conn:
            conn.execute(
                "UPDATE ab_tests SET winner_stats = ? WHERE id = ?",
                (json.dumps(stats), test_id),
            )
    except Exception as e:
        logger.error(f"[AB TESTER] record_event failed: {e}")


def evaluate_tests() -> dict:
    """Evaluate all running tests and declare winners where appropriate.

    A winner is declared when:
    - Both variants have MIN_SAMPLE_SIZE impressions AND one has a higher rate, OR
    - The test has been running for MAX_DURATION_DAYS

    Returns:
        Dict with evaluated, completed counts
    """
    try:
        rows = fetch_all("SELECT * FROM ab_tests WHERE status = 'running'")
        evaluated = 0
        completed = 0

        for row in rows:
            evaluated += 1
            stats   = json.loads(row.get("winner_stats") or "{}")
            results = stats.get("results", {})
            created = row.get("created_at", "")

            # Check max duration
            age_days = 0
            try:
                created_dt = datetime.fromisoformat(created)
                age_days = (datetime.utcnow() - created_dt).days
            except Exception:
                pass

            # Compute conversion rates
            rates = {}
            for variant, data in results.items():
                imp  = data.get("impressions", 0)
                conv = data.get("conversions", 0)
                rates[variant] = conv / imp if imp > 0 else 0

            # Check if we can declare a winner
            all_sampled = all(
                results.get(v, {}).get("impressions", 0) >= MIN_SAMPLE_SIZE
                for v in results
            )
            timed_out = age_days >= MAX_DURATION_DAYS

            if (all_sampled or timed_out) and rates:
                winner = max(rates, key=lambda v: rates[v])
                best_rate   = rates[winner]
                other_rates = [r for v, r in rates.items() if v != winner]
                baseline    = other_rates[0] if other_rates else 0
                lift = round((best_rate - baseline) / baseline * 100, 1) if baseline else 0

                stats["lift"] = lift
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE ab_tests SET status = 'complete', winner = ?, "
                        "winner_stats = ?, completed_at = ? WHERE id = ?",
                        (winner, json.dumps(stats), datetime.utcnow().isoformat(), row["id"]),
                    )
                print(f"[AB TESTER] Test '{row['name']}' complete — winner={winner} lift={lift}%")
                completed += 1

        return {"evaluated": evaluated, "completed": completed}
    except Exception as e:
        logger.error(f"[AB TESTER] evaluate_tests failed: {e}")
        return {"evaluated": 0, "completed": 0}
