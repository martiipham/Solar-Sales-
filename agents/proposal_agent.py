"""Proposal Agent — Proposal generator for solar leads and retainer clients.

Two modes:
  1. generate()            — B2B retainer proposal for solar SMEs (automation service)
  2. generate_from_lead()  — Solar installation proposal for homeowner leads (HTML email)

Solar installation proposals include:
  - System size recommendation based on monthly bill
  - Estimated annual savings (AUD)
  - Payback period (years)
  - STC rebate calculation by state
  - Generic panel + inverter recommendation
  - Installed price range
"""

import logging
import os
from datetime import datetime
from pathlib import Path
import config
from memory.database import fetch_one, insert

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


# ─── Solar Installation Proposal (for homeowner leads) ───────────────────────

# STC zone multipliers (Clean Energy Regulator zones 1-4, AU 2026)
_STC_ZONE = {
    "NT": 1.622, "QLD": 1.536, "WA": 1.536, "SA": 1.536,
    "NSW": 1.382, "ACT": 1.382, "VIC": 1.185, "TAS": 1.000,
}

# Average peak sun hours by state
_PEAK_SUN = {
    "NT": 5.5, "QLD": 5.0, "WA": 5.2, "SA": 4.8,
    "NSW": 4.5, "ACT": 4.2, "VIC": 4.0, "TAS": 3.5,
}

_DEEMING_YEARS = 5          # 2031 - 2026
_STC_PRICE_AUD = 38         # spot price approximation
_TARIFF_AUD_KWH = 0.30      # average AU retail electricity rate
_SELF_CONSUMPTION = 0.75    # fraction of solar consumed on-site
_COST_PER_KW = 1_050        # installed cost per kW (mid-market AU 2026)


def _calc_system_size(monthly_bill: float, state: str) -> float:
    """Estimate recommended system size in kW from monthly bill and state.

    Args:
        monthly_bill: Average monthly electricity bill in AUD
        state: Two-letter AU state code

    Returns:
        Recommended system size in kW, rounded to nearest 0.5
    """
    monthly_kwh = monthly_bill / _TARIFF_AUD_KWH
    daily_kwh = monthly_kwh / 30
    peak_sun = _PEAK_SUN.get(state.upper(), 4.5)
    raw_kw = daily_kwh / (peak_sun * 0.78)
    return max(3.0, round(raw_kw * 2) / 2)  # round to nearest 0.5, min 3 kW


def _calc_stc_rebate(system_kw: float, state: str) -> int:
    """Calculate Small-scale Technology Certificate rebate in AUD.

    Args:
        system_kw: System size in kW
        state: Two-letter AU state code

    Returns:
        Estimated STC rebate in AUD (rounded to nearest $100)
    """
    zone = _STC_ZONE.get(state.upper(), 1.185)
    stcs = round(system_kw * _DEEMING_YEARS * zone)
    return round(stcs * _STC_PRICE_AUD / 100) * 100


def _calc_savings_and_payback(system_kw: float, state: str, stc_rebate: int) -> tuple:
    """Calculate annual savings and payback period.

    Args:
        system_kw: System size in kW
        state: Two-letter AU state code
        stc_rebate: STC rebate amount in AUD

    Returns:
        Tuple of (est_annual_savings_aud, payback_years)
    """
    peak_sun = _PEAK_SUN.get(state.upper(), 4.5)
    annual_kwh = system_kw * peak_sun * 365 * 0.80      # 80% performance ratio
    savings = round(annual_kwh * _SELF_CONSUMPTION * _TARIFF_AUD_KWH)
    gross_cost = round(system_kw * _COST_PER_KW)
    net_cost = max(1, gross_cost - stc_rebate)
    payback = round(net_cost / max(1, savings), 1)
    return savings, payback


