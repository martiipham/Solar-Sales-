"""Technical Research Agent — Integration and build intelligence for Solar Swarm.

Researches tools, APIs, and technical approaches for building
solar automation systems. Assesses build complexity and identifies
what an autonomous agent can build vs. what needs human intervention.
"""

import json
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical research analyst for an AI automation agency.
You evaluate tools, APIs, and integrations for building automation systems for
Australian solar companies on GoHighLevel CRM.

Assess each component for:
- Availability (does it exist and work?)
- Cost (free / monthly / per-use)
- Complexity to integrate (low/medium/high)
- GoHighLevel compatibility
- Whether an AI agent can configure it autonomously

Return ONLY valid JSON:
{
  "components": [
    {
      "name": "<tool or API name>",
      "purpose": "<what it does>",
      "cost_model": "<free|$X/mo|per-use>",
      "integration_complexity": "low|medium|high",
      "ghl_compatible": <true/false/partial>,
      "agent_can_configure": <true/false>,
      "documentation_quality": "good|adequate|poor",
      "recommended": <true/false>,
      "notes": "<key consideration>"
    }
  ],
  "build_plan": {
    "total_estimated_hours": <integer>,
    "phases": [
      {"phase": "<name>", "hours": <integer>, "blockers": ["<blocker>"]}
    ],
    "autonomous_buildable": <true/false>,
    "human_steps_required": ["<step requiring human>"]
  },
  "recommended_stack": "<2-3 sentence tech stack recommendation>",
  "confidence": <0.0-1.0>
}"""


def run(query: str, context: dict = None) -> dict:
    """Run technical research on a build question.

    Args:
        query: What needs to be built or evaluated
        context: Optional additional context

    Returns:
        Dict with components, build plan, stack recommendation
    """
    print(f"[TECHNICAL RESEARCH] Query: {query[:70]}")

    if not config.is_configured():
        logger.warning("[TECHNICAL RESEARCH] No OpenAI key — returning mock research")
        return _mock_research(query)

    prompt = f"Technical research query: {query}\n"
    if context:
        prompt += f"Context: {json.dumps(context)[:400]}\n"
    prompt += "\nFocus on GoHighLevel CRM integrations and Australian solar use cases."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        hours = result.get("build_plan", {}).get("total_estimated_hours", "?")
        autonomous = result.get("build_plan", {}).get("autonomous_buildable", False)
        print(f"[TECHNICAL RESEARCH] Build est: {hours}h | Autonomous: {autonomous}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"[TECHNICAL RESEARCH] JSON parse error: {e}")
        return _mock_research(query)
    except Exception as e:
        logger.error(f"[TECHNICAL RESEARCH] Error: {e}")
        return _mock_research(query)


def _mock_research(query: str) -> dict:
    """Return mock technical research when OpenAI is unavailable."""
    return {
        "components": [
            {
                "name": "GoHighLevel API",
                "purpose": "CRM, pipeline, contact management, SMS/email automation",
                "cost_model": "$97-497/mo (client pays)",
                "integration_complexity": "medium",
                "ghl_compatible": True,
                "agent_can_configure": True,
                "documentation_quality": "adequate",
                "recommended": True,
                "notes": "Core platform — all workflows built inside GHL",
            },
            {
                "name": "Twilio / GHL Voice",
                "purpose": "AI voice callbacks for new leads",
                "cost_model": "$0.013/min",
                "integration_complexity": "medium",
                "ghl_compatible": True,
                "agent_can_configure": False,
                "documentation_quality": "good",
                "recommended": True,
                "notes": "Human needs to create Twilio account and set up number",
            },
            {
                "name": "OpenAI GPT-4o",
                "purpose": "Lead qualification, message personalisation, proposal generation",
                "cost_model": "per-use ~$0.01-0.05/lead",
                "integration_complexity": "low",
                "ghl_compatible": False,
                "agent_can_configure": True,
                "documentation_quality": "good",
                "recommended": True,
                "notes": "Already integrated in Solar Swarm",
            },
        ],
        "build_plan": {
            "total_estimated_hours": 16,
            "phases": [
                {
                    "phase": "GHL workflow setup",
                    "hours": 4,
                    "blockers": ["GHL sub-account access required from client"],
                },
                {
                    "phase": "Lead qualification integration",
                    "hours": 3,
                    "blockers": [],
                },
                {
                    "phase": "AI voice callback setup",
                    "hours": 6,
                    "blockers": ["Twilio account needs human to create and verify"],
                },
                {
                    "phase": "Reporting and Slack alerts",
                    "hours": 3,
                    "blockers": [],
                },
            ],
            "autonomous_buildable": False,
            "human_steps_required": [
                "Create Twilio account and verify phone number",
                "Obtain GHL sub-account API key from client",
                "Configure DNS for email deliverability",
            ],
        },
        "recommended_stack": (
            "GoHighLevel CRM as the core platform with Python backend for AI logic. "
            "Twilio for voice callbacks. OpenAI for qualification and personalisation. "
            "Slack for operator alerts. SQLite for local state management."
        ),
        "confidence": 0.80,
        "mock": True,
    }
