"""Synthesis Agent — Reconciles and distils multi-source research findings.

Receives raw findings from market, competitive, prospect, and technical
sub-agents and produces a unified research card with entities, actionable
insights, and scored opportunities for Solar Swarm.
"""

import json
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior research synthesis analyst for an AI automation agency
targeting Australian solar companies on GoHighLevel CRM.

You receive raw findings from multiple research sub-agents and must:
1. Reconcile contradictions (weight by source confidence)
2. Extract unique entities (companies, people, tools, markets)
3. Identify the top 3 actionable insights
4. Surface concrete opportunities with effort/impact scores
5. Assign an overall confidence score

Return ONLY valid JSON:
{
  "key_facts": ["<verified fact>"],
  "entities": [
    {"name": "<name>", "type": "company|person|tool|market", "relevance": "<why it matters>"}
  ],
  "insights": [
    {"insight": "<actionable insight>", "evidence": "<supporting data>", "priority": "high|medium|low"}
  ],
  "opportunities": [
    {
      "title": "<opportunity title>",
      "description": "<what to do>",
      "effort": "low|medium|high",
      "impact": "low|medium|high",
      "time_to_value": "<e.g. 2 weeks>",
      "confidence": <0.0-1.0>
    }
  ],
  "contradictions_resolved": ["<contradiction and resolution>"],
  "overall_confidence": <0.0-1.0>,
  "recommended_next_research": "<what to research next>"
}"""


def run(research_id: str, query: str, findings: list, research_type: str) -> dict:
    """Synthesise multi-source findings into a unified research card.

    Args:
        research_id: ID of the parent research task
        query: Original research query
        findings: List of raw finding dicts from sub-agents
        research_type: market|competitive|prospect|technical|validation

    Returns:
        Synthesised research card dict
    """
    print(f"[SYNTHESIS] Synthesising {len(findings)} findings for: {query[:60]}")

    if not config.is_configured():
        logger.warning("[SYNTHESIS] No OpenAI key — returning mock synthesis")
        return _mock_synthesis(query, findings, research_type)

    prompt = _build_prompt(query, findings, research_type)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        n_opp = len(result.get("opportunities", []))
        conf = result.get("overall_confidence", 0)
        print(f"[SYNTHESIS] Done — {n_opp} opportunities | confidence {conf:.2f}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[SYNTHESIS] JSON parse error: {e}")
        return _mock_synthesis(query, findings, research_type)
    except Exception as e:
        logger.error(f"[SYNTHESIS] Error: {e}")
        return _mock_synthesis(query, findings, research_type)


def _build_prompt(query: str, findings: list, research_type: str) -> str:
    """Build the synthesis prompt from raw findings."""
    prompt = f"Research type: {research_type}\nOriginal query: {query}\n\n"
    prompt += "Raw findings from sub-agents:\n"
    for i, f in enumerate(findings, 1):
        snippet = json.dumps(f)[:600]
        prompt += f"\n[Finding {i}]\n{snippet}\n"
    prompt += "\nSynthesise these findings into a unified research card."
    return prompt


def _mock_synthesis(query: str, findings: list, research_type: str) -> dict:
    """Return mock synthesis when OpenAI is unavailable."""
    return {
        "key_facts": [
            "Australian solar market has 3.5M+ rooftop installations",
            "Avg residential installation value: $8,000–$12,000 AUD",
            "Solar companies average 40–60 leads/month from digital channels",
            "GoHighLevel adoption growing among AU trade businesses",
        ],
        "entities": [
            {"name": "GoHighLevel", "type": "tool", "relevance": "Primary CRM platform for automation"},
            {"name": "Australian Solar Council", "type": "company", "relevance": "Industry body — membership list is prospecting gold"},
            {"name": "Clean Energy Regulator", "type": "market", "relevance": "Publishes installer licence data"},
        ],
        "insights": [
            {
                "insight": "Solar companies waste 60%+ of ad spend on unqualified leads — AI qualification is high-value",
                "evidence": "Industry survey data + client anecdote",
                "priority": "high",
            },
            {
                "insight": "Most AU solar CRMs have no SMS follow-up automation — immediate wedge opportunity",
                "evidence": "Competitive gap analysis",
                "priority": "high",
            },
            {
                "insight": "Referral programmes are under-leveraged — GHL workflows can automate ask + reward",
                "evidence": "Market research finding",
                "priority": "medium",
            },
        ],
        "opportunities": [
            {
                "title": "AI Lead Qualifier for Solar Companies",
                "description": "Deploy GPT-4o qualification bot via GHL SMS/web chat; score leads 1-10 and auto-route hot leads to sales team within 5 minutes",
                "effort": "medium",
                "impact": "high",
                "time_to_value": "2 weeks",
                "confidence": 0.88,
            },
            {
                "title": "Referral Automation Workflow",
                "description": "Post-install GHL sequence that auto-requests referrals, tracks them, and triggers reward delivery — full set-and-forget",
                "effort": "low",
                "impact": "medium",
                "time_to_value": "1 week",
                "confidence": 0.75,
            },
        ],
        "contradictions_resolved": [
            "Market size estimates varied ($2B–$4B AU) — used Clean Energy Regulator data as ground truth ($3.1B)"
        ],
        "overall_confidence": 0.82,
        "recommended_next_research": "Identify top 20 solar installers in Perth/Brisbane not yet using CRM automation",
        "mock": True,
    }
