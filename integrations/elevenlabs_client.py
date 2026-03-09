"""ElevenLabs API Client — Text-to-Speech and Conversational AI.

Covers two ElevenLabs products:
  1. Text-to-Speech (TTS) — convert text to audio bytes
  2. Conversational AI — full voice agent sessions (alternative to Retell)

Pricing reference (as of 2025):
  TTS:              ~$0.0050 / 1,000 characters (Starter), $0.0024 (Creator+)
  Conversational AI: ~$0.0050 / 1,000 characters generated

API Reference: https://elevenlabs.io/docs/api-reference

Usage:
    from integrations.elevenlabs_client import tts, list_voices, is_configured
    audio_bytes = tts("Hello, welcome to SunTech Solar!", voice_id="21m00...")
"""

import logging
import requests

import config

logger = logging.getLogger(__name__)

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Cost estimate per 1,000 characters (USD) — update if pricing changes
COST_PER_1K_CHARS_USD = 0.005


def _headers(accept: str = "application/json") -> dict:
    """Return authenticated headers for ElevenLabs API.

    Args:
        accept: Accept header value

    Returns:
        Headers dict
    """
    return {
        "xi-api-key":   config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept":       accept,
    }


def _request(method: str, endpoint: str, data: dict = None, stream: bool = False):
    """Make an authenticated request to the ElevenLabs API.

    Args:
        method: HTTP method
        endpoint: API endpoint path (e.g. /tts/voice-id)
        data: JSON body
        stream: If True, return raw response for streaming audio

    Returns:
        Response JSON dict, bytes, or None on failure
    """
    if not config.ELEVENLABS_API_KEY:
        logger.warning("[ELEVENLABS] No API key configured")
        return None
    try:
        url  = f"{ELEVENLABS_BASE}{endpoint}"
        resp = requests.request(
            method, url,
            headers=_headers("audio/mpeg" if stream else "application/json"),
            json=data,
            stream=stream,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return resp.content if stream else resp.json()
        logger.error(f"[ELEVENLABS] {method} {endpoint} → {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[ELEVENLABS] Request failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TEXT-TO-SPEECH
# ─────────────────────────────────────────────────────────────────────────────

def tts(
    text: str,
    voice_id: str = None,
    model_id: str = "eleven_turbo_v2_5",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
) -> bytes | None:
    """Convert text to speech audio bytes (MP3).

    Args:
        text: Text to synthesise
        voice_id: ElevenLabs voice ID (defaults to config.ELEVENLABS_DEFAULT_VOICE)
        model_id: TTS model — eleven_turbo_v2_5 (fastest), eleven_multilingual_v2 (quality)
        stability: Voice stability 0.0–1.0 (higher = more consistent)
        similarity_boost: Voice clarity 0.0–1.0
        style: Style exaggeration 0.0–1.0 (0 = no exaggeration)
        use_speaker_boost: Enhance speaker similarity

    Returns:
        MP3 audio bytes or None on failure
    """
    vid = voice_id or config.ELEVENLABS_DEFAULT_VOICE
    if not vid:
        logger.error("[ELEVENLABS] No voice_id provided and no default configured")
        return None

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability":        stability,
            "similarity_boost": similarity_boost,
            "style":            style,
            "use_speaker_boost": use_speaker_boost,
        },
    }
    audio = _request("POST", f"/text-to-speech/{vid}", data=payload, stream=True)
    if audio:
        char_count = len(text)
        estimated_cost = (char_count / 1000) * COST_PER_1K_CHARS_USD
        logger.info(f"[ELEVENLABS] TTS {char_count} chars → ~${estimated_cost:.4f} USD")
    return audio


