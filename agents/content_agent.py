"""Content Agent — Tier 2: Department Head for content operations.

Runs daily. Manages the content task queue:
  - Ad copy generation
  - Email sequences
  - Landing page copy
  - Social media content
  - Proposal drafting

Spawns Tier 3 workers for individual content tasks.
"""

import json
import logging
from datetime import datetime
from memory.hot_memory import get_next_task, complete_task, fail_task
from memory.database import parse_payload
from memory.cold_ledger import log_event
import config

logger = logging.getLogger(__name__)

CONTENT_SYSTEM_PROMPT = """You are a direct-response copywriter specialising in Australian B2B marketing.
You write for solar company owners — plain, punchy, results-focused.
No corporate speak. No fluff. Every word earns its place.
Australian English spelling (colour not color, realise not realize).
Always include a specific, low-risk call to action."""


def run(max_tasks: int = 5) -> dict:
    """Run the content department's daily task processing cycle.

    Args:
        max_tasks: Maximum tasks to process

    Returns:
        Dict with tasks_processed, tasks_failed
    """
    print(f"\n[CONTENT HEAD] === Daily Content Cycle ===")
    print(f"[CONTENT HEAD] Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    processed = 0
    failed = 0

    for _ in range(max_tasks):
        task = get_next_task(tier=3)
        if not task or task.get("job_type", "").split("_")[0] != "content":
            break

        task_id = task["id"]
        job_type = task["job_type"]
        context = parse_payload(task.get("context_payload", "{}"))

        print(f"[CONTENT HEAD] Processing task #{task_id}: {job_type}")

        try:
            result = _dispatch_task(job_type, context)
            complete_task(task_id, result)
            processed += 1
        except Exception as e:
            logger.error(f"[CONTENT HEAD] Task #{task_id} failed: {e}")
            fail_task(task_id, str(e))
            failed += 1

    result = {"tasks_processed": processed, "tasks_failed": failed}
    log_event("CONTENT_CYCLE", result, agent_id="content_agent")
    print(f"[CONTENT HEAD] Cycle complete: {result}")
    return result


def _dispatch_task(job_type: str, context: dict) -> dict:
    """Route a content task to the appropriate handler."""
    handlers = {
        "content_ad_copy": _generate_ad_copy,
        "content_email": _generate_email_sequence,
        "content_linkedin": _generate_linkedin_post,
        "content_sms": _generate_sms,
    }
    handler = handlers.get(job_type)
    if not handler:
        raise ValueError(f"Unknown content job type: {job_type}")
    return handler(context)


def _generate_ad_copy(context: dict) -> dict:
    """Generate Facebook/Google ad copy for a solar experiment.

    Args:
        context: Dict with target_audience, pain_point, offer, url

    Returns:
        Dict with headline, body, cta, hook variants
    """
    pain_point = context.get("pain_point", "losing leads to slow follow-up")
    offer = context.get("offer", "free lead response audit")

    if not config.is_configured():
        return _mock_ad_copy(pain_point, offer)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        prompt = (
            f"Write 3 Facebook ad variants for Australian solar company owners.\n"
            f"Pain point: {pain_point}\nOffer: {offer}\n"
            f"Format: headline (10 words max), body (50 words), CTA (5 words)"
        )
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": CONTENT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=400,
        )
        return {"ad_copy": response.choices[0].message.content, "status": "generated"}
    except Exception as e:
        logger.error(f"[CONTENT HEAD] Ad copy generation failed: {e}")
        return _mock_ad_copy(pain_point, offer)


def _generate_email_sequence(context: dict) -> dict:
    """Generate a 3-email outreach sequence.

    Args:
        context: Dict with prospect_name, company, pain_point

    Returns:
        Dict with email_1, email_2, email_3
    """
    company = context.get("company", "your company")
    pain_point = context.get("pain_point", "slow lead follow-up")

    if not config.is_configured():
        return {
            "email_1": f"Subject: Quick question about {company}'s lead process\n\nHi,\n\nI help solar companies in WA stop losing leads to slow follow-up. Is that a problem at {company}?\n\nWorth a 15-min chat?\n\nMartin",
            "email_2": f"Subject: Re: {company}\n\nFollowing up — we helped a Perth solar company recover 23% of their dead leads last month. Happy to show you how.\n\nMartin",
            "email_3": f"Subject: Last email\n\nI won't keep bothering you. If {pain_point} isn't a priority right now, no worries. Feel free to reach out when it is.\n\nMartin",
            "status": "mock",
        }

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        prompt = f"Write a 3-email cold outreach sequence targeting solar company owners. Company: {company}. Pain: {pain_point}. Aussie tone, no fluff."
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "system", "content": CONTENT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600,
        )
        return {"sequence": response.choices[0].message.content, "status": "generated"}
    except Exception as e:
        logger.error(f"[CONTENT HEAD] Email sequence failed: {e}")
        return {"error": str(e), "status": "failed"}


def _generate_linkedin_post(context: dict) -> dict:
    """Generate a LinkedIn post for organic distribution."""
    topic = context.get("topic", "AI automation for solar companies")
    return {
        "post": f"Australian solar companies are leaving money on the table.\n\nEvery missed call after hours = a lost lead.\nEvery slow follow-up = a competitor wins.\n\nWe built a system that responds to every lead in under 5 minutes, 24/7.\n\nInterested in seeing how it works? DM me.\n\n#{topic.replace(' ', '')} #SolarAustralia #AIAutomation",
        "status": "generated",
    }


def _generate_sms(context: dict) -> dict:
    """Generate a follow-up SMS template."""
    name = context.get("name", "there")
    return {
        "sms": f"Hi {name}, this is Martin from Solar AI Systems. You recently enquired about solar — still looking for quotes? Happy to help. Reply YES for a callback.",
        "status": "generated",
    }


def _mock_ad_copy(pain_point: str, offer: str) -> dict:
    """Return mock ad copy when OpenAI unavailable."""
    return {
        "ad_copy": f"HEADLINE: Stop losing solar leads to slow follow-up\nBODY: Most solar companies respond to leads in 4+ hours. We respond in 5 minutes. 24/7. Automatically. See how we do it.\nCTA: Get free audit",
        "pain_point": pain_point,
        "offer": offer,
        "status": "mock",
    }
