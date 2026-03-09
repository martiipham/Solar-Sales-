"""Slack Web API Client for Solar Swarm.

Full Slack Web API integration using a Bot Token (xoxb-...).
Supports posting messages, reading channels, threading, reactions,
file uploads, and user lookups.

This complements the existing webhook-only slack_notifier.py by enabling
two-way interaction — the swarm can read Slack for commands/feedback,
not just post outbound alerts.

Requires SLACK_BOT_TOKEN in environment.
"""

import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


def _headers() -> dict:
    """Build authenticated Slack API request headers."""
    return {
        "Authorization": f"Bearer {config.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _request(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict | None:
    """Make an authenticated request to the Slack Web API.

    Args:
        method: HTTP method (GET or POST)
        endpoint: API method name (e.g. 'chat.postMessage')
        data: Request body dict for POST
        params: Query params for GET

    Returns:
        Response dict or None on failure
    """
    if not config.SLACK_BOT_TOKEN:
        logger.warning("[SLACK_API] No bot token configured — skipping call")
        return None
    try:
        url = f"{SLACK_API_BASE}/{endpoint}"
        if method == "GET":
            resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        else:
            resp = requests.post(url, headers=_headers(), json=data, timeout=10)
        result = resp.json()
        if not result.get("ok"):
            logger.error(f"[SLACK_API] {endpoint} error: {result.get('error', 'unknown')}")
            return None
        return result
    except Exception as e:
        logger.error(f"[SLACK_API] {endpoint} failed: {e}")
        return None


# ── Messaging ───────────────────────────────────────────────────────────────

def post_message(channel: str, text: str, blocks: list = None, thread_ts: str = None) -> dict | None:
    """Post a message to a Slack channel.

    Args:
        channel: Channel ID or name (e.g. '#swarm-alerts' or 'C0123456789')
        text: Plain text fallback (also shown in notifications)
        blocks: Optional Block Kit blocks for rich formatting
        thread_ts: Parent message timestamp to reply in thread

    Returns:
        Message result dict with 'ts' timestamp, or None
    """
    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    if thread_ts:
        payload["thread_ts"] = thread_ts
    result = _request("POST", "chat.postMessage", data=payload)
    if result:
        print(f"[SLACK_API] Message posted to {channel}")
    return result


def post_blocks(channel: str, blocks: list, text: str = "") -> dict | None:
    """Post a Block Kit message to a Slack channel.

    Args:
        channel: Channel ID or name
        blocks: Slack Block Kit blocks list
        text: Plain text fallback for notifications

    Returns:
        Message result dict or None
    """
    return post_message(channel, text=text, blocks=blocks)


def update_message(channel: str, ts: str, text: str, blocks: list = None) -> dict | None:
    """Update an existing Slack message in-place.

    Args:
        channel: Channel ID
        ts: Message timestamp (from original post_message result)
        text: New plain text content
        blocks: Optional new Block Kit blocks

    Returns:
        Updated message dict or None
    """
    payload = {"channel": channel, "ts": ts, "text": text}
    if blocks:
        payload["blocks"] = blocks
    result = _request("POST", "chat.update", data=payload)
    if result:
        print(f"[SLACK_API] Message {ts} updated in {channel}")
    return result


def delete_message(channel: str, ts: str) -> bool:
    """Delete a Slack message.

    Args:
        channel: Channel ID
        ts: Message timestamp

    Returns:
        True if deleted successfully
    """
    result = _request("POST", "chat.delete", data={"channel": channel, "ts": ts})
    return result is not None


def add_reaction(channel: str, ts: str, emoji: str) -> bool:
    """Add an emoji reaction to a message.

    Args:
        channel: Channel ID
        ts: Message timestamp
        emoji: Emoji name without colons (e.g. 'white_check_mark')

    Returns:
        True if reaction added
    """
    result = _request("POST", "reactions.add", data={
        "channel": channel, "timestamp": ts, "name": emoji
    })
    return result is not None


# ── Reading ─────────────────────────────────────────────────────────────────

def get_channel_history(channel: str, limit: int = 20, oldest: str = None) -> list:
    """Fetch recent messages from a Slack channel.

    Args:
        channel: Channel ID
        limit: Max messages to return (default 20, max 1000)
        oldest: Only return messages after this Unix timestamp

    Returns:
        List of message dicts (newest first) or empty list
    """
    params = {"channel": channel, "limit": limit}
    if oldest:
        params["oldest"] = oldest
    result = _request("GET", "conversations.history", params=params)
    if not result:
        return []
    return result.get("messages", [])


def get_thread_replies(channel: str, thread_ts: str) -> list:
    """Fetch all replies in a message thread.

    Args:
        channel: Channel ID
        thread_ts: Thread parent message timestamp

    Returns:
        List of reply message dicts or empty list
    """
    result = _request("GET", "conversations.replies", params={
        "channel": channel, "ts": thread_ts
    })
    if not result:
        return []
    return result.get("messages", [])[1:]  # Skip the parent message


def get_unread_mentions(channel: str, bot_user_id: str, since_ts: str = None) -> list:
    """Fetch messages in a channel that mention the bot.

    Args:
        channel: Channel ID
        bot_user_id: Bot's Slack user ID (e.g. 'U0123456789')
        since_ts: Only look at messages after this timestamp

    Returns:
        List of message dicts that mention the bot
    """
    messages = get_channel_history(channel, limit=50, oldest=since_ts)
    mention = f"<@{bot_user_id}>"
    return [m for m in messages if mention in m.get("text", "")]


# ── Channels ────────────────────────────────────────────────────────────────

def list_channels(exclude_archived: bool = True) -> list:
    """List all public channels the bot has access to.

    Args:
        exclude_archived: Skip archived channels (default True)

    Returns:
        List of channel dicts with id, name, num_members etc.
    """
    result = _request("GET", "conversations.list", params={
        "exclude_archived": exclude_archived,
        "types": "public_channel,private_channel",
        "limit": 200,
    })
    if not result:
        return []
    return result.get("channels", [])


def get_channel_id(channel_name: str) -> str | None:
    """Look up a channel ID by name.

    Args:
        channel_name: Channel name without # prefix

    Returns:
        Channel ID string or None
    """
    channels = list_channels()
    name = channel_name.lstrip("#")
    for ch in channels:
        if ch.get("name") == name:
            return ch["id"]
    return None


def join_channel(channel: str) -> bool:
    """Join a Slack channel.

    Args:
        channel: Channel ID

    Returns:
        True if joined successfully
    """
    result = _request("POST", "conversations.join", data={"channel": channel})
    return result is not None


# ── Users ────────────────────────────────────────────────────────────────────

def get_user_info(user_id: str) -> dict | None:
    """Fetch a Slack user's profile.

    Args:
        user_id: Slack user ID

    Returns:
        User dict with name, email, real_name etc. or None
    """
    result = _request("GET", "users.info", params={"user": user_id})
    if not result:
        return None
    return result.get("user")


def get_bot_user_id() -> str | None:
    """Get the bot's own Slack user ID.

    Returns:
        Bot user ID string or None
    """
    result = _request("GET", "auth.test")
    if not result:
        return None
    user_id = result.get("user_id")
    print(f"[SLACK_API] Bot user ID: {user_id}")
    return user_id


# ── Files ────────────────────────────────────────────────────────────────────

def upload_file(channel: str, content: str, filename: str, title: str = None) -> dict | None:
    """Upload a text file/snippet to a Slack channel.

    Args:
        channel: Channel ID
        content: File text content
        filename: Filename (e.g. 'report.txt')
        title: Optional display title

    Returns:
        File dict or None
    """
    if not config.SLACK_BOT_TOKEN:
        return None
    try:
        resp = requests.post(
            f"{SLACK_API_BASE}/files.upload",
            headers={"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"},
            data={
                "channels": channel,
                "filename": filename,
                "title": title or filename,
            },
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
            timeout=30,
        )
        result = resp.json()
        if result.get("ok"):
            print(f"[SLACK_API] File '{filename}' uploaded to {channel}")
            return result.get("file")
        logger.error(f"[SLACK_API] File upload error: {result.get('error')}")
        return None
    except Exception as e:
        logger.error(f"[SLACK_API] File upload failed: {e}")
        return None


# ── Swarm-specific helpers ──────────────────────────────────────────────────

def post_experiment_update(channel: str, experiment_id: int, status: str,
                           idea: str, score: float, details: str = "") -> str | None:
    """Post a formatted experiment status update.

    Args:
        channel: Channel ID or name
        experiment_id: Database experiment id
        status: Current status (approved/rejected/running/completed/killed)
        idea: One-line experiment description
        score: Confidence score
        details: Optional extra detail text

    Returns:
        Message timestamp for threading, or None
    """
    icons = {
        "approved": "✅", "rejected": "❌", "running": "🔄",
        "completed": "🏁", "killed": "🚫", "pending": "🚦",
    }
    icon = icons.get(status, "📌")
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{icon} Experiment #{experiment_id} — {status.upper()}*"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Idea:*\n{idea}"},
            {"type": "mrkdwn", "text": f"*Confidence:*\n{score}/10"},
        ]},
    ]
    if details:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": details}})
    result = post_message(channel, text=f"Experiment #{experiment_id}: {status}", blocks=blocks)
    return result.get("ts") if result else None


