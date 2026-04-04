"""Tests for Twilio SID validation logic.

Covers: Account SID, Message SID, Call SID, Auth Token format validation,
and full config validation used before sending SMS via Twilio API.
"""

import os
import sys

import pytest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, APP_ROOT)

from integrations.twilio_validators import (
    is_valid_account_sid,
    is_valid_auth_token,
    is_valid_call_sid,
    is_valid_message_sid,
    is_valid_sid,
    validate_twilio_config,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_ACCOUNT_SID = "AC" + "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"  # AC + 32 hex
VALID_MESSAGE_SID = "SM" + "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
VALID_CALL_SID = "CA" + "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
VALID_AUTH_TOKEN = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"  # 32 hex chars


# ── Generic SID validation ───────────────────────────────────────────────────


class TestIsValidSid:
    """is_valid_sid() — generic SID format checks."""

    def test_valid_account_sid(self):
        assert is_valid_sid(VALID_ACCOUNT_SID) is True

    def test_valid_message_sid(self):
        assert is_valid_sid(VALID_MESSAGE_SID) is True

    def test_valid_call_sid(self):
        assert is_valid_sid(VALID_CALL_SID) is True

    def test_with_correct_prefix(self):
        assert is_valid_sid(VALID_ACCOUNT_SID, prefix="AC") is True

    def test_with_wrong_prefix(self):
        assert is_valid_sid(VALID_ACCOUNT_SID, prefix="SM") is False

    def test_empty_string(self):
        assert is_valid_sid("") is False

    def test_none_value(self):
        assert is_valid_sid(None) is False

    def test_integer_value(self):
        assert is_valid_sid(12345) is False

    def test_too_short(self):
        assert is_valid_sid("AC" + "a1b2c3") is False

    def test_too_long(self):
        assert is_valid_sid("AC" + "a" * 33) is False

    def test_uppercase_hex_rejected(self):
        """Twilio SIDs use lowercase hex after the prefix."""
        assert is_valid_sid("AC" + "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4") is False

    def test_non_hex_chars_rejected(self):
        assert is_valid_sid("AC" + "g" * 32) is False

    def test_lowercase_prefix_rejected(self):
        assert is_valid_sid("ac" + "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4") is False

    def test_no_prefix(self):
        """32 hex chars without prefix is not a valid SID."""
        assert is_valid_sid(VALID_AUTH_TOKEN) is False

    def test_whitespace_rejected(self):
        assert is_valid_sid(" " + VALID_ACCOUNT_SID) is False
        assert is_valid_sid(VALID_ACCOUNT_SID + " ") is False

    def test_all_zeros(self):
        assert is_valid_sid("AC" + "0" * 32) is True

    def test_all_fs(self):
        assert is_valid_sid("AC" + "f" * 32) is True


# ── Account SID ──────────────────────────────────────────────────────────────


class TestIsValidAccountSid:
    """is_valid_account_sid() — AC-prefixed SIDs."""

    def test_valid(self):
        assert is_valid_account_sid(VALID_ACCOUNT_SID) is True

    def test_rejects_message_sid(self):
        assert is_valid_account_sid(VALID_MESSAGE_SID) is False

    def test_rejects_call_sid(self):
        assert is_valid_account_sid(VALID_CALL_SID) is False

    def test_empty(self):
        assert is_valid_account_sid("") is False

    def test_none(self):
        assert is_valid_account_sid(None) is False

    def test_just_prefix(self):
        assert is_valid_account_sid("AC") is False

    def test_realistic_sid(self):
        """Format mirrors what Twilio actually issues."""
        assert is_valid_account_sid("AC" + "5ef8732a1c49e47baf87ab2c1f3e9d04") is True


# ── Message SID ──────────────────────────────────────────────────────────────


class TestIsValidMessageSid:
    """is_valid_message_sid() — SM-prefixed SIDs."""

    def test_valid(self):
        assert is_valid_message_sid(VALID_MESSAGE_SID) is True

    def test_rejects_account_sid(self):
        assert is_valid_message_sid(VALID_ACCOUNT_SID) is False

    def test_empty(self):
        assert is_valid_message_sid("") is False

    def test_realistic_sid(self):
        assert is_valid_message_sid("SM8c3f47e92d1a5b6c0e4f8a7d3b2c1e09") is True


# ── Call SID ─────────────────────────────────────────────────────────────────


class TestIsValidCallSid:
    """is_valid_call_sid() — CA-prefixed SIDs."""

    def test_valid(self):
        assert is_valid_call_sid(VALID_CALL_SID) is True

    def test_rejects_account_sid(self):
        assert is_valid_call_sid(VALID_ACCOUNT_SID) is False

    def test_empty(self):
        assert is_valid_call_sid("") is False

    def test_realistic_sid(self):
        assert is_valid_call_sid("CA9e7d3f1a2b5c8064e1d9a7f3c2b4e608") is True


# ── Auth Token ───────────────────────────────────────────────────────────────


class TestIsValidAuthToken:
    """is_valid_auth_token() — 32 hex chars, no prefix."""

    def test_valid(self):
        assert is_valid_auth_token(VALID_AUTH_TOKEN) is True

    def test_empty(self):
        assert is_valid_auth_token("") is False

    def test_none(self):
        assert is_valid_auth_token(None) is False

    def test_too_short(self):
        assert is_valid_auth_token("a1b2c3") is False

    def test_too_long(self):
        assert is_valid_auth_token("a" * 33) is False

    def test_rejects_sid_format(self):
        """An Account SID is not a valid auth token."""
        assert is_valid_auth_token(VALID_ACCOUNT_SID) is False

    def test_uppercase_hex_rejected(self):
        assert is_valid_auth_token("A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4") is False

    def test_non_hex_rejected(self):
        assert is_valid_auth_token("z" * 32) is False

    def test_all_zeros(self):
        assert is_valid_auth_token("0" * 32) is True

    def test_whitespace_rejected(self):
        assert is_valid_auth_token(" " + VALID_AUTH_TOKEN) is False


# ── Full config validation ───────────────────────────────────────────────────


class TestValidateTwilioConfig:
    """validate_twilio_config() — end-to-end credential check."""

    def test_all_valid(self):
        errors = validate_twilio_config(
            VALID_ACCOUNT_SID, VALID_AUTH_TOKEN, "+61400000000",
        )
        assert errors == []

    def test_empty_account_sid(self):
        errors = validate_twilio_config("", VALID_AUTH_TOKEN, "+61400000000")
        assert any("ACCOUNT_SID is empty" in e for e in errors)

    def test_malformed_account_sid(self):
        errors = validate_twilio_config("not-a-sid", VALID_AUTH_TOKEN, "+61400000000")
        assert any("invalid format" in e for e in errors)

    def test_message_sid_rejected_as_account_sid(self):
        errors = validate_twilio_config(
            VALID_MESSAGE_SID, VALID_AUTH_TOKEN, "+61400000000",
        )
        assert any("invalid format" in e for e in errors)

    def test_empty_auth_token(self):
        errors = validate_twilio_config(VALID_ACCOUNT_SID, "", "+61400000000")
        assert any("AUTH_TOKEN is empty" in e for e in errors)

    def test_malformed_auth_token(self):
        errors = validate_twilio_config(
            VALID_ACCOUNT_SID, "short", "+61400000000",
        )
        assert any("AUTH_TOKEN has invalid format" in e for e in errors)

    def test_empty_from_number(self):
        errors = validate_twilio_config(VALID_ACCOUNT_SID, VALID_AUTH_TOKEN, "")
        assert any("FROM_NUMBER is empty" in e for e in errors)

    def test_from_number_missing_plus(self):
        errors = validate_twilio_config(
            VALID_ACCOUNT_SID, VALID_AUTH_TOKEN, "61400000000",
        )
        assert any("E.164" in e for e in errors)

    def test_all_empty_returns_three_errors(self):
        errors = validate_twilio_config("", "", "")
        assert len(errors) == 3

    def test_all_malformed_returns_three_errors(self):
        errors = validate_twilio_config("bad-sid", "bad-token", "no-plus")
        assert len(errors) == 3
