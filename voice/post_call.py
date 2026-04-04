"""Post-Call Processor — Transcript analysis and CRM finalisation.

After every call ends, Retell sends the full transcript + metadata.
This module:
  1. Extracts structured data from the transcript via GPT-4o
  2. Updates the lead record with all collected information
  3. Scores the lead if not already scored
  4. Updates GHL with final call notes and tags
  5. Creates follow-up tasks for sales team
  6. Posts Slack notification
  7. Logs to cold ledger

Usage:
    from voice.post_call import process_post_call
    result = process_post_call(retell_webhook_data, call_context)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import config
from memory.database import get_conn, fetch_one, update as db_update, insert

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are analysing a transcript from a solar sales call in Australia.
Extract ALL structured information mentioned during the call.

Return ONLY valid JSON:
{
  "name":               "customer's full name or null",
  "email":              "email address or null",
  "phone":              "phone number or null",
  "suburb":             "suburb or null",
  "state":              "AU state code or null",
  "homeowner_status":   "owner|renter|unknown",
  "monthly_bill":       <number in AUD or null>,
  "roof_type":          "tile|colorbond|flat|metal|unknown or null",
  "roof_age":           <years or null>,
  "num_people":         <integer or null>,
  "has_ev":             <true|false|null>,
  "interested_battery": <true|false|null>,
  "preferred_time":     "customer's preferred callback/assessment time or null",
  "outcome":            "booked_assessment|callback_requested|proposal_sent|not_interested|transferred|support_resolved",
  "sentiment":          "positive|neutral|negative",
  "key_objections":     ["objection1", "objection2"],
  "follow_up_required": <true|false>,
  "follow_up_notes":    "specific notes for sales team or null",
  "call_summary":       "2-3 sentence summary of the call",
  "qualification_signals": ["signal1", "signal2"]
}"""


def process_post_call(webhook_data: dict, call_ctx: dict) -> dict:
    """Process a completed call — extract data, update CRM, create tasks.

    Args:
        webhook_data: Full Retell post-call webhook payload
        call_ctx: In-memory call context accumulated during the call

    Returns:
        Processing result dict
    """
    call_id      = webhook_data.get("call_id", call_ctx.get("call_id", "unknown"))
    transcript   = webhook_data.get("transcript", [])
    duration_s   = webhook_data.get("duration_seconds", 0)
    recording    = webhook_data.get("recording_url", "")
    client_id    = call_ctx.get("client_id", "default")

    # Idempotency guard — Retell may retry the post-call webhook on 5xx responses.
    # If this call has already been finalised, skip processing to prevent duplicate
    # CRM updates, Slack notifications, and follow-up task creation.
    already_done = fetch_one(
        "SELECT id FROM call_logs WHERE call_id = ? AND status = 'complete'",
        (call_id,),
    )
    if already_done:
        logger.warning(
            f"[POST-CALL] Duplicate post-call webhook for call_id={call_id} — skipping."
        )
        return {"call_id": call_id, "skipped": True, "reason": "already_processed"}

    print(f"[POST-CALL] Processing call {call_id} | {duration_s}s | {len(transcript)} turns")

    # ── Step 1: Extract structured data from transcript
    extracted = _extract_from_transcript(transcript, call_ctx)

    # ── Step 2: Merge with in-call collected context
    merged = {**extracted, **(call_ctx.get("lead_data", {}))}
    # Explicit fields from in-call context take priority
    for key in ("call_outcome", "lead_score", "lead_action"):
        if call_ctx.get(key):
            merged[key] = call_ctx[key]

    # ── Step 3: Upsert lead in DB
    db_id = call_ctx.get("contact_db_id")
    if not db_id:
        phone  = call_ctx.get("contact_phone") or merged.get("phone")
        if phone:
            row = fetch_one("SELECT id FROM leads WHERE phone = ?", (phone,))
            db_id = row.get("id") if row else None

    if db_id:
        _update_lead_record(db_id, merged, call_id, duration_s, recording)
    else:
        db_id = _create_lead_record(merged, call_id, client_id, duration_s, recording)

    # ── Step 4: Score lead if not already done
    score  = merged.get("lead_score") or call_ctx.get("lead_score")
    action = merged.get("lead_action") or call_ctx.get("lead_action")
    if not score and db_id:
        try:
            from agents.qualification_agent import qualify
            q = qualify(merged, db_id)
            score  = q.get("score")
            action = q.get("recommended_action")
        except Exception as e:
            logger.error(f"[POST-CALL] Qualification failed: {e}")

    # ── Step 4b: Flag HOT leads in DB
    if score and score >= 7 and db_id:
        try:
            with get_conn() as conn:
                conn.execute("UPDATE leads SET status = 'hot' WHERE id = ?", (db_id,))
            print(f"[POST-CALL] HOT lead flagged: db_id={db_id} score={score}")
        except Exception as e:
            logger.error(f"[POST-CALL] HOT flag failed: {e}")

    # ── Step 5: Update GHL CRM
    ghl_id = call_ctx.get("ghl_contact_id")
    _update_ghl(ghl_id, merged, score, action, call_id, recording, extracted)

    # ── Step 6: Create follow-up task
    if extracted.get("follow_up_required") and ghl_id:
        _create_followup_task(ghl_id, merged, score, action, extracted)

    # ── Step 7: Update call_logs table
    _finalise_call_log(call_id, duration_s, recording, merged, score, transcript)

    # ── Step 8: Slack notification
    _notify_slack(merged, score, action, duration_s, extracted)

    print(f"[POST-CALL] Complete: score={score} action={action} outcome={merged.get('call_outcome')}")
    return {"call_id": call_id, "score": score, "action": action, "lead_db_id": db_id}


