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
GHL_PIPELINE_ID   = get("GHL_PIPELINE_ID", "")
GHL_STAGE_HOT     = get("GHL_STAGE_HOT", "")
GHL_STAGE_BOOKED  = get("GHL_STAGE_BOOKED", "")
GHL_STAGE_NURTURE = get("GHL_STAGE_NURTURE", "")

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

# ── Voice AI (Retell)
RETELL_API_KEY           = get("RETELL_API_KEY", "")
RETELL_AGENT_ID          = get("RETELL_AGENT_ID", "")
RETELL_DEFAULT_VOICE_ID  = get("RETELL_DEFAULT_VOICE_ID", "11labs-Adrian")
RETELL_WEBHOOK_SECRET    = get("RETELL_WEBHOOK_SECRET", "")
ELEVENLABS_API_KEY       = get("ELEVENLABS_API_KEY", "")
ELEVENLABS_DEFAULT_VOICE = get("ELEVENLABS_DEFAULT_VOICE", "")
PORT_VOICE_WEBHOOK       = int(get("PORT_VOICE_WEBHOOK", "5002"))
VOICE_WEBHOOK_BASE_URL   = get("VOICE_WEBHOOK_BASE_URL", "http://localhost:5002")
TRANSFER_PHONE           = get("TRANSFER_PHONE", "")
DEFAULT_CLIENT_ID        = get("DEFAULT_CLIENT_ID", "default")

# ── Auth
JWT_SECRET = get("JWT_SECRET", "")

# ── Cal.com (booking)
CALCOM_API_KEY        = get("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID  = get("CALCOM_EVENT_TYPE_ID", "")
CALCOM_BOOKING_URL    = get("CALCOM_BOOKING_URL", "")

# ── Twilio (SMS confirmations)
TWILIO_ACCOUNT_SID  = get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER  = get("TWILIO_FROM_NUMBER", "")

# ── Email processing (optional IMAP polling)
IMAP_HOST   = get("IMAP_HOST", "")
IMAP_USER   = get("IMAP_USER", "")
IMAP_PASS   = get("IMAP_PASS", "")
IMAP_FOLDER = get("IMAP_FOLDER", "INBOX")


def check_required_env_vars() -> None:
    """Warn on startup if any critical environment variables are missing.

    Prints a warning for each missing key and exits if OPENAI_API_KEY is absent,
    since the system cannot function without it.
    """
    warnings = []

    critical = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "GATE_API_KEY":   GATE_API_KEY,
    }
    recommended = {
        "GHL_API_KEY":           GHL_API_KEY,
        "GHL_LOCATION_ID":       GHL_LOCATION_ID,
        "GHL_WEBHOOK_SECRET":    GHL_WEBHOOK_SECRET,
        "RETELL_WEBHOOK_SECRET": RETELL_WEBHOOK_SECRET,
        "JWT_SECRET":            JWT_SECRET,
        "SLACK_SIGNING_SECRET":  SLACK_SIGNING_SECRET,
    }

    for key, val in critical.items():
        if not val or val.startswith("your-") or val.startswith("sk-your-"):
            warnings.append(f"  [CRITICAL] {key} is not set")

    for key, val in recommended.items():
        if not val:
            warnings.append(f"  [WARNING]  {key} is not set (recommended for production)")

    if warnings:
        print("[CONFIG] Startup environment check:")
        for w in warnings:
            print(w)
        # Exit only if a truly critical key is missing
        critical_missing = [w for w in warnings if "[CRITICAL]" in w]
        if critical_missing:
            import sys
            print("[CONFIG] Aborting — set missing critical keys in .env and restart.")
            sys.exit(1)


def is_configured() -> bool:
    """Check if critical API keys are configured."""
    return bool(OPENAI_API_KEY and OPENAI_API_KEY != "sk-your-openai-key-here")


def retell_configured() -> bool:
    """Check if Retell AI is configured."""
    return bool(RETELL_API_KEY)


def elevenlabs_configured() -> bool:
    """Check if ElevenLabs is configured."""
    return bool(ELEVENLABS_API_KEY)
