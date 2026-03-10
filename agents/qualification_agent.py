"""Lead Qualification Agent — Solar lead scoring using GPT-4o.

Scores solar leads 1-10 based on four key signals:
  1. Homeowner status (owner = high, renter = low)
  2. Monthly electricity bill (>$300 = high, <$150 = low)
  3. Roof type and age (tile/colorbond <15yr = ideal)
  4. Location in Australia (sunlight hours, grid costs)

Returns: score (1-10), reason (2 sentences), recommended_action
"""

import json
import logging
from datetime import datetime
from memory.database import update, fetch_one
from notifications.slack_notifier import alert_new_lead, alert_high_value_lead
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a solar lead qualification specialist for an Australian solar company.
Score leads based on their solar installation potential.

Scoring criteria:
- Homeowner status: owner = +3 points, renter = 0-1 points
- Monthly electricity bill: >$300 = +3 pts, $200-300 = +2 pts, $150-200 = +1 pt, <$150 = 0 pts
- Roof: tile or colorbond <15 years = +2 pts, older or flat = +1 pt, unknown = +1 pt
- Location: high sun states (QLD, WA, SA, NSW) = +2 pts, VIC/TAS = +1 pt

Return ONLY valid JSON:
{
  "score": <integer 1-10>,
  "reason": "<exactly 2 sentences explaining the score>",
  "recommended_action": "<call_now OR nurture OR disqualify>",
  "key_signals": ["<signal 1>", "<signal 2>"],
  "risk_flags": ["<flag 1>"]
}

recommended_action rules:
- call_now: score >= 7 (high value, act immediately)
- nurture: score 5-6 (worth warming up)
- disqualify: score <= 4 (not worth pursuing)"""


def qualify(lead_data: dict, lead_id: int = None) -> dict:
    """Score a solar lead and update the database record.

    Args:
        lead_data: Dict with name, homeowner_status, monthly_bill,
                   roof_type, roof_age, suburb, state, email, phone
        lead_id: Optional database lead id to update

    Returns:
        Dict with score, reason, recommended_action, key_signals
    """
    name = lead_data.get("name", "Unknown")
    print(f"[QUALIFICATION] Scoring lead: {name}")

    if not config.is_configured():
        logger.warning("[QUALIFICATION] No OpenAI key — using rule-based scoring")
        result = _rule_based_score(lead_data)
    else:
        result = _ai_score(lead_data)

    score = result.get("score", 5)
    action = result.get("recommended_action", "nurture")

    if lead_id:
        _save_to_lead(lead_id, result)
        logger.info(f"[QUALIFY] Lead {lead_id} scored {score} — {action}")

    _send_alerts(name, score, result.get("reason", ""), action, lead_data)

    # Fire an outbound call for hot leads when Retell is configured
    if action == "call_now" and lead_data.get("phone"):
        _trigger_outbound_call(lead_data, lead_id)

    print(f"[QUALIFICATION] {name}: {score}/10 → {action}")
    return result


def _ai_score(lead_data: dict) -> dict:
    """Use GPT-4o to score the lead.

    Args:
        lead_data: Lead information dict

    Returns:
        Parsed scoring result dict
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        lead_summary = _format_lead(lead_data)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Score this lead:\n\n{lead_summary}"},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"[QUALIFICATION] JSON parse error: {e}")
        return _rule_based_score(lead_data)
    except Exception as e:
        logger.error(f"[QUALIFICATION] OpenAI error: {e}")
        return _rule_based_score(lead_data)


def _rule_based_score(lead_data: dict) -> dict:
    """Fallback rule-based scoring when OpenAI unavailable.

    Args:
        lead_data: Lead information dict

    Returns:
        Scored result dict
    """
    score = 0
    signals = []

    homeowner = (lead_data.get("homeowner_status") or "").lower()
    if homeowner == "owner":
        score += 3
        signals.append("Homeowner")
    elif homeowner == "renter":
        score += 0
        signals.append("Renter — low priority")
    else:
        score += 1

    bill = lead_data.get("monthly_bill") or 0
    if bill > 300:
        score += 3
        signals.append(f"High bill ${bill}/mo")
    elif bill > 200:
        score += 2
        signals.append(f"Medium bill ${bill}/mo")
    elif bill > 150:
        score += 1
    else:
        signals.append("Low bill — may not see value")

    roof = (lead_data.get("roof_type") or "").lower()
    age = lead_data.get("roof_age") or 20
    if roof in ("tile", "colorbond") and age < 15:
        score += 2
        signals.append("Ideal roof")
    else:
        score += 1

    state = (lead_data.get("state") or "").upper()
    if state in ("QLD", "WA", "SA", "NSW", "NT"):
        score += 2
        signals.append(f"High sun state ({state})")
    else:
        score += 1

    score = min(10, max(1, score))
    if score >= 7:
        action = "call_now"
    elif score >= 5:
        action = "nurture"
    else:
        action = "disqualify"

    return {
        "score": score,
        "reason": f"Rule-based score of {score}/10 based on homeowner status, electricity bill, roof type, and location. {', '.join(signals[:2])}.",
        "recommended_action": action,
        "key_signals": signals,
        "risk_flags": [],
        "method": "rule_based",
    }


