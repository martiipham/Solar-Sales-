# Cost & Usage Tracking

## Overview

Every API call made by the system — OpenAI, Retell, ElevenLabs — is logged to the `api_usage` table with a calculated cost in USD. This makes it possible to track per-client profitability, identify expensive operations, and project monthly costs.

**File:** `tracking/cost_tracker.py`

---

## api_usage Table Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `recorded_at` | TEXT | UTC timestamp |
| `service` | TEXT | `openai` / `retell` / `elevenlabs` |
| `operation` | TEXT | e.g. `chat_completion`, `voice_call`, `tts` |
| `model` | TEXT | e.g. `gpt-4o`, `retell-agent`, voice ID |
| `units` | REAL | Tokens, minutes, or characters consumed |
| `unit_type` | TEXT | `tokens` / `minutes` / `characters` |
| `cost_usd` | REAL | Estimated cost in USD (6 decimal places) |
| `call_id` | TEXT | Links to `call_logs.call_id` |
| `client_id` | TEXT | Links to `company_profiles` |
| `metadata` | TEXT | JSON with extra context (token split, agent_id, etc.) |

---

## Pricing Reference

Current rates used by the cost tracker (update in `tracking/cost_tracker.py` if rates change):

### OpenAI

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|-----------------------|------------------------|
| `gpt-4o` | $2.50 USD | $10.00 USD |
| `gpt-4o-mini` | $0.15 USD | $0.60 USD |
| `gpt-4-turbo` | $10.00 USD | $30.00 USD |
| `gpt-3.5-turbo` | $0.50 USD | $1.50 USD |

### Retell AI

$0.07 USD per minute of call duration.

### ElevenLabs

$0.005 USD per 1,000 characters of synthesised speech (Starter plan).

**AUD conversion:** The tracker uses a fixed rate of **1.55 AUD per USD**. Update `AUD_PER_USD` in `cost_tracker.py` if the rate drifts significantly.

---

## Logging Functions

### log_openai

```python
from tracking.cost_tracker import log_openai

cost_usd = log_openai(
    model="gpt-4o",
    prompt_tokens=512,
    completion_tokens=128,
    call_id="call_abc123",     # optional
    client_id="sunpower_perth", # optional
    operation="chat_completion", # default
)
```

Called automatically by `voice/call_handler.py` on every GPT-4o LLM call during a conversation.

### log_retell_call

```python
from tracking.cost_tracker import log_retell_call

cost_usd = log_retell_call(
    call_id="call_abc123",
    duration_seconds=180,
    client_id="sunpower_perth",
    agent_id="agent_xyz",
)
```

Called by `voice/call_handler.py` in the post-call webhook handler.

### log_elevenlabs

```python
from tracking.cost_tracker import log_elevenlabs

cost_usd = log_elevenlabs(
    characters=1500,
    voice_id="11labs-Adrian",
    call_id="call_abc123",
    client_id="sunpower_perth",
    operation="tts",           # or "conversation"
)
```

Called when ElevenLabs TTS or Conversational AI is used.

---

## Reporting API

### get_cost_summary(days=7)

Returns total cost breakdown by service for the last N days.

```python
from tracking.cost_tracker import get_cost_summary

summary = get_cost_summary(days=30)
# {
#   "period_days": 30,
#   "breakdown": {
#     "openai":     {"cost_usd": 12.50, "calls": 480, "units": 5000000, "unit_type": "tokens"},
#     "retell":     {"cost_usd": 8.40,  "calls": 120},
#     "elevenlabs": {"cost_usd": 0.75,  "calls": 120}
#   },
#   "total_usd": 21.65,
#   "total_aud": 33.56,
#   "generated_at": "2026-03-09T08:00:00"
# }
```

### get_daily_costs(days=30)

Day-by-day totals for trend analysis.

```python
daily = get_daily_costs(days=7)
# [
#   {"date": "2026-03-09", "cost_usd": 0.82, "cost_aud": 1.27, "api_calls": 24},
#   {"date": "2026-03-08", "cost_usd": 1.10, "cost_aud": 1.71, "api_calls": 31},
#   ...
# ]
```

### get_call_cost(call_id)

Total cost for a single voice call across all services.

```python
call_cost = get_call_cost("call_abc123")
# {
#   "call_id": "call_abc123",
#   "total_usd": 0.094,
#   "total_aud": 0.15,
#   "services": [
#     {"service": "openai",     "cost_usd": 0.024, "units": 2400,  "unit_type": "tokens"},
#     {"service": "retell",     "cost_usd": 0.063, "units": 0.9,   "unit_type": "minutes"},
#     {"service": "elevenlabs", "cost_usd": 0.007, "units": 1500,  "unit_type": "characters"}
#   ]
# }
```