def tts_stream(text: str, voice_id: str = None, model_id: str = "eleven_turbo_v2_5"):
    """Stream TTS audio for low-latency playback.

    Args:
        text: Text to synthesise
        voice_id: ElevenLabs voice ID
        model_id: TTS model

    Yields:
        Audio byte chunks
    """
    vid = voice_id or config.ELEVENLABS_DEFAULT_VOICE
    if not config.ELEVENLABS_API_KEY or not vid:
        return

    try:
        url  = f"{ELEVENLABS_BASE}/text-to-speech/{vid}/stream"
        resp = requests.post(
            url,
            headers=_headers("audio/mpeg"),
            json={
                "text": text,
                "model_id": model_id,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            stream=True,
            timeout=30,
        )
        if resp.status_code == 200:
            for chunk in resp.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk
    except Exception as e:
        logger.error(f"[ELEVENLABS] Stream TTS failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# VOICE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def list_voices() -> list:
    """List all available voices in the account.

    Returns:
        List of voice dicts with voice_id, name, category, labels
    """
    result = _request("GET", "/voices")
    return result.get("voices", []) if result else []


def get_voice(voice_id: str) -> dict | None:
    """Fetch a single voice by ID.

    Args:
        voice_id: ElevenLabs voice ID

    Returns:
        Voice dict or None
    """
    return _request("GET", f"/voices/{voice_id}")


def clone_voice(name: str, audio_file_paths: list[str], description: str = "") -> dict | None:
    """Clone a voice from audio samples (requires Creator plan+).

    Args:
        name: Name for the cloned voice
        audio_file_paths: List of local paths to audio sample files (WAV/MP3)
        description: Optional voice description

    Returns:
        Created voice dict or None
    """
    if not config.ELEVENLABS_API_KEY:
        return None
    try:
        files = [("files", open(p, "rb")) for p in audio_file_paths]
        resp  = requests.post(
            f"{ELEVENLABS_BASE}/voices/add",
            headers={"xi-api-key": config.ELEVENLABS_API_KEY},
            data={"name": name, "description": description},
            files=files,
            timeout=60,
        )
        if resp.status_code in (200, 201):
            result = resp.json()
            print(f"[ELEVENLABS] Voice cloned: {name} (id={result.get('voice_id')})")
            return result
        logger.error(f"[ELEVENLABS] Clone failed: {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[ELEVENLABS] Clone voice failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSATIONAL AI AGENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def create_conversational_agent(
    agent_name: str,
    system_prompt: str,
    voice_id: str = None,
    first_message: str = "Hello! How can I help you today?",
    language: str = "en",
) -> dict | None:
    """Create an ElevenLabs Conversational AI agent.

    This is the ElevenLabs alternative to Retell — a fully managed
    conversational AI that handles the entire call pipeline.

    Args:
        agent_name: Display name
        system_prompt: System instructions for the agent
        voice_id: ElevenLabs voice ID to use
        first_message: Opening line the agent speaks first
        language: Language code

    Returns:
        Created agent dict with agent_id, or None
    """
    vid = voice_id or config.ELEVENLABS_DEFAULT_VOICE or "21m00Tcm4TlvDq8ikWAM"
    payload = {
        "name": agent_name,
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": system_prompt,
                    "llm": "gpt-4o",
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
                "first_message": first_message,
                "language": language,
            },
            "tts": {
                "voice_id": vid,
                "model_id": "eleven_turbo_v2_5",
                "optimize_streaming_latency": 4,
            },
            "stt": {
                "provider": "deepgram",
                "model": "nova-2",
                "language": language,
            },
            "turn": {
                "mode": "turn",
                "turn_timeout": 7,
            },
        },
    }
    result = _request("POST", "/convai/agents/create", data=payload)
    if result:
        print(f"[ELEVENLABS] Agent created: {agent_name} (id={result.get('agent_id')})")
    return result


def get_conversational_agent(agent_id: str) -> dict | None:
    """Fetch a Conversational AI agent by ID.

    Args:
        agent_id: ElevenLabs agent ID

    Returns:
        Agent dict or None
    """
    return _request("GET", f"/convai/agents/{agent_id}")


def update_conversational_agent(agent_id: str, updates: dict) -> dict | None:
    """Update a Conversational AI agent.

    Args:
        agent_id: ElevenLabs agent ID
        updates: Partial update dict

    Returns:
        Updated agent dict or None
    """
    result = _request("PATCH", f"/convai/agents/{agent_id}", data=updates)
    if result:
        print(f"[ELEVENLABS] Agent updated: {agent_id}")
    return result


def list_conversational_agents() -> list:
    """List all Conversational AI agents in the account.

    Returns:
        List of agent dicts
    """
    result = _request("GET", "/convai/agents")
    return result.get("agents", []) if result else []


def get_conversation(conversation_id: str) -> dict | None:
    """Fetch a completed conversation with transcript.

    Args:
        conversation_id: ElevenLabs conversation ID

    Returns:
        Conversation dict with transcript, duration, cost, or None
    """
    return _request("GET", f"/convai/conversations/{conversation_id}")


