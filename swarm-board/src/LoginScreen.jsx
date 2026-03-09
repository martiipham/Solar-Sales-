/**
 * LoginScreen — full-page login for Solar Swarm.
 * Dark ops mission-control aesthetic, consistent with App.jsx.
 */
import { useState } from "react";
import { useAuth } from "./AuthContext";

const C = {
  bg:      "#050810",
  panel:   "#080D1A",
  card:    "#0C1222",
  border:  "#132035",
  borderB: "#1E3050",
  amber:   "#F59E0B",
  amberL:  "#FCD34D",
  cyan:    "#22D3EE",
  green:   "#4ADE80",
  red:     "#F87171",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Syne+Mono&family=DM+Sans:wght@300;400;500;600;700&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; background: #050810; }
  body { font-family: 'DM Sans', sans-serif; color: #CBD5E1; }
  @keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
  .login-card { animation: fadeUp .35s ease; }
  input:focus { outline: 2px solid #F59E0B44; outline-offset: 0; }
`;

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [showPw, setShowPw]     = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    if (!email || !password) { setError("Email and password are required."); return; }
    setLoading(true);
    setError("");
    try {
      await login(email.trim().toLowerCase(), password);
      // AuthContext updates user → AppShell will redirect automatically
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 20,
    }}>
      <style>{STYLES}</style>

      {/* Background grid effect */}
      <div style={{
        position: "fixed", inset: 0, zIndex: 0,
        backgroundImage: `
          linear-gradient(${h(C.amber, 0.03)} 1px, transparent 1px),
          linear-gradient(90deg, ${h(C.amber, 0.03)} 1px, transparent 1px)
        `,
        backgroundSize: "48px 48px",
        pointerEvents: "none",
      }} />

      <div className="login-card" style={{
        position: "relative", zIndex: 1,
        background: C.panel,
        border: `1px solid ${C.borderB}`,
        borderRadius: 20,
        padding: "44px 48px",
        width: "100%", maxWidth: 420,
        boxShadow: `0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px ${h(C.amber, 0.08)}`,
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>☀️</div>
          <div className="mono" style={{ fontSize: 18, color: C.amber, letterSpacing: 3, marginBottom: 4 }}>
            SOLAR SWARM
          </div>
          <div style={{ fontSize: 12, color: C.muted, letterSpacing: 1 }}>
            Agent Command Platform
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Email */}
          <div>
            <label style={{
              display: "block", fontSize: 11, color: C.muted,
              fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5,
              textTransform: "uppercase", marginBottom: 7,
            }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin@solarswarm.io"
              autoFocus
              autoComplete="email"
              style={{
                width: "100%", background: C.card,
                border: `1px solid ${C.border}`,
                borderRadius: 8, padding: "11px 14px",
                fontSize: 14, color: C.text,
                transition: "border-color .15s",
              }}
            />
          </div>

          {/* Password */}
          <div>
            <label style={{
              display: "block", fontSize: 11, color: C.muted,
              fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5,
              textTransform: "uppercase", marginBottom: 7,
            }}>
              Password
            </label>
            <div style={{ position: "relative" }}>
              <input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                style={{
                  width: "100%", background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8, padding: "11px 44px 11px 14px",
                  fontSize: 14, color: C.text,
                }}
              />
              <button
                type="button"
                onClick={() => setShowPw(v => !v)}
                style={{
                  position: "absolute", right: 12, top: "50%",
                  transform: "translateY(-50%)",
                  background: "none", border: "none",
                  color: C.muted, cursor: "pointer", fontSize: 15,
                  padding: 2,
                }}
                tabIndex={-1}
              >
                {showPw ? "○" : "●"}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              background: h(C.red, 0.1),
              border: `1px solid ${h(C.red, 0.3)}`,
              borderRadius: 8, padding: "10px 14px",
              fontSize: 13, color: C.red, lineHeight: 1.5,
            }}>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{
              background: loading ? h(C.amber, 0.08) : h(C.amber, 0.15),
              border: `1px solid ${loading ? h(C.amber, 0.3) : C.amber}`,
              color: loading ? h(C.amber, 0.5) : C.amber,
              padding: "13px 24px",
              borderRadius: 10, cursor: loading ? "wait" : "pointer",
              fontSize: 13, fontFamily: "'Syne Mono', monospace",
              letterSpacing: 1.5,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
              transition: "all .2s",
              boxShadow: loading ? "none" : `0 0 20px ${h(C.amber, 0.15)}`,
              marginTop: 4,
            }}
          >
            {loading
              ? <><span style={{ display: "inline-block", animation: "spin 1s linear infinite" }}>◌</span> SIGNING IN…</>
              : "→ SIGN IN"
            }
          </button>
        </form>

        {/* Default credentials hint */}
        <div style={{
          marginTop: 28, padding: "12px 14px",
          background: h(C.cyan, 0.04),
          border: `1px solid ${h(C.cyan, 0.15)}`,
          borderRadius: 8, fontSize: 12, color: C.muted, lineHeight: 1.7,
        }}>
          <span style={{ color: C.cyan }}>First time?</span> Default credentials:<br />
          <span className="mono" style={{ color: C.text }}>admin@solarswarm.io</span>
          {" / "}
          <span className="mono" style={{ color: C.text }}>changeme</span>
          <br />
          <span style={{ color: h(C.amber, 0.7) }}>Change your password in Settings after login.</span>
        </div>
      </div>
    </div>
  );
}
