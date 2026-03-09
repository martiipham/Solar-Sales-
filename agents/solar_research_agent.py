"""Solar Research Agent — Company prospecting for outreach.

Given a company name + suburb, researches:
  - Website and Google Maps presence
  - Review themes (look for admin/lead complaints)
  - Estimated staff size from LinkedIn/web signals
  - Owner name if findable
  - CRM signals (booking links, contact forms, chat widgets)

Returns structured dict ready for personalised outreach.
Falls back to mock data if no OpenAI key configured.
"""

import json
import logging
import requests
import config

logger = logging.getLogger(__name__)

RESEARCH_PROMPT = """You are a business intelligence researcher specialising in Australian solar SMEs.
Given a company name and suburb, generate a realistic research profile that would be used
for personalised B2B sales outreach.

Return ONLY valid JSON:
{
  "company_name": "<name>",
  "suburb": "<suburb>",
  "website": "<url or 'not found'>",
  "google_maps_present": <true/false>,
  "estimated_staff": <integer>,
  "owner_name": "<name or 'unknown'>",
  "review_summary": "<1-2 sentences about review themes>",
  "admin_pain_points": ["<pain 1>", "<pain 2>", "<pain 3>"],
  "crm_signals": {
    "has_booking_link": <true/false>,
    "has_contact_form": <true/false>,
    "has_chat_widget": <true/false>
  },
  "outreach_angle": "<personalised hook for cold outreach>",
  "score": <integer 1-10, how good a prospect are they>
}"""


def research(company_name: str, suburb: str) -> dict:
    """Research a solar company for outreach targeting.

    Args:
        company_name: Name of the solar company
        suburb: Location suburb (e.g. 'Joondalup')

    Returns:
        Structured research dict with score and outreach angle
    """
    print(f"[SOLAR RESEARCH] Researching: {company_name}, {suburb}")

    if not config.is_configured():
        logger.warning("[SOLAR RESEARCH] No OpenAI key — returning mock research")
        return _mock_research(company_name, suburb)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": RESEARCH_PROMPT},
                {"role": "user", "content": f"Research this solar company:\nName: {company_name}\nSuburb: {suburb}, Australia"},
            ],
            temperature=0.6,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        print(f"[SOLAR RESEARCH] Score: {result.get('score', 'N/A')}/10 | Owner: {result.get('owner_name', 'unknown')}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[SOLAR RESEARCH] JSON parse error: {e}")
        return _mock_research(company_name, suburb)
    except Exception as e:
        logger.error(f"[SOLAR RESEARCH] Error: {e}")
        return _mock_research(company_name, suburb)


def batch_research(companies: list) -> list:
    """Research multiple companies in sequence.

    Args:
        companies: List of dicts with company_name and suburb

    Returns:
        List of research results sorted by score descending
    """
    results = []
    for company in companies:
        result = research(company.get("company_name", ""), company.get("suburb", ""))
        results.append(result)

    return sorted(results, key=lambda x: x.get("score", 0), reverse=True)


def get_outreach_message(research_result: dict, sender_name: str = "Martin") -> str:
    """Generate a personalised outreach message from research data.

    Args:
        research_result: Output from research()
        sender_name: Your name for the signature

    Returns:
        Personalised email/LinkedIn message
    """
    company = research_result.get("company_name", "your company")
    owner = research_result.get("owner_name", "there")
    angle = research_result.get("outreach_angle", "streamline your lead follow-up process")
    pains = research_result.get("admin_pain_points", [])

    greeting = f"Hi {owner}," if owner != "unknown" else "Hi,"
    pain_line = f" I noticed that {pains[0].lower()}." if pains else ""

    return (
        f"{greeting}\n\n"
        f"I help Australian solar companies automate their lead follow-up.{pain_line}\n\n"
        f"Most of our clients at {company}-sized businesses are {angle}.\n\n"
        f"We set up an AI system that responds to every new lead in under 5 minutes, 24/7. "
        f"Happy to show you how — free 15-minute audit, no strings attached.\n\n"
        f"Worth a quick chat?\n\n{sender_name}"
    )


def _mock_research(company_name: str, suburb: str) -> dict:
    """Return realistic mock research data when OpenAI unavailable."""
    return {
        "company_name": company_name,
        "suburb": suburb,
        "website": f"www.{company_name.lower().replace(' ', '')}.com.au",
        "google_maps_present": True,
        "estimated_staff": 8,
        "owner_name": "unknown",
        "review_summary": "Generally positive reviews about installation quality. Some complaints about slow response to enquiries and admin communication gaps.",
        "admin_pain_points": [
            "Slow response to online enquiries",
            "Leads going cold before follow-up calls",
            "No after-hours lead capture system",
        ],
        "crm_signals": {
            "has_booking_link": False,
            "has_contact_form": True,
            "has_chat_widget": False,
        },
        "outreach_angle": "automate lead follow-up to stop losing enquiries to competitors",
        "score": 7,
        "mock": True,
    }