def list_conversations(agent_id: str = None, limit: int = 50) -> list:
    """List recent conversations.

    Args:
        agent_id: Optional filter by agent ID
        limit: Max conversations to return

    Returns:
        List of conversation dicts
    """
    params = f"?page_size={limit}"
    if agent_id:
        params += f"&agent_id={agent_id}"
    result = _request("GET", f"/convai/conversations{params}")
    return result.get("conversations", []) if result else []


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT & USAGE
# ─────────────────────────────────────────────────────────────────────────────

def get_subscription() -> dict | None:
    """Get current subscription / usage details.

    Returns:
        Subscription dict with character_count, character_limit, status, or None
    """
    return _request("GET", "/user/subscription")


def get_usage_stats() -> dict:
    """Get character usage summary from subscription info.

    Returns:
        Dict with characters_used, characters_remaining, plan, reset_date
    """
    sub = get_subscription()
    if not sub:
        return {"error": "Could not fetch subscription info"}
    return {
        "characters_used":      sub.get("character_count", 0),
        "characters_limit":     sub.get("character_limit", 0),
        "characters_remaining": sub.get("character_limit", 0) - sub.get("character_count", 0),
        "plan":                 sub.get("tier", "unknown"),
        "next_reset":           sub.get("next_character_count_reset_unix", None),
        "estimated_cost_usd":   round(sub.get("character_count", 0) / 1000 * COST_PER_1K_CHARS_USD, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SETUP HELPER
# ─────────────────────────────────────────────────────────────────────────────

def setup_client_voice_agent(
    client_id: str,
    company_name: str,
    voice_id: str = None,
    webhook_base_url: str = None,
) -> dict:
    """One-command setup: create an ElevenLabs agent for a new client.

    Args:
        client_id: Company client ID
        company_name: Human-readable company name
        voice_id: ElevenLabs voice ID (optional — uses default if not set)
        webhook_base_url: Your server URL for post-call webhooks (optional)

    Returns:
        Setup result dict with agent_id
    """
    try:
        from voice.prompt_templates import build_prompt
        system_prompt = build_prompt("inbound_solar", client_id=client_id, call_id="setup")
    except Exception as e:
        logger.error(f"[ELEVENLABS SETUP] Prompt build failed: {e}")
        system_prompt = f"You are a solar sales assistant for {company_name}."

    agent = create_conversational_agent(
        agent_name=f"{company_name} — AI Receptionist",
        system_prompt=system_prompt,
        voice_id=voice_id,
        first_message=f"Hello! Thanks for calling {company_name}. How can I help you today?",
    )

    if not agent:
        return {"success": False, "error": "Agent creation failed"}

    agent_id = agent.get("agent_id")

    # Save agent_id to company profile
    try:
        from knowledge.company_kb import upsert_company
        upsert_company(client_id, {"elevenlabs_voice_id": voice_id or agent_id})
    except Exception as e:
        logger.error(f"[ELEVENLABS SETUP] Profile update failed: {e}")

    print(f"[ELEVENLABS SETUP] Complete: {company_name} | agent={agent_id}")
    return {"success": True, "agent_id": agent_id, "company": company_name}


def is_configured() -> bool:
    """Check if ElevenLabs API key is configured.

    Returns:
        True if configured
    """
    return bool(config.ELEVENLABS_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# VOICE PRESETS (reference configs for common use cases)
# ─────────────────────────────────────────────────────────────────────────────

VOICE_PRESETS = {
    "professional_male_au": {
        "description": "Professional Australian male — good for solar sales",
        "voice_id":    "pNInz6obpgDQGcFmaJgB",  # Adam (English, male)
        "model_id":    "eleven_turbo_v2_5",
        "settings":    {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0},
    },
    "friendly_female_au": {
        "description": "Warm friendly female — good for support calls",
        "voice_id":    "EXAVITQu4vr4xnSDxMaL",  # Bella (English, female)
        "model_id":    "eleven_turbo_v2_5",
        "settings":    {"stability": 0.5, "similarity_boost": 0.8, "style": 0.1},
    },
    "authoritative_male": {
        "description": "Confident, authoritative — good for callbacks",
        "voice_id":    "VR6AewLTigWG4xSOukaG",  # Arnold (English, male)
        "model_id":    "eleven_multilingual_v2",
        "settings":    {"stability": 0.65, "similarity_boost": 0.7, "style": 0.05},
    },
}
