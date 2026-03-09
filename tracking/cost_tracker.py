"""API Usage & Cost Tracker.

Logs every API call (OpenAI, Retell, ElevenLabs) to the api_usage table
so you can see exactly what's being spent and where.

Pricing reference (2025 — update if rates change):
  OpenAI GPT-4o:     input $2.50 / 1M tokens | output $10.00 / 1M tokens
  OpenAI GPT-4o-mini: input $0.15 / 1M tokens | output $0.60 / 1M tokens
  Retell:            ~$0.07 / minute
  ElevenLabs TTS:    ~$0.005 / 1,000 characters

Usage:
    from tracking.cost_tracker import log_openai, log_retell_call, log_elevenlabs
    log_openai("gpt-4o", prompt_tokens=512, completion_tokens=128, call_id="abc")
    log_retell_call(call_id="abc", duration_seconds=180, client_id="suntech")
"""

import logging
from datetime import datetime, timedelta

from memory.database import get_conn, fetch_all, fetch_one

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PRICING TABLE (USD per unit)
# ─────────────────────────────────────────────────────────────────────────────

PRICING = {
    "openai": {
        "gpt-4o":              {"input": 2.50 / 1_000_000,  "output": 10.00 / 1_000_000},
        "gpt-4o-mini":         {"input": 0.15 / 1_000_000,  "output": 0.60  / 1_000_000},
        "gpt-4-turbo":         {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
        "gpt-3.5-turbo":       {"input": 0.50  / 1_000_000, "output": 1.50  / 1_000_000},
    },
    "retell": {
        "per_minute": 0.07,   # USD per minute of call
    },
    "elevenlabs": {
        "per_1k_chars": 0.005,  # USD per 1,000 characters (Starter plan)
    },
}

# AUD / USD exchange rate estimate — update or make dynamic if needed
AUD_PER_USD = 1.55


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def log_openai(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    call_id: str = None,
    client_id: str = None,
    operation: str = "chat_completion",
) -> float:
    """Log an OpenAI API call and return the estimated USD cost.

    Args:
        model: Model name (gpt-4o, gpt-4o-mini, etc.)
        prompt_tokens: Number of input tokens used
        completion_tokens: Number of output tokens generated
        call_id: Optional call ID to link to call_logs
        client_id: Optional client ID
        operation: Operation label (chat_completion, embedding, etc.)

    Returns:
        Estimated cost in USD
    """
    rates = PRICING["openai"].get(model, PRICING["openai"]["gpt-4o"])
    cost_usd = (prompt_tokens * rates["input"]) + (completion_tokens * rates["output"])
    total_tokens = prompt_tokens + completion_tokens

    _insert(
        service="openai",
        operation=operation,
        model=model,
        units=total_tokens,
        unit_type="tokens",
        cost_usd=cost_usd,
        call_id=call_id,
        client_id=client_id,
        metadata={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    )
    return cost_usd


def log_retell_call(
    call_id: str,
    duration_seconds: int,
    client_id: str = None,
    agent_id: str = None,
) -> float:
    """Log a completed Retell voice call and return estimated cost.

    Args:
        call_id: Retell call ID
        duration_seconds: Total call duration in seconds
        client_id: Optional client ID
        agent_id: Optional Retell agent ID

    Returns:
        Estimated cost in USD
    """
    minutes = duration_seconds / 60
    cost_usd = minutes * PRICING["retell"]["per_minute"]

    _insert(
        service="retell",
        operation="voice_call",
        model=agent_id or "retell-agent",
        units=round(minutes, 3),
        unit_type="minutes",
        cost_usd=cost_usd,
        call_id=call_id,
        client_id=client_id,
        metadata={"duration_seconds": duration_seconds, "agent_id": agent_id},
    )
    return cost_usd


def log_elevenlabs(
    characters: int,
    voice_id: str = None,
    call_id: str = None,
    client_id: str = None,
    operation: str = "tts",
) -> float:
    """Log an ElevenLabs TTS or Conversational AI usage event.

    Args:
        characters: Number of characters synthesised
        voice_id: ElevenLabs voice ID
        call_id: Optional call ID
        client_id: Optional client ID
        operation: tts | conversation

    Returns:
        Estimated cost in USD
    """
    cost_usd = (characters / 1000) * PRICING["elevenlabs"]["per_1k_chars"]

    _insert(
        service="elevenlabs",
        operation=operation,
        model=voice_id or "default",
        units=characters,
        unit_type="characters",
        cost_usd=cost_usd,
        call_id=call_id,
        client_id=client_id,
        metadata={"voice_id": voice_id},
    )
    return cost_usd


def _insert(
    service: str,
    operation: str,
    model: str,
    units: float,
    unit_type: str,
    cost_usd: float,
    call_id: str = None,
    client_id: str = None,
    metadata: dict = None,
):
    """Write one usage record to the api_usage table.

    Args:
        service: API provider name
        operation: Operation type
        model: Model/voice/agent identifier
        units: Quantity consumed
        unit_type: Unit label
        cost_usd: Estimated cost in USD
        call_id: Optional call reference
        client_id: Optional client reference
        metadata: Optional extra JSON context
    """
    import json as _json
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO api_usage
                   (service, operation, model, units, unit_type, cost_usd, call_id, client_id, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    service, operation, model, units, unit_type,
                    round(cost_usd, 6), call_id, client_id,
                    _json.dumps(metadata) if metadata else None,
                ),
            )
    except Exception as e:
        logger.error(f"[COST TRACKER] Insert failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def get_cost_summary(days: int = 7) -> dict:
    """Return total cost breakdown by service for the last N days.

    Args:
        days: Number of days to look back

    Returns:
        Dict with totals per service, overall total, and AUD equivalent
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = fetch_all(
        """SELECT service, SUM(cost_usd) as total_usd, SUM(units) as total_units, unit_type,
                  COUNT(*) as call_count
           FROM api_usage
           WHERE recorded_at >= ?
           GROUP BY service, unit_type
           ORDER BY total_usd DESC""",
        (since,),
    )

    breakdown = {}
    total_usd = 0.0
    for r in rows:
        svc = r["service"]
        if svc not in breakdown:
            breakdown[svc] = {"cost_usd": 0.0, "calls": 0}
        breakdown[svc]["cost_usd"] += r["total_usd"] or 0
        breakdown[svc]["calls"]    += r["call_count"] or 0
        breakdown[svc]["units"]     = round(r["total_units"] or 0, 2)
        breakdown[svc]["unit_type"] = r["unit_type"]
        total_usd += r["total_usd"] or 0

    return {
        "period_days":    days,
        "breakdown":      breakdown,
        "total_usd":      round(total_usd, 4),
        "total_aud":      round(total_usd * AUD_PER_USD, 2),
        "generated_at":   datetime.utcnow().isoformat(),
    }


def get_daily_costs(days: int = 30) -> list:
    """Return day-by-day cost totals for the last N days.

    Args:
        days: Number of days to look back

    Returns:
        List of dicts with date, cost_usd, cost_aud, call_count
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = fetch_all(
        """SELECT DATE(recorded_at) as day,
                  SUM(cost_usd) as cost_usd,
                  COUNT(*) as api_calls
           FROM api_usage
           WHERE recorded_at >= ?
           GROUP BY DATE(recorded_at)
           ORDER BY day DESC""",
        (since,),
    )
    return [
        {
            "date":      r["day"],
            "cost_usd":  round(r["cost_usd"] or 0, 4),
            "cost_aud":  round((r["cost_usd"] or 0) * AUD_PER_USD, 2),
            "api_calls": r["api_calls"],
        }
        for r in rows
    ]


def get_call_cost(call_id: str) -> dict:
    """Return the total API cost for a single call across all services.

    Args:
        call_id: Call or session ID

    Returns:
        Dict with total cost and per-service breakdown
    """
    rows = fetch_all(
        """SELECT service, SUM(cost_usd) as cost_usd, SUM(units) as units, unit_type
           FROM api_usage WHERE call_id = ?
           GROUP BY service""",
        (call_id,),
    )
    total = sum(r["cost_usd"] or 0 for r in rows)
    return {
        "call_id":   call_id,
        "total_usd": round(total, 4),
        "total_aud": round(total * AUD_PER_USD, 2),
        "services":  [dict(r) for r in rows],
    }


def get_client_costs(client_id: str, days: int = 30) -> dict:
    """Return cost totals for a specific client over the last N days.

    Useful for understanding per-client profitability vs retainer fee.

    Args:
        client_id: Company client ID
        days: Number of days to look back

    Returns:
        Dict with total cost and per-service breakdown
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = fetch_all(
        """SELECT service, SUM(cost_usd) as cost_usd, COUNT(*) as calls
           FROM api_usage
           WHERE client_id = ? AND recorded_at >= ?
           GROUP BY service ORDER BY cost_usd DESC""",
        (client_id, since),
    )
    total = sum(r["cost_usd"] or 0 for r in rows)
    return {
        "client_id":  client_id,
        "period_days": days,
        "total_usd":  round(total, 4),
        "total_aud":  round(total * AUD_PER_USD, 2),
        "breakdown":  [dict(r) for r in rows],
    }


def get_projected_monthly_cost() -> dict:
    """Extrapolate current week's usage to a monthly estimate.

    Returns:
        Dict with projected monthly cost in USD and AUD
    """
    summary_7d = get_cost_summary(days=7)
    weekly_usd = summary_7d["total_usd"]
    monthly_usd = weekly_usd * (30 / 7)

    return {
        "last_7_days_usd":     round(weekly_usd, 2),
        "projected_month_usd": round(monthly_usd, 2),
        "projected_month_aud": round(monthly_usd * AUD_PER_USD, 2),
        "margin_note":         f"At ${monthly_usd * AUD_PER_USD:.0f} AUD/month costs vs $1,500-2,000 retainer = ~{((1750 - monthly_usd * AUD_PER_USD) / 1750 * 100):.0f}% margin",
    }
