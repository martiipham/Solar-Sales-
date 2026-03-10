"""Service health monitor for Solar Admin AI.

Checks all internal Flask services and OpenAI reachability every 5 minutes.
Sends Slack alerts on first failure and on recovery.
Sends SMS (via Twilio) to TRANSFER_PHONE as a backup alert channel.

Services monitored:
  - Human Gate API   (localhost:PORT_HUMAN_GATE/health)
  - GHL Webhooks     (localhost:PORT_GHL_WEBHOOKS/health)
  - Voice AI         (localhost:PORT_VOICE_WEBHOOK/voice/health)
  - Dashboard API    (localhost:PORT_DASHBOARD_API/api/health)
  - OpenAI           (api.openai.com reachability check)
"""

import logging
import time
from datetime import datetime, timezone

import requests

import config

logger = logging.getLogger(__name__)

# Module-level state — tracks last known status of each service.
# Structure: { service_name: {"ok": bool, "failed_at": iso_str | None} }
_state: dict = {}

# Services to monitor — (name, url)
def _services() -> list[tuple[str, str]]:
    """Return list of (name, health_url) pairs based on current config."""
    base = "http://127.0.0.1"
    return [
        ("Human Gate API",  f"{base}:{config.PORT_HUMAN_GATE}/health"),
        ("GHL Webhooks",    f"{base}:{config.PORT_GHL_WEBHOOKS}/health"),
        ("Voice AI",        f"{base}:{config.PORT_VOICE_WEBHOOK}/voice/health"),
        ("Dashboard API",   f"{base}:{config.PORT_DASHBOARD_API}/api/health"),
    ]


def _check_endpoint(name: str, url: str, timeout: int = 5) -> dict:
    """HTTP GET a health endpoint and return its status.

    Args:
        name: Human-readable service name
        url: Health check URL
        timeout: Request timeout in seconds

    Returns:
        Dict with keys: name, ok, status_code, latency_ms, error
    """
    t0 = time.monotonic()
    try:
        resp = requests.get(url, timeout=timeout)
        latency = round((time.monotonic() - t0) * 1000)
        ok = resp.status_code == 200
        return {"name": name, "ok": ok, "status_code": resp.status_code,
                "latency_ms": latency, "error": None}
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000)
        return {"name": name, "ok": False, "status_code": None,
                "latency_ms": latency, "error": str(e)[:100]}


def _check_openai() -> dict:
    """Check OpenAI API reachability with a lightweight models list call.

    Returns:
        Status dict same shape as _check_endpoint
    """
    name = "OpenAI API"
    if not config.OPENAI_API_KEY:
        return {"name": name, "ok": True, "status_code": None,
                "latency_ms": 0, "error": "key not configured — skipped"}
    t0 = time.monotonic()
    try:
        resp = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            timeout=8,
        )
        latency = round((time.monotonic() - t0) * 1000)
        ok = resp.status_code == 200
        return {"name": name, "ok": ok, "status_code": resp.status_code,
                "latency_ms": latency, "error": None}
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000)
        return {"name": name, "ok": False, "status_code": None,
                "latency_ms": latency, "error": str(e)[:100]}


def check_all() -> list[dict]:
    """Run all health checks and return results.

    Returns:
        List of status dicts, one per service
    """
    results = []
    for name, url in _services():
        results.append(_check_endpoint(name, url))
    results.append(_check_openai())
    return results


def _send_sms(body: str) -> None:
    """Send an SMS alert to TRANSFER_PHONE via Twilio.

    Only fires if TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER,
    and TRANSFER_PHONE are all configured.

    Args:
        body: SMS message text (kept under 160 chars by caller)
    """
    sid   = config.TWILIO_ACCOUNT_SID
    token = config.TWILIO_AUTH_TOKEN
    from_ = config.TWILIO_FROM_NUMBER
    to    = config.TRANSFER_PHONE

    if not all([sid, token, from_, to]):
        return

    try:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"From": from_, "To": to, "Body": body},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.error(f"[MONITOR] SMS failed: HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[MONITOR] SMS send error: {e}")


def run_health_check() -> None:
    """Run all health checks and send alerts on status changes.

    Called by APScheduler every 5 minutes.

    - On first failure: Slack alert + SMS to TRANSFER_PHONE
    - On recovery: Slack recovery alert
    - No alert if service was already in the same state as last check
    """
    from notifications.slack_notifier import alert_service_down, alert_service_recovered

    results = check_all()
    now_iso = datetime.now(timezone.utc).isoformat()

    for r in results:
        name  = r["name"]
        ok    = r["ok"]
        prev  = _state.get(name, {"ok": True, "failed_at": None})

        if not ok and prev["ok"]:
            # Newly failed
            detail = r.get("error") or f"HTTP {r.get('status_code', '?')}"
            logger.error(f"[MONITOR] DOWN: {name} — {detail}")
            _state[name] = {"ok": False, "failed_at": now_iso}

            alert_service_down(name, detail)
            sms_body = f"[Solar AI] SERVICE DOWN: {name}. {detail[:80]}. Check the server."
            _send_sms(sms_body[:160])

        elif ok and not prev["ok"]:
            # Recovered
            down_since = prev.get("failed_at", "unknown")
            logger.info(f"[MONITOR] RECOVERED: {name} (was down since {down_since})")
            _state[name] = {"ok": True, "failed_at": None}

            alert_service_recovered(name, down_since)

        else:
            # No change — update state silently
            _state[name] = {"ok": ok, "failed_at": prev.get("failed_at")}
            if not ok:
                logger.warning(f"[MONITOR] Still down: {name} ({r.get('error', '')})")
