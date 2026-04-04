"""Centralized HTTP request helpers with retry logic.

Provides request_with_retry() — a drop-in replacement for requests.get/post
with exponential backoff, jitter, and configurable retry behavior.

All external API calls in SolarAdmin should route through this module
to ensure consistent retry handling, timeout defaults, and logging.

Usage:
    from api_helpers import request_with_retry

    resp = request_with_retry("GET", "https://api.example.com/data", timeout=10)
    resp = request_with_retry("POST", url, json=payload, headers=headers)
"""

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Retry-eligible HTTP status codes (server errors + rate limiting)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0   # seconds
DEFAULT_MAX_DELAY = 30.0   # seconds cap
DEFAULT_TIMEOUT = 15       # seconds


def request_with_retry(
    method: str,
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retry_on: set[int] | None = None,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with exponential backoff retry.

    Retries on connection errors, timeouts, and server-side HTTP errors
    (429, 500, 502, 503, 504 by default). Client errors (4xx except 429)
    are NOT retried.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        url: Request URL
        max_retries: Maximum number of retry attempts (0 = no retries)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap in seconds
        retry_on: Set of HTTP status codes to retry on (overrides default)
        **kwargs: Passed directly to requests.request() (json, headers, auth,
                  timeout, data, params, etc.)

    Returns:
        requests.Response object

    Raises:
        requests.exceptions.RequestException: After all retries exhausted
    """
    if "timeout" not in kwargs:
        kwargs["timeout"] = DEFAULT_TIMEOUT

    retryable = retry_on or RETRYABLE_STATUS_CODES
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, **kwargs)

            # Success or non-retryable error — return immediately
            if resp.status_code not in retryable:
                return resp

            # Retryable status but last attempt — return what we got
            if attempt == max_retries:
                logger.warning(
                    "[API_RETRY] %s %s returned %d after %d retries",
                    method, _truncate_url(url), resp.status_code, max_retries,
                )
                return resp

            # Check for Retry-After header (common with 429)
            delay = _calculate_delay(attempt, base_delay, max_delay, resp)
            logger.info(
                "[API_RETRY] %s %s → %d, retrying in %.1fs (attempt %d/%d)",
                method, _truncate_url(url), resp.status_code, delay,
                attempt + 1, max_retries,
            )
            time.sleep(delay)

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt == max_retries:
                logger.error(
                    "[API_RETRY] %s %s failed after %d retries: %s",
                    method, _truncate_url(url), max_retries, str(e)[:100],
                )
                raise

            delay = _calculate_delay(attempt, base_delay, max_delay)
            logger.info(
                "[API_RETRY] %s %s → %s, retrying in %.1fs (attempt %d/%d)",
                method, _truncate_url(url), type(e).__name__, delay,
                attempt + 1, max_retries,
            )
            time.sleep(delay)

    # Should never reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    raise requests.exceptions.RequestException(f"Retry logic error for {method} {url}")


def _calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    response: requests.Response | None = None,
) -> float:
    """Calculate retry delay with exponential backoff + jitter.

    Respects Retry-After header if present (common for 429 responses).

    Args:
        attempt: Zero-based attempt number
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap
        response: Optional response to check for Retry-After header

    Returns:
        Delay in seconds
    """
    # Honour Retry-After header if present
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), max_delay)
            except ValueError:
                pass

    # Exponential backoff: base * 2^attempt + jitter
    exp_delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, base_delay)
    return min(exp_delay + jitter, max_delay)


def _truncate_url(url: str, max_len: int = 60) -> str:
    """Truncate URL for log readability."""
    return url[:max_len] + "..." if len(url) > max_len else url


# ── Convenience wrappers ──────────────────────────────────────────────────────

def get(url: str, **kwargs) -> requests.Response:
    """GET with retry. Same signature as requests.get() + retry params."""
    return request_with_retry("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """POST with retry. Same signature as requests.post() + retry params."""
    return request_with_retry("POST", url, **kwargs)


def put(url: str, **kwargs) -> requests.Response:
    """PUT with retry. Same signature as requests.put() + retry params."""
    return request_with_retry("PUT", url, **kwargs)


def patch(url: str, **kwargs) -> requests.Response:
    """PATCH with retry. Same signature as requests.patch() + retry params."""
    return request_with_retry("PATCH", url, **kwargs)


def delete(url: str, **kwargs) -> requests.Response:
    """DELETE with retry. Same signature as requests.delete() + retry params."""
    return request_with_retry("DELETE", url, **kwargs)
