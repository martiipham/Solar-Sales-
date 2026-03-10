"""Voice AI Call Handler — Flask webhook for Retell AI custom LLM.

Retell AI calls this endpoint when it needs a response from our LLM.
We inject company knowledge, call history, and function results into
GPT-4o, then return the response back to Retell to speak.

Compatible with ElevenLabs Conversational AI as well (see comments).

Retell LLM endpoint:   POST /voice/response
Post-call webhook:     POST /voice/post-call
Call started webhook:  POST /voice/call-started

Architecture:
  Retell receives call → sends POST /voice/call-started
  Retell needs response → sends POST /voice/response (conversation so far)
  Our server → calls GPT-4o with full system prompt + function definitions
  GPT-4o → returns text + optional function calls
  We execute function calls (GHL updates, DB writes) → return results to Retell
  Retell speaks the text, loops until call ends
  Retell → sends POST /voice/post-call with full transcript
  Our server → post_call.py analyses and finalises CRM

Usage:
    # Retell webhook configuration:
    # LLM Endpoint: https://your-server.com/voice/response
    # Post-call:    https://your-server.com/voice/post-call
"""

import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
from voice.call_functions import FUNCTION_DEFINITIONS, execute_function
from knowledge.company_kb import get_kb_for_agent
from voice.prompt_templates import build_prompt

logger = logging.getLogger(__name__)

voice_app = Flask(__name__)

# Security headers — applied to every response from this app
@voice_app.after_request
def _security_headers(response):
    """Attach security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

# Rate limiting — Redis-backed when REDIS_URL is set, in-memory fallback.
# Retell sends ~1 request per conversation turn; 120/min is generous headroom.
_storage_uri = config.REDIS_URL if config.REDIS_URL else "memory://"
_limiter = Limiter(
    app=voice_app,
    key_func=get_remote_address,
    default_limits=[],       # No blanket limit — applied per route below
    storage_uri=_storage_uri,
)

# In-memory call context store — lock guards concurrent access from Retell
_call_contexts: dict = {}
_ctx_lock = threading.Lock()
_CTX_MAX_AGE_HOURS = 2  # Evict contexts older than this (memory + info-disclosure fix)


def _cleanup_stale_contexts():
    """Background loop: evict call contexts that are more than 2 hours old.

    Runs every 30 minutes. Prevents unbounded memory growth and ensures
    stale lead data isn't kept in-process longer than necessary.
    """
    while True:
        threading.Event().wait(1800)  # 30-minute interval
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_CTX_MAX_AGE_HOURS)
        with _ctx_lock:
            stale = [
                cid for cid, ctx in _call_contexts.items()
                if datetime.fromisoformat(ctx.get("started_at", "2000-01-01")).replace(
                    tzinfo=timezone.utc
                ) < cutoff
            ]
            for cid in stale:
                del _call_contexts[cid]
        if stale:
            logger.info(f"[VOICE] Evicted {len(stale)} stale call context(s)")


# Start cleanup thread as daemon so it doesn't block shutdown
threading.Thread(target=_cleanup_stale_contexts, daemon=True, name="ctx-cleanup").start()

# ─────────────────────────────────────────────────────────────────────────────
# SIGNATURE VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def _verify_retell_signature() -> bool:
    """Verify HMAC-SHA256 signature from Retell webhook request.

    Retell sends the signature in the x-retell-signature header.
    If RETELL_WEBHOOK_SECRET is not set, verification is skipped (dev mode).

    Returns:
        True if signature is valid or secret is not configured, False otherwise.
    """
    secret = config.get("RETELL_WEBHOOK_SECRET", "")
    if not secret:
        return True  # Skip verification when secret is not configured

    sig_header = request.headers.get("x-retell-signature", "")
    if not sig_header:
        return False

    raw_body = request.get_data()
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

VOICE_SYSTEM_PROMPT = """You are a professional, friendly AI receptionist for {company_name}, an Australian solar energy company.

