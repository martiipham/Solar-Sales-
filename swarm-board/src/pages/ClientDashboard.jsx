/**
 * ClientDashboard — client-facing portal (solar-dashboard-v3 design).
 *
 * Pages: Overview · Leads · Calls · Emails · Agents · Reporting · Settings
 *
 * Live APIs:
 *   GET /api/voice/status      — AI status
 *   GET /api/calls/stats       — call metrics
 *   GET /api/calls             — call list
 *   GET /api/calls/:id         — call detail + transcript
 *   GET /api/swarm/leads       — lead list
 *   GET /api/agents/config     — agent toggles
 *   PATCH /api/agents/config   — update agent toggles
 *   GET /api/reports/monthly   — month KPIs vs prior month
 *   GET /api/reports/weekly    — 30-day daily breakdown
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:      "#04070E",
  panel:   "#080D1A",
  card:    "#0B1222",
  border:  "#12203A",
  accent:  "#22D3EE",
  amber:   "#F5A623",
  green:   "#34D399",
  red:     "#F87171",
  purple:  "#A78BFA",
  muted:   "#4A6080",
  text:    "#E2EAF4",
  subtext: "#8BA4C0",
};

const a = (c, o) => c + Math.round(o * 255).toString(16).padStart(2, "0");

// ─── Google Fonts ─────────────────────────────────────────────────────────────
const FONTS = `@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');`;

// ─── Primitive components ─────────────────────────────────────────────────────
function Mono({ children, style }) {
  return (
    <span style={{ fontFamily: "'JetBrains Mono', monospace", ...style }}>
      {children}
    </span>
  );
}

function ScoreBadge({ score }) {
  const n = Number(score) || 0;
  const color = n >= 80 ? T.green : n >= 50 ? T.amber : T.red;
  return (
    <span style={{
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 11, fontWeight: 600,
      color, background: a(color, 0.12),
      padding: "2px 8px", borderRadius: 4,
    }}>
      {n}
    </span>
  );
}

function ActionPill({ label, color = T.accent }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, letterSpacing: 1,
      color, background: a(color, 0.1),
      border: `1px solid ${a(color, 0.3)}`,
      padding: "2px 8px", borderRadius: 20,
      textTransform: "uppercase",
    }}>
      {label}
    </span>
  );
}

function StatusDot({ active, label }) {
  const color = active ? T.green : T.muted;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%",
        background: color,
        boxShadow: active ? `0 0 6px ${color}` : "none",
      }} />
      <span style={{ fontSize: 11, color: T.subtext, letterSpacing: 1,
        fontFamily: "'JetBrains Mono', monospace" }}>
        {label}
      </span>
    </span>
  );
}

function Metric({ label, value, unit, sub, accent = T.accent }) {
  return (
    <div style={{
      background: T.card, border: `1px solid ${T.border}`,
      borderRadius: 10, padding: "16px 20px",
    }}>
      <div style={{ fontSize: 10, color: T.muted, letterSpacing: 2,
        textTransform: "uppercase", marginBottom: 8,
        fontFamily: "'JetBrains Mono', monospace" }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: accent,
          fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
          {value ?? "—"}
        </span>
        {unit && (
          <span style={{ fontSize: 12, color: T.muted,
            fontFamily: "'JetBrains Mono', monospace" }}>
            {unit}
          </span>
        )}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: T.subtext, marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

function Toggle({ checked, onChange }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 36, height: 20, borderRadius: 10, cursor: "pointer",
        background: checked ? a(T.accent, 0.25) : a(T.muted, 0.2),
        border: `1px solid ${checked ? T.accent : T.muted}`,
        position: "relative", transition: "all 0.2s",
      }}
    >
      <div style={{
        position: "absolute", top: 2,
        left: checked ? 18 : 2,
        width: 14, height: 14, borderRadius: "50%",
        background: checked ? T.accent : T.muted,
        transition: "left 0.2s",
      }} />
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, color: T.muted, letterSpacing: 3,
      textTransform: "uppercase", padding: "12px 16px 6px",
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {children}
    </div>
  );
}

function Btn({ children, onClick, variant = "primary", style }) {
  const styles = {
    primary: {
      background: a(T.accent, 0.15),
      border: `1px solid ${a(T.accent, 0.4)}`,
      color: T.accent,
    },
    ghost: {
      background: "transparent",
      border: `1px solid ${T.border}`,
      color: T.subtext,
    },
    danger: {
      background: a(T.red, 0.12),
      border: `1px solid ${a(T.red, 0.3)}`,
      color: T.red,
    },
  };
  return (
    <button
      onClick={onClick}
      style={{
        padding: "7px 16px", borderRadius: 7, cursor: "pointer",
        fontSize: 12, fontWeight: 600,
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        transition: "opacity 0.15s",
        ...styles[variant],
        ...style,
      }}
      onMouseEnter={e => (e.currentTarget.style.opacity = "0.8")}
      onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
    >
      {children}
    </button>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: T.card, border: `1px solid ${T.border}`,
      borderRadius: 12, ...style,
    }}>
      {children}
    </div>
  );
}

function CardHeader({ title, sub, right }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "16px 20px", borderBottom: `1px solid ${T.border}`,
    }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{title}</div>
        {sub && <div style={{ fontSize: 11, color: T.subtext, marginTop: 2 }}>{sub}</div>}
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}

// ─── Nav config ───────────────────────────────────────────────────────────────
const NAV = [
  {
    section: "OPERATIONS",
    items: [
      { id: "overview",  label: "Overview",  icon: "◈" },
      { id: "leads",     label: "Leads",     icon: "◎" },
      { id: "calls",     label: "Calls",     icon: "◷" },
      { id: "emails",    label: "Emails",    icon: "◻" },
    ],
  },
  {
    section: "SYSTEM",
    items: [
      { id: "agents",    label: "Agents",    icon: "◬" },
      { id: "reporting", label: "Reporting", icon: "◫" },
    ],
  },
  {
    section: "CONFIG",
    items: [
      { id: "settings",  label: "Settings",  icon: "◯" },
    ],
  },
];

// ─── Pages ────────────────────────────────────────────────────────────────────

function OverviewPage({ apiFetch }) {
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [stats, setStats]             = useState(null);
  const [leads, setLeads]             = useState([]);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    if (!apiFetch) { setLoading(false); return; }
    setLoading(true);
    Promise.all([
      apiFetch("/api/voice/status").then(r => r.json()).catch(() => null),
      apiFetch("/api/calls/stats").then(r => r.json()).catch(() => null),
      apiFetch("/api/swarm/leads?limit=5").then(r => r.json()).catch(() => null),
    ]).then(([vs, st, ld]) => {
      setVoiceStatus(vs);
      setStats(st);
      setLeads(ld?.leads || ld || []);
      setLoading(false);
    });
  }, [apiFetch]);

  const aiActive = voiceStatus?.active === true || voiceStatus?.status === "active";
  const week = stats?.this_week || {};

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>
            System Overview
          </h2>
          <div style={{ fontSize: 12, color: T.subtext, marginTop: 4 }}>
            Live performance snapshot
          </div>
        </div>
        <StatusDot active={aiActive} label={aiActive ? "AI ONLINE" : "AI OFFLINE"} />
      </div>

      {/* Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="Calls This Week" value={loading ? "…" : (week.calls ?? "—")} accent={T.accent} />
        <Metric label="Completed"       value={loading ? "…" : (week.completed ?? "—")} accent={T.green} />
        <Metric label="Avg Duration"    value={loading ? "…" : (week.avg_duration ?? "—")} accent={T.amber} />
        <Metric label="Booking Rate"    value={loading ? "…" : (week.booking_rate ?? "—")} unit={week.booking_rate != null ? "%" : undefined} accent={T.purple} />
      </div>

      {/* Hot leads */}
      <Card>
        <CardHeader title="Recent Leads" sub="Latest prospects from AI outreach" />
        <div style={{ padding: "0 20px 16px" }}>
          {leads.length === 0 ? (
            <div style={{ padding: "20px 0", color: T.muted, fontSize: 13 }}>
              {loading ? "Loading…" : "No leads yet"}
            </div>
          ) : leads.map((l, i) => (
            <div key={l.id || i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "12px 0",
              borderBottom: i < leads.length - 1 ? `1px solid ${T.border}` : "none",
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                  {l.name || l.contact_name || "Unknown"}
                </div>
                <div style={{ fontSize: 11, color: T.subtext, marginTop: 2 }}>
                  {l.phone || l.email || "—"}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <ScoreBadge score={l.qualification_score ?? l.score ?? 0} />
                <ActionPill label={l.status || "new"} color={T.accent} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function LeadsPage({ apiFetch }) {
  const [leads, setLeads]   = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!apiFetch) { setLoading(false); return; }
    apiFetch("/api/swarm/leads?limit=100")
      .then(r => r.json())
      .then(d => { setLeads(d?.leads || d || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [apiFetch]);

  const statusColor = s => {
    if (!s) return T.muted;
    if (s === "converted") return T.green;
    if (s === "called") return T.accent;
    if (s === "failed") return T.red;
    return T.amber;
  };

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 20, fontWeight: 700, color: T.text }}>
        Lead Pipeline
      </h2>
      <Card>
        <CardHeader title="All Leads" sub={`${leads.length} prospects`} />
        <div style={{ padding: "0 20px 16px" }}>
          {loading ? (
            <div style={{ padding: "20px 0", color: T.muted, fontSize: 13 }}>Loading…</div>
          ) : leads.length === 0 ? (
            <div style={{ padding: "20px 0", color: T.muted, fontSize: 13 }}>No leads found</div>
          ) : leads.map((l, i) => (
            <div key={l.id || i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "12px 0",
              borderBottom: i < leads.length - 1 ? `1px solid ${T.border}` : "none",
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                  {l.name || l.contact_name || "Unknown"}
                </div>
                <div style={{ fontSize: 11, color: T.subtext, marginTop: 2 }}>
                  {l.phone || l.email || "—"}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <ScoreBadge score={l.qualification_score ?? l.score ?? 0} />
                <span style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: 1,
                  color: statusColor(l.status),
                  background: a(statusColor(l.status), 0.1),
                  border: `1px solid ${a(statusColor(l.status), 0.3)}`,
                  padding: "2px 8px", borderRadius: 20,
                  textTransform: "uppercase",
                }}>
                  {l.status || "new"}
                </span>
                <div style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace", width: 90, textAlign: "right" }}>
                  {l.created_at ? new Date(l.created_at).toLocaleDateString() : "—"}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function CallsPage({ apiFetch }) {
  const [calls, setCalls]     = useState([]);
  const [stats, setStats]     = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail]   = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!apiFetch) { setLoading(false); return; }
    Promise.all([
      apiFetch("/api/calls?limit=50").then(r => r.json()).catch(() => ({ calls: [] })),
      apiFetch("/api/calls/stats").then(r => r.json()).catch(() => null),
    ]).then(([cl, st]) => {
      setCalls(cl?.calls || []);
      setStats(st);
      setLoading(false);
    });
  }, [apiFetch]);

  const openCall = useCallback(id => {
    setSelected(id);
    setDetail(null);
    apiFetch(`/api/calls/${id}`)
      .then(r => r.json())
      .then(d => setDetail(d?.call || d))
      .catch(() => setDetail(null));
  }, [apiFetch]);

  const week = stats?.this_week || {};

  const statusColor = s => s === "completed" ? T.green : s === "failed" ? T.red : T.amber;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>Call Log</h2>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Metric label="This Week"    value={week.calls ?? "—"}          accent={T.accent} />
        <Metric label="Completed"    value={week.completed ?? "—"}      accent={T.green} />
        <Metric label="Avg Duration" value={week.avg_duration ?? "—"}   accent={T.amber} />
        <Metric label="Avg Score"    value={week.avg_score ?? "—"}      accent={T.purple} />
      </div>

      <div style={{ display: "flex", gap: 16, flex: 1 }}>
        {/* Call list */}
        <Card style={{ flex: 1 }}>
          <CardHeader title="Recent Calls" sub={`${calls.length} records`} />
          <div style={{ overflowY: "auto", maxHeight: 480 }}>
            {loading ? (
              <div style={{ padding: "20px", color: T.muted, fontSize: 13 }}>Loading…</div>
            ) : calls.length === 0 ? (
              <div style={{ padding: "20px", color: T.muted, fontSize: 13 }}>No calls found</div>
            ) : calls.map(c => (
              <div
                key={c.call_id}
                onClick={() => openCall(c.call_id)}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "12px 20px",
                  borderBottom: `1px solid ${T.border}`,
                  cursor: "pointer",
                  background: selected === c.call_id ? a(T.accent, 0.06) : "transparent",
                  transition: "background 0.15s",
                }}
                onMouseEnter={e => { if (selected !== c.call_id) e.currentTarget.style.background = a(T.text, 0.03); }}
                onMouseLeave={e => { if (selected !== c.call_id) e.currentTarget.style.background = "transparent"; }}
              >
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: T.text,
                    fontFamily: "'JetBrains Mono', monospace" }}>
                    {c.from_phone || "Unknown"}
                  </div>
                  <div style={{ fontSize: 11, color: T.subtext, marginTop: 2 }}>
                    {c.started_at ? new Date(c.started_at).toLocaleString() : "—"}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Mono style={{ fontSize: 11, color: T.muted }}>{c.duration_fmt || "—"}</Mono>
                  <span style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: 1,
                    color: statusColor(c.status),
                    background: a(statusColor(c.status), 0.1),
                    border: `1px solid ${a(statusColor(c.status), 0.25)}`,
                    padding: "1px 7px", borderRadius: 20, textTransform: "uppercase",
                  }}>
                    {c.status || "—"}
                  </span>
                  {c.lead_score != null && <ScoreBadge score={c.lead_score} />}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Detail panel */}
        {selected && (
          <Card style={{ width: 340 }}>
            <CardHeader
              title="Call Detail"
              right={<Btn variant="ghost" onClick={() => { setSelected(null); setDetail(null); }}>✕</Btn>}
            />
            <div style={{ padding: 16, overflowY: "auto", maxHeight: 480 }}>
              {!detail ? (
                <div style={{ color: T.muted, fontSize: 12 }}>Loading transcript…</div>
              ) : (
                <>
                  <div style={{ marginBottom: 16, display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ fontSize: 11, color: T.subtext }}>
                      <Mono>{detail.from_phone || "—"}</Mono> → <Mono>{detail.to_phone || "—"}</Mono>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <ActionPill label={detail.status || "—"} color={statusColor(detail.status)} />
                      <Mono style={{ fontSize: 11, color: T.muted }}>{detail.duration_fmt || "—"}</Mono>
                      {detail.lead_score != null && <ScoreBadge score={detail.lead_score} />}
                    </div>
                  </div>
                  {/* Transcript */}
                  {detail.transcript && detail.transcript.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {detail.transcript.map((t, i) => {
                        const isAgent = (t.role || "").toLowerCase() !== "user";
                        return (
                          <div key={i} style={{
                            padding: "8px 12px", borderRadius: 8,
                            background: isAgent ? a(T.accent, 0.08) : a(T.purple, 0.08),
                            border: `1px solid ${isAgent ? a(T.accent, 0.2) : a(T.purple, 0.2)}`,
                            alignSelf: isAgent ? "flex-start" : "flex-end",
                            maxWidth: "90%",
                          }}>
                            <div style={{ fontSize: 9, color: isAgent ? T.accent : T.purple,
                              letterSpacing: 1, marginBottom: 4, textTransform: "uppercase",
                              fontFamily: "'JetBrains Mono', monospace" }}>
                              {t.role || "unknown"}
                            </div>
                            <div style={{ fontSize: 12, color: T.text, lineHeight: 1.5 }}>
                              {t.content || t.text || ""}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ color: T.muted, fontSize: 12 }}>No transcript available</div>
                  )}
                </>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function EmailsPage() {
  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 20, fontWeight: 700, color: T.text }}>
        Email Inbox
      </h2>
      <Card>
        <div style={{
          padding: 48, textAlign: "center",
          display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
        }}>
          <div style={{ fontSize: 40, opacity: 0.3 }}>◻</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: T.subtext }}>
            No email inbox connected yet
          </div>
          <div style={{ fontSize: 12, color: T.muted, maxWidth: 320 }}>
            Email automation will appear here once your inbox is connected.
            Contact your account manager to enable email integration.
          </div>
        </div>
      </Card>
    </div>
  );
}

