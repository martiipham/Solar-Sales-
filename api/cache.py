"""Redis-backed API response cache with in-memory fallback.

Provides:
  - get / set / delete / invalidate_pattern — low-level KV operations
  - cached(ttl, key, vary_on_args)         — Flask route decorator
  - cache_revocation / get_revocation      — JWT revocation fast-path

Redis is used when REDIS_URL is configured; falls back to a process-local
dict so the app works on any deployment without Redis installed.
"""

import functools
import hashlib
import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazily initialised Redis client (None = not yet attempted)
_redis_client: Any = None
_redis_checked: bool = False

# In-memory fallback: key → (value, expires_at_unix)
_mem: dict[str, tuple[Any, float]] = {}


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _client():
    """Return the Redis client, or None if Redis is unavailable."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis as _redis
        import config
        url = config.REDIS_URL
        if not url:
            return None
        c = _redis.from_url(url, decode_responses=True, socket_timeout=1,
                            socket_connect_timeout=1)
        c.ping()
        _redis_client = c
        logger.info("[CACHE] Redis connected at %s", url)
    except Exception as exc:
        logger.warning("[CACHE] Redis unavailable (%s) — using in-memory fallback", exc)
        _redis_client = None
    return _redis_client


def get(key: str) -> Optional[Any]:
    """Return cached value or None on miss / error."""
    r = _client()
    if r:
        try:
            raw = r.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.debug("[CACHE] get error: %s", exc)
    entry = _mem.get(key)
    if entry:
        val, exp = entry
        if time.time() < exp:
            return val
        del _mem[key]
    return None


def set(key: str, value: Any, ttl: int = 60) -> None:
    """Store value with TTL (seconds)."""
    r = _client()
    if r:
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
            return
        except Exception as exc:
            logger.debug("[CACHE] set error: %s", exc)
    _mem[key] = (value, time.time() + ttl)


def delete(key: str) -> None:
    """Remove a single cached key."""
    r = _client()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _mem.pop(key, None)


def invalidate_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count removed."""
    r = _client()
    if r:
        try:
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.debug("[CACHE] invalidate_pattern error: %s", exc)
    prefix = pattern.rstrip("*")
    victims = [k for k in list(_mem) if k.startswith(prefix)]
    for k in victims:
        del _mem[k]
    return len(victims)


# ── JWT revocation fast-path ──────────────────────────────────────────────────

_REV_PREFIX = "solar:jwt:rev:"


def cache_revocation(token_hash: str, revoked: bool, ttl: int) -> None:
    """Persist revocation status so subsequent requests skip the DB."""
    set(f"{_REV_PREFIX}{token_hash}", int(revoked), ttl)


def get_revocation(token_hash: str) -> Optional[bool]:
    """Return cached revocation status, or None if not yet cached."""
    val = get(f"{_REV_PREFIX}{token_hash}")
    return bool(val) if val is not None else None


def evict_token(token_hash: str) -> None:
    """Mark a token as revoked in the cache (called on logout / refresh)."""
    # Use a 25-hour TTL — slightly longer than max token lifetime
    set(f"{_REV_PREFIX}{token_hash}", 1, ttl=90_000)


# ── Route decorator ───────────────────────────────────────────────────────────

def _build_key(fn_name: str, static_key: Optional[str],
               vary: bool, kwargs: dict) -> str:
    """Build a deterministic cache key for a route call."""
    from flask import request as req
    base = static_key or f"solar:route:{fn_name}"
    parts = [base]
    if vary and req.query_string:
        parts.append(hashlib.md5(req.query_string).hexdigest()[:8])
    if kwargs:
        kw_hash = hashlib.md5(
            json.dumps(sorted(kwargs.items()), default=str).encode()
        ).hexdigest()[:8]
        parts.append(kw_hash)
    return ":".join(parts)


def cached(ttl: int = 60, key: Optional[str] = None, vary_on_args: bool = False):
    """Decorator: cache a Flask JSON route response.

    Args:
        ttl:          Cache lifetime in seconds.
        key:          Static cache key prefix. Derived from function name if None.
        vary_on_args: Include query string in cache key when True.

    Only caches HTTP 200 responses. Adds X-Cache: HIT/MISS header.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from flask import jsonify as _j
            ck = _build_key(f.__name__, key, vary_on_args, kwargs)

            hit = get(ck)
            if hit is not None:
                resp = _j(hit)
                resp.headers["X-Cache"] = "HIT"
                return resp, 200

            result = f(*args, **kwargs)

            # Unpack tuple (Response, status)
            if isinstance(result, tuple):
                resp_obj, status = result[0], result[1]
            else:
                resp_obj, status = result, 200

            if status == 200:
                try:
                    data = resp_obj.get_json()
                    if data is not None:
                        set(ck, data, ttl)
                        resp_obj.headers["X-Cache"] = "MISS"
                except Exception:
                    pass

            return result
        return wrapper
    return decorator