You represent {company_name} on all inbound calls. Your job is to:
1. Warmly greet and qualify solar leads
2. Answer questions about solar, pricing, rebates, and the company
3. Book free site assessments or arrange callbacks
4. Update the CRM in real-time using the available functions
5. Hand off to a human consultant when needed

VOICE RULES — CRITICAL:
- Speak naturally and conversationally — short sentences, easy to understand
- NEVER read out lists or bullet points — weave information into natural speech
- NEVER say "as an AI" or reveal you are an AI unless directly asked
- If asked if you're a robot: "I'm a digital assistant for {company_name} — I can help you just as well as anyone."
- Use Australian English: "colour", "neighbourhood", "organise", "mum"
- Keep responses under 3 sentences unless the customer needs detailed info
- Always confirm understanding: "Does that make sense?" or "Does that sound good?"
- When you collect info, use function calls to save it immediately
- Call lookup_caller at the very start of every call
- Call qualify_and_score once you have homeowner status, bill, and roof info
- End with end_call once the conversation is naturally complete

CONVERSATION FLOW:
1. GREET → Lookup caller → personalise greeting if known
2. DISCOVER → Natural questions about their situation (bill, roof, homeowner)
3. EDUCATE → Relevant rebate/product info based on their answers
4. OVERCOME → Handle objections using the knowledge base
5. CONVERT → Book assessment OR arrange callback OR send info pack
6. CLOSE → Confirm next steps, send SMS, end warmly

{company_knowledge}

