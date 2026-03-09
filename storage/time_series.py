"""Time Series Store — Records and queries metrics over time for Solar Swarm.

Stores CPL benchmarks, lead counts, revenue, experiment scores, and
pheromone signals with timestamps so agents can detect trends and
make data-driven strategy adjustments.
"""

import logging
import uuid
from datetime import datetime
from memory.database import get_conn, fetch_all, json_payload, parse_payload

logger = logging.getLogger(__name__)


def record(
    metric_name: str,
    value: float,
    dimensions: dict = None,
    source: str = "system",
) -> str:
    """Record a single metric data point.

    Args:
        metric_name: e.g. "cpl_benchmark", "lead_count", "experiment_score"
        value: Numeric value
        dimensions: Dict of tags (e.g. {"keyword": "solar installation", "state": "WA"})
        source: Which agent or system recorded this

    Returns:
        ts_id
    """
    ts_id = f"ts_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO time_series
               (ts_id, metric_name, metric_value, dimensions, source, recorded_at)
               VALUES (?,?,?,?,?,?)""",
            (ts_id, metric_name, value,
             json_payload(dimensions or {}), source,
             datetime.utcnow().isoformat()),
        )
    return ts_id


def get_latest(metric_name: str, dimensions: dict = None) -> dict:
    """Get the most recent value for a metric.

    Args:
        metric_name: Metric to query
        dimensions: Optional dimension filter (exact match on all keys)

    Returns:
        Latest data point dict or empty dict
    """
    rows = fetch_all(
        "SELECT * FROM time_series WHERE metric_name=? ORDER BY recorded_at DESC LIMIT 50",
        (metric_name,),
    )
    if not rows:
        return {}

    if dimensions:
        for row in rows:
            stored_dims = parse_payload(row.get("dimensions", "{}"))
            if all(stored_dims.get(k) == v for k, v in dimensions.items()):
                return {**dict(row), "dimensions": stored_dims}
        return {}

    row = rows[0]
    return {**dict(row), "dimensions": parse_payload(row.get("dimensions", "{}"))}


def get_series(metric_name: str, days: int = 30, dimensions: dict = None) -> list:
    """Return time series data for a metric over the last N days.

    Args:
        metric_name: Metric to retrieve
        days: How many days back to look
        dimensions: Optional dimension filter

    Returns:
        List of {ts_id, metric_value, dimensions, recorded_at} dicts
    """
    rows = fetch_all(
        """SELECT * FROM time_series
           WHERE metric_name=?
           AND recorded_at >= datetime('now', ? || ' days')
           ORDER BY recorded_at ASC""",
        (metric_name, f"-{days}"),
    )
    result = []
    for row in rows:
        dims = parse_payload(row.get("dimensions", "{}"))
        if dimensions and not all(dims.get(k) == v for k, v in dimensions.items()):
            continue
        result.append({**dict(row), "dimensions": dims})
    return result


def get_trend(metric_name: str, days: int = 14, dimensions: dict = None) -> dict:
    """Calculate trend direction and percentage change over N days.

    Returns:
        {direction: rising|stable|falling, pct_change, first_value, last_value, n_points}
    """
    series = get_series(metric_name, days, dimensions)
    if len(series) < 2:
        return {"direction": "stable", "pct_change": 0, "n_points": len(series)}

    first = series[0]["metric_value"]
    last = series[-1]["metric_value"]
    pct = ((last - first) / first * 100) if first else 0

    direction = "stable"
    if pct > 5:
        direction = "rising"
    elif pct < -5:
        direction = "falling"

    return {
        "direction": direction,
        "pct_change": round(pct, 2),
        "first_value": first,
        "last_value": last,
        "n_points": len(series),
    }


def get_metrics_summary() -> dict:
    """Return latest value for all tracked metrics — for dashboard."""
    rows = fetch_all(
        """SELECT metric_name, metric_value, recorded_at
           FROM time_series t1
           WHERE recorded_at = (
               SELECT MAX(recorded_at) FROM time_series t2
               WHERE t2.metric_name = t1.metric_name
           )
           GROUP BY metric_name"""
    )
    return {r["metric_name"]: {"value": r["metric_value"], "at": r["recorded_at"]} for r in rows}
