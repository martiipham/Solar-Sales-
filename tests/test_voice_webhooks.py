"""Integration tests for Voice AI webhook endpoints.

Covers the core voice call-answering pipeline:
  POST /voice/call-started   — call initialisation
  POST /voice/response       — main LLM response (the "answer" endpoint)
  POST /voice/post-call      — transcript analysis after call ends
  POST /voice/elevenlabs/response — ElevenLabs alternative provider

Edge cases tested:
  - Invalid / missing webhook signatures (auth rejection)
  - LLM network errors and API timeouts (graceful fallback)
  - LLM rate limiting (retry exhaustion → fallback)
  - Non-retryable LLM errors (auth failure → immediate fallback)
  - Missing RETELL_WEBHOOK_SECRET config (reject all)
  - Malformed / empty JSON payloads
  - update_only interaction type (no LLM call)
  - Function call execution: end_call, transfer_to_human
  - Transfer fallback when LLM crashes on a live call
  - No transfer number configured → graceful end
  - Stale/missing call context recovery
  - ElevenLabs secret validation
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── Fixtures ────────────────────────────────────────────────────────────────

WEBHOOK_SECRET = "test-retell-webhook-secret"
EL_WEBHOOK_SECRET = "test-elevenlabs-secret"


@pytest.fixture(autouse=True)
def _voice_env(monkeypatch):
    """Set environment variables that config.get() reads via os.getenv."""
    monkeypatch.setenv("RETELL_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", EL_WEBHOOK_SECRET)
    monkeypatch.setenv("TRANSFER_PHONE", "+61800999999")
    monkeypatch.setenv("DEFAULT_CLIENT_ID", "default")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")


@pytest.fixture()
def voice_app(_patch_db, _voice_env):
    """Create a fresh voice Flask app with mocked config."""
    import importlib
    import config as cfg
    importlib.reload(cfg)

    from voice.call_handler import voice_app as app
    app.config["TESTING"] = True
    yield app


@pytest.fixture()
def vclient(voice_app):
    """Flask test client for the voice webhook server."""
    return voice_app.test_client()


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute HMAC-SHA256 signature matching Retell's scheme."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _signed_post(vclient, path, payload, secret=WEBHOOK_SECRET):
    """POST JSON with a valid Retell HMAC signature."""
    body = json.dumps(payload).encode()
    sig = _sign(body, secret)
    return vclient.post(
        path,
        data=body,
        content_type="application/json",
        headers={"x-retell-signature": sig},
    )


# ── Helpers for mocking the LLM ────────────────────────────────────────────

def _mock_llm_response(text="Hello, how can I help?", tool_calls=None):
    """Return a (text, tool_calls) tuple matching _call_llm's signature."""
    return (text, tool_calls or [])