def _build_solar_html(lead: dict, system_kw: float, annual_savings: int,
                      payback_years: float, stc_rebate: int) -> str:
    """Render a solar installation proposal as an HTML email string.

    Args:
        lead: Lead data dict from the database
        system_kw: Recommended system size in kW
        annual_savings: Estimated annual savings in AUD
        payback_years: Estimated payback period in years
        stc_rebate: STC government rebate in AUD

    Returns:
        HTML string ready to send as an email body
    """
    name = lead.get("name") or "there"
    first_name = name.split()[0]
    suburb = lead.get("suburb") or ""
    state = (lead.get("state") or "").upper()
    monthly_bill = lead.get("monthly_bill") or 0

    gross_cost = round(system_kw * _COST_PER_KW)
    net_cost = gross_cost - stc_rebate
    price_low = round(net_cost * 0.90 / 100) * 100
    price_high = round(net_cost * 1.10 / 100) * 100

    # Panel/inverter size label
    if system_kw <= 6.6:
        panel_str = "6.6 kW (20 × 330W panels)"
        inv_str = "5 kW single-phase string inverter"
    elif system_kw <= 10:
        panel_str = f"{system_kw:.1f} kW (~{round(system_kw / 0.415)} × 415W panels)"
        inv_str = "8–10 kW single-phase inverter"
    else:
        panel_str = f"{system_kw:.1f} kW (~{round(system_kw / 0.415)} × 415W panels)"
        inv_str = "Three-phase inverter (10+ kW)"

    date_str = datetime.now().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Your Solar Proposal — {suburb or state}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:0; }}
    .wrap {{ max-width:600px; margin:30px auto; background:#fff; border-radius:8px;
             overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.1); }}
    .header {{ background:#F59E0B; padding:28px 32px; color:#fff; }}
    .header h1 {{ margin:0; font-size:22px; }}
    .header p {{ margin:4px 0 0; font-size:14px; opacity:.9; }}
    .body {{ padding:28px 32px; color:#333; line-height:1.6; }}
    h2 {{ color:#F59E0B; font-size:16px; margin:24px 0 8px; border-bottom:2px solid #FEF3C7;
          padding-bottom:4px; }}
    .kpi-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:16px 0; }}
    .kpi {{ background:#FFFBEB; border:1px solid #FDE68A; border-radius:6px;
             padding:14px 16px; text-align:center; }}
    .kpi .val {{ font-size:26px; font-weight:bold; color:#D97706; }}
    .kpi .lbl {{ font-size:12px; color:#6B7280; margin-top:2px; }}
    table {{ width:100%; border-collapse:collapse; margin:12px 0; font-size:14px; }}
    th {{ background:#FEF3C7; text-align:left; padding:8px 10px; }}
    td {{ padding:8px 10px; border-bottom:1px solid #f0f0f0; }}
    .cta {{ background:#F59E0B; color:#fff; text-align:center; padding:20px 32px; }}
    .cta a {{ color:#fff; font-weight:bold; font-size:16px; text-decoration:none; }}
    .footer {{ padding:16px 32px; font-size:11px; color:#9CA3AF; text-align:center; }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>Your Solar Proposal</h1>
    <p>Prepared for {name} &nbsp;|&nbsp; {suburb}{', ' + state if state else ''} &nbsp;|&nbsp; {date_str}</p>
  </div>
  <div class="body">
    <p>Hi {first_name},</p>
    <p>Thanks for your enquiry. Based on your average electricity bill of
    <strong>${monthly_bill:.0f}/month</strong>, here's what a solar system
    could do for your home.</p>

    <h2>Recommended System</h2>
    <div class="kpi-grid">
      <div class="kpi"><div class="val">{system_kw:.1f} kW</div><div class="lbl">System size</div></div>
      <div class="kpi"><div class="val">${annual_savings:,}</div><div class="lbl">Est. annual savings</div></div>
      <div class="kpi"><div class="val">{payback_years} yrs</div><div class="lbl">Payback period</div></div>
      <div class="kpi"><div class="val">${stc_rebate:,}</div><div class="lbl">Govt. rebate (STC)</div></div>
    </div>

    <h2>Equipment (Brand-Agnostic Recommendation)</h2>
    <table>
      <tr><th>Component</th><th>Specification</th></tr>
      <tr><td>Solar panels</td><td>{panel_str}</td></tr>
      <tr><td>Inverter</td><td>{inv_str}</td></tr>
      <tr><td>Monitoring</td><td>App-based real-time monitoring included</td></tr>
      <tr><td>Warranty</td><td>10-yr product, 25-yr performance (panels)</td></tr>
    </table>

    <h2>Investment</h2>
    <table>
      <tr><th>Item</th><th>Amount (AUD)</th></tr>
      <tr><td>Gross system cost</td><td>${gross_cost:,}</td></tr>
      <tr><td>Government STC rebate</td><td>− ${stc_rebate:,}</td></tr>
      <tr><td><strong>Estimated out-of-pocket</strong></td>
          <td><strong>${price_low:,} – ${price_high:,}</strong></td></tr>
    </table>
    <p style="font-size:13px;color:#6B7280;">
      Pricing is an estimate based on current market rates. Final price depends on
      roof complexity, metering, and installer. Get 2–3 quotes to compare.
    </p>

    <h2>How the Rebate Works</h2>
    <p style="font-size:14px;">
      Australia's Small-scale Technology Certificate (STC) scheme provides an
      upfront discount on your system. The rebate is calculated based on your
      location, system size, and the remaining years of the scheme (to 2030).
      Your installer deducts it from the invoice — no paperwork required.
    </p>
  </div>
  <div class="cta">
    <p style="margin:0 0 10px;font-size:14px;">Ready to move forward?</p>
    <a href="mailto:">Book a free site assessment →</a>
  </div>
  <div class="footer">
    This proposal was generated automatically based on information provided.
    Savings estimates assume current tariffs and average Perth/AU conditions.
    Results will vary. Not financial advice.
  </div>
</div>
</body>
</html>"""


def generate_solar_proposal(lead_data: dict) -> dict:
    """Generate a solar installation proposal from lead data.

    Args:
        lead_data: Dict with name, monthly_bill, state, suburb, email, phone

    Returns:
        Dict with html_content, system_size_kw, est_annual_savings,
        payback_years, stc_rebate_aud
    """
    monthly_bill = float(lead_data.get("monthly_bill") or 200)
    state = (lead_data.get("state") or "NSW").upper()
    name = lead_data.get("name") or "Homeowner"

    print(f"[PROPOSAL] Generating solar proposal for: {name} ({state}, ${monthly_bill}/mo)")

    system_kw = _calc_system_size(monthly_bill, state)
    stc_rebate = _calc_stc_rebate(system_kw, state)
    annual_savings, payback_years = _calc_savings_and_payback(system_kw, state, stc_rebate)
    html = _build_solar_html(lead_data, system_kw, annual_savings, payback_years, stc_rebate)

    print(f"[PROPOSAL] {name}: {system_kw}kW, ${annual_savings}/yr savings, {payback_years}yr payback")
    return {
        "html_content": html,
        "system_size_kw": system_kw,
        "est_annual_savings": annual_savings,
        "payback_years": payback_years,
        "stc_rebate_aud": stc_rebate,
    }


def generate_from_lead(lead_id: int) -> dict:
    """Pull lead from SQLite, generate solar proposal HTML, save to proposals table.

    Args:
        lead_id: Database id of the lead record

    Returns:
        Dict with proposal_id, html_content, and proposal metrics,
        or error dict if lead not found
    """
    lead = fetch_one("SELECT * FROM leads WHERE id = ?", (lead_id,))
    if not lead:
        logger.warning(f"[PROPOSAL] No lead found for id={lead_id}")
        return {"error": f"No lead found for id={lead_id}"}

    result = generate_solar_proposal(lead)

    proposal_id = insert("proposals", {
        "lead_id": lead_id,
        "html_content": result["html_content"],
        "system_size_kw": result["system_size_kw"],
        "est_annual_savings": result["est_annual_savings"],
        "payback_years": result["payback_years"],
        "stc_rebate_aud": result["stc_rebate_aud"],
        "status": "draft",
    })

    print(f"[PROPOSAL] Saved proposal id={proposal_id} for lead_id={lead_id}")
    return {**result, "proposal_id": proposal_id, "lead_id": lead_id}
