"""Users API — manage platform users (owner-only for create/delete/role changes).

Blueprint: users_bp
  GET    /api/users          — list all users
  POST   /api/users          — create new user  (owner only)
  PATCH  /api/users/<id>     — update name, role, active, client_id
  DELETE /api/users/<id>     — soft-delete (sets active=0)  (owner only)
"""

import logging
from datetime import datetime

import bcrypt
from flask import Blueprint, g, jsonify, request

from api.auth import require_auth
from memory.database import fetch_all, fetch_one, insert, update, get_conn

logger = logging.getLogger(__name__)
users_bp = Blueprint("users", __name__)

SAFE_FIELDS = {"id", "email", "name", "role", "client_id", "active",
               "created_at", "last_login"}


def _safe(user: dict) -> dict:
    """Strip password_hash before returning user data to the frontend."""
    return {k: v for k, v in user.items() if k in SAFE_FIELDS}


@users_bp.route("/api/users", methods=["GET"])
@require_auth(roles=["owner", "admin"])
def list_users():
    """Return all users (password_hash excluded)."""
    rows = fetch_all(
        "SELECT id, email, name, role, client_id, active, created_at, last_login "
        "FROM users ORDER BY created_at DESC"
    )
    return jsonify({"users": [_safe(r) for r in rows]}), 200


@users_bp.route("/api/users", methods=["POST"])
@require_auth(roles=["owner"])
def create_user():
    """Create a new user. Owner-only."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    role = data.get("role", "admin")
    password = (data.get("password") or "")
    client_id = data.get("client_id")

    if not email or not name or not password:
        return jsonify({"error": "email, name, and password are required"}), 400
    if role not in ("owner", "admin", "client"):
        return jsonify({"error": "role must be owner, admin, or client"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing = fetch_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        return jsonify({"error": "A user with that email already exists"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    new_id = insert("users", {
        "email": email,
        "name": name,
        "role": role,
        "client_id": client_id,
        "password_hash": pw_hash,
        "active": 1,
    })
    user = fetch_one("SELECT id, email, name, role, client_id, active, created_at "
                     "FROM users WHERE id = ?", (new_id,))
    return jsonify({"user": _safe(user)}), 201


@users_bp.route("/api/users/<int:user_id>", methods=["PATCH"])
@require_auth(roles=["owner", "admin"])
def update_user(user_id: int):
    """Update name, role, active status, or client_id. Role changes are owner-only."""
    data = request.get_json() or {}
    target = fetch_one("SELECT id, role FROM users WHERE id = ?", (user_id,))
    if not target:
        return jsonify({"error": "User not found"}), 404

    # Protect owner account from being locked out
    if target["role"] == "owner" and g.user["role"] != "owner":
        return jsonify({"error": "Cannot modify the owner account"}), 403

    allowed = {}
    if "name" in data:
        allowed["name"] = data["name"].strip()
    if "active" in data:
        allowed["active"] = 1 if data["active"] else 0
    if "client_id" in data:
        allowed["client_id"] = data["client_id"]
    if "role" in data:
        if g.user["role"] != "owner":
            return jsonify({"error": "Only the owner can change roles"}), 403
        if data["role"] not in ("owner", "admin", "client"):
            return jsonify({"error": "Invalid role"}), 400
        allowed["role"] = data["role"]
    if "password" in data:
        if len(data["password"]) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        if g.user["role"] != "owner" and g.user["id"] != user_id:
            return jsonify({"error": "Cannot reset another user's password"}), 403
        allowed["password_hash"] = bcrypt.hashpw(
            data["password"].encode(), bcrypt.gensalt()
        ).decode()

    if not allowed:
        return jsonify({"error": "No valid fields to update"}), 400

    update("users", user_id, allowed)
    user = fetch_one(
        "SELECT id, email, name, role, client_id, active, created_at, last_login "
        "FROM users WHERE id = ?", (user_id,)
    )
    return jsonify({"user": _safe(user)}), 200


@users_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@require_auth(roles=["owner"])
def delete_user(user_id: int):
    """Soft-delete a user (sets active=0). Owner-only."""
    if user_id == g.user["id"]:
        return jsonify({"error": "Cannot delete your own account"}), 400
    target = fetch_one("SELECT id FROM users WHERE id = ?", (user_id,))
    if not target:
        return jsonify({"error": "User not found"}), 404

    update("users", user_id, {"active": 0})
    # Revoke all their tokens
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE auth_tokens SET revoked = 1 WHERE user_id = ?",
                (user_id,)
            )
    except Exception as e:
        logger.warning(f"[USERS] token revocation error: {e}")

    return jsonify({"ok": True}), 200