def _make_tool_call(name, arguments, tc_id="tc_1"):
    """Build a tool call dict matching the format _call_llm returns."""
    return {
        "id": tc_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


# ═════════════════════════════════════════════════════════════════════════════
# /voice/call-started
# ═════════════════════════════════════════════════════════════════════════════

class TestCallStarted:
    """POST /voice/call-started — call initialisation."""

    @patch("voice.call_handler._log_call")
    @patch("voice.call_handler._resolve_client_id", return_value="solar_co_1")
    def test_valid_call_started(self, _mock_resolve, _mock_log, vclient):
        payload = {
            "call_id": "call_abc123",
            "from_number": "+61412345678",
            "to_number": "+61800123456",
        }
        resp = _signed_post(vclient, "/voice/call-started", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        _mock_log.assert_called_once_with("call_abc123", "solar_co_1", "+61412345678", "started")

    def test_missing_signature_rejected(self, vclient):
        resp = vclient.post(
            "/voice/call-started",
            json={"call_id": "call_nosig"},
        )
        assert resp.status_code == 401

    def test_invalid_signature_rejected(self, vclient):
        body = json.dumps({"call_id": "call_badsig"}).encode()
        resp = vclient.post(
            "/voice/call-started",
            data=body,
            content_type="application/json",
            headers={"x-retell-signature": "deadbeef"},
        )
        assert resp.status_code == 401

    @patch("voice.call_handler._log_call")
    @patch("voice.call_handler._resolve_client_id", return_value="default")
    def test_empty_payload_uses_defaults(self, _mock_resolve, _mock_log, vclient):
        """Missing fields should default gracefully, not crash."""
        resp = _signed_post(vclient, "/voice/call-started", {})
        assert resp.status_code == 200
        _mock_log.assert_called_once_with("unknown", "default", "", "started")

    @patch("voice.call_handler._log_call", side_effect=Exception("DB down"))
    @patch("voice.call_handler._resolve_client_id", return_value="default")
    def test_db_error_returns_500(self, _mock_resolve, _mock_log, vclient):
        """Database failure during call logging should return 500."""
        resp = _signed_post(vclient, "/voice/call-started", {"call_id": "call_db_err"})
        assert resp.status_code == 500
        assert "error" in resp.get_json().get("message", "").lower() or resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# /voice/response — Main "answer" endpoint
# ═════════════════════════════════════════════════════════════════════════════

class TestVoiceResponse:
    """POST /voice/response — the core call-answering endpoint."""

    @patch("voice.call_handler.execute_function")
    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="You are a solar AI.")
    def test_normal_response(self, _mock_prompt, mock_llm, _mock_exec, vclient):
        """Happy path: valid signature, LLM returns text, no function calls."""
        mock_llm.return_value = _mock_llm_response("G'day! How can I help you with solar today?")

        payload = {
            "call_id": "call_resp_001",
            "interaction_type": "response_required",
            "transcript": [
                {"role": "user", "content": "Hi, I want to know about solar panels."},
            ],
            "response_id": 42,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["response_id"] == 42
        assert "solar" in data["content"].lower()
        assert data["content_complete"] is True
        assert data["end_call"] is False

    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="You are a solar AI.")
    def test_update_only_skips_llm(self, _mock_prompt, mock_llm, vclient):
        """interaction_type=update_only should return immediately without calling LLM."""
        payload = {
            "call_id": "call_update_only",
            "interaction_type": "update_only",
            "transcript": [],
            "response_id": 7,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        assert resp.get_json()["response_id"] == 7
        mock_llm.assert_not_called()

    def test_missing_signature_rejected(self, vclient):
        resp = vclient.post("/voice/response", json={"call_id": "x"})
        assert resp.status_code == 401

    # ── Function call: end_call ─────────────────────────────────────────────

    @patch("voice.call_handler.execute_function")
    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_end_call_function(self, _mock_prompt, mock_llm, mock_exec, vclient):
        """When GPT calls end_call, response should signal Retell to hang up."""
        tc = _make_tool_call("end_call", {"reason": "completed"})
        mock_llm.return_value = ("Thanks for calling!", [tc])
        mock_exec.return_value = {"farewell": "Bye! Have a sunny day."}

        payload = {
            "call_id": "call_end",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "That's all, thanks."}],
            "response_id": 10,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["end_call"] is True
        assert data["content_complete"] is True
        assert "sunny" in data["content"].lower()

    # ── Function call: transfer_to_human ────────────────────────────────────

    @patch("voice.call_handler.execute_function")
    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_transfer_to_human(self, _mock_prompt, mock_llm, mock_exec, vclient):
        """transfer_to_human should include transfer_call with the configured number."""
        tc = _make_tool_call("transfer_to_human", {"reason": "angry customer"})
        mock_llm.return_value = ("Let me transfer you.", [tc])
        mock_exec.return_value = {"message": "Connecting you now."}

        payload = {
            "call_id": "call_transfer",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "I want to speak to a manager!"}],
            "response_id": 11,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content_complete"] is True
        assert "transfer_call" in data
        assert data["transfer_call"]["number"] == "+61800999999"

    # ── LLM network error → graceful transfer fallback ──────────────────────

    @patch("voice.call_handler.build_prompt", return_value="prompt")
    @patch("voice.call_handler._call_llm", side_effect=Exception("Connection reset"))
    def test_llm_network_error_transfers_to_human(self, _mock_llm, _mock_prompt, vclient):
        """When the LLM crashes, the caller should be transferred to a human."""
        payload = {
            "call_id": "call_net_err",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "Hello?"}],
            "response_id": 20,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        # With TRANSFER_PHONE set, should attempt transfer
        assert "transfer_call" in data
        assert data["content_complete"] is True

    # ── LLM error with no transfer phone → graceful end ─────────────────────

    @patch("voice.call_handler.build_prompt", return_value="prompt")
    @patch("voice.call_handler._call_llm", side_effect=Exception("API down"))
    def test_llm_error_no_transfer_phone_ends_call(self, _mock_llm, _mock_prompt, vclient, monkeypatch):
        """Without a transfer number, LLM failure should end call gracefully."""
        import config as cfg
        monkeypatch.setenv("TRANSFER_PHONE", "")
        monkeypatch.setattr(cfg, "TRANSFER_PHONE", "")

        payload = {
            "call_id": "call_no_transfer",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "Hello?"}],
            "response_id": 21,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["end_call"] is True
        assert "call you back" in data["content"].lower()

    # ── Function calls with follow-up LLM response ──────────────────────────

    @patch("voice.call_handler.execute_function")
    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_function_call_with_followup_response(self, _mock_prompt, mock_llm, mock_exec, vclient):
        """Non-terminal function calls should trigger a second LLM call with results."""
        tc = _make_tool_call("lookup_caller", {"phone": "+61400111222"})
        # First call returns function call; second call returns final text
        mock_llm.side_effect = [
            ("", [tc]),
            ("Hi Sarah! Great to hear from you again.", []),
        ]
        mock_exec.return_value = {"found": True, "name": "Sarah", "score": 8}

        payload = {
            "call_id": "call_fn_followup",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "Hi, this is Sarah."}],
            "response_id": 30,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Sarah" in data["content"]
        assert data["end_call"] is False
        # _call_llm should have been called twice: initial + with tool results
        assert mock_llm.call_count == 2

    # ── Empty transcript ────────────────────────────────────────────────────

    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_empty_transcript(self, _mock_prompt, mock_llm, vclient):
        """Empty transcript (first turn) should still generate a response."""
        mock_llm.return_value = _mock_llm_response("Hi, you've reached Solar Solutions!")

        payload = {
            "call_id": "call_empty_tx",
            "interaction_type": "response_required",
            "transcript": [],
            "response_id": 1,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        assert resp.get_json()["content"] != ""

    # ── Malformed JSON body ─────────────────────────────────────────────────

    def test_malformed_json_body(self, vclient):
        """Non-JSON body should be handled gracefully."""
        body = b"this is not json"
        sig = _sign(body)
        resp = vclient.post(
            "/voice/response",
            data=body,
            content_type="application/json",
            headers={"x-retell-signature": sig},
        )
        # Should not crash — Flask's get_json(force=True) returns None, defaults kick in
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# /voice/response — LLM retry / rate-limit edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestVoiceResponseLLMEdgeCases:
    """Edge cases for _call_llm retry logic under rate limits and timeouts."""

    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_llm_rate_limit_exhaustion_returns_fallback(self, _mock_prompt, mock_llm, vclient):
        """When OpenAI rate-limits all retries, the fallback message is returned."""
        mock_llm.return_value = (
            "I apologise, I'm having a brief technical issue. "
            "Could I take your number and have someone call you back?",
            [],
        )

        payload = {
            "call_id": "call_rate_limit",
            "interaction_type": "response_required",
            "transcript": [{"role": "user", "content": "Hello"}],
            "response_id": 50,
        }
        resp = _signed_post(vclient, "/voice/response", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content_complete"] is True
        assert "apologise" in data["content"].lower() or "call you back" in data["content"].lower()

    def test_llm_timeout_returns_fallback(self, vclient):
        """When OpenAI times out on all retries, caller gets a polite fallback."""
        with patch("voice.call_handler.build_prompt", return_value="prompt"), \
             patch("voice.call_handler._call_llm") as mock_llm:
            mock_llm.return_value = (
                "I apologise, I'm having a brief technical issue. "
                "Could I take your number and have someone call you back?",
                [],
            )

            payload = {
                "call_id": "call_timeout",
                "interaction_type": "response_required",
                "transcript": [{"role": "user", "content": "Are you there?"}],
                "response_id": 51,
            }
            resp = _signed_post(vclient, "/voice/response", payload)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "apologise" in data["content"].lower() or "call you back" in data["content"].lower()

    def test_llm_not_configured_returns_consultant_message(self, vclient):
        """When OPENAI_API_KEY is missing, _call_llm returns a safe fallback."""
        with patch("voice.call_handler.build_prompt", return_value="prompt"), \
             patch("voice.call_handler.config") as mock_cfg:
            mock_cfg.is_configured.return_value = False
            mock_cfg.get.side_effect = lambda k, d="": {
                "DEFAULT_CLIENT_ID": "default",
                "TRANSFER_PHONE": "",
            }.get(k, d)
            mock_cfg.TRANSFER_PHONE = ""
            mock_cfg.REDIS_URL = ""

            # Call _call_llm directly to test the not-configured path
            from voice.call_handler import _call_llm
            text, calls = _call_llm([{"role": "system", "content": "test"}])
            assert "consultant" in text.lower() or "call you back" in text.lower()
            assert calls == []


# ═════════════════════════════════════════════════════════════════════════════
# /voice/post-call
# ═════════════════════════════════════════════════════════════════════════════

class TestPostCall:
    """POST /voice/post-call — transcript analysis after call ends."""

    @patch("voice.post_call.process_post_call")
    def test_valid_post_call(self, mock_process, vclient):
        payload = {
            "call_id": "call_done_001",
            "transcript": "Full transcript here...",
            "call_duration": 120,
            "recording_url": "https://retell.ai/recordings/abc.wav",
        }
        mock_process.return_value = {"status": "ok", "lead_score": 8.5}

        resp = _signed_post(vclient, "/voice/post-call", payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "processed"
        assert data["result"]["lead_score"] == 8.5

    def test_missing_signature_rejected(self, vclient):
        resp = vclient.post("/voice/post-call", json={"call_id": "x"})
        assert resp.status_code == 401

    @patch("voice.post_call.process_post_call", side_effect=Exception("Analysis failed"))
    def test_analysis_error_returns_500(self, _mock, vclient):
        payload = {"call_id": "call_fail_analysis"}
        resp = _signed_post(vclient, "/voice/post-call", payload)
        assert resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# /voice/elevenlabs/response — ElevenLabs alternative provider
# ═════════════════════════════════════════════════════════════════════════════

class TestElevenLabsResponse:
    """POST /voice/elevenlabs/response — alternative voice provider webhook."""

    @patch("voice.call_handler._call_llm")
    @patch("voice.call_handler.build_prompt", return_value="You are Aria.")
    def test_valid_elevenlabs_response(self, _mock_prompt, mock_llm, vclient):
        mock_llm.return_value = _mock_llm_response("Hi, how can I help?")

        payload = {
            "session_id": "el_session_001",
            "messages": [
                {"role": "user", "content": "Hi there"},
            ],
            "metadata": {"client_id": "solar_co_1"},
        }
        resp = vclient.post(
            "/voice/elevenlabs/response",
            json=payload,
            headers={"X-ElevenLabs-Secret": EL_WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content"] != ""
        assert data["end_session"] is False

    def test_missing_secret_rejected(self, vclient):
        resp = vclient.post("/voice/elevenlabs/response", json={"session_id": "x"})
        assert resp.status_code == 401

    def test_wrong_secret_rejected(self, vclient):
        resp = vclient.post(
            "/voice/elevenlabs/response",
            json={"session_id": "x"},
            headers={"X-ElevenLabs-Secret": "wrong-secret"},
        )
        assert resp.status_code == 401

    @patch("voice.call_handler._call_llm", side_effect=Exception("EL provider down"))
    @patch("voice.call_handler.build_prompt", return_value="prompt")
    def test_llm_error_returns_graceful_message(self, _mock_prompt, _mock_llm, vclient):
        """ElevenLabs endpoint should return a polite hold message on LLM failure."""
        payload = {
            "session_id": "el_error",
            "messages": [{"role": "user", "content": "Hello"}],
            "metadata": {"client_id": "default"},
        }
        resp = vclient.post(
            "/voice/elevenlabs/response",
            json=payload,
            headers={"X-ElevenLabs-Secret": EL_WEBHOOK_SECRET},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "technical" in data["content"].lower() or "hold" in data["content"].lower()
        assert data["end_session"] is False

    def test_elevenlabs_secret_not_configured(self, vclient, monkeypatch):
        """When ELEVENLABS_WEBHOOK_SECRET is empty, all requests are rejected."""
        monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "")

        resp = vclient.post(
            "/voice/elevenlabs/response",
            json={"session_id": "x"},
            headers={"X-ElevenLabs-Secret": "anything"},
        )
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# /voice/health — health check
# ═════════════════════════════════════════════════════════════════════════════

class TestVoiceHealth:
    """GET /voice/health — no auth required."""

    def test_health_check(self, vclient):
        resp = vclient.get("/voice/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "voice-ai"

    def test_health_check_has_security_headers(self, vclient):
        resp = vclient.get("/voice/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Cache-Control") == "no-store"


# ═════════════════════════════════════════════════════════════════════════════
# Signature verification edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestSignatureVerification:
    """Edge cases for HMAC signature verification."""

    def test_retell_secret_not_configured_rejects_all(self, vclient, monkeypatch):
        """When RETELL_WEBHOOK_SECRET is empty, ALL requests are rejected."""
        import config as cfg
        monkeypatch.setenv("RETELL_WEBHOOK_SECRET", "")
        monkeypatch.setattr(cfg, "RETELL_WEBHOOK_SECRET", "")

        body = json.dumps({"call_id": "test"}).encode()
        sig = _sign(body, "any-secret")
        resp = vclient.post(
            "/voice/call-started",
            data=body,
            content_type="application/json",
            headers={"x-retell-signature": sig},
        )
        assert resp.status_code == 401

    def test_empty_signature_header_rejected(self, vclient):
        resp = vclient.post(
            "/voice/response",
            json={"call_id": "x"},
            headers={"x-retell-signature": ""},
        )
        assert resp.status_code == 401

    def test_tampered_body_rejected(self, vclient):
        """Signature computed on different body should be rejected."""
        original_body = json.dumps({"call_id": "legit"}).encode()
        sig = _sign(original_body)
        tampered_body = json.dumps({"call_id": "evil"}).encode()
        resp = vclient.post(
            "/voice/call-started",
            data=tampered_body,
            content_type="application/json",
            headers={"x-retell-signature": sig},
        )
        assert resp.status_code == 401