def _extract_from_transcript(transcript: list, ctx: dict) -> dict:
    """Use GPT-4o to extract structured data from the call transcript.

    Args:
        transcript: List of {role, content} turn dicts
        ctx: Call context

    Returns:
        Extracted data dict
    """
    if not config.is_configured() or not transcript:
        return ctx.get("lead_data", {})

    try:
        full_transcript = "\n".join(
            f"{t.get('role','?').upper()}: {t.get('content','')}"
            for t in transcript
            if t.get("content")
        )

        from openai import OpenAI
        client   = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user",   "content": f"TRANSCRIPT:\n\n{full_transcript}"},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        extracted = json.loads(raw)
        print(f"[POST-CALL] Extraction complete: {list(k for k, v in extracted.items() if v)}")
        return extracted
    except json.JSONDecodeError as e:
        logger.error(f"[POST-CALL] Extraction JSON error: {e}")
        return ctx.get("lead_data", {})
    except Exception as e:
        logger.error(f"[POST-CALL] Extraction failed: {e}")
        return ctx.get("lead_data", {})


def _update_lead_record(db_id: int, data: dict, call_id: str, duration: int, recording: str):
    """Update existing lead record with post-call data.

    Args:
        db_id: Lead record ID
        data: Merged data dict
        call_id: Retell call ID
        duration: Call duration in seconds
        recording: Recording URL
    """
    fields: dict[str, Any] = {}
    for key in ("name", "email", "suburb", "state", "homeowner_status",
                "monthly_bill", "roof_type", "notes"):
        if data.get(key) is not None:
            fields[key] = data[key]

    if data.get("roof_age") is not None:
        fields["roof_age"] = int(data["roof_age"])

    note_append = (
        f" | Voice call {call_id} ({duration}s)"
        f" | Outcome: {data.get('call_outcome','unknown')}"
        f" | Summary: {data.get('call_summary','')}"
    )
    if recording:
        note_append += f" | Recording: {recording}"

    fields["contacted_at"] = datetime.utcnow().isoformat()
    fields["status"]       = "contacted"

    with get_conn() as conn:
        if fields:
            assigns = ", ".join(f"{k} = ?" for k in fields)
            values  = list(fields.values()) + [db_id]
            conn.execute(f"UPDATE leads SET {assigns} WHERE id = ?", values)
        conn.execute(
            "UPDATE leads SET notes = COALESCE(notes,'') || ? WHERE id = ?",
            (note_append, db_id)
        )