function AgentsPage({ apiFetch }) {
  const [agents, setAgents]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    if (!apiFetch) { setLoading(false); return; }
    apiFetch("/api/agents/config")
      .then(r => r.json())
      .then(d => {
        const list = d?.agents || d?.config || d || [];
        setAgents(Array.isArray(list) ? list : Object.entries(list).map(([k, v]) => ({
          id: k, name: k, enabled: v?.enabled ?? v ?? false,
          description: v?.description || "",
        })));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiFetch]);

  const toggle = async (id, val) => {
    if (!apiFetch) return;
    setSaving(true);
    setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: val } : a));
    try {
      await apiFetch("/api/agents/config", {
        method: "PATCH",
        body: JSON.stringify({ id, enabled: val }),
      });
    } catch {
      // revert on error
      setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !val } : a));
    }
    setSaving(false);
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>AI Agents</h2>
        {saving && <Mono style={{ fontSize: 11, color: T.amber }}>Saving…</Mono>}
      </div>
      <Card>
        <CardHeader title="Agent Configuration" sub="Enable or disable AI agents" />
        <div style={{ padding: "0 20px 16px" }}>
          {loading ? (
            <div style={{ padding: "20px 0", color: T.muted, fontSize: 13 }}>Loading…</div>
          ) : agents.length === 0 ? (
            <div style={{ padding: "20px 0", color: T.muted, fontSize: 13 }}>No agents configured</div>
          ) : agents.map((ag, i) => (
            <div key={ag.id || i} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "14px 0",
              borderBottom: i < agents.length - 1 ? `1px solid ${T.border}` : "none",
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                  {ag.name || ag.id}
                </div>
                {ag.description && (
                  <div style={{ fontSize: 11, color: T.subtext, marginTop: 2 }}>
                    {ag.description}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <StatusDot active={ag.enabled} label={ag.enabled ? "ON" : "OFF"} />
                <Toggle checked={!!ag.enabled} onChange={v => toggle(ag.id, v)} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ReportingPage({ apiFetch }) {
  const [monthly, setMonthly]   = useState(null);
  const [weekly, setWeekly]     = useState(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    if (!apiFetch) { setLoading(false); return; }
    Promise.all([
      apiFetch("/api/reports/monthly").then(r => r.json()).catch(() => null),
      apiFetch("/api/reports/weekly?days=30").then(r => r.json()).catch(() => null),
    ]).then(([m, w]) => {
      setMonthly(m);
      setWeekly(w);
      setLoading(false);
    });
  }, [apiFetch]);

  const curr = monthly?.calls?.current || {};
  const leads = monthly?.leads?.current || {};
  const totals = weekly?.totals || {};
  const period = monthly?.period?.label || "";

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>Reporting</h2>
        {period && <Mono style={{ fontSize: 11, color: T.subtext }}>{period}</Mono>}
      </div>

      {/* Month KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <Metric
          label="Monthly Calls"
          value={loading ? "…" : (curr.calls ?? "—")}
          sub={monthly?.calls?.vs_prior ? `${monthly.calls.vs_prior} vs last month` : undefined}
          accent={T.accent}
        />
        <Metric
          label="Conversion Rate"
          value={loading ? "…" : (leads.conversion_rate ?? "—")}
          unit={leads.conversion_rate != null ? "%" : undefined}
          sub={monthly?.leads?.vs_prior ? `${monthly.leads.vs_prior} vs last month` : undefined}
          accent={T.green}
        />
        <Metric
          label="Avg Lead Score"
          value={loading ? "…" : (leads.avg_score ?? "—")}
          sub={leads.hot != null ? `${leads.hot} hot leads` : undefined}
          accent={T.purple}
        />
      </div>

      {/* 30-day breakdown */}
      <Card>
        <CardHeader title="Last 30 Days" sub="Daily activity" />
        <div style={{ padding: "16px 20px" }}>
          {loading ? (
            <div style={{ color: T.muted, fontSize: 13 }}>Loading…</div>
          ) : !weekly?.days?.length ? (
            <div style={{ color: T.muted, fontSize: 13 }}>No data yet — activity will appear as your AI handles calls.</div>
          ) : (
            <>
              {/* Totals summary */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
                {[
                  { label: "Calls",       value: totals.calls ?? 0,       color: T.accent },
                  { label: "Leads",       value: totals.leads ?? 0,       color: T.amber },
                  { label: "Hot Leads",   value: totals.hot_leads ?? 0,   color: T.red },
                  { label: "Conversions", value: totals.conversions ?? 0, color: T.green },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{
                    background: T.bg, border: `1px solid ${T.border}`,
                    borderRadius: 8, padding: "10px 14px",
                  }}>
                    <div style={{ fontSize: 9, color: T.muted, letterSpacing: 2,
                      textTransform: "uppercase", marginBottom: 4,
                      fontFamily: "'JetBrains Mono', monospace" }}>{label}</div>
                    <div style={{ fontSize: 22, fontWeight: 700, color,
                      fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
                  </div>
                ))}
              </div>

              {/* Bar chart — calls per day */}
              <div style={{ fontSize: 10, color: T.muted, letterSpacing: 2,
                textTransform: "uppercase", marginBottom: 8,
                fontFamily: "'JetBrains Mono', monospace" }}>
                Daily Calls
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 60, marginBottom: 8 }}>
                {weekly.days.map(d => {
                  const maxCalls = Math.max(...weekly.days.map(x => x.calls), 1);
                  const pct = (d.calls / maxCalls) * 100;
                  return (
                    <div
                      key={d.date}
                      title={`${d.date}: ${d.calls} calls`}
                      style={{
                        flex: 1, minWidth: 0, height: `${Math.max(pct, 2)}%`,
                        background: d.calls > 0 ? a(T.accent, 0.5) : a(T.muted, 0.15),
                        borderRadius: 2, cursor: "default",
                        transition: "background 0.15s",
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = d.calls > 0 ? T.accent : a(T.muted, 0.3); }}
                      onMouseLeave={e => { e.currentTarget.style.background = d.calls > 0 ? a(T.accent, 0.5) : a(T.muted, 0.15); }}
                    />
                  );
                })}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between",
                fontSize: 9, color: T.muted, fontFamily: "'JetBrains Mono', monospace" }}>
                <span>{weekly.days[0]?.date?.slice(5)}</span>
                <span>{weekly.days[weekly.days.length - 1]?.date?.slice(5)}</span>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Highlights */}
      {monthly?.highlights?.length > 0 && (
        <Card>
          <CardHeader title="Highlights" sub="Key observations this month" />
          <div style={{ padding: "12px 20px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
            {monthly.highlights.map((h, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ color: T.accent, fontSize: 12 }}>◆</span>
                <span style={{ fontSize: 13, color: T.text }}>{h}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function SettingsPage({ user }) {
  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: "0 0 20px", fontSize: 20, fontWeight: 700, color: T.text }}>
        Settings
      </h2>
      <Card style={{ marginBottom: 16 }}>
        <CardHeader title="Account" />
        <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12, color: T.subtext }}>Name</span>
            <Mono style={{ fontSize: 12, color: T.text }}>{user?.name || "—"}</Mono>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12, color: T.subtext }}>Email</span>
            <Mono style={{ fontSize: 12, color: T.text }}>{user?.email || "—"}</Mono>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12, color: T.subtext }}>Role</span>
            <ActionPill label={user?.role || "client"} color={T.accent} />
          </div>
        </div>
      </Card>
      <Card>
        <CardHeader title="Notifications" sub="Manage how you receive updates" />
        <div style={{ padding: 32, textAlign: "center", color: T.muted, fontSize: 13 }}>
          Notification settings coming soon.
        </div>
      </Card>
    </div>
  );
}

