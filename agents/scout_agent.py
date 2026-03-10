"""Scout Agent — Proactive prospect hunter for new solar SME clients.

Runs daily at 08:00 UTC (scheduled in main.py).

What it does:
  1. Scans local DB for warm leads that haven't been followed up
  2. Queries GHL for contacts not yet in local DB
  3. Flags the best prospects as opportunities
  4. Queues research tasks for the top finds
  5. Returns a summary dict

This is the entry point for new client acquisition (System 1 side).
"""

import logging
from datetime import datetime, timedelta, timezone

import config
from memory.database import fetch_all, fetch_one, insert

logger = logging.getLogger(__name__)

# Leads with score >= this and no contact attempt are warm prospects
WARM_SCORE_THRESHOLD = 6
# Days since creation before a lead is considered "stale and un-followed-up"
STALE_DAYS = 3


def _find_unfollowed_leads() -> list:
    """Find warm local leads that have never been contacted.

    Returns:
        List of lead dicts
    """
    try:
        cutoff = (datetime.utcnow() - timedelta(days=STALE_DAYS)).isoformat()
        rows = fetch_all(
            "SELECT * FROM leads "
            "WHERE qualification_score >= ? "
            "AND status NOT IN ('contacted','converted','not_interested','called') "
            "AND contacted_at IS NULL "
            "AND created_at <= ? "
            "ORDER BY qualification_score DESC LIMIT 20",
            (WARM_SCORE_THRESHOLD, cutoff),
        )
        return rows
    except Exception as e:
        logger.error(f"[SCOUT] unfollowed leads query failed: {e}")
        return []


def _find_new_ghl_contacts() -> list:
    """Pull recent GHL contacts not yet in local leads table.

    Returns:
        List of GHL contact dicts
    """
    if not config.GHL_API_KEY:
        return []
    try:
        from integrations import ghl_client
        contacts = ghl_client.get_contacts(limit=50)
        new_contacts = []
        for c in contacts:
            phone = c.get("phone") or c.get("phoneRaw") or ""
            email = c.get("email") or ""
            exists = None
            if phone:
                exists = fetch_one("SELECT id FROM leads WHERE phone = ? LIMIT 1", (phone,))
            if not exists and email:
                exists = fetch_one("SELECT id FROM leads WHERE email = ? LIMIT 1", (email,))
            if not exists:
                new_contacts.append(c)
        return new_contacts
    except Exception as e:
        logger.error(f"[SCOUT] GHL contact pull failed: {e}")
        return []


def _save_opportunity(lead: dict, source: str) -> bool:
    """Insert a prospect into the opportunities table.

    Args:
        lead:   Lead dict with name, phone, email, score
        source: Where it was found ('unfollowed_lead' or 'new_ghl_contact')

    Returns:
        True on success
    """
    try:
        name  = lead.get("name") or lead.get("firstName", "Unknown")
        score = lead.get("qualification_score") or lead.get("score") or 0
        insert("opportunities", {
            "title":          f"Prospect: {name}",
            "opp_type":       "solar_lead",
            "status":         "discovered",
            "effort":         "low",
            "impact":         "medium" if score >= 7 else "low",
            "priority_score": float(score),
            "source":         source,
            "notes":          f"Phone: {lead.get('phone','')} | Email: {lead.get('email','')}",
        })
        return True
    except Exception as e:
        logger.error(f"[SCOUT] opportunity save failed: {e}")
        return False


def run() -> dict:
    """Run the scout cycle.

    Returns:
        Dict with prospects_found, queued_for_research, opportunities_saved
    """
    print(f"[SCOUT] Starting scout cycle at {datetime.utcnow().isoformat()}")

    unfollowed   = _find_unfollowed_leads()
    new_contacts = _find_new_ghl_contacts()
    all_prospects = unfollowed + new_contacts

    prospects_found    = len(all_prospects)
    opportunities_saved = 0
    queued_for_research = 0

    for lead in unfollowed:
        if _save_opportunity(lead, "unfollowed_lead"):
            opportunities_saved += 1

    for contact in new_contacts:
        if _save_opportunity(contact, "new_ghl_contact"):
            opportunities_saved += 1

    # Queue top 3 warm leads for the task queue (for future research agent)
    top_leads = sorted(
        unfollowed,
        key=lambda x: x.get("qualification_score") or 0,
        reverse=True,
    )[:3]

    try:
        from memory.hot_memory import enqueue_task
        for lead in top_leads:
            enqueue_task(
                job_type="research_prospect",
                context={"lead_id": lead.get("id"), "name": lead.get("name")},
                priority=3,
            )
            queued_for_research += 1
    except Exception as e:
        logger.warning(f"[SCOUT] task queue failed: {e}")

    print(
        f"[SCOUT] Done — prospects={prospects_found} "
        f"saved={opportunities_saved} queued={queued_for_research}"
    )
    return {
        "prospects_found":    prospects_found,
        "queued_for_research": queued_for_research,
        "opportunities_saved": opportunities_saved,
    }
