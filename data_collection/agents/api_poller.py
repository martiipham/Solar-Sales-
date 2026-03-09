"""API Poller Collector — Polls GoHighLevel and other APIs for fresh data.

Fetches contacts, pipeline stages, and campaign stats from GHL API.
Gracefully degrades to mock data when API keys are not configured.
"""

import json
import logging
import uuid
from datetime import datetime
from memory.database import get_conn, json_payload
import config

logger = logging.getLogger(__name__)


def collect(source: dict) -> dict:
    """Poll an API endpoint and store results.

    Args:
        source: Source dict with config containing endpoint, filter, params

    Returns:
        {success, records, signals, error}
    """
    cfg = source.get("config", {})
    endpoint = cfg.get("endpoint", "contacts")
    source_id = source.get("source_id", "unknown")

    print(f"[API POLLER] Polling endpoint: {endpoint}")

    records = _poll_ghl(endpoint, cfg) if _has_ghl_key() else _mock_ghl_data(endpoint)

    stored = _store_records(records, source_id, endpoint)
    signals = _count_signals(records, endpoint)

    print(f"[API POLLER] Stored {stored} records, {signals} new signals")
    return {"success": True, "records": stored, "signals": signals}


def _has_ghl_key() -> bool:
    """Check if GoHighLevel API key is available."""
    return bool(getattr(config, "GHL_API_KEY", None))


def _poll_ghl(endpoint: str, cfg: dict) -> list:
    """Call GoHighLevel REST API."""
    try:
        import requests
        base = "https://rest.gohighlevel.com/v1"
        headers = {
            "Authorization": f"Bearer {config.GHL_API_KEY}",
            "Content-Type": "application/json",
        }
        params = cfg.get("params", {})
        resp = requests.get(f"{base}/{endpoint}", headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # GHL returns {contacts: [...]} or {opportunities: [...]} etc.
        for key in ("contacts", "opportunities", "campaigns", "data"):
            if key in data:
                return data[key]
        return [data]
    except Exception as e:
        logger.error(f"[API POLLER] GHL API error: {e}")
        return _mock_ghl_data(endpoint)


def _mock_ghl_data(endpoint: str) -> list:
    """Return realistic mock GHL data."""
    if endpoint == "contacts":
        return [
            {"id": "c001", "firstName": "Sarah", "lastName": "Chen",
             "email": "sarah@sunpowerperth.com.au", "phone": "+61400111222",
             "tags": ["solar-company", "owner"], "dateAdded": datetime.utcnow().isoformat()},
            {"id": "c002", "firstName": "Mike", "lastName": "Robertson",
             "email": "mike@brisbanesolar.com.au", "phone": "+61400333444",
             "tags": ["solar-company", "manager"], "dateAdded": datetime.utcnow().isoformat()},
        ]
    if endpoint == "opportunities":
        return [
            {"id": "o001", "name": "SunPower Perth — GHL Setup",
             "status": "open", "monetaryValue": 2000,
             "stage": {"name": "Proposal Sent"}},
        ]
    return [{"endpoint": endpoint, "mock": True, "timestamp": datetime.utcnow().isoformat()}]


def _store_records(records: list, source_id: str, data_type: str) -> int:
    """Persist API records to collected_data."""
    stored = 0
    for rec in records:
        rec_id = f"cd_{uuid.uuid4().hex[:10]}"
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO collected_data
                       (record_id, source_id, source_type, data_type, raw_data,
                        data, normalized, collected_at)
                       VALUES (?,?,?,?,?,?,1,?)""",
                    (rec_id, source_id, "api_poll", data_type,
                     json_payload(rec), json_payload(rec),
                     datetime.utcnow().isoformat()),
                )
            stored += 1
        except Exception as e:
            logger.error(f"[API POLLER] Store error: {e}")
    return stored


def _count_signals(records: list, endpoint: str) -> int:
    """Return count of records that represent new leads or opportunities."""
    if endpoint in ("contacts", "opportunities"):
        return len(records)
    return 0
