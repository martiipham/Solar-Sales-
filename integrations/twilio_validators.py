"""Twilio SID and credential validation helpers.

Validates Twilio resource identifiers (SIDs) against their documented
format before they're used in API calls, preventing malformed requests
and improving error diagnostics.

Twilio SID format: 2-char prefix + 32 lowercase hex characters = 34 chars.
Auth tokens: 32 lowercase hex characters (no prefix).
"""

import re

# ── SID format: 2-char prefix + 32 hex chars ─────────────────────────────────
_SID_RE = re.compile(r"^[A-Z]{2}[0-9a-f]{32}$")
_AUTH_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

# ── Known prefixes (subset relevant to SolarAdmin) ───────────────────────────
VALID_PREFIXES = {
    "AC": "Account SID",
    "SM": "Message SID",
    "CA": "Call SID",
    "PN": "Phone Number SID",
    "MM": "MMS Message SID",
}


def is_valid_sid(sid: str, *, prefix: str | None = None) -> bool:
    """Check whether *sid* matches Twilio SID format.

    Args:
        sid: The string to validate.
        prefix: If given, require the SID to start with this 2-char prefix
                (e.g. ``"AC"`` for Account SIDs).

    Returns:
        ``True`` when the SID is well-formed (and optionally matches *prefix*).
    """
    if not isinstance(sid, str):
        return False
    if not _SID_RE.match(sid):
        return False
    if prefix is not None and not sid.startswith(prefix):
        return False
    return True


def is_valid_account_sid(sid: str) -> bool:
    """Validate an Account SID (must start with ``AC``)."""
    return is_valid_sid(sid, prefix="AC")


def is_valid_message_sid(sid: str) -> bool:
    """Validate a Message SID (must start with ``SM``)."""
    return is_valid_sid(sid, prefix="SM")


def is_valid_call_sid(sid: str) -> bool:
    """Validate a Call SID (must start with ``CA``)."""
    return is_valid_sid(sid, prefix="CA")


def is_valid_auth_token(token: str) -> bool:
    """Validate a Twilio auth token (32 hex chars, no prefix).

    Args:
        token: The string to validate.

    Returns:
        ``True`` when the token is well-formed.
    """
    if not isinstance(token, str):
        return False
    return bool(_AUTH_TOKEN_RE.match(token))


def validate_twilio_config(
    account_sid: str, auth_token: str, from_number: str,
) -> list[str]:
    """Validate a complete set of Twilio credentials.

    Returns a list of human-readable error strings (empty = valid).
    """
    errors: list[str] = []
    if not account_sid:
        errors.append("TWILIO_ACCOUNT_SID is empty")
    elif not is_valid_account_sid(account_sid):
        errors.append(
            f"TWILIO_ACCOUNT_SID has invalid format (expected AC + 32 hex chars, got {account_sid!r})"
        )
    if not auth_token:
        errors.append("TWILIO_AUTH_TOKEN is empty")
    elif not is_valid_auth_token(auth_token):
        errors.append("TWILIO_AUTH_TOKEN has invalid format (expected 32 hex chars)")
    if not from_number:
        errors.append("TWILIO_FROM_NUMBER is empty")
    elif not from_number.startswith("+"):
        errors.append(
            f"TWILIO_FROM_NUMBER should be E.164 format (start with +), got {from_number!r}"
        )
    return errors
