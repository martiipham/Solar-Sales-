"""Social Signal Collector — Monitors LinkedIn and social media for solar company signals.

Detects hiring posts, funding announcements, new partnerships, and pain-point
complaints that indicate a company is ripe for CRM automation outreach.
Uses GPT-4o to classify signal strength when OpenAI is configured.
"""

import json
import logging
import uuid
from datetime import datetime
from memory.database import get_conn, json_payload
import config

logger = logging.getLogger(__name__)

SIGNAL_KEYWORDS = [
    "hiring", "scaling", "growth", "looking for", "need help",
    "manual process", "too many leads", "follow up", "crm",
    "solar install", "new office", "expanding", "franchise",
]


def collect(source: dict) -> dict:
    """Collect and classify social signals for solar companies.

    Args:
        source: Source dict with config: platform, query, limit

    Returns:
        {success, records, signals, error}
    """
    cfg = source.get("config", {})
    platform = cfg.get("platform", "linkedin")
    query = cfg.get("query", "solar company Australia")
    limit = cfg.get("limit", 20)
    source_id = source.get("source_id", "unknown")

    print(f"[SOCIAL SIGNAL] Scanning {platform}: {query[:50]}")

    posts = _fetch_posts(platform, query, limit)
    classified = [_classify_post(p) for p in posts]
    strong_signals = [p for p in classified if p.get("signal_strength") in ("high", "medium")]

    stored = _store_records(classified, source_id, platform)
    print(f"[SOCIAL SIGNAL] {len(strong_signals)} strong signals from {len(posts)} posts")

    return {"success": True, "records": stored, "signals": len(strong_signals)}


def _fetch_posts(platform: str, query: str, limit: int) -> list:
    """Fetch social posts — mock implementation (real API requires paid access)."""
    logger.info(f"[SOCIAL SIGNAL] Fetching from {platform} (mock — live API requires credentials)")
    return _mock_posts(query)[:limit]


def _classify_post(post: dict) -> dict:
    """Score a post for signal strength based on keywords and GPT-4o."""
    text = (post.get("text", "") + " " + post.get("title", "")).lower()
    keyword_hits = [k for k in SIGNAL_KEYWORDS if k in text]
    base_score = len(keyword_hits)

    if base_score >= 3:
        signal_strength = "high"
    elif base_score >= 1:
        signal_strength = "medium"
    else:
        signal_strength = "low"

    if config.is_configured() and base_score >= 2:
        signal_strength = _gpt_classify(post.get("text", ""), signal_strength)

    return {**post, "keyword_hits": keyword_hits, "signal_strength": signal_strength}


def _gpt_classify(text: str, fallback: str) -> str:
    """Use GPT-4o to refine signal classification."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        prompt = (
            f"Rate this post as 'high', 'medium', or 'low' signal for selling CRM automation "
            f"to an Australian solar company. Return only the word.\n\nPost: {text[:300]}"
        )
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        result = response.choices[0].message.content.strip().lower()
        return result if result in ("high", "medium", "low") else fallback
    except Exception as e:
        logger.error(f"[SOCIAL SIGNAL] GPT classify error: {e}")
        return fallback


def _store_records(records: list, source_id: str, platform: str) -> int:
    """Persist classified social signals."""
    stored = 0
    for rec in records:
        rec_id = f"cd_{uuid.uuid4().hex[:10]}"
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO collected_data
                       (record_id, source_id, source_type, data_type, raw_data,
                        data, normalized, collected_at)
                       VALUES (?,?,?,?,?,?,1,?)""",
                    (rec_id, source_id, "social", platform,
                     json_payload(rec), json_payload(rec),
                     datetime.utcnow().isoformat()),
                )
            stored += 1
        except Exception as e:
            logger.error(f"[SOCIAL SIGNAL] Store error: {e}")
    return stored


def _mock_posts(query: str) -> list:
    """Return mock social posts for testing."""
    return [
        {
            "platform": "linkedin",
            "author": "Tom Mitchell",
            "company": "SunPower Perth",
            "title": "We're hiring! Sales team growing fast.",
            "text": "Exciting times at SunPower Perth — we're hiring 3 solar consultants. "
                    "Our lead volume has doubled but our follow up process needs work. "
                    "Manual crm processes are killing us. Looking for better solutions.",
            "date": datetime.utcnow().isoformat(),
            "url": "https://linkedin.com/posts/mock1",
        },
        {
            "platform": "linkedin",
            "author": "Jessica Park",
            "company": "Brisbane Solar Co",
            "title": "Scaling our solar install business",
            "text": "We've gone from 20 to 60 solar installs per month this year. "
                    "Managing everything in spreadsheets. Need to upgrade our systems.",
            "date": datetime.utcnow().isoformat(),
            "url": "https://linkedin.com/posts/mock2",
        },
        {
            "platform": "linkedin",
            "author": "David Wong",
            "company": "Eco Energy Melbourne",
            "title": "Great weekend installing solar panels",
            "text": "Another beautiful day installing solar in the suburbs. Love this work.",
            "date": datetime.utcnow().isoformat(),
            "url": "https://linkedin.com/posts/mock3",
        },
    ]
