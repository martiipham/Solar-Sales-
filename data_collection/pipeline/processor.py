"""Pipeline Processor — Normalises raw collected data and emits actionable signals.

Takes raw records from collected_data, deduplicates, enriches, and routes
high-value signals to the message bus so agents can act immediately.

Runs at end of each collection cycle.
"""

import logging
import uuid
from datetime import datetime
from memory.database import get_conn, fetch_all, json_payload, parse_payload
from bus import message_bus

logger = logging.getLogger(__name__)

# Minimum signal strength to post to the bus
SIGNAL_THRESHOLD = "medium"


def process_batch(since_minutes: int = 60) -> dict:
    """Process all raw records collected in the last N minutes.

    Args:
        since_minutes: Window of records to process

    Returns:
        {processed, deduplicated, signals_posted}
    """
    print(f"[PIPELINE] Processing records from last {since_minutes} minutes")
    raw_records = _fetch_unprocessed(since_minutes)

    if not raw_records:
        print("[PIPELINE] No new records to process")
        return {"processed": 0, "deduplicated": 0, "signals_posted": 0}

    seen_hashes = set()
    processed = deduplicated = signals_posted = 0

    for rec in raw_records:
        fingerprint = _fingerprint(rec)
        if fingerprint in seen_hashes:
            deduplicated += 1
            continue
        seen_hashes.add(fingerprint)

        enriched = _enrich(rec)
        signal = _extract_signal(enriched)

        if signal and _signal_meets_threshold(signal):
            _post_signal_to_bus(signal, enriched)
            signals_posted += 1

        _mark_processed(rec["record_id"])
        processed += 1

    print(f"[PIPELINE] processed={processed} deduped={deduplicated} signals={signals_posted}")
    return {"processed": processed, "deduplicated": deduplicated, "signals_posted": signals_posted}


def _fetch_unprocessed(since_minutes: int) -> list:
    """Fetch records not yet passed through the pipeline."""
    rows = fetch_all(
        """SELECT * FROM collected_data
           WHERE pipeline_processed IS NULL
           AND collected_at >= datetime('now', ? || ' minutes')
           ORDER BY collected_at ASC LIMIT 200""",
        (f"-{since_minutes}",),
    )
    return [{**r, "data": parse_payload(r.get("data", "{}"))} for r in rows]


def _fingerprint(rec: dict) -> str:
    """Create a deduplication fingerprint from key fields."""
    data = rec.get("data", {})
    parts = [
        str(data.get("company_name", "")),
        str(data.get("url", "")),
        str(data.get("keyword", "")),
        str(data.get("id", "")),
    ]
    return "|".join(p.lower().strip() for p in parts if p)


def _enrich(rec: dict) -> dict:
    """Add metadata and scoring to a raw record."""
    data = rec.get("data", {})
    source_type = rec.get("source_type", "unknown")

    score = 0
    if source_type == "social" and data.get("signal_strength") == "high":
        score = 9
    elif source_type == "social" and data.get("signal_strength") == "medium":
        score = 6
    elif source_type == "web_scrape" and data.get("company_name"):
        score = 5
    elif source_type == "api_poll":
        score = 7

    return {**rec, "enriched_score": score, "enriched_at": datetime.utcnow().isoformat()}


def _extract_signal(rec: dict) -> dict | None:
    """Convert an enriched record to a signal dict if it warrants one."""
    data = rec.get("data", {})
    source_type = rec.get("source_type", "")
    score = rec.get("enriched_score", 0)

    if score < 5:
        return None

    if source_type == "social":
        return {
            "signal_type": "social_buying_signal",
            "company": data.get("company", "Unknown"),
            "strength": data.get("signal_strength", "medium"),
            "evidence": data.get("text", "")[:200],
            "url": data.get("url", ""),
            "score": score,
        }

    if source_type == "web_scrape" and data.get("company_name"):
        return {
            "signal_type": "new_prospect_found",
            "company": data.get("company_name", ""),
            "state": data.get("state", ""),
            "licence": data.get("licence_number", ""),
            "score": score,
        }

    if source_type == "api_poll":
        return {
            "signal_type": "ghl_contact_update",
            "contact_id": data.get("id", ""),
            "name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            "score": score,
        }

    return None


def _signal_meets_threshold(signal: dict) -> bool:
    """Check if signal score is high enough to post to bus."""
    return signal.get("score", 0) >= 5


def _post_signal_to_bus(signal: dict, rec: dict) -> str:
    """Post a qualifying signal to the research queue."""
    priority = "HIGH" if signal.get("score", 0) >= 8 else "NORMAL"
    return message_bus.post(
        from_agent="pipeline_processor",
        to_queue="research_queue",
        msg_type="ALERT",
        payload={"signal": signal, "source_record_id": rec.get("record_id")},
        priority=priority,
    )


def _mark_processed(record_id: str):
    """Stamp the record as pipeline-processed."""
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE collected_data SET pipeline_processed=? WHERE record_id=?",
                (datetime.utcnow().isoformat(), record_id),
            )
    except Exception as e:
        logger.error(f"[PIPELINE] Mark processed error: {e}")
