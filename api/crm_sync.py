"""CRM Sync — Pulls live data from the active CRM and caches it in SQLite.

Called by APScheduler every 30 minutes via main.py.

What it does:
  1. Pulls pipeline stages from the active CRM (GHL / HubSpot / Salesforce)
  2. Pulls recent contacts (last 50)
  3. Computes a conversion funnel metrics summary
  4. Writes everything to the crm_cache table in SQLite
  5. Injects a crmMetrics block into public/board-state.json

This keeps the React board's Overview tab fed with real CRM data
without the browser ever having direct API credentials.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from memory.database import get_conn, fetch_one
import config

logger = logging.getLogger(__name__)

BOARD_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public",
    "board-state.json",
)


def _upsert_cache(key: str, value: dict):
    """Write or update a single cache entry by key.

    Args:
        key: Unique cache key (e.g. 'pipeline_abc123', 'metrics_summary')
        value: Data dict to store as JSON
    """
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO crm_cache (cache_key, cache_value, cached_at) VALUES (?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET "
            "cache_value = excluded.cache_value, cached_at = excluded.cached_at",
            (key, json.dumps(value), datetime.utcnow().isoformat()),
        )


def _sync_pipeline() -> list:
    """Pull pipeline stages from the active CRM and cache each stage.

    Returns:
        List of stage dicts from the CRM, or empty list on failure
    """
    try:
        from integrations.crm_router import get_pipeline_stages, active_crm
        pipeline_id = config.get("GHL_PIPELINE_ID", "")
        stages = get_pipeline_stages(pipeline_id)
        for stage in stages:
            stage_id = stage.get("id") or stage.get("stageId") or stage.get("name", "unknown")
            _upsert_cache(f"pipeline_{stage_id}", stage)
        print(f"[CRM SYNC] Cached {len(stages)} pipeline stages from {active_crm()}")
        return stages
    except Exception as e:
        logger.error(f"[CRM SYNC] Pipeline sync failed: {e}")
        return []


def _sync_recent_contacts(limit: int = 50) -> list:
    """Pull recent contacts from the active CRM and cache each one.

    Args:
        limit: Max number of contacts to fetch

    Returns:
        List of contact dicts
    """
    try:
        from integrations.crm_router import active_crm
        crm = active_crm()
        contacts = []

        if crm == "ghl":
            from integrations.crm_router import _get_ghl
            result = _get_ghl()._request(
                "GET",
                f"/contacts/?locationId={config.GHL_LOCATION_ID}&limit={limit}&sortBy=date_added&sortOrder=desc",
            )
            contacts = (result or {}).get("contacts", [])

        elif crm == "hubspot":
            from integrations.crm_router import _get_hubspot
            result = _get_hubspot()._request(
                "GET",
                f"/crm/v3/objects/contacts?limit={limit}"
                "&properties=firstname,lastname,email,phone,hs_lead_status,createdate,lifecyclestage"
                "&sort=-createdate",
            )
            contacts = (result or {}).get("results", [])

        elif crm == "salesforce":
            from integrations.crm_router import _get_salesforce
            contacts = _get_salesforce()._soql(
                f"SELECT Id, FirstName, LastName, Email, Phone, CreatedDate, "
                f"LeadSource, StageName FROM Contact ORDER BY CreatedDate DESC LIMIT {limit}"
            ) or []

        for c in contacts:
            cid = (
                c.get("id") or c.get("Id") or c.get("contactId") or "unknown"
            )
            _upsert_cache(f"contact_{cid}", c)

        print(f"[CRM SYNC] Cached {len(contacts)} contacts from {crm}")
        return contacts

    except Exception as e:
        logger.error(f"[CRM SYNC] Contact sync failed: {e}")
        return []


def _is_converted(contact: dict) -> bool:
    """Check if a contact is marked as converted/won in any CRM's format.

    Args:
        contact: Contact dict from any CRM

    Returns:
        True if the contact appears to be a converted customer
    """
    status = (
        contact.get("opportunityStatus") or
        contact.get("hs_lead_status") or
        contact.get("StageName") or
        contact.get("lifecyclestage") or
        ""
    ).lower()
    return any(w in status for w in ("won", "closed", "converted", "customer", "client"))


def _compute_metrics(contacts: list, stages: list) -> dict:
    """Compute funnel summary metrics from contacts and pipeline stages.

    Args:
        contacts: List of contact dicts from CRM
        stages: List of pipeline stage dicts from CRM

    Returns:
        Metrics dict with total_contacts, new_this_week, pipeline_stages,
        conversion_rate, and synced_at
    """
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    new_this_week = sum(
        1 for c in contacts
        if (
            c.get("dateAdded") or
            c.get("createdate") or
            c.get("CreatedDate") or
            ""
        ) >= week_ago
    )

    stage_summary = [
        {
            "name":  s.get("name") or s.get("stageName", "Unknown"),
            "id":    s.get("id") or s.get("stageId", ""),
            "count": s.get("opportunityCount") or s.get("count") or 0,
        }
        for s in stages
    ]

    total = len(contacts)
    converted = sum(1 for c in contacts if _is_converted(c))
    conversion_rate = round(converted / total * 100, 1) if total > 0 else 0

    return {
        "total_contacts":   total,
        "new_this_week":    new_this_week,
        "converted":        converted,
        "conversion_rate":  conversion_rate,
        "pipeline_stages":  stage_summary,
        "synced_at":        datetime.utcnow().isoformat(),
    }


def _update_board_state(metrics: dict):
    """Inject a crmMetrics block into public/board-state.json.

    Args:
        metrics: Metrics dict from _compute_metrics()
    """
    try:
        try:
            with open(BOARD_STATE_PATH) as f:
                state = json.load(f)
        except Exception:
            state = {}

        state["crmMetrics"] = metrics
        state["lastUpdated"] = datetime.utcnow().isoformat()

        with open(BOARD_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)

        print("[CRM SYNC] board-state.json updated with CRM metrics")
    except Exception as e:
        logger.error(f"[CRM SYNC] board-state.json update failed: {e}")


def run():
    """Main sync entry point — called by scheduler every 30 minutes."""
    print(f"[CRM SYNC] Starting CRM data sync at {datetime.utcnow().isoformat()}")

    from integrations.crm_router import is_configured
    if not is_configured():
        print("[CRM SYNC] No CRM configured — skipping sync")
        return

    stages   = _sync_pipeline()
    contacts = _sync_recent_contacts()

    if contacts or stages:
        metrics = _compute_metrics(contacts, stages)
        _upsert_cache("metrics_summary", metrics)
        _update_board_state(metrics)

    print("[CRM SYNC] Sync complete")
