"""Competitive Intel Agent — Competitor analysis for Solar Swarm.

Researches other CRM automation and AI providers targeting
Australian solar companies. Identifies pricing gaps, feature gaps,
and positioning opportunities.

Output: competitor matrix + exploitable gaps.
"""

import json
import logging
from datetime import datetime
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a competitive intelligence analyst for an AI automation consultancy
targeting Australian solar SMEs. Research competitors offering CRM automation,
lead management, or AI tools to solar companies.

Known context:
- Our platform: GoHighLevel CRM
- Our price: $1,500–2,500 AUD/month retainer
- Our differentiator: 5-minute AI lead response, 24/7
- Our market: Australian solar companies, 5-15 salespeople

Identify:
1. Direct competitors (offering similar AI/automation for solar)
2. Partial competitors (CRM tools solar companies use but aren't specialised)
3. Pricing gaps (where we are cheaper or more expensive)
4. Feature gaps (things nobody is doing well)
5. Audience gaps (solar sub-segments nobody is targeting)

Return ONLY valid JSON:
{
  "competitors": [
    {
      "name": "<company name>",
      "type": "direct|partial|adjacent",
      "estimated_price_aud_per_month": <number or null>,
      "target_market": "<who they target>",
      "key_strengths": ["<strength 1>", "<strength 2>"],
      "key_weaknesses": ["<weakness 1>", "<weakness 2>"],
      "exploitable_gap": "<one sentence on how we can beat them>"
    }
  ],
  "market_gaps": [
    {
      "gap_type": "price|feature|audience|channel",
      "description": "<specific gap>",
      "exploit_strategy": "<how to capture this>",
      "estimated_tam_aud": <monthly revenue potential or null>
    }
  ],
  "positioning_recommendation": "<1-2 sentence recommendation for our positioning>",
  "confidence": <0.0-1.0>
}"""


def run(query: str, context: dict = None) -> dict:
    """Run competitive intelligence research.

    Args:
        query: Research question (e.g. competitors in solar automation space)
        context: Optional additional context

    Returns:
        Dict with competitors, gaps, positioning recommendation
    """
    print(f"[COMPETITIVE INTEL] Query: {query[:70]}")

    if not config.is_configured():
        logger.warning("[COMPETITIVE INTEL] No OpenAI key — returning mock intel")
        return _mock_intel(query)

    prompt = f"Research query: {query}\n"
    if context:
        prompt += f"Context: {json.dumps(context)[:400]}\n"
    prompt += "\nFocus on the Australian solar SME market specifically."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        _print_summary(result)
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[COMPETITIVE INTEL] JSON parse error: {e}")
        return _mock_intel(query)
    except Exception as e:
        logger.error(f"[COMPETITIVE INTEL] Error: {e}")
        return _mock_intel(query)


def _print_summary(result: dict):
    """Print competitive summary to console."""
    competitors = result.get("competitors", [])
    gaps = result.get("market_gaps", [])
    print(f"[COMPETITIVE INTEL] {len(competitors)} competitors | {len(gaps)} gaps identified")
    if result.get("positioning_recommendation"):
        print(f"[COMPETITIVE INTEL] Positioning: {result['positioning_recommendation'][:70]}")


def _mock_intel(query: str) -> dict:
    """Return mock competitive intel when OpenAI is unavailable."""
    return {
        "competitors": [
            {
                "name": "Generic CRM Agencies",
                "type": "partial",
                "estimated_price_aud_per_month": 800,
                "target_market": "Any small business, not solar-specific",
                "key_strengths": ["Lower price", "Established brand"],
                "key_weaknesses": [
                    "No solar-specific expertise",
                    "No AI lead response",
                    "Generic templates",
                ],
                "exploitable_gap": "We offer solar-specific AI with 5-min response vs their generic, slow setup",
            },
            {
                "name": "In-house GHL Consultants",
                "type": "direct",
                "estimated_price_aud_per_month": 1200,
                "target_market": "GHL users generally",
                "key_strengths": ["GHL expertise", "Lower price"],
                "key_weaknesses": [
                    "No AI components",
                    "Manual process-heavy",
                    "No 24/7 automation",
                ],
                "exploitable_gap": "We add AI voice + qualification layer they cannot offer",
            },
        ],
        "market_gaps": [
            {
                "gap_type": "audience",
                "description": "No provider specifically targets WA solar companies with local market knowledge",
                "exploit_strategy": "Lead with 'Perth solar specialists' positioning in all outreach",
                "estimated_tam_aud": 150000,
            },
            {
                "gap_type": "feature",
                "description": "No competitor offers AI voice callback within 5 minutes of lead submission",
                "exploit_strategy": "Make 5-minute AI callback the centrepiece of every demo",
                "estimated_tam_aud": None,
            },
        ],
        "positioning_recommendation": (
            "Position as the only AI automation service purpose-built for Australian solar companies. "
            "Lead with the 5-minute guarantee and solar-specific qualification scoring."
        ),
        "confidence": 0.65,
        "mock": True,
    }