def _create_lead_record(data: dict, call_id: str, client_id: str, duration: int, recording: str) -> int:
    """Create a new lead record from post-call data.

    Args:
        data: Extracted lead data
        call_id: Retell call ID
        client_id: Company client ID
        duration: Call duration in seconds
        recording: Recording URL

    Returns:
        New lead DB ID
    """
    notes = (
        f"Voice call {call_id} ({duration}s) | "
        f"Outcome: {data.get('call_outcome','unknown')} | "
        f"Summary: {data.get('call_summary','')} | "
        f"Recording: {recording}"
    )
    return insert("leads", {
        "source":           "ghl_webhook",
        "name":             data.get("name", "Voice Call Lead"),
        "phone":            data.get("phone"),
        "email":            data.get("email"),
        "suburb":           data.get("suburb"),
        "state":            data.get("state"),
        "homeowner_status": data.get("homeowner_status"),
        "monthly_bill":     data.get("monthly_bill"),
        "roof_type":        data.get("roof_type"),
        "roof_age":         data.get("roof_age"),
        "status":           "contacted",
        "contacted_at":     datetime.utcnow().isoformat(),
        "client_account":   client_id,
        "notes":            notes,
    })


def _update_ghl(ghl_id: str, data: dict, score, action: str, call_id: str, recording: str, extracted: dict):
    """Update GoHighLevel with all post-call data.

    Args:
        ghl_id: GHL contact ID
        data: Merged data dict
        score: Lead score
        action: Recommended action
        call_id: Call ID
        recording: Recording URL
        extracted: GPT-extracted transcript data
    """
    if not ghl_id:
        return
    try:
        from integrations.ghl_client import (
            update_contact_field, add_contact_tag,
            create_task, is_configured
        )
        if not is_configured():
            return

        # Update custom fields
        field_map = {
            "homeowner_status": "homeowner_status",
            "monthly_bill":     "monthly_electricity_bill",
            "roof_type":        "roof_type",
            "email":            "email",
            "suburb":           "city",
        }
        for data_key, ghl_field in field_map.items():
            if data.get(data_key):
                update_contact_field(ghl_id, ghl_field, str(data[data_key]))

        if score:
            update_contact_field(ghl_id, "ai_lead_score",         str(score))
            update_contact_field(ghl_id, "ai_recommended_action", action or "")
        if recording:
            update_contact_field(ghl_id, "call_recording_url", recording)

        update_contact_field(ghl_id, "last_called_at", datetime.utcnow().isoformat())
        update_contact_field(ghl_id, "call_summary",   data.get("call_summary", "")[:500])

        # Tags
        outcome = data.get("call_outcome", "unknown")
        tag_map = {
            "booked_assessment": ["assessment-booked", "voice-ai-qualified"],
            "callback_requested": ["callback-requested", "voice-ai-lead"],
            "not_interested":    ["not-interested-voice"],
            "transferred":       ["transferred-to-human"],
        }
        for tag in tag_map.get(outcome, ["voice-ai-contacted"]):
            add_contact_tag(ghl_id, tag)

        if score and score >= 7:
            add_contact_tag(ghl_id, "hot-lead")
        if extracted.get("interested_battery"):
            add_contact_tag(ghl_id, "battery-interest")
        if extracted.get("has_ev"):
            add_contact_tag(ghl_id, "ev-owner")

    except Exception as e:
        logger.error(f"[POST-CALL] GHL update failed: {e}")


