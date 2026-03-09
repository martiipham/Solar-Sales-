"""Slack notification system for Solar Swarm.

All alerts and reports route through this module.
Uses simple incoming webhooks — no Slack SDK required.
"""

import json
import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)


def _post(payload: dict) -> bool:
    """Send a JSON payload to the configured Slack webhook.

    Args:
        payload: Slack message payload dict

    Returns:
        True if successful, False otherwise
    """
    if not config.SLACK_WEBHOOK_URL:
        logger.warning("[SLACK] No webhook URL configured — skipping notification")
        return False
    try:
        resp = requests.post(
            config.SLACK_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"[SLACK] HTTP {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"[SLACK] Failed to send notification: {e}")
        return False


def _block(text: str, block_type: str = "section") -> dict:
    """Create a simple Slack block element."""
    return {"type": block_type, "text": {"type": "mrkdwn", "text": text}}


def alert_new_lead(name: str, score: float, reason: str, action: str) -> bool:
    """Send a new lead alert to Slack.

    Args:
        name: Lead's name
        score: Qualification score (1-10)
        reason: Two-sentence explanation
        action: call_now / nurture / disqualify
    """
    emoji = "🔥" if score >= 7 else "📋" if score >= 5 else "❌"
    payload = {
        "blocks": [
            _block(f"*{emoji} New Solar Lead*"),
            _block(f"*Name:* {name}\n*Score:* {score}/10\n*Action:* `{action}`"),
            _block(f"_{reason}_"),
        ]
    }
    print(f"[SLACK] New lead alert: {name} ({score}/10)")
    return _post(payload)


def alert_high_value_lead(name: str, score: float, details: dict) -> bool:
    """Send a high-value lead (7+) alert with full details.

    Args:
        name: Lead's name
        score: Score (expected >= 7)
        details: Dict with email, phone, suburb, monthly_bill etc.
    """
    lines = [f"*{k.replace('_',' ').title()}:* {v}" for k, v in details.items() if v]
    payload = {
        "blocks": [
            _block(f"*🚨 HIGH VALUE LEAD — {name}* ({score}/10)"),
            _block("\n".join(lines)),
            _block("Action required: *CALL NOW* within 5 minutes"),
        ]
    }
    print(f"[SLACK] High value lead alert: {name}")
    return _post(payload)


def alert_circuit_breaker(level: str, reason: str) -> bool:
    """Send a circuit breaker trigger alert.

    Args:
        level: yellow / orange / red
        reason: Why the breaker was triggered
    """
    icons = {"yellow": "⚠️", "orange": "🟠", "red": "🛑"}
    icon = icons.get(level, "⚠️")
    msg = f"*{icon} CIRCUIT BREAKER — {level.upper()}*\n{reason}"
    if level == "red":
        msg += "\n\n*ALL EXPERIMENTS PAUSED. Run `/approve` to resume.*"
    payload = {"blocks": [_block(msg)]}
    print(f"[SLACK] Circuit breaker {level.upper()}: {reason}")
    return _post(payload)


def alert_human_gate(experiment_id: int, idea: str, score: float, budget: float) -> bool:
    """Alert that an experiment needs human approval.

    Sends interactive approve/reject buttons when Slack bot token is configured.
    Falls back to webhook with CLI instructions otherwise.

    Args:
        experiment_id: Database id
        idea: One-line description
        score: Confidence score
        budget: Recommended budget in AUD
    """
    info_block = _block(
        f"*ID:* #{experiment_id}\n"
        f"*Idea:* {idea}\n"
        f"*Confidence:* {score}/10\n"
        f"*Recommended Budget:* ${budget:.0f} AUD"
    )

    # Use interactive buttons if bot token is available
    if config.SLACK_BOT_TOKEN:
        try:
            from integrations.slack_client import post_blocks
            blocks = [
                _block("*🚦 Human Gate — Experiment Awaiting Approval*"),
                info_block,
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve"},
                            "style": "primary",
                            "action_id": f"approve_experiment_{experiment_id}",
                            "value": str(experiment_id),
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Reject"},
                            "style": "danger",
                            "action_id": f"reject_experiment_{experiment_id}",
                            "value": str(experiment_id),
                        },
                    ],
                },
            ]
            print(f"[SLACK] Human gate interactive alert for experiment #{experiment_id}")
            return post_blocks(blocks)
        except Exception as e:
            logger.warning(f"[SLACK] Interactive alert failed, falling back to webhook: {e}")

    # Fallback: webhook with CLI instructions
    payload = {
        "blocks": [
            _block("*🚦 Human Gate — Experiment Awaiting Approval*"),
            info_block,
            _block(f"Approve: `python cli.py approve {experiment_id}` | Reject: `python cli.py reject {experiment_id}`"),
        ]
    }
    print(f"[SLACK] Human gate alert for experiment #{experiment_id}")
    return _post(payload)


def post_weekly_report(report_text: str) -> bool:
    """Post a weekly client performance report to Slack.

    Args:
        report_text: Full formatted report text
    """
    payload = {
        "blocks": [
            _block("*📊 Weekly Client Performance Report*"),
            _block(f"_{datetime.now().strftime('%d %B %Y')}_"),
            {"type": "divider"},
            _block(report_text[:2900]),
        ]
    }
    print("[SLACK] Posting weekly client report")
    return _post(payload)


def post_retrospective(retro_text: str) -> bool:
    """Post the weekly swarm retrospective to Slack.

    Args:
        retro_text: Full retrospective analysis text
    """
    payload = {
        "blocks": [
            _block("*🔁 Weekly Swarm Retrospective*"),
            _block(f"_{datetime.now().strftime('%A %d %B %Y')}_"),
            {"type": "divider"},
            _block(retro_text[:2900]),
        ]
    }
    print("[SLACK] Posting weekly retrospective")
    return _post(payload)


def post_message(text: str) -> bool:
    """Send a plain text message to Slack.

    Args:
        text: The message text (markdown supported)
    """
    return _post({"text": text})
