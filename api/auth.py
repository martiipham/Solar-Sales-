"""Authentication — JWT login/logout, auth middleware, and default owner seeding.

Blueprint: auth_bp
  POST /api/auth/login           — email + password → JWT token + user info
  POST /api/auth/logout          — revoke current token
  GET  /api/auth/me              — return current user info
  POST /api/auth/refresh         — issue new token, revoke old one (proactive renewal)
  POST /api/auth/change-password — update own password (requires current password)
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import bcrypt
import jwt
from flask import Blueprint, g, jsonify, request

from memory.database import fetch_one, get_conn, insert, update

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

# JWT secret — read from env or generate a transient one (sessions lost on restart)
_JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
if not os.environ.get("JWT_SECRET"):
    logger.critical(
        "[AUTH] JWT_SECRET is not set in the environment. A random secret has been "
        "generated for this process. All sessions will be invalidated on every restart. "
        "Set JWT_SECRET to a stable value in your .env file before deploying to production."
    )
JWT_EXPIRY_HOURS = 24


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 hash of a JWT string for DB revocation storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _make_token(user_id: int, role: str) -> str:
    """Create a signed JWT and persist its hash for revocation support."""
    exp = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {"sub": user_id, "role": role,
               "exp": exp, "iat": datetime.utcnow()}
    token = jwt.encode(payload, _JWT_SECRET, algorithm="HS256")
    insert("auth_tokens", {
        "token_hash": _hash_token(token),
        "user_id": user_id,
        "expires_at": exp.isoformat(),
        "revoked": 0,
    })
    return token


def _check_revocation(token: str, token_hash: str, payload: dict) -> bool:
    """Return True if token is revoked. Uses Redis fast-path, falls back to DB.

    Caches the result in Redis with the token's remaining lifetime so
    subsequent requests skip the SQLite query entirely.
    """
    from api.cache import cache_revocation, get_revocation
    cached = get_revocation(token_hash)
    if cached is not None:
        return cached  # True = revoked, False = valid

    row = fetch_one(
        "SELECT revoked FROM auth_tokens WHERE token_hash = ?", (token_hash,)
    )
    revoked = not row or bool(row.get("revoked"))

    # Cache result — TTL = remaining token lifetime (min 1s, max 90000s)
    exp = payload.get("exp", 0)
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = max(1, min(exp - now, 90_000))
    cache_revocation(token_hash, revoked, remaining)
    return revoked


def _fetch_user_cached(user_id: int) -> Optional[dict]:
    """Fetch user from Redis cache, or DB on miss. Returns None if not found."""
    from api.cache import get as cache_get, set as cache_set
    cache_key = f"solar:user:{user_id}"
    hit = cache_get(cache_key)
    if hit is not None:
        return hit
    user = fetch_one(
        "SELECT id, email, name, role, client_id, active FROM users WHERE id = ?",
        (user_id,),
    )
    if user:
        cache_set(cache_key, dict(user), ttl=300)
    return dict(user) if user else None


def require_auth(roles=None):
    """Decorator factory: validates JWT and injects g.user.

    Args:
        roles: Optional list of allowed roles, e.g. ['owner', 'admin'].
               If None, any authenticated user is accepted.

    Uses Redis for revocation check and user lookup to avoid SQLite on
    every authenticated request.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify({"error": "Authentication required"}), 401
            token = header[7:]
            try:
                payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Session expired — please log in again"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            token_hash = _hash_token(token)
            if _check_revocation(token, token_hash, payload):
                return jsonify({"error": "Session revoked"}), 401

            user = _fetch_user_cached(payload["sub"])
            if not user or not user.get("active"):
                return jsonify({"error": "Account not found or disabled"}), 401

            if roles and user["role"] not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403

            g.user = user
            g.token = token
            return f(*args, **kwargs)
        return wrapper
    return decorator


def seed_owner():
    """Create the default owner account if the users table is empty.

    Generates a random password and prints it once. The admin MUST note
    it down immediately and change it after first login.
    """
    existing = fetch_one("SELECT id FROM users LIMIT 1")
    if existing:
        return
    temp_password = secrets.token_urlsafe(16)
    pw_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()
    insert("users", {
        "email": "admin@solarswarm.io",
        "password_hash": pw_hash,
        "name": "Owner",
        "role": "owner",
        "active": 1,
    })
    print("[AUTH] Default owner seeded  →  admin@solarswarm.io")
    print(f"[AUTH] Temporary password   →  {temp_password}")
    print("[AUTH] ⚠  Save this password now — it will NOT be shown again.")
    print("[AUTH] ⚠  Change it immediately after first login.")


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """POST /api/auth/login — returns JWT token on valid credentials."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = fetch_one(
        "SELECT id, email, name, role, client_id, active, password_hash "
        "FROM users WHERE email = ?",
        (email,)
    )
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user["active"]:
        return jsonify({"error": "Account is disabled"}), 403

    token = _make_token(user["id"], user["role"])
    update("users", user["id"], {"last_login": datetime.utcnow().isoformat()})

    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "client_id": user["client_id"],
        },
    }), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """POST /api/auth/logout — revoke the current session token."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:]
        token_hash = _hash_token(token)
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE auth_tokens SET revoked = 1 WHERE token_hash = ?",
                    (token_hash,)
                )
        except Exception as e:
            logger.warning(f"[AUTH] logout revocation error: {e}")
        # Evict Redis cache so the revocation is immediately visible
        try:
            from api.cache import evict_token
            evict_token(token_hash)
        except Exception:
            pass
    return jsonify({"ok": True}), 200


@auth_bp.route("/api/auth/refresh", methods=["POST"])
@require_auth()
def refresh_token():
    """POST /api/auth/refresh — issue a new JWT, revoke the current one.

    Called proactively by the frontend 30 minutes before the current token
    expires so the user is never hard-logged-out mid-session.
    """
    old_hash = _hash_token(g.token)
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE auth_tokens SET revoked = 1 WHERE token_hash = ?",
                (old_hash,)
            )
    except Exception as e:
        logger.warning(f"[AUTH] refresh revocation error: {e}")
    # Evict old token from Redis cache immediately
    try:
        from api.cache import evict_token
        evict_token(old_hash)
    except Exception:
        pass

    new_token = _make_token(g.user["id"], g.user["role"])
    return jsonify({
        "token": new_token,
        "user": {
            "id":        g.user["id"],
            "email":     g.user["email"],
            "name":      g.user["name"],
            "role":      g.user["role"],
            "client_id": g.user["client_id"],
        },
    }), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@require_auth()
def me():
    """GET /api/auth/me — return the current authenticated user."""
    return jsonify({"user": dict(g.user)}), 200


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@require_auth()
def change_password():
    """POST /api/auth/change-password — update own password."""
    data = request.get_json() or {}
    current_pw = (data.get("current") or "")
    new_pw = (data.get("new") or "")
    if not current_pw or not new_pw:
        return jsonify({"error": "current and new password required"}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    row = fetch_one(
        "SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)
    )
    if not bcrypt.checkpw(current_pw.encode(), row["password_hash"].encode()):
        return jsonify({"error": "Current password is incorrect"}), 400

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    update("users", g.user["id"], {"password_hash": new_hash})
    # Evict user from Redis cache so next request reloads updated record
    try:
        from api.cache import delete as cache_delete
        cache_delete(f"solar:user:{g.user['id']}")
    except Exception:
        pass
    return jsonify({"ok": True}), 200