def _format_lead(lead_data: dict) -> str:
    """Format lead data as readable text for GPT prompt."""
    fields = [
        f"Name: {lead_data.get('name', 'Unknown')}",
        f"Homeowner status: {lead_data.get('homeowner_status', 'unknown')}",
        f"Monthly electricity bill: ${lead_data.get('monthly_bill', 'unknown')}",
        f"Roof type: {lead_data.get('roof_type', 'unknown')}",
        f"Roof age: {lead_data.get('roof_age', 'unknown')} years",
        f"Suburb: {lead_data.get('suburb', 'unknown')}",
        f"State: {lead_data.get('state', 'unknown')}",
    ]
    return "\n".join(fields)


def qualify_from_call(call_id: str) -> dict:
    """Read extracted call data from leads table and run qualification scoring.

    Args:
        call_id: Retell/voice call ID linked to a lead record

    Returns:
        Qualification result dict, or error dict if lead not found
    """
    lead = fetch_one("SELECT * FROM leads WHERE call_id = ?", (call_id,))
    if not lead:
        logger.warning(f"[QUALIFICATION] No lead found for call_id={call_id}")
        return {"error": f"No lead found for call_id={call_id}"}

    lead_data = {
        "name": lead.get("name"),
        "homeowner_status": lead.get("homeowner_status") or lead.get("homeowner"),
        "monthly_bill": lead.get("monthly_bill"),
        "roof_type": lead.get("roof_type"),
        "roof_age": lead.get("roof_age"),
        "suburb": lead.get("suburb"),
        "state": lead.get("state"),
        "email": lead.get("email"),
        "phone": lead.get("phone"),
    }

    print(f"[QUALIFICATION] qualify_from_call: call_id={call_id}, lead_id={lead['id']}")
    return qualify(lead_data, lead_id=lead["id"])


def _save_to_lead(lead_id: int, result: dict):
    """Update the lead record with qualification results."""
    update("leads", lead_id, {
        "qualification_score": result.get("score"),
        "score": result.get("score"),
        "score_reason": result.get("reason"),
        "recommended_action": result.get("recommended_action"),
        "status": "qualified",
    })


def _trigger_outbound_call(lead_data: dict, lead_id: int | None = None):
    """Initiate a Retell outbound call to a hot lead.

    Looks up the client's Retell agent from the company profile,
    then fires a call with lead context injected as metadata.

    Args:
        lead_data: Lead dict with phone, name, client_account, etc.
        lead_id: Optional database lead id for metadata
    """
    if not config.retell_configured():
        logger.debug("[QUALIFICATION] Retell not configured — skipping outbound call")
        return

    try:
        from voice.retell_client import create_outbound_call
        from knowledge.company_kb import get_company

        client_id = lead_data.get("client_account") or config.DEFAULT_CLIENT_ID
        profile   = get_company(client_id) or {}
        agent_id  = profile.get("retell_agent_id")
        from_phone = profile.get("phone")

        if not agent_id or not from_phone:
            logger.warning(f"[QUALIFICATION] No Retell agent/phone for client '{client_id}' — skipping outbound call")
            return

        to_phone = lead_data.get("phone", "")
        if not to_phone.startswith("+"):
            to_phone = "+61" + to_phone.lstrip("0")

        metadata = {
            "lead_id":    lead_id,
            "client_id":  client_id,
            "lead_name":  lead_data.get("name", ""),
            "call_type":  "outbound_callback",
        }

        result = create_outbound_call(from_phone, to_phone, agent_id, metadata)
        if result:
            call_id = result.get("call_id", "?")
            print(f"[QUALIFICATION] Outbound call fired: {to_phone} (call={call_id})")
            if lead_id:
                update("leads", lead_id, {"status": "called", "notes": f"Outbound call initiated: {call_id}"})
        else:
            logger.warning(f"[QUALIFICATION] Outbound call failed for {to_phone}")

    except Exception as e:
        logger.error(f"[QUALIFICATION] Outbound call error: {e}")


def _send_alerts(name: str, score: float, reason: str, action: str, lead_data: dict):
    """Send appropriate Slack alerts based on lead score."""
    alert_new_lead(name, score, reason, action)
    if score >= 7:
        alert_high_value_lead(name, score, {
            "suburb": lead_data.get("suburb"),
            "state": lead_data.get("state"),
            "monthly_bill": f"${lead_data.get('monthly_bill', '?')}/mo",
            "homeowner": lead_data.get("homeowner_status"),
            "phone": lead_data.get("phone"),
            "email": lead_data.get("email"),
        })
