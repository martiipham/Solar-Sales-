/**
 * AuthContext — JWT authentication state + authenticated fetch wrapper.
 *
 * Provides:
 *   useAuth()  → { user, token, login, logout, apiFetch, loading }
 *
 * Token is persisted in localStorage under "swarm-token".
 * apiFetch() automatically adds the Authorization header and handles 401s.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";

// Empty string = relative URLs — requests go through the Vite proxy to Flask.
// The proxy target (localhost:5003) is set in vite.config.js.
export const API_BASE = "";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken]   = useState(() => localStorage.getItem("swarm-token") || null);
  const [user, setUser]     = useState(null);
  const [loading, setLoading] = useState(true);  // true while validating stored token

  // Validate stored token on mount
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => setUser(d.user))
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
    return data.user;
  }, []);

  const logout = useCallback(async () => {
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