def post_daily_summary(channel: str, summary: dict) -> bool:
    """Post a daily swarm summary to Slack.

    Args:
        channel: Channel ID or name
        summary: Dict with keys: experiments_run, leads_generated,
                 budget_spent, top_performer, circuit_breaker_status

    Returns:
        True if posted successfully
    """
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": f"Daily Swarm Summary — {datetime.now().strftime('%d %b %Y')}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Experiments Run:*\n{summary.get('experiments_run', 0)}"},
            {"type": "mrkdwn", "text": f"*Leads Generated:*\n{summary.get('leads_generated', 0)}"},
            {"type": "mrkdwn", "text": f"*Budget Spent:*\n${summary.get('budget_spent', 0):.0f} AUD"},
            {"type": "mrkdwn", "text": f"*Circuit Breaker:*\n{summary.get('circuit_breaker_status', 'GREEN')}"},
        ]},
    ]
    if summary.get("top_performer"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Top Performer:* {summary['top_performer']}"}})
    result = post_message(channel, text="Daily Swarm Summary", blocks=blocks)
    return result is not None


def is_configured() -> bool:
    """Check if Slack bot token is configured.

    Returns:
        True if SLACK_BOT_TOKEN is set
    """
    return bool(config.SLACK_BOT_TOKEN)
