"""API Keys — generate and revoke API keys for client embeds and webhook auth.

Keys are shown in full exactly once (at creation). Only the SHA-256 hash is
stored in the DB. Use X-API-Key header to authenticate machine-to-machine calls.

Blueprint: apikeys_bp
  GET    /api/keys           — list all keys (hash hidden, shows prefix only)
  POST   /api/keys           — generate a new key (returns full key once)
  DELETE /api/keys/<key_id>  — revoke a key
"""

import hashlib
import logging
import secrets
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from api.auth import require_auth
from memory.database import fetch_all, fetch_one, insert, get_conn

logger = logging.getLogger(__name__)
apikeys_bp = Blueprint("apikeys", __name__)

VALID_PERMISSIONS = {"read", "write", "webhook"}


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key for DB storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str) -> dict | None:
    """Return the key record if the raw key is valid and active, else None.

    Used by other API modules to authenticate machine-to-machine requests.
    """
    key_hash = _hash_key(raw_key)
    row = fetch_one(
        "SELECT id, key_id, name, client_id, permissions, active, expires_at "
        "FROM api_keys WHERE key_hash = ? AND active = 1",
        (key_hash,)
    )
    if not row:
        return None
    if row.get("expires_at") and row["expires_at"] < datetime.utcnow().isoformat():
        return None
    # Update last_used timestamp
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE key_hash = ?",
                (datetime.utcnow().isoformat(), key_hash)
            )
    except Exception:
        pass
    return dict(row)


@apikeys_bp.route("/api/keys", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def list_keys():
    """List all API keys — key_hash is never returned, only a short prefix."""
    rows = fetch_all(
        "SELECT id, key_id, name, client_id, permissions, active, "
        "created_at, last_used, expires_at "
        "FROM api_keys ORDER BY created_at DESC"
    )
    return jsonify({"keys": [dict(r) for r in rows]}), 200


@apikeys_bp.route("/api/keys", methods=["POST"])
@require_auth(roles=["owner", "admin"])
def create_key():
    """Generate a new API key. The full key is returned only in this response."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Key name is required"}), 400

    # Validate permissions
    raw_perms = data.get("permissions", ["read"])
    if not isinstance(raw_perms, list):
        raw_perms = [raw_perms]
    perms = [p for p in raw_perms if p in VALID_PERMISSIONS]
    if not perms:
        perms = ["read"]

    # Generate: prefix + 32 random bytes hex
    prefix = "ss_"
    raw_key = prefix + secrets.token_hex(32)
    key_id = secrets.token_hex(8)

    import json
    insert("api_keys", {
        "key_id": key_id,
        "key_hash": _hash_key(raw_key),
        "name": name,
        "created_by": g.user["id"],
        "client_id": data.get("client_id"),
        "permissions": json.dumps(perms),
        "active": 1,
        "expires_at": data.get("expires_at"),
    })

    return jsonify({
        "key": raw_key,          # Full key — shown ONCE only
        "key_id": key_id,
        "name": name,
        "permissions": perms,
        "warning": "Save this key now — it will not be shown again.",
    }), 201


@apikeys_bp.route("/api/keys/<key_id>", methods=["DELETE"])
@require_auth(roles=["owner", "admin"])
def revoke_key(key_id: str):
    """Revoke (deactivate) an API key by key_id."""
    row = fetch_one("SELECT id FROM api_keys WHERE key_id = ?", (key_id,))
    if not row:
        return jsonify({"error": "Key not found"}), 404

    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE api_keys SET active = 0 WHERE key_id = ?", (key_id,)
            )
    except Exception as e:
        logger.error(f"[APIKEYS] revoke error: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True}), 200
