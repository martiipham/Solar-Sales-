/**
 * AuthContext — JWT authentication state + authenticated fetch wrapper.
 *
 * Provides:
 *   useAuth()  → { user, token, login, logout, apiFetch, loading }
 *
 * Token is persisted in localStorage under "swarm-token".
 * apiFetch() automatically adds the Authorization header and handles 401s.
 *
 * Proactive refresh: 30 minutes before the JWT expires, a silent POST to
 * /api/auth/refresh issues a new token so users are never hard-logged-out
 * mid-session.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";

// Empty string = relative URLs — requests go through the Vite proxy to Flask.
// The proxy target (localhost:5003) is set in vite.config.js.
export const API_BASE = "";

const AuthContext = createContext(null);

/** Decode the `exp` claim from a JWT payload (no signature verification). */
function getTokenExp(token) {
  try {
    return JSON.parse(atob(token.split(".")[1])).exp; // seconds since epoch
  } catch { return null; }
}

export function AuthProvider({ children }) {
  const [token, setToken]     = useState(() => localStorage.getItem("swarm-token") || null);
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);  // true while validating stored token
  const refreshTimerRef       = useRef(null);

  /** Schedule a silent token refresh 30 min before expiry. */
  const scheduleRefresh = useCallback((tok) => {
    clearTimeout(refreshTimerRef.current);
    const exp = getTokenExp(tok);
    if (!exp) return;
    const msUntilRefresh = (exp * 1000) - Date.now() - 30 * 60 * 1000;
    if (msUntilRefresh <= 0) return; // already inside or past the refresh window
    refreshTimerRef.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API_BASE}/api/auth/refresh`, {
          method: "POST",
          headers: { Authorization: `Bearer ${tok}` },
        });
        if (r.ok) {
          const data = await r.json();
          localStorage.setItem("swarm-token", data.token);
          setToken(data.token);
          setUser(data.user);
          scheduleRefresh(data.token); // re-arm for the next cycle
        }
      } catch { /* silent — 401 on next apiFetch will log out */ }
    }, msUntilRefresh);
  }, []); // eslint-disable-line

  // Validate stored token on mount
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { setUser(d.user); scheduleRefresh(token); })
      .catch(() => { localStorage.removeItem("swarm-token"); setToken(null); })
      .finally(() => setLoading(false));
  }, []);  // eslint-disable-line

  const login = useCallback(async (email, password) => {
    const r = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Login failed");
    localStorage.setItem("swarm-token", data.token);
    setToken(data.token);
    setUser(data.user);
    scheduleRefresh(data.token);
    return data.user;
  }, [scheduleRefresh]);

  const logout = useCallback(async () => {
    clearTimeout(refreshTimerRef.current);
    if (token) {
      try {
        await fetch(`${API_BASE}/api/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch { /* ignore network errors on logout */ }
    }
    localStorage.removeItem("swarm-token");
    setToken(null);
    setUser(null);
  }, [token]);

  /** Authenticated fetch — same API as window.fetch but adds Bearer header. */
  const apiFetch = useCallback(async (path, options = {}) => {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    const r = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (r.status === 401) {
      // Token expired or revoked — force logout
      clearTimeout(refreshTimerRef.current);
      localStorage.removeItem("swarm-token");
      setToken(null);
      setUser(null);
      throw new Error("SESSION_EXPIRED");
    }
    return r;
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, apiFetch, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
