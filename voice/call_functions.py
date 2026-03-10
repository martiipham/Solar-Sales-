"""Voice Agent Function Definitions — GHL + Swarm integration.

These are the functions the AI voice agent can call in real-time during a call.
Retell AI (or ElevenLabs) executes these as tool calls, exactly like OpenAI
function calling, then feeds the result back to the LLM.

Each function:
  - Has a JSON schema for the AI to know when/how to call it
  - Returns a plain dict that gets serialised and fed back to the LLM
  - Updates GHL CRM and/or local database as a side-effect

Usage:
    from voice.call_functions import FUNCTION_DEFINITIONS, execute_function
    result = execute_function("lookup_caller", {"phone": "+61412345678"}, call_ctx)
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION SCHEMAS (sent to Retell / OpenAI as tool definitions)
# ─────────────────────────────────────────────────────────────────────────────

FUNCTION_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_caller",
            "description": (
                "Look up an existing contact in the CRM by phone number. "
                "Call this at the START of every call to personalise the conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Caller's phone number in E.164 format (e.g. +61412345678)"
                    }
                },
                "required": ["phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead_info",
            "description": (
                "Update the CRM with qualifying information collected during the call. "
                "Call this whenever you learn a new piece of information from the customer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "homeowner_status": {
                        "type": "string",
                        "enum": ["owner", "renter", "unknown"],
                        "description": "Whether the caller owns or rents their property"
                    },
                    "monthly_bill": {
                        "type": "number",
                        "description": "Approximate monthly electricity bill in AUD"
                    },
                    "roof_type": {
                        "type": "string",
                        "description": "Type of roof (e.g. tile, colorbond, flat, metal)"
                    },
                    "roof_age": {
                        "type": "number",
                        "description": "Approximate age of roof in years"
                    },
                    "suburb": {
                        "type": "string",
                        "description": "Customer's suburb"
                    },
                    "state": {
                        "type": "string",
                        "description": "Australian state (WA, QLD, NSW, VIC, SA, TAS, NT, ACT)"
                    },
                    "num_people": {
                        "type": "integer",
                        "description": "Number of people in the household"
                    },
                    "has_ev": {
                        "type": "boolean",
                        "description": "Whether the customer has or plans to get an EV"
                    },
                    "interested_in_battery": {
                        "type": "boolean",
                        "description": "Whether the customer expressed interest in a battery"
                    },
                    "best_time_to_call": {
                        "type": "string",
                        "description": "Customer's preferred callback time"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any other notes from the conversation"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "qualify_and_score",
            "description": (
                "Score the lead based on all information collected so far. "
                "Call this once you have collected homeowner status, bill, and roof info. "
                "Returns a score 1-10 and recommended action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of what you've learned about the customer"
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_assessment",
            "description": (
                "Book a free site assessment appointment for the customer. "
                "Call this when the customer agrees to a site visit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred date (e.g. 'Monday morning', 'this Friday', '2026-03-15')"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred time (e.g. 'morning', 'afternoon', '10am')"
                    },
                    "address": {
                        "type": "string",
                        "description": "Property address for the assessment"
                    }
                },
                "required": ["preferred_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_followup",
            "description": (
                "Send a follow-up message to the customer via SMS or email. "
                "Use this to send a proposal summary, callback confirmation, or info pack."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["sms_callback", "sms_proposal", "sms_info_pack"],
                        "description": "Type of follow-up to send"
                    }
                },
                "required": ["type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_rebate_info",
            "description": (
                "Get current government rebate information for a specific state and system size. "
                "Call this when a customer asks about rebates, incentives, or how much they can save."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Australian state code (WA, QLD, NSW, VIC, SA)"
                    },
                    "system_size_kw": {
                        "type": "number",
                        "description": "Estimated system size in kW (default 6.6 if unknown)"
                    }
                },
                "required": ["state"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": (
                "Transfer the call to a human sales consultant. "
                "Use this for complex technical questions, pricing negotiations, or if the customer specifically requests a human."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for transfer"
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": (
                "End the call gracefully. Call this when the conversation is complete, "
                "the customer wants to end the call, or after booking an appointment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "outcome": {
                        "type": "string",
                        "enum": ["booked_assessment", "callback_requested", "proposal_sent", "not_interested", "transferred", "support_resolved"],
                        "description": "Call outcome"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of the call for CRM notes"
                    }
                },
                "required": ["outcome", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Check if a specific date and time is available for a site assessment via Cal.com. "
                "Call this before offering a specific time slot to the customer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to check in YYYY-MM-DD format (e.g. 2026-03-15)"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time to check in HH:MM 24-hour format (e.g. 10:00)"
                    }
                },
                "required": ["date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": (
                "Create a confirmed Cal.com booking for a solar site assessment. "
                "Only call this after the customer has agreed to a specific date and time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Customer's full name"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number in E.164 format"
                    },
                    "date": {
                        "type": "string",
                        "description": "Booking date in YYYY-MM-DD format"
                    },
                    "time": {
                        "type": "string",
                        "description": "Booking time in HH:MM 24-hour format"
                    },
                    "address": {
                        "type": "string",
                        "description": "Property address for the assessment"
                    }
                },
                "required": ["name", "phone", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_sms_confirmation",
            "description": (
                "Send an SMS confirmation to the customer via Twilio after a booking is made. "
                "Call this immediately after book_appointment succeeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number in E.164 format"
                    },
                    "booking_details": {
                        "type": "string",
                        "description": "Booking summary to include in the SMS (date, time, address)"
                    }
                },
                "required": ["phone", "booking_details"]
            }
        }
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION EXECUTOR
# ─────────────────────────────────────────────────────────────────────────────

def execute_function(name: str, args: dict, call_ctx: dict) -> dict:
    """Execute a named function and return the result to feed back to the LLM.

    Args:
        name: Function name matching FUNCTION_DEFINITIONS
        args: Arguments from the LLM
        call_ctx: Call context with call_id, contact_id, client_id, etc.

    Returns:
        Result dict that gets serialised and sent back to the voice agent
    """
    dispatch = {
        "lookup_caller":      _fn_lookup_caller,
        "update_lead_info":   _fn_update_lead_info,
        "qualify_and_score":  _fn_qualify_and_score,
        "book_assessment":    _fn_book_assessment,
        "send_followup":      _fn_send_followup,
        "get_rebate_info":    _fn_get_rebate_info,
        "transfer_to_human":    _fn_transfer_to_human,
        "end_call":             _fn_end_call,
        "check_availability":   _fn_check_availability,
        "book_appointment":     _fn_book_appointment,
        "send_sms_confirmation": _fn_send_sms_confirmation,
    }

    fn = dispatch.get(name)
    if not fn:
        logger.warning(f"[VOICE FN] Unknown function: {name}")
        return {"error": f"Unknown function: {name}"}

    try:
        result = fn(args, call_ctx)
        logger.info(f"[VOICE FN] {name}({args}) → {result}")
        return result
    except Exception as e:
        logger.error(f"[VOICE FN] {name} failed: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _fn_lookup_caller(args: dict, ctx: dict) -> dict:
    """Look up caller in CRM and local DB by phone number."""
    from memory.database import fetch_one
    from integrations import crm_router

    phone = args.get("phone", "").strip()

    # Check local DB first (fastest)
    local = fetch_one(
        "SELECT * FROM leads WHERE phone = ? ORDER BY created_at DESC LIMIT 1",
        (phone,)
    )

    if local:
        ctx["contact_db_id"] = local.get("id")
        ctx["contact_phone"]  = phone
        ctx["contact_name"]   = local.get("name", "")
        return {
            "found": True,
            "name": local.get("name", "Unknown"),
            "suburb": local.get("suburb", ""),
            "state": local.get("state", ""),
            "previous_score": local.get("qualification_score"),
            "previous_action": local.get("recommended_action"),
            "previous_contact": local.get("contacted_at"),
            "status": local.get("status"),
            "instruction": "Greet them by name. They've called before — acknowledge the previous interaction naturally."
        }

    # Try CRM if configured
    if crm_router.is_configured():
        try:
            contact = crm_router.find_contact_by_phone(phone)
            if contact:
                ctx["ghl_contact_id"] = contact.get("id")
                ctx["contact_phone"]  = phone
                ctx["contact_name"]   = (
                    contact.get("name") or
                    f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip() or
                    f"{contact.get('FirstName', '')} {contact.get('LastName', '')}".strip()
                )
                return {
                    "found": True,
                    "name": ctx["contact_name"],
                    "email": contact.get("email") or contact.get("Email"),
                    "suburb": contact.get("city") or contact.get("MailingCity"),
                    "state": contact.get("state") or contact.get("MailingState"),
                    "source": "crm",
                    "instruction": "Greet them by name. Ask how you can help today."
                }
        except Exception as e:
            logger.error(f"[VOICE FN] CRM lookup failed: {e}")

    ctx["contact_phone"] = phone
    return {
        "found": False,
        "instruction": "New caller. Greet warmly and ask for their name early in the conversation."
    }


def _fn_update_lead_info(args: dict, ctx: dict) -> dict:
    """Update the lead record in DB and GHL with new information."""
    from memory.database import get_conn, insert as db_insert
    from integrations.crm_router import update_contact_field, add_contact_tag, is_configured

    phone  = ctx.get("contact_phone", "")
    db_id  = ctx.get("contact_db_id")
    ghl_id = ctx.get("ghl_contact_id")

    # Store in context for qualification later
    for key, val in args.items():
        ctx.setdefault("lead_data", {})[key] = val
    ctx["lead_data"]["phone"] = phone
    if ctx.get("contact_name"):
        ctx["lead_data"]["name"] = ctx["contact_name"]

    # Update local DB
    with get_conn() as conn:
        if db_id:
            assigns = ", ".join(f"{k} = ?" for k in args if k in
                               ("homeowner_status","monthly_bill","roof_type","roof_age","suburb","state","notes"))
            vals = [args[k] for k in args if k in
                   ("homeowner_status","monthly_bill","roof_type","roof_age","suburb","state","notes")]
            if assigns:
                conn.execute(f"UPDATE leads SET {assigns} WHERE id = ?", vals + [db_id])
        else:
            # Create a stub lead record
            new_id = db_insert("leads", {
                "source": "ghl_webhook",
                "phone": phone,
                "name": ctx.get("contact_name", "Voice Call Lead"),
                **{k: v for k, v in args.items() if k in
                   ("homeowner_status","monthly_bill","roof_type","roof_age","suburb","state","notes")},
                "client_account": ctx.get("client_id", "default"),
            })
            ctx["contact_db_id"] = new_id

    # Mirror to GHL
    if ghl_id and is_configured():
        field_map = {
            "homeowner_status":     "homeowner_status",
            "monthly_bill":         "monthly_electricity_bill",
            "roof_type":            "roof_type",
            "roof_age":             "roof_age_years",
            "interested_in_battery":"interested_in_battery",
            "has_ev":               "has_electric_vehicle",
            "best_time_to_call":    "best_time_to_call",
        }
        for arg_key, ghl_field in field_map.items():
            if arg_key in args:
                update_contact_field(ghl_id, ghl_field, str(args[arg_key]))

        if args.get("interested_in_battery"):
            add_contact_tag(ghl_id, "interested-battery")
        if args.get("has_ev"):
            add_contact_tag(ghl_id, "has-ev")

    updated = list(args.keys())
    return {"updated": updated, "status": "CRM updated"}


def _fn_qualify_and_score(args: dict, ctx: dict) -> dict:
    """Score the lead based on collected information."""
    from agents.qualification_agent import qualify

    lead_data = ctx.get("lead_data", {})
    if ctx.get("contact_name"):
        lead_data["name"] = ctx["contact_name"]

    db_id = ctx.get("contact_db_id")
    result = qualify(lead_data, db_id)

    score  = result.get("score", 5)
    action = result.get("recommended_action", "nurture")

    # Store score in context
    ctx["lead_score"]  = score
    ctx["lead_action"] = action

    # Build voice-friendly response guidance
    if score >= 7:
        guidance = "HIGH VALUE LEAD. Enthusiastically confirm the assessment booking. Mention the priority slot."
    elif score >= 5:
        guidance = "MEDIUM VALUE. Book an assessment or arrange a callback. Keep warm."
    else:
        guidance = "LOW VALUE. Be polite, offer info pack, note they can call back if situation changes."

    return {
        "score": score,
        "action": action,
        "reason": result.get("reason", ""),
        "guidance": guidance,
    }


def _fn_book_assessment(args: dict, ctx: dict) -> dict:
    """Book a site assessment and create GHL task."""
    from integrations.crm_router import create_task, add_contact_tag, is_configured
    from memory.database import get_conn

    preferred = args.get("preferred_date", "as soon as possible")
    pref_time = args.get("preferred_time", "morning")
    address   = args.get("address", ctx.get("lead_data", {}).get("suburb", "Customer's home"))
    ghl_id    = ctx.get("ghl_contact_id")

    # Calculate next business day as task due date
    due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    task_title = f"Site Assessment — {address} — {preferred} {pref_time}"

    if ghl_id and is_configured():
        create_task(ghl_id, task_title, due)
        add_contact_tag(ghl_id, "assessment-booked")
        add_contact_tag(ghl_id, "voice-ai-booked")

    # Update lead status
    db_id = ctx.get("contact_db_id")
    if db_id:
        with get_conn() as conn:
            conn.execute(
                "UPDATE leads SET status = 'contacted', notes = notes || ? WHERE id = ?",
                (f" | Assessment booked: {preferred} {pref_time} @ {address}", db_id)
            )

    ctx["call_outcome"] = "booked_assessment"

    # Notify via Slack
    try:
        from notifications.slack_notifier import _post
        name = ctx.get("contact_name", "Customer")
        _post(f"📅 *Assessment Booked via Voice AI*\n*Customer:* {name}\n*Time:* {preferred} {pref_time}\n*Address:* {address}\n*Score:* {ctx.get('lead_score', '?')}/10")
    except Exception:
        pass

    return {
        "booked": True,
        "date": preferred,
        "time": pref_time,
        "address": address,
        "confirmation": f"Assessment scheduled for {preferred} {pref_time} at {address}. We'll send an SMS confirmation shortly.",
        "next_step": "Send SMS confirmation, then end the call warmly."
    }


def _fn_send_followup(args: dict, ctx: dict) -> dict:
    """Send an SMS follow-up to the customer."""
    from integrations.crm_router import send_sms, is_configured
    from notifications.slack_notifier import _post

    ghl_id     = ctx.get("ghl_contact_id")
    ftype      = args.get("type", "sms_callback")
    name       = ctx.get("contact_name", "there")
    company    = ctx.get("company_name", "SunTech Solar")
    phone_num  = ctx.get("company_phone", "08 9XXX XXXX")

    messages = {
        "sms_callback": (
            f"Hi {name.split()[0] if name else 'there'}! Thanks for calling {company}. "
            f"One of our solar consultants will call you back shortly to discuss your quote. "
            f"Any questions? Reply here or call us on {phone_num}."
        ),
        "sms_proposal": (
            f"Hi {name.split()[0] if name else 'there'}! As discussed, here's what to expect from your {company} proposal: "
            f"personalised system design, exact pricing after rebates, and a payback period calculation. "
            f"We'll email it within 48 hours of your assessment. 🌞"
        ),
        "sms_info_pack": (
            f"Hi {name.split()[0] if name else 'there'}! Thanks for your interest in solar with {company}. "
            f"We'll email you our info pack shortly covering system options, pricing, and government rebates. "
            f"Questions? Call us: {phone_num}"
        ),
    }

    message = messages.get(ftype, messages["sms_callback"])

    sent = False
    if ghl_id and is_configured():
        result = send_sms(ghl_id, message)
        sent = result is not None

    return {
        "sent": sent,
        "type": ftype,
        "message_preview": message[:80] + "...",
        "note": "SMS queued. Continue conversation naturally."
    }


def _fn_get_rebate_info(args: dict, ctx: dict) -> dict:
    """Return rebate information for the customer's state."""
    from knowledge.company_kb import get_rebate_for_state

    state      = (args.get("state") or ctx.get("lead_data", {}).get("state") or "WA").upper()
    system_kw  = float(args.get("system_size_kw", 6.6))

    summary = get_rebate_for_state(state, system_kw)
    return {
        "state": state,
        "system_size_kw": system_kw,
        "rebate_summary": summary,
        "voice_note": "Share the rebate total naturally — e.g. 'So for a 6.6kW system in WA, you'd be looking at roughly $3,000 off upfront from the federal rebate alone.'"
    }