TODAY'S DATE: {today}
CALL ID: {call_id}"""


def _build_system_prompt(client_id: str, call_id: str, template: str = "inbound_solar", extra: dict = None) -> str:
    """Build the full system prompt with injected company knowledge.

    Args:
        client_id: Client identifier for knowledge base lookup
        call_id: Current call ID for context
        template: Prompt template name (inbound_solar | outbound_cold | outbound_callback | support)
        extra: Optional extra variables to inject (lead_name, lead_score, etc.)

    Returns:
        Formatted system prompt string
    """
    return build_prompt(template=template, client_id=client_id, call_id=call_id, extra=extra)


# ─────────────────────────────────────────────────────────────────────────────
# RETELL WEBHOOK ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@voice_app.route("/voice/health", methods=["GET"])
def voice_health():
    """Health check for voice webhook server."""
    return jsonify({"status": "ok", "service": "voice-ai", "timestamp": datetime.utcnow().isoformat()}), 200


@voice_app.route("/voice/call-started", methods=["POST"])
def call_started():
    """Handle Retell call-started event.

    Initialises the call context and logs the inbound call.
    """
    if not _verify_retell_signature():
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data = request.get_json(force=True) or {}
        call_id      = data.get("call_id", "unknown")
        from_phone   = data.get("from_number") or data.get("caller_number", "")
        to_phone     = data.get("to_number", "")
        client_id    = _resolve_client_id(to_phone)

        # Initialise call context (lock guards concurrent Retell events)
        with _ctx_lock:
            _call_contexts[call_id] = {
                "call_id":      call_id,
                "client_id":    client_id,
                "from_phone":   from_phone,
                "to_phone":     to_phone,
                "started_at":   datetime.utcnow().isoformat(),
                "lead_data":    {"phone": from_phone},
                "call_outcome": None,
            }

        # Log to database
        _log_call(call_id, client_id, from_phone, "started")
        logger.debug(f"[VOICE] Call started: {call_id} | client={client_id}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"[VOICE] call-started error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@voice_app.route("/voice/response", methods=["POST"])
@_limiter.limit("120 per minute; 1000 per hour")
def retell_response():
    """Main Retell Custom LLM endpoint — generate next agent response.

    Retell sends the full conversation transcript and we return the next
    response from GPT-4o, potentially including function calls.
    """
    if not _verify_retell_signature():
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data = request.get_json(force=True) or {}
        call_id          = data.get("call_id", "unknown")
        interaction_type = data.get("interaction_type", "response_required")
        transcript       = data.get("transcript", [])
        response_id      = data.get("response_id", 0)

        # Get or create call context
        with _ctx_lock:
            ctx = _call_contexts.get(call_id, {
                "call_id": call_id,
                "client_id": config.get("DEFAULT_CLIENT_ID", "default"),
                "lead_data": {},
            })

        if interaction_type == "update_only":
            return jsonify({"response_id": response_id}), 200

        # Build GPT messages from Retell transcript format
        client_id   = ctx.get("client_id", "default")
        system_msg  = _build_system_prompt(client_id, call_id)
        messages    = _transcript_to_messages(system_msg, transcript)

        # Call GPT-4o
        response_text, function_calls = _call_llm(messages)

        # Execute any function calls, build tool results
        tool_results = []
        for fc in function_calls:
            fn_name   = fc.get("function", {}).get("name", "")
            fn_args   = json.loads(fc.get("function", {}).get("arguments", "{}"))
            fn_result = execute_function(fn_name, fn_args, ctx)
            tool_results.append({
                "tool_call_id": fc.get("id"),
                "result": json.dumps(fn_result),
            })

            # If end_call function was called, signal Retell to end
            if fn_name == "end_call":
                return jsonify({
                    "response_id":      response_id,
                    "content":          fn_result.get("farewell", response_text),
                    "content_complete": True,
                    "end_call":         True,
                }), 200

            # If transfer_to_human was called
            if fn_name == "transfer_to_human":
                return jsonify({
                    "response_id":      response_id,
                    "content":          fn_result.get("message", response_text),
                    "content_complete": True,
                    "transfer_call":    {"number": config.get("TRANSFER_PHONE", "")},
                }), 200

        # If we had function calls, get the final response with results injected
        if function_calls and tool_results:
            messages_with_results = messages + [
                {"role": "assistant", "tool_calls": function_calls},
                *[{"role": "tool", "tool_call_id": tr["tool_call_id"], "content": tr["result"]}
                  for tr in tool_results],
            ]
            response_text, _ = _call_llm(messages_with_results, allow_tools=False)

        with _ctx_lock:
            _call_contexts[call_id] = ctx
        return jsonify({
            "response_id":      response_id,
            "content":          response_text,
            "content_complete": True,
            "end_call":         False,
        }), 200

    except Exception as e:
        logger.error(f"[VOICE] response error: {e}")
        return jsonify({
            "response_id": data.get("response_id", 0) if "data" in dir() else 0,
            "content": "I'm sorry, I had a technical issue. Let me get someone to call you back shortly.",
            "content_complete": True,
            "end_call": False,
        }), 200


@voice_app.route("/voice/post-call", methods=["POST"])
def post_call():
    """Handle Retell post-call webhook — full transcript analysis and CRM update.

    Retell sends this after the call ends with the full transcript,
    call duration, recording URL, and any detected sentiments.
    """
    if not _verify_retell_signature():
        return jsonify({"error": "Invalid signature"}), 401
    try:
        data    = request.get_json(force=True) or {}
        call_id = data.get("call_id", "unknown")
        logger.debug(f"[VOICE] Post-call received: {call_id}")

        from voice.post_call import process_post_call
        with _ctx_lock:
            ctx_data = _call_contexts.pop(call_id, {})
        result = process_post_call(data, ctx_data)

        return jsonify({"status": "processed", "result": result}), 200

    except Exception as e:
        logger.error(f"[VOICE] post-call error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ELEVENLABS CONVERSATIONAL AI ENDPOINT (alternative to Retell)
# ─────────────────────────────────────────────────────────────────────────────

@voice_app.route("/voice/elevenlabs/response", methods=["POST"])
def elevenlabs_response():
    """ElevenLabs Conversational AI webhook endpoint.

    ElevenLabs sends messages in a slightly different format than Retell.
    This adapter normalises to our standard LLM pipeline.
    """
    try:
        data       = request.get_json(force=True) or {}
        session_id = data.get("session_id", "unknown")
        messages   = data.get("messages", [])
        client_id  = data.get("metadata", {}).get("client_id", "default")

        with _ctx_lock:
            ctx = _call_contexts.get(session_id, {
                "call_id":   session_id,
                "client_id": client_id,
                "lead_data": {},
            })

        system_msg = _build_system_prompt(client_id, session_id)
        gpt_msgs   = [{"role": "system", "content": system_msg}]

        for m in messages:
            role = "user" if m.get("role") == "user" else "assistant"
            gpt_msgs.append({"role": role, "content": m.get("content", "")})

        response_text, function_calls = _call_llm(gpt_msgs)

        for fc in function_calls:
            fn_name = fc.get("function", {}).get("name", "")
            fn_args = json.loads(fc.get("function", {}).get("arguments", "{}"))
            execute_function(fn_name, fn_args, ctx)

        with _ctx_lock:
            _call_contexts[session_id] = ctx
        return jsonify({"content": response_text, "end_session": False}), 200

    except Exception as e:
        logger.error(f"[VOICE ELEVENLABS] Error: {e}")
        return jsonify({"content": "I'm sorry, there was a technical issue. Please hold.", "end_session": False}), 200


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALLER
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm(messages: list, allow_tools: bool = True) -> tuple[str, list]:
    """Call GPT-4o with the conversation and optional function calling.

    Args:
        messages: OpenAI-format message list
        allow_tools: Whether to include function definitions

    Returns:
        Tuple of (response_text, function_calls_list)
    """
    if not config.is_configured():
        return "Thank you for calling. Let me arrange for one of our consultants to call you back.", []

    try:
        from openai import OpenAI
        client   = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30.0)
        kwargs   = {
            "model":       config.OPENAI_MODEL,
            "messages":    messages,
            "temperature": 0.7,
            "max_tokens":  300,
        }

        if allow_tools:
            kwargs["tools"]       = FUNCTION_DEFINITIONS
            kwargs["tool_choice"] = "auto"

        response  = client.chat.completions.create(**kwargs)
        choice    = response.choices[0].message
        text      = choice.content or ""
        tool_calls = []

        if hasattr(choice, "tool_calls") and choice.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in choice.tool_calls
            ]

        return text, tool_calls

    except Exception as e:
        logger.error(f"[VOICE LLM] GPT-4o error: {e}")
        return "I apologise, I'm having a brief technical issue. Could I take your number and have someone call you back?", []


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _transcript_to_messages(system_prompt: str, transcript: list) -> list:
    """Convert Retell transcript format to OpenAI messages format.

    Args:
        system_prompt: The system prompt string
        transcript: Retell transcript list of {role, content} dicts

    Returns:
        OpenAI-format messages list
    """
    messages = [{"role": "system", "content": system_prompt}]
    for turn in transcript:
        role    = "user" if turn.get("role") == "user" else "assistant"
        content = turn.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    return messages


def _resolve_client_id(to_phone: str) -> str:
    """Map the called phone number to a client_id.

    Each solar company client has their own phone number on Retell.
    This maps the inbound DID to the company's client_id.

    Args:
        to_phone: The phone number that was called

    Returns:
        client_id string
    """
    from memory.database import fetch_one
    profile = fetch_one(
        "SELECT client_id FROM company_profiles WHERE phone = ? AND active = 1",
        (to_phone,)
    )
    if profile:
        return profile.get("client_id", "default")

    # Fallback to env default
    return config.get("DEFAULT_CLIENT_ID", "default")


def _log_call(call_id: str, client_id: str, from_phone: str, status: str):
    """Log call event to the database.

    Args:
        call_id: Retell call ID
        client_id: Company client ID
        from_phone: Caller's phone number
        status: Current call status
    """
    try:
        from memory.database import get_conn
        with get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO call_logs
                   (call_id, client_id, from_phone, status, started_at)
                   VALUES (?,?,?,?,?)""",
                (call_id, client_id, from_phone, status, datetime.utcnow().isoformat())
            )
    except Exception as e:
        logger.error(f"[VOICE] Log failed: {e}")
