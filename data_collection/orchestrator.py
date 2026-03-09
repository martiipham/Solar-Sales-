"""Data Collection Orchestrator — Coordinates all data collection for Solar Swarm.

Manages source registration, dispatches collection jobs to specialist
collectors, pipes results through the normalisation pipeline, and stores
clean records ready for agents to consume.

Collection cycle runs every 4 hours via APScheduler.
"""

import logging
from datetime import datetime
from memory.database import get_conn, fetch_all, fetch_one, json_payload, parse_payload

logger = logging.getLogger(__name__)

# Source type → collector module mapping
COLLECTOR_MAP = {
    "web_scrape": "data_collection.agents.web_scraper",
    "api_poll": "data_collection.agents.api_poller",
    "social": "data_collection.agents.social_signal",
    "price_monitor": "data_collection.agents.price_monitor",
}


def run(max_sources: int = 10) -> dict:
    """Run one data collection cycle across registered sources.

    Args:
        max_sources: Max sources to collect from in this cycle

    Returns:
        Summary dict: {collected, failed, new_signals, sources_run}
    """
    print("[DATA COLLECTION] Starting collection cycle")
    sources = _get_due_sources(max_sources)

    if not sources:
        print("[DATA COLLECTION] No sources due for collection")
        _register_default_sources()
        return {"collected": 0, "failed": 0, "new_signals": 0, "sources_run": 0}

    collected = failed = new_signals = 0

    for source in sources:
        try:
            result = _collect_from_source(source)
            if result.get("success"):
                collected += result.get("records", 0)
                new_signals += result.get("signals", 0)
                _mark_source_collected(source["source_id"])
            else:
                failed += 1
                _mark_source_failed(source["source_id"], result.get("error", "unknown"))
        except Exception as e:
            logger.error(f"[DATA COLLECTION] Source {source['source_id']} error: {e}")
            failed += 1

    print(f"[DATA COLLECTION] Cycle done — collected={collected} failed={failed} signals={new_signals}")
    return {
        "collected": collected,
        "failed": failed,
        "new_signals": new_signals,
        "sources_run": len(sources),
    }


def register_source(
    source_type: str,
    name: str,
    config: dict,
    frequency_hours: int = 6,
    priority: str = "NORMAL",
) -> str:
    """Register a new data collection source.

    Args:
        source_type: web_scrape|api_poll|social|price_monitor
        name: Human-readable source name
        config: Source-specific configuration dict
        frequency_hours: How often to collect (hours)
        priority: CRITICAL|HIGH|NORMAL|LOW

    Returns:
        source_id
    """
    import uuid
    source_id = f"src_{uuid.uuid4().hex[:10]}"
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO collection_sources
               (source_id, source_type, name, config, frequency_hours, priority, active)
               VALUES (?,?,?,?,?,?,1)""",
            (source_id, source_type, name, json_payload(config), frequency_hours, priority),
        )
    logger.info(f"[DATA COLLECTION] Registered source: {name} ({source_type})")
    return source_id


def get_recent_data(source_type: str = None, limit: int = 50) -> list:
    """Fetch recent normalised collected records.

    Args:
        source_type: Optional filter by source type
        limit: Max records to return

    Returns:
        List of normalised data dicts
    """
    if source_type:
        rows = fetch_all(
            "SELECT * FROM collected_data WHERE source_type=? AND normalized=1 "
            "ORDER BY collected_at DESC LIMIT ?",
            (source_type, limit),
        )
    else:
        rows = fetch_all(
            "SELECT * FROM collected_data WHERE normalized=1 "
            "ORDER BY collected_at DESC LIMIT ?",
            (limit,),
        )
    return [{**r, "data": parse_payload(r.get("normalized_data") or r.get("raw_data") or "{}")} for r in rows]


def _get_due_sources(limit: int) -> list:
    """Return sources due for collection based on last_collected + frequency."""
    rows = fetch_all(
        """SELECT * FROM collection_sources
           WHERE active=1
           AND (last_collected IS NULL
                OR datetime(last_collected, '+' || frequency_hours || ' hours') <= datetime('now'))
           ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'NORMAL' THEN 3 ELSE 4 END, last_collected ASC
           LIMIT ?""",
        (limit,),
    )
    return [{**r, "config": parse_payload(r.get("config", "{}"))} for r in rows]


def _collect_from_source(source: dict) -> dict:
    """Dispatch to the appropriate collector module."""
    source_type = source.get("source_type", "web_scrape")
    module_path = COLLECTOR_MAP.get(source_type)

    if not module_path:
        return {"success": False, "error": f"Unknown source type: {source_type}"}

    try:
        import importlib
        mod = importlib.import_module(module_path)
        return mod.collect(source)
    except Exception as e:
        logger.error(f"[DATA COLLECTION] Collector error for {source_type}: {e}")
        return {"success": False, "error": str(e)}


def _mark_source_collected(source_id: str):
    """Update last_collected timestamp."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE collection_sources SET last_collected=? WHERE source_id=?",
            (datetime.utcnow().isoformat(), source_id),
        )


def _mark_source_failed(source_id: str, reason: str):
    """Increment failure count and log error."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE collection_sources SET error_count=COALESCE(error_count,0)+1 WHERE source_id=?",
            (source_id,),
        )
    logger.warning(f"[DATA COLLECTION] Source {source_id} failed: {reason}")


def _register_default_sources():
    """Register built-in sources if none exist yet."""
    existing = fetch_all("SELECT name FROM collection_sources LIMIT 1")
    if existing:
        return

    defaults = [
        ("web_scrape", "Clean Energy Regulator Installer List",
         {"url": "https://www.rec-registry.gov.au/rec-registry/app/public/registered-agents",
          "selector": "table", "data_type": "solar_installer"}, 24, "HIGH"),
        ("api_poll", "GoHighLevel Pipeline Snapshot",
         {"endpoint": "contacts", "filter": "new_leads_today"}, 2, "HIGH"),
        ("social", "LinkedIn Solar Australia",
         {"platform": "linkedin", "query": "solar company Perth Brisbane Melbourne", "limit": 20}, 12, "NORMAL"),
        ("price_monitor", "Google Ads Solar CPL Benchmark",
         {"keywords": ["solar installation", "solar panels cost", "solar quotes"],
          "market": "AU"}, 24, "NORMAL"),
    ]

    for source_type, name, cfg, freq, priority in defaults:
        register_source(source_type, name, cfg, freq, priority)

    print("[DATA COLLECTION] Default sources registered")
