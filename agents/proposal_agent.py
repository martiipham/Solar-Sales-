"""Proposal Agent — Client proposal generator for solar retainers.

Generates 3-section proposals:
  1. Current State (their problem, quantified)
  2. Future State (what the system delivers)
  3. Investment (tiered: $1,500 / $2,000 / $2,500 AUD/month)

Saves to proposals/ folder as {client_name}_{date}.txt
"""

import logging
import os
from datetime import datetime
from pathlib import Path
import config

logger = logging.getLogger(__name__)

PROPOSALS_DIR = Path("proposals")
PROPOSALS_DIR.mkdir(exist_ok=True)

PROPOSAL_PROMPT = """You are a B2B proposal writer for an AI automation consultancy.
Write in plain Australian business English. Confident but not arrogant.
Focus on the client's outcome, not our technology.
Use specific numbers where possible.
No corporate jargon. No bullet point overload."""


def generate(
    client_name: str,
    pain_points: list,
    current_process: str,
    estimated_leads_per_month: int,
) -> dict:
    """Generate a client proposal and save to proposals/ folder.

    Args:
        client_name: Solar company name
        pain_points: List of specific pain points identified
        current_process: How they currently handle leads
        estimated_leads_per_month: Their approximate monthly lead volume

    Returns:
        Dict with file_path, proposal_text, tiers
    """
    print(f"[PROPOSAL] Generating proposal for: {client_name}")

    if config.is_configured():
        proposal_text = _ai_generate(client_name, pain_points, current_process, estimated_leads_per_month)
    else:
        proposal_text = _template_generate(client_name, pain_points, current_process, estimated_leads_per_month)

    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = client_name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_{date_str}.txt"
    file_path = PROPOSALS_DIR / filename

    with open(file_path, "w") as f:
        f.write(proposal_text)

    print(f"[PROPOSAL] Saved to: {file_path}")
    return {
        "file_path": str(file_path),
        "client_name": client_name,
        "proposal_text": proposal_text,
        "generated_at": datetime.now().isoformat(),
    }


def _ai_generate(client_name: str, pain_points: list, current_process: str, leads: int) -> str:
    """Use GPT-4o to generate the proposal.

    Args:
        client_name: Solar company name
        pain_points: List of pain points
        current_process: Their current lead handling process
        leads: Monthly lead volume estimate

    Returns:
        Full proposal text
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        prompt = f"""Write a business proposal for {client_name}, an Australian solar company.

Pain points:
{chr(10).join(f'- {p}' for p in pain_points)}

Current process: {current_process}
Monthly leads: approximately {leads}

Structure the proposal with exactly 3 sections:
1. Current State — their problem, quantified with estimated cost of lost leads
2. Future State — what our AI automation system delivers, with specific metrics
3. Investment — three tiers:
   Starter: $1,500/month (basic automation)
   Growth: $2,000/month (full automation + reporting)
   Premium: $2,500/month (custom integrations + dedicated support)

End with a clear next step (15-minute call, no commitment)."""

        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": PROPOSAL_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=1200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[PROPOSAL] OpenAI error: {e}")
        return _template_generate(client_name, pain_points, current_process, leads)


def _template_generate(client_name: str, pain_points: list, current_process: str, leads: int) -> str:
    """Generate a template-based proposal when OpenAI unavailable.

    Args:
        client_name: Solar company name
        pain_points: List of pain points
        current_process: Their current lead handling process
        leads: Monthly lead volume estimate

    Returns:
        Template-filled proposal text
    """
    date_str = datetime.now().strftime("%d %B %Y")
    pain_list = "\n".join(f"  - {p}" for p in pain_points) if pain_points else "  - Slow lead response times\n  - Leads going cold before contact"
    lost_leads = max(1, round(leads * 0.25))
    lost_revenue = lost_leads * 8000

    return f"""PROPOSAL: AI LEAD AUTOMATION SYSTEM
{client_name} | Prepared {date_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION 1 — CURRENT STATE

{client_name} currently handles approximately {leads} new enquiries per month.
Current lead process: {current_process or 'Manual follow-up by sales team'}

Pain points identified:
{pain_list}

With an industry average response window of 4+ hours, research shows that
25% of solar leads contact a competitor before receiving a callback.

Estimated impact for {client_name}:
  Lost leads per month: ~{lost_leads}
  Average solar system value: $8,000–12,000
  Estimated monthly revenue at risk: ${lost_revenue:,}–${lost_leads * 12000:,} AUD

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION 2 — FUTURE STATE

With our AI Lead Automation System integrated into your GoHighLevel CRM:

  ✓ Every new lead receives an automated response in under 5 minutes, 24/7
  ✓ AI voice agent calls back warm leads during business hours
  ✓ Leads are scored and prioritised so your team focuses on hot prospects
  ✓ No-shows are automatically re-engaged with follow-up sequences
  ✓ Weekly reports show exactly how many leads were saved and converted

Expected outcomes in 90 days:
  → Response time: 4+ hours → under 5 minutes
  → Lead contact rate: +35–50%
  → Leads not lost to competitors: estimated {lost_leads} additional/month
  → Pipeline value recovered: ${lost_revenue:,}+ AUD/month

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECTION 3 — INVESTMENT

All plans include setup, integration, training, and monthly reporting.

STARTER — $1,500/month AUD
  Automated lead response (SMS + email)
  Basic lead scoring
  Monthly performance report
  GHL integration
  Best for: teams < 5 salespeople

GROWTH — $2,000/month AUD (recommended)
  Everything in Starter, plus:
  AI voice callback system
  Pipeline stage automation
  Weekly Slack/email reports
  Quarterly strategy review
  Best for: 5–10 salespeople

PREMIUM — $2,500/month AUD
  Everything in Growth, plus:
  Custom workflow development
  Dedicated account manager
  Priority support (same-day response)
  Monthly 1:1 strategy call
  Best for: 10+ salespeople or multi-location

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT STEP

Book a 15-minute walkthrough — I'll show you exactly how the system works
using your current GHL setup. No commitment, no sales pressure.

Martin Pham
AI Automation Consultant | Perth, WA
"""