// ─── Main shell ───────────────────────────────────────────────────────────────

export default function ClientDashboard() {
  const auth     = useAuth?.() || {};
  const user     = auth.user;
  const logout   = auth.logout;
  const apiFetch = auth.apiFetch;

  const [page, setPage] = useState("overview");

  const renderPage = () => {
    switch (page) {
      case "overview":  return <OverviewPage  apiFetch={apiFetch} />;
      case "leads":     return <LeadsPage     apiFetch={apiFetch} />;
      case "calls":     return <CallsPage     apiFetch={apiFetch} />;
      case "emails":    return <EmailsPage />;
      case "agents":    return <AgentsPage    apiFetch={apiFetch} />;
      case "reporting": return <ReportingPage apiFetch={apiFetch} />;
      case "settings":  return <SettingsPage  user={user} />;
      default:          return <OverviewPage  apiFetch={apiFetch} />;
    }
  };

  return (
    <div style={{
      display: "flex", height: "100vh", background: T.bg,
      fontFamily: "'Plus Jakarta Sans', sans-serif",
      color: T.text, overflow: "hidden",
    }}>
      <style>{`
        ${FONTS}
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: ${T.bg}; }
        ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 2px; }
      `}</style>

      {/* Sidebar */}
      <div style={{
        width: 220, background: T.panel,
        borderRight: `1px solid ${T.border}`,
        display: "flex", flexDirection: "column",
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{
          padding: "20px 16px 16px",
          borderBottom: `1px solid ${T.border}`,
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: `linear-gradient(135deg, ${T.amber}, #E07B1A)`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 700, color: "#000",
            }}>
              S
            </div>
            <div>
              <div style={{
                fontSize: 12, fontWeight: 700, color: T.text,
                letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace",
              }}>
                SOLAR<span style={{ color: T.amber }}>AI</span>
              </div>
              <div style={{ fontSize: 9, color: T.muted, letterSpacing: 1 }}>
                CLIENT PORTAL
              </div>
            </div>
          </div>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, overflowY: "auto", paddingTop: 8 }}>
          {NAV.map(group => (
            <div key={group.section}>
              <SectionLabel>{group.section}</SectionLabel>
              {group.items.map(item => {
                const active = page === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setPage(item.id)}
                    style={{
                      width: "100%", display: "flex", alignItems: "center", gap: 10,
                      padding: "9px 16px", border: "none", cursor: "pointer",
                      background: active ? a(T.accent, 0.1) : "transparent",
                      borderLeft: `2px solid ${active ? T.accent : "transparent"}`,
                      color: active ? T.accent : T.subtext,
                      fontSize: 13, fontWeight: active ? 600 : 400,
                      transition: "all 0.15s",
                      textAlign: "left",
                    }}
                    onMouseEnter={e => { if (!active) e.currentTarget.style.background = a(T.text, 0.04); }}
                    onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
                  >
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 14, opacity: active ? 1 : 0.6,
                    }}>
                      {item.icon}
                    </span>
                    {item.label}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer — user info + sign out */}
        <div style={{
          padding: "12px 16px",
          borderTop: `1px solid ${T.border}`,
          display: "flex", flexDirection: "column", gap: 10,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              background: a(T.accent, 0.15),
              border: `1px solid ${a(T.accent, 0.3)}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, color: T.accent,
            }}>
              {(user?.name || user?.email || "C")[0].toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: T.text,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.name || user?.email || "Client"}
              </div>
              <div style={{ fontSize: 10, color: T.muted }}>Client</div>
            </div>
          </div>
          {logout && (
            <button
              onClick={logout}
              style={{
                width: "100%", padding: "7px 0", border: `1px solid ${T.border}`,
                background: "transparent", color: T.muted, fontSize: 11,
                fontWeight: 600, letterSpacing: 1, borderRadius: 6,
                cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                textTransform: "uppercase", transition: "all 0.15s",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = T.red;
                e.currentTarget.style.color = T.red;
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = T.border;
                e.currentTarget.style.color = T.muted;
              }}
            >
              Sign Out
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflowY: "auto", background: T.bg }}>
        {/* Top bar */}
        <div style={{
          height: 52, borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 24px", background: T.panel, flexShrink: 0,
          position: "sticky", top: 0, zIndex: 10,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
            {NAV.flatMap(g => g.items).find(i => i.id === page)?.label || "Overview"}
          </div>
          <div style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
            {new Date().toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short" }).toUpperCase()}
          </div>
        </div>

        {/* Page content */}
        {renderPage()}
      </div>
    </div>
  );
}
