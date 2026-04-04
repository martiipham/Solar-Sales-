/**
 * SolarAdmin API Client
 *
 * Foundation module for all frontend → backend communication.
 * - Auth header management (JWT from localStorage)
 * - Exponential backoff retry on transient errors (429, 502, 503, 504)
 * - Automatic token refresh on 401, with one-shot retry
 * - VITE_API_BASE_URL env prefix support
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RetryOptions {
  /** Maximum number of retry attempts (default: 3) */
  maxRetries?: number;
  /** Initial delay in ms before first retry (default: 500) */
  initialDelayMs?: number;
  /** Maximum delay in ms between retries (default: 10000) */
  maxDelayMs?: number;
  /** Multiplier for exponential growth (default: 2) */
  backoffMultiplier?: number;
  /** HTTP status codes that trigger a retry (default: [429, 502, 503, 504]) */
  retryableStatuses?: number[];
  /** Called before each retry with attempt number and delay */
  onRetry?: (attempt: number, delayMs: number, error: unknown) => void;
}

const DEFAULT_OPTIONS: Required<Omit<RetryOptions, 'onRetry'>> = {
  maxRetries: 3,
  initialDelayMs: 500,
  maxDelayMs: 10_000,
  backoffMultiplier: 2,
  retryableStatuses: [429, 502, 503, 504],
};

// ---------------------------------------------------------------------------
// Auth — extracted from src/utils/crm.ts
// ---------------------------------------------------------------------------

/**
 * Build the Authorization + Content-Type headers from the stored JWT.
 * Throws if the user is not logged in.
 */
export function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('Not authenticated — please log in');
  }
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

// ---------------------------------------------------------------------------
// Retry helpers — ported from apps/selledger/src/lib/retry.ts
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Full jitter: random value between 0 and the exponential cap.
 * Avoids thundering-herd re-collision after burst failures.
 */
function getJitteredDelay(
  attempt: number,
  initialDelayMs: number,
  maxDelayMs: number,
  multiplier: number,
): number {
  const exponential = initialDelayMs * Math.pow(multiplier, attempt);
  const capped = Math.min(exponential, maxDelayMs);
  return Math.floor(Math.random() * capped);
}

/**
 * Parse Retry-After header (seconds or HTTP-date) into milliseconds.
 * Returns null if the header is absent or unparseable.
 */
function parseRetryAfter(response: Response): number | null {
  const header = response.headers.get('Retry-After');
  if (!header) return null;

  const seconds = Number(header);
  if (!isNaN(seconds) && seconds > 0) return seconds * 1000;

  const date = Date.parse(header);
  if (!isNaN(date)) {
    const delta = date - Date.now();
    return delta > 0 ? delta : null;
  }

  return null;
}

function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError) {
    return /fetch|network|failed to fetch/i.test(error.message);
  }
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  return false;
}

/**
 * Thrown when fetch() receives a retryable HTTP status.
 * Carries the Response so callers can read headers before retrying.
 */
export class FetchRetryError extends Error {
  constructor(
    public readonly status: number,
    public readonly response: Response,
    public readonly body?: string,
  ) {
    super(`HTTP ${status}`);
    this.name = 'FetchRetryError';
  }
}

function isRetryable(error: unknown, options: RetryOptions): boolean {
  if (isNetworkError(error)) return true;
  if (error instanceof FetchRetryError) {
    const statuses = options.retryableStatuses ?? DEFAULT_OPTIONS.retryableStatuses;
    return statuses.includes(error.status);
  }
  return false;
}

async function withRetry<T>(
  fn: (attempt: number) => Promise<T>,
  options: RetryOptions = {},
): Promise<T> {
  const maxRetries = options.maxRetries ?? DEFAULT_OPTIONS.maxRetries;
  const initialDelayMs = options.initialDelayMs ?? DEFAULT_OPTIONS.initialDelayMs;
  const maxDelayMs = options.maxDelayMs ?? DEFAULT_OPTIONS.maxDelayMs;
  const multiplier = options.backoffMultiplier ?? DEFAULT_OPTIONS.backoffMultiplier;

  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn(attempt);
    } catch (error) {
      lastError = error;
      if (attempt >= maxRetries) break;
      if (!isRetryable(error, options)) break;

      const delay = getJitteredDelay(attempt, initialDelayMs, maxDelayMs, multiplier);
      options.onRetry?.(attempt + 1, delay, error);
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * fetch() with exponential backoff retry on transient errors.
 * Ported from apps/selledger/src/lib/retry.ts.
 *
 * Does NOT retry 401 — token refresh is handled at the apiFetch layer.
 */
export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  retryOptions: RetryOptions = {},
): Promise<Response> {
  const statuses = retryOptions.retryableStatuses ?? DEFAULT_OPTIONS.retryableStatuses;

  return withRetry(async () => {
    const response = await fetch(input, init);

    if (statuses.includes(response.status)) {
      const body = await response.text().catch(() => '');
      const retryAfterMs = parseRetryAfter(response);
      if (retryAfterMs !== null && retryAfterMs > 0) {
        await sleep(Math.min(retryAfterMs, retryOptions.maxDelayMs ?? DEFAULT_OPTIONS.maxDelayMs));
      }
      throw new FetchRetryError(response.status, response, body);
    }

    return response;
  }, retryOptions);
}

// ---------------------------------------------------------------------------
// Token refresh & proactive renewal
// ---------------------------------------------------------------------------

/** Singleton in-flight refresh promise to prevent parallel refresh races. */
let refreshPromise: Promise<string> | null = null;