def _create_followup_task(ghl_id: str, data: dict, score, action: str, extracted: dict):
    """Create a follow-up task in GHL for the sales team.

    Args:
        ghl_id: GHL contact ID
        data: Lead data
        score: Lead score
        action: Recommended action
        extracted: Extracted transcript data
    """
    try:
        from integrations.ghl_client import create_task, is_configured
        if not is_configured():
            return

        due = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        name = data.get("name", "Customer")

        task_titles = {
            "booked_assessment": f"CONFIRMED: Site assessment for {name} — confirm time and send reminder",
            "callback_requested": f"CALLBACK: {name} requested callback — CALL WITHIN 1 HOUR",
            "not_interested":   None,  # No task for not interested
        }

        outcome   = data.get("call_outcome", "unknown")
        title     = task_titles.get(outcome, f"Follow up with {name} — voice AI lead (score {score}/10)")

        if title:
            notes = extracted.get("follow_up_notes") or f"Score: {score}/10. Action: {action}."
            create_task(ghl_id, f"{title}\n{notes}", due)

    except Exception as e:
        logger.error(f"[POST-CALL] Task creation failed: {e}")


def _finalise_call_log(call_id: str, duration: int, recording: str, data: dict, score, transcript: list | None = None):
    """Update the call_logs record with final status.

    Args:
        call_id: Call ID
        duration: Duration in seconds
        recording: Recording URL
        data: Lead data
        score: Lead score
        transcript: List of transcript turn dicts (optional)
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """UPDATE call_logs SET
                   status = 'complete',
                   duration_seconds = ?,
                   recording_url = ?,
                   outcome = ?,
                   lead_score = ?,
                   summary = ?,
                   transcript_text = ?,
                   ended_at = ?
                WHERE call_id = ?""",
                (
                    duration,
                    recording,
                    data.get("call_outcome", "unknown"),
                    score,
                    data.get("call_summary", "")[:500],
                    json.dumps(transcript or []),
                    datetime.utcnow().isoformat(),
                    call_id,
                )
            )
    except Exception as e:
        logger.error(f"[POST-CALL] call_logs update failed: {e}")


def _notify_slack(data: dict, score, action: str, duration: int, extracted: dict):
    """Post Slack notification about the completed call.

    Args:
        data: Lead data
        score: Lead score
        action: Recommended action
        duration: Call duration in seconds
        extracted: GPT-extracted data
    """
    try:
        from notifications.slack_notifier import _post

        name    = data.get("name", "Unknown")
        outcome = data.get("call_outcome", "unknown")
        suburb  = data.get("suburb", "")
        bill    = data.get("monthly_bill")

        outcome_icons = {
            "booked_assessment": "📅 *ASSESSMENT BOOKED*",
            "callback_requested": "📞 *CALLBACK REQUESTED*",
            "not_interested":    "❌ Not interested",
            "transferred":       "🔀 *TRANSFERRED TO HUMAN*",
            "proposal_sent":     "📧 Proposal sent",
        }
        icon = outcome_icons.get(outcome, "📞 Call complete")
        score_emoji = "🔥" if (score or 0) >= 7 else "📋" if (score or 0) >= 5 else "❌"

        mins = duration // 60
        secs = duration % 60

        msg = (
            f"{icon}\n"
            f"*Name:* {name}  {score_emoji} *{score}/10*\n"
            f"*Suburb:* {suburb}  |  *Bill:* ${bill or '?'}/mo\n"
            f"*Action:* {action or '?'}  |  *Duration:* {mins}m {secs}s\n"
        )

        if extracted.get("call_summary"):
            msg += f"*Summary:* _{extracted['call_summary']}_\n"
        if extracted.get("follow_up_notes"):
            msg += f"*Follow-up:* {extracted['follow_up_notes']}"

        _post(msg)

    except Exception as e:
        logger.error(f"[POST-CALL] Slack notify failed: {e}")