def _fn_transfer_to_human(args: dict, ctx: dict) -> dict:
    """Flag call for human takeover."""
    from notifications.slack_notifier import _post

    reason = args.get("reason", "Customer requested human agent")
    name   = ctx.get("contact_name", "Customer")
    phone  = ctx.get("contact_phone", "Unknown")

    try:
        _post(
            f"🔔 *TRANSFER REQUEST — Voice AI*\n"
            f"*Customer:* {name} ({phone})\n"
            f"*Reason:* {reason}\n"
            f"*Score:* {ctx.get('lead_score', '?')}/10\n"
            f"*Please call them back within 5 minutes.*"
        )
    except Exception:
        pass

    ctx["call_outcome"] = "transferred"
    return {
        "transfer_initiated": True,
        "message": "I'm going to connect you with one of our specialists right now. Please hold for just a moment.",
        "reason": reason,
    }


def _fn_end_call(args: dict, ctx: dict) -> dict:
    """Finalise call record and trigger post-call processing."""
    from memory.database import get_conn

    outcome = args.get("outcome", "unknown")
    summary = args.get("summary", "")
    db_id   = ctx.get("contact_db_id")

    ctx["call_outcome"] = outcome
    ctx["call_summary"] = summary

    if db_id:
        with get_conn() as conn:
            conn.execute(
                "UPDATE leads SET contacted_at = ?, notes = notes || ? WHERE id = ?",
                (datetime.utcnow().isoformat(), f" | Voice call: {outcome}. {summary}", db_id)
            )

    farewells = {
        "booked_assessment": "We look forward to visiting you. You'll get an SMS confirmation in the next few minutes. Have a great day!",
        "callback_requested": "Perfect — one of our team will give you a call back shortly. Have a wonderful day!",
        "proposal_sent":      "Keep an eye on your inbox — we'll have the proposal to you within 48 hours. Have a great day!",
        "not_interested":     "No worries at all. If your situation ever changes, we're always here to help. Have a lovely day!",
        "transferred":        "I'll have someone with you shortly. Thank you for your patience.",
        "support_resolved":   "Glad we could sort that out for you. Have a wonderful day — enjoy your solar!",
    }

    return {
        "end_call": True,
        "farewell": farewells.get(outcome, "Thank you for calling. Have a wonderful day!"),
        "outcome": outcome,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CAL.COM + TWILIO FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _fn_check_availability(args: dict, ctx: dict) -> dict:
    """Check Cal.com slot availability for a given date and time.

    Args:
        args: date (YYYY-MM-DD), time (HH:MM)
        ctx: Call context

    Returns:
        Dict with available bool and message for the agent
    """
    import os
    import requests as _requests

    api_key      = os.getenv("CALCOM_API_KEY", "")
    event_type   = os.getenv("CALCOM_EVENT_TYPE_ID", "")

    if not api_key or not event_type:
        return {"available": True, "message": "Availability check unavailable — assume slot is open."}

    date = args.get("date", "")
    time = args.get("time", "09:00")

    try:
        start = f"{date}T{time}:00Z"
        # Check one hour window
        end_h = str(int(time.split(":")[0]) + 1).zfill(2)
        end   = f"{date}T{end_h}:{time.split(':')[1]}:00Z"

        resp = _requests.get(
            "https://api.cal.com/v1/slots/available",
            params={
                "apiKey":      api_key,
                "eventTypeId": event_type,
                "startTime":   start,
                "endTime":     end,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            slots = resp.json().get("slots", {})
            available = bool(slots.get(date))
            return {
                "available": available,
                "date":      date,
                "time":      time,
                "message":   f"{'Available' if available else 'Not available'} on {date} at {time}.",
            }
        logger.error(f"[VOICE FN] Cal.com availability check failed: {resp.status_code}")
        return {"available": True, "message": "Could not verify — offer the slot and confirm with team."}
    except Exception as e:
        logger.error(f"[VOICE FN] check_availability error: {e}")
        return {"available": True, "message": "Could not verify — offer the slot and confirm with team."}


def _fn_book_appointment(args: dict, ctx: dict) -> dict:
    """Create a Cal.com booking for a solar site assessment.

    Args:
        args: name, phone, date (YYYY-MM-DD), time (HH:MM), address (optional)
        ctx: Call context

    Returns:
        Dict with booking confirmation details
    """
    import os
    import requests as _requests

    api_key    = os.getenv("CALCOM_API_KEY", "")
    event_type = os.getenv("CALCOM_EVENT_TYPE_ID", "")

    name    = args.get("name", ctx.get("contact_name", "Solar Lead"))
    phone   = args.get("phone", ctx.get("contact_phone", ""))
    date    = args.get("date", "")
    time    = args.get("time", "09:00")
    address = args.get("address", ctx.get("lead_data", {}).get("suburb", ""))

    ctx["call_outcome"] = "booked_assessment"

    if not api_key or not event_type:
        logger.warning("[VOICE FN] Cal.com not configured — logging booking locally only")
        return {
            "booked":       False,
            "confirmation": f"Noted {name} for {date} at {time}. Team will confirm via SMS.",
            "note":         "Cal.com not configured — manual booking required.",
        }

    try:
        start_iso = f"{date}T{time}:00Z"
        payload = {
            "eventTypeId": int(event_type),
            "start":       start_iso,
            "responses": {
                "name":  name,
                "email": ctx.get("lead_data", {}).get("email", f"{phone}@placeholder.com"),
                "phone": phone,
            },
            "timeZone": "Australia/Perth",
            "language": "en",
            "metadata": {"address": address, "source": "voice-ai"},
        }
        resp = _requests.post(
            "https://api.cal.com/v1/bookings",
            params={"apiKey": api_key},
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            booking = resp.json()
            booking_id = booking.get("id", "unknown")
            print(f"[VOICE FN] Cal.com booking created: {booking_id} for {name} on {date} {time}")
            return {
                "booked":      True,
                "booking_id":  booking_id,
                "date":        date,
                "time":        time,
                "name":        name,
                "confirmation": f"Confirmed! Assessment booked for {name} on {date} at {time}. Confirmation SMS on its way.",
            }
        logger.error(f"[VOICE FN] Cal.com booking failed: {resp.status_code} {resp.text[:200]}")
        return {
            "booked":       False,
            "confirmation": f"We'll lock in {date} at {time} for you — team will confirm by SMS shortly.",
        }
    except Exception as e:
        logger.error(f"[VOICE FN] book_appointment error: {e}")
        return {"booked": False, "confirmation": "Booking noted — team will confirm by SMS."}


def _fn_send_sms_confirmation(args: dict, ctx: dict) -> dict:
    """Send a booking confirmation SMS via Twilio.

    Args:
        args: phone, booking_details
        ctx: Call context

    Returns:
        Dict with sent status
    """
    import os
    import requests as _requests
    from requests.auth import HTTPBasicAuth

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    phone           = args.get("phone", ctx.get("contact_phone", ""))
    booking_details = args.get("booking_details", "")
    name            = (ctx.get("contact_name") or "").split()[0] or "there"

    message = (
        f"Hi {name}! Your free solar assessment with {ctx.get('company_name', 'our team')} "
        f"is confirmed. {booking_details} "
        f"Reply STOP to opt out."
    )

    if not account_sid or not auth_token or not from_number:
        logger.warning("[VOICE FN] Twilio not configured — SMS not sent")
        return {"sent": False, "reason": "Twilio not configured"}

    try:
        resp = _requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data={"From": from_number, "To": phone, "Body": message},
            auth=HTTPBasicAuth(account_sid, auth_token),
            timeout=10,
        )
        if resp.status_code in (200, 201):
            sid = resp.json().get("sid", "")
            print(f"[VOICE FN] SMS sent to {phone}: {sid}")
            return {"sent": True, "sid": sid, "preview": message[:80]}
        logger.error(f"[VOICE FN] Twilio SMS failed: {resp.status_code} {resp.text[:200]}")
        return {"sent": False, "reason": f"Twilio error {resp.status_code}"}
    except Exception as e:
        logger.error(f"[VOICE FN] send_sms_confirmation error: {e}")
        return {"sent": False, "reason": str(e)}