/** Handle for the proactive refresh timer so it can be cleared. */
let refreshTimerId: ReturnType<typeof setTimeout> | null = null;

/** Minimum ms before expiry to trigger proactive refresh (5 minutes). */
const REFRESH_MARGIN_MS = 5 * 60 * 1000;

/**
 * Decode the payload of a JWT without verification (browser-side).
 * Returns null if the token is malformed.
 */
function parseTokenPayload(token: string): { exp?: number; sub?: number } | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    return payload;
  } catch {
    return null;
  }
}

/**
 * Returns the ms until the stored JWT expires, or -1 if no valid token.
 */
function msUntilExpiry(): number {
  const token = localStorage.getItem('token');
  if (!token) return -1;
  const payload = parseTokenPayload(token);
  if (!payload?.exp) return -1;
  return payload.exp * 1000 - Date.now();
}

/**
 * Callback invoked when authentication is irrecoverably lost.
 * Set via `setAuthFailureHandler()` so the app can redirect to login.
 */
let authFailureHandler: (() => void) | null = null;

/**
 * Register a callback that fires when the session cannot be recovered
 * (token expired and refresh failed). Typically used to redirect to /login.
 */
export function setAuthFailureHandler(handler: () => void): void {
  authFailureHandler = handler;
}

function handleAuthFailure(): void {
  localStorage.removeItem('token');
  clearProactiveRefresh();
  authFailureHandler?.();
}

/**
 * Call POST /api/auth/refresh to obtain a new access token.
 * Sends the current (still-valid) JWT so the backend can authenticate,
 * issue a fresh token, and revoke the old one.
 * Multiple simultaneous callers share a single in-flight request.
 */
async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const currentToken = localStorage.getItem('token');
      if (!currentToken) throw new Error('No token to refresh');

      const response = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${currentToken}`,
        },
      });

      if (!response.ok) {
        handleAuthFailure();
        throw new Error(`Token refresh failed — HTTP ${response.status}`);
      }

      const data: { token: string } = await response.json();
      localStorage.setItem('token', data.token);
      scheduleProactiveRefresh();
      return data.token;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Schedule a proactive token refresh before the JWT expires.
 * Fires REFRESH_MARGIN_MS (5 min) before expiry so the user never
 * encounters a 401 mid-session.
 */
function scheduleProactiveRefresh(): void {
  clearProactiveRefresh();
  const remaining = msUntilExpiry();
  if (remaining <= 0) return; // already expired — nothing to schedule

  // Refresh 5 min before expiry, but at least 10s from now
  const delay = Math.max(remaining - REFRESH_MARGIN_MS, 10_000);
  refreshTimerId = setTimeout(() => {
    refreshAccessToken().catch(() => {
      // Proactive refresh failed — user will get 401 on next request
      // which triggers the reactive path in apiFetch
    });
  }, delay);
}

function clearProactiveRefresh(): void {
  if (refreshTimerId !== null) {
    clearTimeout(refreshTimerId);
    refreshTimerId = null;
  }
}

/**
 * Initialize the proactive refresh timer. Call once on app startup
 * (e.g., in the root component mount) and after every login.
 */
export function initTokenLifecycle(): void {
  const token = localStorage.getItem('token');
  if (!token) return;

  const remaining = msUntilExpiry();
  if (remaining <= 0) {
    // Token already expired — clear it
    handleAuthFailure();
    return;
  }

  scheduleProactiveRefresh();
}

// ---------------------------------------------------------------------------
// Main API client
// ---------------------------------------------------------------------------

export class AuthError extends Error {
  constructor(message = 'Session expired — please log in again') {
    super(message);
    this.name = 'AuthError';
  }
}

/**
 * Primary fetch wrapper for the SolarAdmin frontend.
 *
 * - Prepends VITE_API_BASE_URL to every path
 * - Attaches JWT Authorization header
 * - Retries transient errors with exponential backoff
 * - On 401: refreshes the token and retries the original request once
 * - Throws AuthError if the refresh also fails
 *
 * @example
 * const res = await apiFetch('/api/leads');
 * const leads = await res.json();
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
  retryOptions: RetryOptions = {},
): Promise<Response> {
  const url = `${API_BASE}${path}`;

  const makeRequest = async (): Promise<Response> => {
    const headers = { ...getAuthHeader(), ...(init.headers as Record<string, string> | undefined) };
    return fetchWithRetry(url, { ...init, headers }, retryOptions);
  };

  let response: Response;

  try {
    response = await makeRequest();
  } catch (error) {
    // Only intercept 401 — everything else propagates as-is
    if (!(error instanceof FetchRetryError) || error.status !== 401) throw error;

    // Attempt token refresh then retry once
    try {
      await refreshAccessToken();
    } catch {
      handleAuthFailure();
      throw new AuthError();
    }

    try {
      response = await makeRequest();
    } catch (retryError) {
      if (retryError instanceof FetchRetryError && retryError.status === 401) {
        handleAuthFailure();
        throw new AuthError();
      }
      throw retryError;
    }
  }

  return response;
}

/**
 * Convenience wrapper: apiFetch() + JSON parse.
 * Throws on non-2xx responses after retries.
 */
export async function apiJSON<T = unknown>(
  path: string,
  init: RequestInit = {},
  retryOptions: RetryOptions = {},
): Promise<T> {
  const response = await apiFetch(path, init, retryOptions);

  if (!response.ok) {
    const err = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(err.error ?? `API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}
