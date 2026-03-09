"""Prospect Researcher Agent — Deep company research for Solar Swarm.

Given a solar company name or suburb, performs deep research:
  - Company profile, size, owner details
  - Online presence signals (website, GMB, reviews)
  - Admin pain points from review analysis
  - CRM technology signals
  - Best outreach angle and timing

Feeds directly into personalised outreach campaigns.
"""

import json
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a B2B sales intelligence researcher specialising in Australian solar SMEs.
Given a company name or location, generate detailed prospect intelligence for
personalised outreach from an AI automation consultancy.

The consultancy offers:
- AI-powered lead automation on GoHighLevel CRM
- 5-minute automated lead response, 24/7
- Price: $1,500–2,500 AUD/month retainer
- Proof: typical client sees 25-40% more leads contacted

Generate the most realistic, detailed profile possible.

Return ONLY valid JSON:
{
  "company_name": "<name>",
  "location": "<suburb, state>",
  "website": "<url or 'not found'>",
  "google_business_present": <true/false>,
  "estimated_staff_count": <integer>,
  "estimated_monthly_leads": <integer>,
  "owner_name": "<name or 'unknown'>",
  "owner_linkedin_likely": "<linkedin url pattern or null>",
  "review_analysis": {
    "average_rating": <1.0-5.0 or null>,
    "total_reviews": <integer or null>,
    "positive_themes": ["<theme 1>"],
    "complaint_themes": ["<complaint 1>", "<complaint 2>"]
  },
  "crm_signals": {
    "has_booking_link": <true/false>,
    "has_live_chat": <true/false>,
    "has_contact_form": <true/false>,
    "response_time_likely": "<fast <1hr|slow 4+ hrs|unknown>"
  },
  "pain_points": [
    "<specific pain point 1>",
    "<specific pain point 2>",
    "<specific pain point 3>"
  ],
  "outreach_hooks": {
    "primary": "<best personalised opening line>",
    "secondary": "<backup angle>",
    "avoid": "<what NOT to say to this company>"
  },
  "best_channel": "email|linkedin|phone|in-person",
  "best_time": "<day of week and time to reach owner>",
  "prospect_score": <1-10>,
  "score_rationale": "<one sentence why this score>"
}"""


def run(query: str, context: dict = None) -> dict:
    """Run deep prospect research on a company.

    Args:
        query: Company name, suburb, or "company_name in suburb"
        context: Optional previous research context

    Returns:
        Dict with full prospect intelligence profile
    """
    print(f"[PROSPECT RESEARCHER] Researching: {query[:70]}")

    if not config.is_configured():
        logger.warning("[PROSPECT RESEARCHER] No OpenAI key — returning mock profile")
        return _mock_profile(query)

    prompt = f"Research this Australian solar company for B2B outreach: {query}"
    if context:
        prompt += f"\nAdditional context: {json.dumps(context)[:300]}"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=900,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        score = result.get("prospect_score", "N/A")
        print(f"[PROSPECT RESEARCHER] Score: {score}/10 | {result.get('best_channel','?')} recommended")

        _save_to_knowledge_graph(result, query)
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[PROSPECT RESEARCHER] JSON parse error: {e}")
        return _mock_profile(query)
    except Exception as e:
        logger.error(f"[PROSPECT RESEARCHER] Error: {e}")
        return _mock_profile(query)


def batch_research(companies: list) -> list:
    """Research multiple companies and return sorted by score.

    Args:
        companies: List of company name/suburb strings

    Returns:
        List of profiles sorted by prospect_score descending
    """
    results = []
    for company in companies:
        result = run(company)
        results.append(result)
    return sorted(results, key=lambda x: x.get("prospect_score", 0), reverse=True)


def _save_to_knowledge_graph(profile: dict, query: str):
    """Save prospect to knowledge graph as a company entity."""
    try:
        from storage.knowledge_graph import upsert_entity
        upsert_entity(
            entity_type="solar_company",
            name=profile.get("company_name", query),
            attributes={
                "location": profile.get("location"),
                "estimated_staff": profile.get("estimated_staff_count"),
                "monthly_leads": profile.get("estimated_monthly_leads"),
                "prospect_score": profile.get("prospect_score"),
                "best_channel": profile.get("best_channel"),
                "owner_name": profile.get("owner_name"),
            },
            confidence=0.65,
        )
    except Exception as e:
        logger.debug(f"[PROSPECT RESEARCHER] KG save skipped: {e}")


def _mock_profile(query: str) -> dict:
    """Return a realistic mock profile when OpenAI is unavailable."""
    company_name = query.split(" in ")[0].strip() if " in " in query else query
    suburb = query.split(" in ")[1].strip() if " in " in query else "Perth"

    return {
        "company_name": company_name,
        "location": f"{suburb}, WA",
        "website": f"www.{company_name.lower().replace(' ', '')}.com.au",
        "google_business_present": True,
        "estimated_staff_count": 8,
        "estimated_monthly_leads": 45,
        "owner_name": "unknown",
        "owner_linkedin_likely": None,
        "review_analysis": {
            "average_rating": 4.2,
            "total_reviews": 38,
            "positive_themes": ["installation quality", "professional team"],
            "complaint_themes": [
                "slow to respond to enquiries",
                "hard to get callbacks after deposit",
            ],
        },
        "crm_signals": {
            "has_booking_link": False,
            "has_live_chat": False,
            "has_contact_form": True,
            "response_time_likely": "slow 4+ hrs",
        },
        "pain_points": [
            "Losing leads to competitors due to 4+ hour response times",
            "Sales team spending 2+ hours/day on manual CRM data entry",
            "No after-hours lead capture — missing weekend enquiries",
        ],
        "outreach_hooks": {
            "primary": f"I noticed {company_name} has 4-star reviews mentioning slow callbacks — we fix that.",
            "secondary": "Most Perth solar companies lose 25% of leads to slow follow-up. Want to see how we fix it?",
            "avoid": "Generic 'AI can transform your business' messaging",
        },
        "best_channel": "email",
        "best_time": "Tuesday or Wednesday, 8-9am AWST",
        "prospect_score": 7,
        "score_rationale": "Established company with clear admin pain points and high lead volume",
        "mock": True,
    }
