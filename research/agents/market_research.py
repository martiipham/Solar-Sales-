"""Market Research Agent — Solar market intelligence for Solar Swarm.

Researches Australian solar market demand, pricing trends,
seasonal patterns, and growth signals using GPT-4o.

Returns structured findings with confidence scores per data point.
"""

import json
import logging
from datetime import datetime
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a market research analyst specialising in the Australian solar industry.
You produce concise, evidence-based market intelligence for a B2B AI automation consultancy
targeting Australian solar SMEs (5-15 salespeople).

Focus on:
- Demand signals (are solar enquiries rising/falling?)
- Pricing trends (what are solar systems selling for in 2025?)
- Pain points (what operational problems do solar companies report?)
- Seasonal patterns (when is the busy season in each state?)
- Lead quality trends (are leads getting harder/easier to convert?)

Always cite your reasoning. Rate each finding's confidence 0.0–1.0.

Return ONLY valid JSON:
{
  "findings": [
    {
      "claim": "<specific market insight>",
      "confidence": <0.0-1.0>,
      "source_type": "industry_knowledge|trend_data|customer_feedback",
      "relevance": "high|medium|low",
      "actionable": true
    }
  ],
  "market_summary": "<2-3 sentence executive summary>",
  "key_opportunity": "<single biggest opportunity identified>",
  "key_risk": "<single biggest risk>",
  "pheromone": {
    "type": "POSITIVE|NEGATIVE|NEUTRAL",
    "topic": "<topic string>",
    "strength": <0.1-1.0>
  }
}"""


def run(query: str, context: dict = None) -> dict:
    """Run market research on a given query.

    Args:
        query: Research question or topic
        context: Optional additional context from previous research

    Returns:
        Dict with findings, summary, opportunity, risk, pheromone signal
    """
    print(f"[MARKET RESEARCH] Query: {query[:70]}")

    if not config.is_configured():
        logger.warning("[MARKET RESEARCH] No OpenAI key — returning mock findings")
        return _mock_findings(query)

    prompt = f"Research query: {query}\n"
    if context:
        prompt += f"Additional context: {json.dumps(context)[:500]}\n"
    prompt += "\nProvide market intelligence specific to Australian solar SMEs."

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
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        _print_summary(result)
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[MARKET RESEARCH] JSON parse error: {e}")
        return _mock_findings(query)
    except Exception as e:
        logger.error(f"[MARKET RESEARCH] Error: {e}")
        return _mock_findings(query)


def _print_summary(result: dict):
    """Print research summary to console."""
    findings = result.get("findings", [])
    high_conf = [f for f in findings if f.get("confidence", 0) >= 0.7]
    print(f"[MARKET RESEARCH] {len(findings)} findings ({len(high_conf)} high-confidence)")
    if result.get("key_opportunity"):
        print(f"[MARKET RESEARCH] Key opportunity: {result['key_opportunity'][:60]}")


def _mock_findings(query: str) -> dict:
    """Return mock findings when OpenAI is unavailable."""
    return {
        "findings": [
            {
                "claim": "Australian solar installations grew 18% YoY in 2024, with WA leading at 23% growth",
                "confidence": 0.75,
                "source_type": "industry_knowledge",
                "relevance": "high",
                "actionable": True,
            },
            {
                "claim": "Average response time for solar enquiries is 4.2 hours — leads going to first responder 68% of the time",
                "confidence": 0.80,
                "source_type": "customer_feedback",
                "relevance": "high",
                "actionable": True,
            },
            {
                "claim": "Solar companies report admin overhead consuming 35% of sales team time, primarily manual CRM entry",
                "confidence": 0.70,
                "source_type": "customer_feedback",
                "relevance": "high",
                "actionable": True,
            },
            {
                "claim": "Residential solar system average value is $8,000–$14,000 AUD in WA/QLD",
                "confidence": 0.85,
                "source_type": "industry_knowledge",
                "relevance": "medium",
                "actionable": False,
            },
        ],
        "market_summary": (
            "The Australian solar market is in strong growth, especially in WA and QLD. "
            "Lead response speed is the #1 competitive differentiator — companies that "
            "respond fastest win the deal. Admin overhead is a major pain point."
        ),
        "key_opportunity": (
            "Automated 5-minute lead response system targeting WA solar companies — "
            "proven pain point with clear ROI story"
        ),
        "key_risk": "Solar incentive policy changes could reduce lead volume by 20-30%",
        "pheromone": {
            "type": "POSITIVE",
            "topic": "solar_market_demand",
            "strength": 0.75,
        },
        "mock": True,
    }
