"""CRM Sync — Pulls live GHL data and caches it in SQLite.

Called by APScheduler every 30 minutes via main.py.

What it does:
  1. Pulls GHL contacts updated in the last 30 minutes
  2. Upserts each contact into the local leads table (match on phone or email)
  3. Pulls open opportunities from the GHL pipeline
  4. Computes summary stats from local leads table
  5. Writes stats to crm_stats table (total_leads, hot_leads,
     booked_assessments, proposals_sent, updated_at)
  6. Logs the sync result

Also exposes push_lead_to_ghl(lead_id) for the reverse direction.
"""

import logging
from datetime import datetime, timedelta, timezone

from memory.database import get_conn, fetch_one, insert
import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_crm_stats_table():
    """Create crm_stats table if it does not yet exist.

    Safe to call on every sync — CREATE TABLE IF NOT EXISTS is idempotent.
    """
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                updated_at TEXT DEFAULT (datetime('now')),
                total_leads INTEGER DEFAULT 0,
                hot_leads INTEGER DEFAULT 0,
                booked_assessments INTEGER DEFAULT 0,
                proposals_sent INTEGER DEFAULT 0
            )
        """)


# ─────────────────────────────────────────────────────────────────────────────
# CONTACT PULL & UPSERT
# ─────────────────────────────────────────────────────────────────────────────

def _pull_contacts_updated_since(minutes: int = 30) -> list:
    """Pull GHL contacts updated within the last N minutes.

    Fetches the 200 most-recently-updated contacts, then filters
    to those whose dateUpdated falls within the cutoff window.

    Args:
        minutes: Lookback window in minutes

    Returns:
        List of GHL contact dicts
    """
    try:
        from integrations import ghl_client
        contacts = ghl_client.get_contacts(limit=200)
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=minutes)
        ).isoformat()
        recent = [
            c for c in contacts
            if (c.get("dateUpdated") or c.get("dateAdded") or "") >= cutoff
        ]
        print(f"[CRM SYNC] {len(recent)} contacts updated in last {minutes} min "
              f"(of {len(contacts)} fetched)")
        return recent
    except Exception as e:
        logger.error(f"[CRM SYNC] Contact pull failed: {e}")
        return []


def _upsert_lead(contact: dict) -> int | None:
    """Upsert a GHL contact into the local leads table.

    Matches on phone first, then email. Creates a new row if neither matches.

    Args:
        contact: GHL contact dict

    Returns:
        Lead DB id (new or existing) or None on failure
    """
    try:
        name = (
            contact.get("name")
            or f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
            or "Unknown"
        )
        phone  = contact.get("phone") or contact.get("phoneRaw") or ""
        email  = contact.get("email") or ""
        suburb = contact.get("city") or ""
        state  = contact.get("state") or ""
        ghl_id = contact.get("id") or contact.get("contactId") or ""

        # Match on phone or email
        existing = None
        if phone:
            existing = fetch_one("SELECT id FROM leads WHERE phone = ? LIMIT 1", (phone,))
        if not existing and email:
            existing = fetch_one("SELECT id FROM leads WHERE email = ? LIMIT 1", (email,))

        now = datetime.utcnow().isoformat()

        if existing:
            db_id = existing.get("id")
            with get_conn() as conn:
                conn.execute(
                    """UPDATE leads SET
                       name   = COALESCE(?, name),
                       email  = COALESCE(?, email),
                       suburb = COALESCE(?, suburb),
                       state  = COALESCE(?, state),
                       notes  = COALESCE(notes, '') || ?
                       WHERE id = ?""",
                    (
                        name   or None,
                        email  or None,
                        suburb or None,
                        state  or None,
                        f" | GHL sync {now}" if ghl_id else "",
                        db_id,
                    ),
                )
            return db_id

        # New lead — insert
        return insert("leads", {
            "source":         "ghl_webhook",
            "name":           name,
            "phone":          phone  or None,
            "email":          email  or None,
            "suburb":         suburb or None,
            "state":          state  or None,
            "pipeline_stage": contact.get("pipelineStage") or contact.get("stage"),
            "status":         "new",
            "client_account": config.get("DEFAULT_CLIENT_ID", "default"),
            "notes":          f"Synced from GHL contact {ghl_id} at {now}",
        })
    except Exception as e:
        logger.error(f"[CRM SYNC] Lead upsert failed for {contact.get('id')}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OPPORTUNITIES PULL
# ─────────────────────────────────────────────────────────────────────────────

def _pull_open_opportunities() -> list:
    """Pull open opportunities from the GHL pipeline.

    Returns:
        List of GHL opportunity dicts
    """
    try:
        from integrations.ghl_client import _request
        pipeline_id = config.GHL_PIPELINE_ID
        params = (
            f"/opportunities/search/?location_id={config.GHL_LOCATION_ID}"
            f"&status=open&limit=100"
        )
        if pipeline_id:
            params += f"&pipeline_id={pipeline_id}"
        result = _request("GET", params)
        opps = (result or {}).get("opportunities", [])
        print(f"[CRM SYNC] Fetched {len(opps)} open opportunities")
        return opps
    except Exception as e:
        logger.error(f"[CRM SYNC] Opportunities pull failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_crm_stats() -> dict:
    """Compute summary stats from the local leads table.

    Returns:
        Dict with total_leads, hot_leads, booked_assessments, proposals_sent
    """
    try:
        total  = fetch_one("SELECT COUNT(*) as n FROM leads", ())
        hot    = fetch_one("SELECT COUNT(*) as n FROM leads WHERE status = 'hot'", ())
        booked = fetch_one(
            "SELECT COUNT(*) as n FROM leads WHERE pipeline_stage LIKE '%booked%' "
            "OR pipeline_stage LIKE '%assessment%'", ()
        )
        sent = fetch_one(
            "SELECT COUNT(*) as n FROM proposals WHERE status IN ('sent','accepted')", ()
        )
        return {
            "total_leads":        total.get("n", 0)  if total  else 0,
            "hot_leads":          hot.get("n", 0)    if hot    else 0,
            "booked_assessments": booked.get("n", 0) if booked else 0,
            "proposals_sent":     sent.get("n", 0)   if sent   else 0,
            "updated_at":         datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[CRM SYNC] Stats compute failed: {e}")
        return {
            "total_leads": 0, "hot_leads": 0,
            "booked_assessments": 0, "proposals_sent": 0,
            "updated_at": datetime.utcnow().isoformat(),
        }


def _write_crm_stats(stats: dict):
    """Write computed stats to the crm_stats table.

    Args:
        stats: Dict from _compute_crm_stats()
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO crm_stats
                   (updated_at, total_leads, hot_leads, booked_assessments, proposals_sent)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    stats["updated_at"],
                    stats["total_leads"],
                    stats["hot_leads"],
                    stats["booked_assessments"],
                    stats["proposals_sent"],
                ),
            )
        print(
            f"[CRM SYNC] Stats — leads: {stats['total_leads']} "
            f"hot: {stats['hot_leads']} "
            f"booked: {stats['booked_assessments']} "
            f"proposals: {stats['proposals_sent']}"
        )
    except Exception as e:
        logger.error(f"[CRM SYNC] Stats write failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run():
    """Main sync entry point — called by scheduler every 30 minutes.

    Pulls recent GHL contacts, upserts to leads, pulls open opportunities,
    computes stats, and writes a crm_stats row.
    """
    print(f"[CRM SYNC] Starting sync at {datetime.utcnow().isoformat()}")

    if not config.GHL_API_KEY:
        print("[CRM SYNC] GHL not configured — skipping sync")
        return

    _ensure_crm_stats_table()

    # Pull and upsert contacts updated in last 30 min
    contacts = _pull_contacts_updated_since(minutes=30)
    upserted = sum(1 for c in contacts if _upsert_lead(c))
    print(f"[CRM SYNC] Upserted {upserted}/{len(contacts)} contacts to leads table")

    # Pull open opportunities (informational — feeds dashboard counts)
    _pull_open_opportunities()

    # Compute and persist stats
    stats = _compute_crm_stats()
    _write_crm_stats(stats)

    print("[CRM SYNC] Sync complete")


# ─────────────────────────────────────────────────────────────────────────────
# PUSH LEAD → GHL
# ─────────────────────────────────────────────────────────────────────────────

def push_lead_to_ghl(lead_id: int) -> dict:
    """Push a local lead record to GHL — create/update contact and opportunity.

    Reads the lead from SQLite, finds or creates a GHL contact, adds a
    qualification score note, then creates an opportunity in the pipeline
    stage that matches recommended_action.

    Stage routing:
        call_now        → GHL_STAGE_HOT
        book_assessment → GHL_STAGE_BOOKED
        nurture         → GHL_STAGE_NURTURE
        disqualify      → skip (no opportunity created)

    Args:
        lead_id: Lead row ID in the local leads table

    Returns:
        Dict with success, ghl_contact_id, action, and optional error
    """
    lead = fetch_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not lead:
        logger.error(f"[CRM SYNC] push_lead_to_ghl: lead {lead_id} not found")
        return {"success": False, "error": "Lead not found"}

    if not config.GHL_API_KEY:
        return {"success": False, "error": "GHL not configured"}

    from integrations import ghl_client

    phone = lead.get("phone") or ""
    email = lead.get("email") or ""
    name  = lead.get("name") or "Solar Lead"
    parts = name.split(" ", 1)
    first = parts[0]
    last  = parts[1] if len(parts) > 1 else ""

    contact_payload = {
        "firstName": first,
        "lastName":  last,
        "email":     email or None,
        "phone":     phone or None,
        "city":      lead.get("suburb") or "",
        "state":     lead.get("state") or "",
        "tags":      ["voice-ai-lead"],
    }

    # Find existing GHL contact by phone
    ghl_id = None
    if phone:
        existing = _request_ghl_search(phone)
        if existing:
            ghl_id = existing.get("id")
            ghl_client.update_contact(ghl_id, contact_payload)
            print(f"[CRM SYNC] Updated existing GHL contact: {ghl_id}")

    if not ghl_id:
        result = ghl_client.create_contact(contact_payload)
        if not result:
            return {"success": False, "error": "GHL contact creation failed"}
        ghl_id = (
            result.get("contact", {}).get("id")
            or result.get("id")
        )
        print(f"[CRM SYNC] Created new GHL contact: {ghl_id}")

    if not ghl_id:
        return {"success": False, "error": "Could not obtain GHL contact ID"}

    # Add qualification score as a note
    score  = lead.get("qualification_score") or lead.get("score")
    action = lead.get("recommended_action") or ""
    if score:
        note = (
            f"AI Lead Score: {score}/10. "
            f"Recommended action: {action}. "
            f"Monthly bill: ${lead.get('monthly_bill') or '?'}. "
            f"Homeowner: {lead.get('homeowner_status') or 'unknown'}. "
            f"Source: Solar-Admin-AI."
        )
        ghl_client.add_note(ghl_id, note)

    # Create opportunity at the correct pipeline stage
    stage_map = {
        "call_now":        config.get("GHL_STAGE_HOT", ""),
        "book_assessment": config.get("GHL_STAGE_BOOKED", ""),
        "nurture":         config.get("GHL_STAGE_NURTURE", ""),
    }
    stage_id    = stage_map.get(action)
    pipeline_id = config.GHL_PIPELINE_ID

    if action == "disqualify":
        print(f"[CRM SYNC] Lead {lead_id} disqualified — no opportunity created")
    elif stage_id and pipeline_id:
        ghl_client.create_opportunity(
            contact_id=ghl_id,
            pipeline_id=pipeline_id,
            stage_id=stage_id,
        )
        print(f"[CRM SYNC] Opportunity created for contact {ghl_id} → stage: {action}")
    else:
        logger.warning(f"[CRM SYNC] No stage mapped for action '{action}' — opportunity skipped")

    return {"success": True, "ghl_contact_id": ghl_id, "action": action}


def bulk_push_leads(lead_ids: list[int]) -> dict:
    """Push multiple leads to GHL with error isolation.

    Each lead is pushed individually via push_lead_to_ghl(). Failures on
    one lead do not block processing of subsequent leads. The GHL client's
    token bucket rate limiter automatically paces the underlying API calls.

    Args:
        lead_ids: List of lead row IDs to push

    Returns:
        Dict with succeeded count, failed count, and per-lead errors
    """
    succeeded = 0
    failed = 0
    errors = {}

    for lead_id in lead_ids:
        try:
            result = push_lead_to_ghl(lead_id)
            if result.get("success"):
                succeeded += 1
            else:
                failed += 1
                errors[lead_id] = result.get("error", "Unknown error")
        except Exception as e:
            failed += 1
            errors[lead_id] = str(e)
            logger.error(f"[CRM SYNC] bulk_push lead {lead_id} exception: {e}")

    print(f"[CRM SYNC] Bulk push complete: {succeeded} succeeded, {failed} failed")
    return {"succeeded": succeeded, "failed": failed, "errors": errors}


def _request_ghl_search(phone: str) -> dict | None:
    """Search GHL for a contact by phone number.

    Args:
        phone: Phone number (E.164 or local format)

    Returns:
        Contact dict or None
    """
    try:
        from integrations.ghl_client import _request
        result = _request("GET", f"/contacts/search/duplicate?phone={phone}")
        return result.get("contact") if result else None
    except Exception as e:
        logger.error(f"[CRM SYNC] GHL phone search failed: {e}")
        return None
