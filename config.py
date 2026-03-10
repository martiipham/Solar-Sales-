"""Configuration loader for Solar Swarm.

Loads all environment variables from .env file and provides
typed access to configuration throughout the application.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get(key: str, default=None):
    """Get an environment variable with optional default."""
    return os.getenv(key, default)


def require(key: str) -> str:
    """Get a required environment variable, raising if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return value


# OpenAI
OPENAI_API_KEY = get("OPENAI_API_KEY", "")
OPENAI_MODEL = get("OPENAI_MODEL", "gpt-4o")

# GoHighLevel
GHL_API_KEY = get("GHL_API_KEY", "")
GHL_LOCATION_ID = get("GHL_LOCATION_ID", "")
GHL_BASE_URL = "https://services.leadconnectorhq.com"

# Slack
SLACK_WEBHOOK_URL = get("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = get("SLACK_BOT_TOKEN", "")          # xoxb-... for Web API
SLACK_DEFAULT_CHANNEL = get("SLACK_DEFAULT_CHANNEL", "#swarm-alerts")
SLACK_SIGNING_SECRET = get("SLACK_SIGNING_SECRET", "")  # For verifying interactive payloads

# Human Gate — protect approve/reject/dashboard endpoints with a shared secret
# Set GATE_API_KEY in .env to enable. Requests must send: Authorization: Bearer <key>
GATE_API_KEY = get("GATE_API_KEY", "")

# JWT token expiry in seconds (default 24h). Tokens issued by POST /auth/token.
GATE_TOKEN_EXPIRY = int(get("GATE_TOKEN_EXPIRY", "86400"))

# Redis URL for rate limiter persistence across restarts and multiple processes.
# If not set, in-memory storage is used (fine for single-server deployments).
# Example: redis://localhost:6379/0
REDIS_URL = get("REDIS_URL", "")

# GHL webhook secret — validate inbound webhook payloads from GoHighLevel
# Set in GHL → Settings → Webhooks → Signing Secret
GHL_WEBHOOK_SECRET = get("GHL_WEBHOOK_SECRET", "")

# HubSpot
HUBSPOT_API_KEY = get("HUBSPOT_API_KEY", "")           # Private app token

# Salesforce
SALESFORCE_USERNAME = get("SALESFORCE_USERNAME", "")
SALESFORCE_PASSWORD = get("SALESFORCE_PASSWORD", "")
SALESFORCE_SECURITY_TOKEN = get("SALESFORCE_SECURITY_TOKEN", "")
SALESFORCE_CLIENT_ID = get("SALESFORCE_CLIENT_ID", "")
SALESFORCE_CLIENT_SECRET = get("SALESFORCE_CLIENT_SECRET", "")

# Budget
WEEKLY_BUDGET_AUD = float(get("WEEKLY_BUDGET_AUD", "500"))

# Flask
PORT_HUMAN_GATE    = int(get("PORT_HUMAN_GATE",    "5010"))  # 5000 reserved by macOS ControlCenter
PORT_GHL_WEBHOOKS  = int(get("PORT_GHL_WEBHOOKS",  "5001"))
PORT_DASHBOARD_API = int(get("PORT_DASHBOARD_API", "5003"))  # swarm-board live feed

# GoHighLevel pipeline id (optional — used by crm_sync for stage counts)
GHL_PIPELINE_ID = get("GHL_PIPELINE_ID", "")

# Database
DATABASE_PATH = get("DATABASE_PATH", "swarm.db")

# Logging
LOG_LEVEL = get("LOG_LEVEL", "INFO")

# Capital allocation buckets (fractions must sum to 1.0)
BUCKET_EXPLOIT = 0.60
BUCKET_EXPLORE = 0.30
BUCKET_MOONSHOT = 0.10

# Confidence thresholds
CONFIDENCE_AUTO_PROCEED = 8.5
CONFIDENCE_AUTO_KILL = 5.0

# Circuit breaker thresholds
CB_YELLOW_FAILURES = 3
CB_ORANGE_BURN_RATE = 1.50   # 150% of plan
CB_RED_FAILURES = 5
CB_RED_LOSS_FRACTION = 0.40  # 40% of weekly budget

# Kelly fraction (25% fractional Kelly)
KELLY_FRACTION = 0.25
KELLY_MAX_SINGLE = 0.25      # Never more than 25% in one experiment

# Explore protocol hours
EXPLORE_TOTAL_HOURS = 72
EXPLORE_CTR_THRESHOLD = 0.02  # 2% CTR triggers paid spend

# Pheromone decay
PHEROMONE_DECAY_DAYS = 7     # Start decaying after 7 days
PHEROMONE_DECAY_RATE = 0.50  # 50% weight loss per day after threshold

# ── Voice AI (Retell + ElevenLabs)
RETELL_API_KEY           = get("RETELL_API_KEY", "")
RETELL_DEFAULT_VOICE_ID  = get("RETELL_DEFAULT_VOICE_ID", "11labs-Adrian")
ELEVENLABS_API_KEY       = get("ELEVENLABS_API_KEY", "")
ELEVENLABS_DEFAULT_VOICE = get("ELEVENLABS_DEFAULT_VOICE", "")
PORT_VOICE_WEBHOOK       = int(get("PORT_VOICE_WEBHOOK", "5002"))
VOICE_WEBHOOK_BASE_URL   = get("VOICE_WEBHOOK_BASE_URL", "http://localhost:5002")
TRANSFER_PHONE           = get("TRANSFER_PHONE", "")
DEFAULT_CLIENT_ID        = get("DEFAULT_CLIENT_ID", "default")

# ── Email processing (optional IMAP polling)
IMAP_HOST   = get("IMAP_HOST", "")
IMAP_USER   = get("IMAP_USER", "")
IMAP_PASS   = get("IMAP_PASS", "")
IMAP_FOLDER = get("IMAP_FOLDER", "INBOX")


def is_configured() -> bool:
    """Check if critical API keys are configured."""
    return bool(OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-openai-key-here")


def retell_configured() -> bool:
    """Check if Retell AI is configured."""
    return bool(RETELL_API_KEY)


def elevenlabs_configured() -> bool:
    """Check if ElevenLabs is configured."""
    return bool(ELEVENLABS_API_KEY)