### get_client_costs(client_id, days=30)

Cost totals for a specific solar company client. Use this to check per-client profitability against their retainer.

```python
client = get_client_costs("sunpower_perth", days=30)
# {
#   "client_id": "sunpower_perth",
#   "period_days": 30,
#   "total_usd": 14.20,
#   "total_aud": 22.01,
#   "breakdown": [
#     {"service": "openai",  "cost_usd": 8.50, "calls": 340},
#     {"service": "retell",  "cost_usd": 5.70, "calls": 82},
#   ]
# }
```

### get_projected_monthly_cost()

Extrapolates the last 7 days of usage to a monthly estimate and calculates margin against the $1,500–2,000 AUD retainer.

```python
projection = get_projected_monthly_cost()
# {
#   "last_7_days_usd": 5.20,
#   "projected_month_usd": 22.29,
#   "projected_month_aud": 34.55,
#   "margin_note": "At $35 AUD/month costs vs $1,500-2,000 retainer = ~98% margin"
# }
```

---

## HTTP API

All cost reporting is available via the Human Gate API on port 5000.

```bash
# Overall 7-day summary
curl -H "Authorization: Bearer $GATE_API_KEY" \
  http://localhost:5000/costs

# 30-day view
curl -H "Authorization: Bearer $GATE_API_KEY" \
  "http://localhost:5000/costs?days=30"

# Cost for one call
curl -H "Authorization: Bearer $GATE_API_KEY" \
  "http://localhost:5000/costs?call_id=call_abc123"

# Cost for one client (30 days)
curl -H "Authorization: Bearer $GATE_API_KEY" \
  "http://localhost:5000/costs?client_id=sunpower_perth&days=30"
```

---

## Typical Monthly Cost Estimates

At typical Australian solar SME volumes:

| Component | Volume | Monthly Cost (USD) |
|-----------|--------|-------------------|
| OpenAI GPT-4o | ~2M tokens (agent runs + voice) | ~$10–20 |
| Retell AI | ~100 calls × 3 min avg | ~$21 |
| ElevenLabs | ~300,000 chars/month | ~$1.50 |
| **Total** | | **~$32–42 USD (~$50–65 AUD)** |

This leaves a margin of approximately 95–97% on a $1,500 AUD/month retainer.

---

## Querying the Database Directly

For ad-hoc analysis, query the `api_usage` table directly:

```bash
sqlite3 swarm.db
```

```sql
-- Total cost by service this month
SELECT service,
       SUM(cost_usd) AS total_usd,
       COUNT(*) AS call_count
FROM api_usage
WHERE recorded_at >= date('now', 'start of month')
GROUP BY service
ORDER BY total_usd DESC;

-- Most expensive individual calls
SELECT call_id,
       SUM(cost_usd) AS total_usd,
       client_id,
       MIN(recorded_at) AS started_at
FROM api_usage
WHERE call_id IS NOT NULL
GROUP BY call_id
ORDER BY total_usd DESC
LIMIT 20;

-- Daily trend
SELECT DATE(recorded_at) AS day,
       ROUND(SUM(cost_usd), 4) AS cost_usd,
       COUNT(*) AS api_calls
FROM api_usage
WHERE recorded_at >= date('now', '-30 days')
GROUP BY day
ORDER BY day DESC;
```

---

## Budget Alerts

The circuit breaker monitors experiment budget burn (not API costs). If budget spending exceeds 150% of the planned daily rate, the circuit breaker moves to Orange level.

To set up a budget alert for total API costs, add a check in your weekly retrospective:

```python
from tracking.cost_tracker import get_cost_summary

summary = get_cost_summary(days=7)
if summary["total_aud"] > 50:  # Alert if weekly API costs exceed $50 AUD
    from notifications.slack_notifier import notify
    notify(f"Weekly API costs: ${summary['total_aud']} AUD — review usage")
```

---

## Adding a New Tracked Service

1. Add a pricing entry to the `PRICING` dict in `tracking/cost_tracker.py`
2. Create a `log_<service>()` function following the same pattern as `log_openai()`
3. Call `_insert()` with the correct `service`, `units`, `unit_type`, and `cost_usd`
4. Call your logging function wherever the service API is invoked
