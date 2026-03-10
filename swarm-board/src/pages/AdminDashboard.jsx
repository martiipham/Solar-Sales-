/**
 * AdminDashboard — self-contained admin/owner shell with sidebar, topbar,
 * and all inline page components wired to real APIs.
 *
 * Replaces Layout.jsx + individual page routing for admin/owner roles.
 * Client role continues to use ClientDashboard.
 *
 * Imports external pages for knowledge-base, onboarding, docs, company,
 * users, apikeys, and client-view.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../AuthContext";
import { useToast } from "../components/Toast";
import KnowledgeBasePage from "./KnowledgeBasePage";
import OnboardingPage from "./OnboardingPage";
import DocsPage from "./DocsPage";
import CompanyPage from "./CompanyPage";
import UsersPage from "./UsersPage";
import ApiKeysPage from "./ApiKeysPage";
import ClientDashboard from "./ClientDashboard";

/* ─── Design tokens ─────────────────────────────────────────────────────── */
const T = {
  bg: "#04070E", panel: "#080D1A", card: "#0B1222", cardHover: "#0E1730",
  surface: "#111C30", border: "#12203A", borderHover: "#1E3558",
  accent: "#22D3EE", accentDim: "#1AA3B8", amber: "#F5A623", amberWarm: "#FBBF24",
  green: "#34D399", red: "#F87171", orange: "#FB923C", purple: "#A78BFA",
  blue: "#60A5FA", teal: "#2DD4BF", white: "#F1F5F9", text: "#94A3B8",
  textLight: "#CBD5E1", muted: "#475569", dim: "#0F172A",
};
const a = (c, o) => c + Math.round(o * 255).toString(16).padStart(2, "0");

/* ─── Styles ─────────────────────────────────────────────────────────────── */
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Plus Jakarta Sans', sans-serif; background: ${T.bg}; color: ${T.text}; }
  .mono { font-family: 'JetBrains Mono', monospace !important; }
  @keyframes fadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:none; } }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  @keyframes breathe { 0%,100%{box-shadow:0 0 0 0 ${a(T.green,0.4)}} 50%{box-shadow:0 0 0 6px ${a(T.green,0)}} }
  @keyframes tooltipIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: ${T.panel}; }
  ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: ${T.borderHover}; }
  input, select, textarea, button { font-family: inherit; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: ${T.accent} !important; }
`;

/* ─── NAV config ─────────────────────────────────────────────────────────── */
const NAV = [
  { section: "OPERATIONS", items: [
    { id: "overview",   icon: "◈",  label: "Overview",       badge: null },
    { id: "leads",      icon: "★",  label: "Leads",          badge: "hotLeads" },
    { id: "calls",      icon: "◎",  label: "Calls",          badge: null },
    { id: "emails",     icon: "✉",  label: "Emails",         badge: "pendingEmails" },
  ]},
  { section: "SYSTEM", items: [
    { id: "agents",         icon: "⚡", label: "Agents",         badge: null },
    { id: "reporting",      icon: "▦",  label: "Reporting",      badge: null },
    { id: "knowledge-base", icon: "◉",  label: "Knowledge Base", badge: null },
  ]},
  { section: "SETUP", items: [
    { id: "onboarding", icon: "►",  label: "Onboarding",     badge: null },
    { id: "docs",       icon: "≡",  label: "Docs",           badge: null },
  ]},
  { section: "CONFIG", minRole: "admin", items: [
    { id: "settings",   icon: "⚙",  label: "Settings",       badge: null },
    { id: "companies",  icon: "▣",  label: "Company",        badge: null },
  ]},
  { section: "ADMIN", minRole: "owner", items: [
    { id: "users",       icon: "◎",  label: "Users",          badge: null },
    { id: "apikeys",     icon: "◆",  label: "API Keys",       badge: null },
    { id: "client-view", icon: "◑",  label: "Client Preview", badge: null },
  ]},
];

const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const canSee = (userRole, minRole) =>
  (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole ?? "admin"] ?? 0);

/* ─── Page titles ────────────────────────────────────────────────────────── */
const PAGE_META = {
  overview:       { title: "Command Center",    sub: "Live operations overview" },
  leads:          { title: "Lead Pipeline",     sub: "AI-scored inbound leads" },
  calls:          { title: "Call Logs",         sub: "Every call handled by AI" },
  emails:         { title: "Email Queue",       sub: "AI-drafted replies awaiting approval" },
  agents:         { title: "AI Agents",         sub: "Monitor and control your automation" },
  reporting:      { title: "Reporting",         sub: "Performance metrics and trends" },
  "knowledge-base": { title: "Knowledge Base", sub: "Company data the AI uses on calls" },
  onboarding:     { title: "Onboarding",        sub: "Get your system configured" },
  docs:           { title: "Documentation",     sub: "Guides and API reference" },
  settings:       { title: "Settings",          sub: "Runtime configuration" },
  companies:      { title: "Company",           sub: "Your business profile" },
  users:          { title: "Users",             sub: "Team access and roles" },
  apikeys:        { title: "API Keys",          sub: "Manage integration credentials" },
  "client-view":  { title: "Client Preview",   sub: "See what your client sees" },
};

/* ─── Shared micro-components ────────────────────────────────────────────── */

function InfoTip({ text }) {
  const [show, setShow] = useState(false);
  const ref = useRef(null);
  return (
    <span ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        style={{
          background: a(T.accent, 0.12), border: `1px solid ${a(T.accent, 0.25)}`,
          color: T.accent, borderRadius: "50%", width: 16, height: 16, fontSize: 9,
          cursor: "default", display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontFamily: "'JetBrains Mono', monospace",
        }}
      >?</button>
      {show && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: "50%",
          transform: "translateX(-50%)",
          background: T.surface, border: `1px solid ${T.borderHover}`,
          color: T.textLight, borderRadius: 8, padding: "8px 12px",
          fontSize: 12, lineHeight: 1.5, whiteSpace: "normal", minWidth: 200, maxWidth: 280,
          zIndex: 9999, boxShadow: "0 8px 24px rgba(0,0,0,.5)",
          animation: "tooltipIn .15s ease",
        }}>
          {text}
        </div>
      )}
    </span>
  );
}

function Mono({ children, style }) {
  return (
    <span style={{ fontFamily: "'JetBrains Mono', monospace", ...style }}>{children}</span>
  );
}

function ScoreBadge({ score }) {
  const val = score != null ? Number(score) : null;
  const color = val == null ? T.muted : val >= 8 ? T.green : val >= 5 ? T.amber : T.red;
  return (
    <span style={{
      display: "inline-block",
      background: a(color, 0.15), border: `1px solid ${a(color, 0.35)}`,
      color, borderRadius: 6, padding: "2px 9px",
      fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
    }}>
      {val != null ? val.toFixed(1) : "—"}
    </span>
  );
}

function ActionPill({ action }) {
  const act = (action || "").toLowerCase();
  let color = T.muted;
  let label = action || "—";
  if (act.includes("call")) { color = T.green; label = "CALL NOW"; }
  else if (act.includes("nurture")) { color = T.purple; label = "NURTURE"; }
  else if (act.includes("disqualif")) { color = T.red; label = "DISQUALIFY"; }
  else if (act.includes("proposal") || act.includes("send")) { color = T.amber; label = "PROPOSAL"; }
  return (
    <span style={{
      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
      color, background: a(color, 0.1), border: `1px solid ${a(color, 0.25)}`,
      borderRadius: 10, padding: "2px 9px", whiteSpace: "nowrap",
    }}>
      {label.toUpperCase().replace(/_/g, " ")}
    </span>
  );
}

function StatusDot({ active, color }) {
  const c = color || (active ? T.green : T.muted);
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: c,
      boxShadow: active ? `0 0 0 0 ${a(c, 0.4)}` : "none",
      animation: active ? "breathe 2s infinite" : "none",
    }} />
  );
}

function Metric({ label, value, sub, color, tip }) {
  return (
    <div style={{
      background: T.card, border: `1px solid ${T.border}`,
      borderTop: `2px solid ${color || T.accent}`,
      borderRadius: 12, padding: "18px 20px", flex: "1 1 140px",
    }}>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 6, display: "flex", alignItems: "center", gap: 5 }}>
        {label}
        {tip && <InfoTip text={tip} />}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || T.white, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
        {value ?? "—"}
      </div>
      {sub && <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function Toggle({ enabled, onChange, disabled }) {
  return (
    <button
      onClick={() => !disabled && onChange(!enabled)}
      style={{
        position: "relative", width: 40, height: 22,
        background: enabled ? (disabled ? T.muted : T.green) : T.dim,
        borderRadius: 11,
        border: `1px solid ${enabled ? (disabled ? T.muted : T.green) : T.border}`,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all .2s", flexShrink: 0,
        opacity: disabled ? 0.5 : 1, padding: 0,
      }}
    >
      <span style={{
        position: "absolute", top: 2, left: enabled ? 20 : 2,
        width: 16, height: 16, background: T.white,
        borderRadius: "50%", transition: "left .2s",
        boxShadow: "0 1px 3px rgba(0,0,0,.4)",
      }} />
    </button>
  );
}

function SectionLabel({ label }) {
  return (
    <div style={{
      padding: "14px 14px 4px", fontSize: 9,
      fontFamily: "'JetBrains Mono', monospace",
      letterSpacing: 2, color: T.muted,
    }}>
      {label}
    </div>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: T.card, border: `1px solid ${T.border}`,
      borderRadius: 14, overflow: "hidden", ...style,
    }}>
      {children}
    </div>
  );
}

function CardHeader({ title, action, sub }) {
  return (
    <div style={{
      padding: "14px 18px", borderBottom: `1px solid ${T.border}`,
      display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: T.textLight }}>{title}</div>
        {sub && <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{sub}</div>}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

function Btn({ children, onClick, variant = "default", style, disabled }) {
  const base = {
    padding: "8px 16px", borderRadius: 8, fontSize: 12, cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: "'JetBrains Mono', monospace", letterSpacing: 0.5,
    transition: "all .15s", border: "1px solid", opacity: disabled ? 0.5 : 1,
  };
  const variants = {
    default: { background: a(T.accent, 0.1), borderColor: a(T.accent, 0.3), color: T.accent },
    solid:   { background: T.amber, borderColor: T.amber, color: "#050810" },
    ghost:   { background: "transparent", borderColor: T.border, color: T.muted },
  };
  return (
    <button onClick={disabled ? undefined : onClick} style={{ ...base, ...variants[variant], ...style }}>
      {children}
    </button>
  );
}

function Skeleton({ width = "100%", height = 16 }) {
  return (
    <div style={{
      width, height, borderRadius: 6,
      background: `linear-gradient(90deg,${T.card} 25%,${T.border} 50%,${T.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

/* ─── OVERVIEW PAGE ──────────────────────────────────────────────────────── */
function OverviewPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [summary, setSummary] = useState(null);
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [recentCalls, setRecentCalls] = useState([]);
  const [hotLeads, setHotLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, voiceRes, callsRes, leadsRes] = await Promise.allSettled([
        apiFetch("/api/dashboard/summary").then(r => r.json()),
        apiFetch("/api/voice/status").then(r => r.json()),
        apiFetch("/api/calls?limit=4").then(r => r.json()),
        apiFetch("/api/leads?limit=50").then(r => r.json()),
      ]);
      if (sumRes.status === "fulfilled") setSummary(sumRes.value);
      if (voiceRes.status === "fulfilled") setVoiceStatus(voiceRes.value);
      if (callsRes.status === "fulfilled") setRecentCalls(callsRes.value.calls || []);
      if (leadsRes.status === "fulfilled") {
        setHotLeads((leadsRes.value.leads || []).filter(l => (l.qualification_score || 0) >= 8));
      }
    } catch (e) {
      toast.error("Failed to load overview");
    } finally {
      setLoading(false);
    }
  }, [apiFetch]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const pipelineValue = loading ? "—" : `$${((summary?.hot_leads || 0) * 9200).toLocaleString()}`;
  const voiceActive = voiceStatus?.status === "active" || voiceStatus?.agent_ready;

  const AGENTS_STATIC = [
    { name: "Email Processor", icon: "✉", color: T.accent,  active: true },
    { name: "Lead Qualifier",  icon: "★", color: T.orange,  active: true },
    { name: "Proposal Gen",    icon: "≡", color: T.green,   active: true },
    { name: "CRM Sync",        icon: "↻", color: T.teal,    active: true },
  ];

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      {/* KPI row */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        <Metric label="Calls Today"    value={loading ? "—" : summary?.calls_today ?? 0}    color={T.purple} tip="Inbound calls handled by AI today" />
        <Metric label="Emails Today"   value={loading ? "—" : summary?.emails_today ?? 0}   color={T.accent} tip="Emails triaged and drafted today" />
        <Metric label="New Leads"      value={loading ? "—" : summary?.leads_today ?? 0}    color={T.amber}  tip="Leads created and scored today" />
        <Metric label="Hot Leads"      value={loading ? "—" : summary?.hot_leads ?? 0}      color={T.green}  tip="Leads with score >= 8 (call now)" />
        <Metric label="Pipeline Est."  value={loading ? "—" : pipelineValue} color={T.teal} tip="Hot leads × $9,200 avg deal value" />
      </div>

      {/* Main grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Recent calls */}
        <Card>
          <CardHeader title="Recent Calls" sub="Last 4 AI-handled calls" />
          <div>
            {loading ? (
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                {[1,2,3,4].map(i => <Skeleton key={i} height={44} />)}
              </div>
            ) : recentCalls.length === 0 ? (
              <div style={{ padding: "32px 20px", textAlign: "center", color: T.muted, fontSize: 13 }}>
                No calls yet — the AI receptionist is standing by.
              </div>
            ) : recentCalls.map(call => {
              const score = call.lead_score || 0;
              const scoreColor = score >= 8 ? T.green : score >= 5 ? T.amber : T.red;
              return (
                <div key={call.call_id} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: T.textLight }}>
                      {call.from_phone || "Unknown"}
                    </div>
                    <div style={{ fontSize: 11, color: T.muted }}>
                      {call.started_at ? new Date(call.started_at).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" }) : "—"}
                      {" · "}{call.duration_fmt || "0:00"}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                      color: scoreColor, background: a(scoreColor, 0.1), border: `1px solid ${a(scoreColor, 0.25)}`,
                      borderRadius: 10, padding: "2px 8px",
                    }}>
                      {score.toFixed(1)}
                    </span>
                    <span style={{
                      fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                      color: call.status === "completed" ? T.green : T.muted,
                      background: a(call.status === "completed" ? T.green : T.muted, 0.1),
                      border: `1px solid ${a(call.status === "completed" ? T.green : T.muted, 0.25)}`,
                      borderRadius: 10, padding: "2px 8px",
                    }}>
                      {(call.status || "—").toUpperCase()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Agent status */}
        <Card>
          <CardHeader title="Agent Status" sub="Live automation health" />
          <div style={{ padding: "8px 0" }}>
            {/* Voice agent from API */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 16 }}>◎</span>
                <div>
                  <div style={{ fontSize: 13, color: voiceActive ? T.textLight : T.muted }}>Voice AI</div>
                  <div style={{ fontSize: 11, color: T.muted }}>AI Phone Receptionist</div>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <StatusDot active={voiceActive} />
                <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: T.muted }}>
                  {loading ? "—" : voiceActive ? "ACTIVE" : "IDLE"}
                </span>
              </div>
            </div>
            {AGENTS_STATIC.map(ag => (
              <div key={ag.name} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 16 }}>{ag.icon}</span>
                  <div style={{ fontSize: 13, color: T.textLight }}>{ag.name}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <StatusDot active={ag.active} color={ag.color} />
                  <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: T.muted }}>
                    ACTIVE
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Hot leads banner */}
      {!loading && hotLeads.length > 0 && (
        <Card>
          <CardHeader
            title="Hot Leads"
            sub={`${hotLeads.length} leads scoring 8+ — call now for best conversion`}
          />
          <div>
            {hotLeads.slice(0, 6).map(lead => (
              <div key={lead.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.textLight }}>
                    {lead.name || "Unknown Lead"}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted }}>
                    {lead.phone || "—"} · {lead.suburb || "—"}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ScoreBadge score={lead.qualification_score} />
                  <ActionPill action={lead.recommended_action} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {loading && !summary && (
        <div style={{ color: T.muted, fontSize: 13, padding: "12px 0" }}>Loading overview…</div>
      )}
    </div>
  );
}

/* ─── LEADS PAGE ─────────────────────────────────────────────────────────── */
function LeadsPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [leads, setLeads]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState("all");
  const [search, setSearch]   = useState("");
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch("/api/leads?limit=100");
      const d = await r.json();
      setLeads(d.leads || []);
    } catch { setLeads([]); } finally { setLoading(false); }
  }, [apiFetch]);

  useEffect(() => { load(); }, [load]);

  const normalizeAction = (action) => {
    const a = (action || "").toLowerCase();
    if (a.includes("call")) return "call_now";
    if (a.includes("nurture")) return "nurture";
    if (a.includes("disqualif")) return "disqualify";
    return "other";
  };

  const filtered = leads.filter(l => {
    if (filter !== "all" && normalizeAction(l.recommended_action) !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (l.name || "").toLowerCase().includes(q) ||
             (l.phone || "").includes(q) ||
             (l.suburb || "").toLowerCase().includes(q);
    }
    return true;
  });

  const handleProposal = async (lead) => {
    try {
      await apiFetch(`/api/leads/${lead.id}/proposal`, { method: "POST" });
      toast.success("Proposal generation triggered");
    } catch { toast.error("Failed to trigger proposal"); }
  };

  const handleMarkCalled = async (lead) => {
    try {
      const r = await apiFetch(`/api/leads/${lead.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "called" }),
      });
      if (r.ok) {
        toast.success("Lead marked as called");
        setLeads(prev => prev.map(x => x.id === lead.id ? { ...x, status: "called" } : x));
        setExpanded(null);
      } else toast.error("Failed to update lead");
    } catch { toast.error("Failed to update lead"); }
  };

  const handleCloseLead = async (lead) => {
    try {
      const r = await apiFetch(`/api/leads/${lead.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: "closed" }),
      });
      if (r.ok) {
        toast.success("Lead closed");
        setLeads(prev => prev.map(x => x.id === lead.id ? { ...x, status: "closed" } : x));
        setExpanded(null);
      } else toast.error("Failed to close lead");
    } catch { toast.error("Failed to close lead"); }
  };

  const FILTER_OPTS = ["all", "call_now", "nurture", "disqualify"];
  const FILTER_COLORS = { all: T.accent, call_now: T.green, nurture: T.purple, disqualify: T.red };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      {/* Stats row */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        <Metric label="Total Leads"   value={loading ? "—" : leads.length}                                          color={T.accent} />
        <Metric label="Hot (8+)"      value={loading ? "—" : leads.filter(l => (l.qualification_score||0)>=8).length} color={T.green} />
        <Metric label="Call Now"      value={loading ? "—" : leads.filter(l => normalizeAction(l.recommended_action)==="call_now").length} color={T.amber} />
        <Metric label="Avg Score"     value={loading || !leads.length ? "—" : (leads.reduce((s,l)=>s+(l.qualification_score||0),0)/leads.length).toFixed(1)} color={T.teal} />
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 6 }}>
          {FILTER_OPTS.map(f => {
            const active = filter === f;
            const col = FILTER_COLORS[f];
            return (
              <button key={f} onClick={() => setFilter(f)} style={{
                background: active ? a(col, 0.15) : "transparent",
                border: `1px solid ${active ? col : T.border}`,
                color: active ? col : T.muted,
                borderRadius: 7, padding: "6px 12px", cursor: "pointer",
                fontSize: 11, fontFamily: "'JetBrains Mono', monospace",
                transition: "all .13s",
              }}>
                {f === "all" ? "ALL" : f.replace(/_/g, " ").toUpperCase()}
              </button>
            );
          })}
        </div>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search name, phone, suburb…"
          style={{
            background: T.card, border: `1px solid ${T.border}`, color: T.textLight,
            borderRadius: 8, padding: "7px 13px", fontSize: 13, width: 220,
          }}
        />
        <Btn onClick={load} style={{ marginLeft: "auto" }}>Refresh</Btn>
      </div>

      {/* Table */}
      <Card>
        {/* Header */}
        <div style={{
          display: "grid", gridTemplateColumns: "1.6fr 130px 110px 80px 150px 90px 110px 40px",
          padding: "10px 16px", background: T.surface, borderBottom: `1px solid ${T.border}`,
        }}>
          {["Name / Phone", "Location", "Score", "Action", "Status", "Source", "Created", ""].map(col => (
            <span key={col} style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
              {col}
            </span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} height={48} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: T.muted, fontSize: 13 }}>
            {leads.length === 0 ? "No leads yet — the qualification agent is standing by." : "No leads match this filter."}
          </div>
        ) : filtered.map(lead => {
          const isExpanded = expanded === lead.id;
          return (
            <div key={lead.id}>
              <div
                style={{
                  display: "grid", gridTemplateColumns: "1.6fr 130px 110px 80px 150px 90px 110px 40px",
                  padding: "12px 16px", borderBottom: `1px solid ${T.border}`,
                  alignItems: "center", transition: "background .1s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = a(T.white, 0.015)}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.textLight }}>{lead.name || "Unknown"}</div>
                  <div style={{ fontSize: 11, color: T.muted }}>{lead.phone || "—"}</div>
                </div>
                <div style={{ fontSize: 12, color: T.text }}>{lead.suburb || lead.state || "—"}</div>
                <div><ScoreBadge score={lead.qualification_score} /></div>
                <div><ActionPill action={lead.recommended_action} /></div>
                <div>
                  <span style={{
                    fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
                    color: { converted: T.green, new: T.accent, qualified: T.amber, rejected: T.red }[lead.status] || T.muted,
                    background: a(({ converted: T.green, new: T.accent, qualified: T.amber, rejected: T.red }[lead.status] || T.muted), 0.1),
                    border: `1px solid ${a(({ converted: T.green, new: T.accent, qualified: T.amber, rejected: T.red }[lead.status] || T.muted), 0.25)}`,
                    borderRadius: 10, padding: "2px 8px",
                  }}>
                    {(lead.status || "new").toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: T.muted }}>{lead.source || "—"}</div>
                <div style={{ fontSize: 11, color: T.muted }}>
                  {lead.created_at ? new Date(lead.created_at).toLocaleDateString("en-AU") : "—"}
                </div>
                <div>
                  <button onClick={() => setExpanded(isExpanded ? null : lead.id)} style={{
                    background: "transparent", border: "none", color: T.muted,
                    cursor: "pointer", fontSize: 14, padding: "4px 8px",
                    transform: isExpanded ? "rotate(90deg)" : "none", transition: "transform .15s",
                  }}>
                    ›
                  </button>
                </div>
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div style={{
                  background: a(T.accent, 0.03), borderBottom: `1px solid ${T.border}`,
                  padding: "16px 20px", display: "flex", gap: 16, flexWrap: "wrap",
                }}>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <div style={{ fontSize: 11, color: T.muted, marginBottom: 6, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
                      LEAD DETAILS
                    </div>
                    {[
                      ["Suburb", lead.suburb], ["State", lead.state],
                      ["Email", lead.email], ["Monthly Bill", lead.monthly_bill ? `$${lead.monthly_bill}` : null],
                    ].filter(([,v]) => v).map(([k,v]) => (
                      <div key={k} style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: T.muted, minWidth: 90 }}>{k}</span>
                        <span style={{ fontSize: 12, color: T.textLight }}>{v}</span>
                      </div>
                    ))}
                  </div>
                  {lead.score_reason && (
                    <div style={{ flex: 2, minWidth: 200 }}>
                      <div style={{ fontSize: 11, color: T.muted, marginBottom: 6, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>
                        SCORE REASONING
                      </div>
                      <div style={{
                        background: T.card, border: `1px solid ${T.border}`,
                        borderRadius: 8, padding: "10px 12px", fontSize: 13, color: T.text, lineHeight: 1.55,
                      }}>
                        {typeof lead.score_reason === "string" ? lead.score_reason : JSON.stringify(lead.score_reason)}
                      </div>
                    </div>
                  )}
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, justifyContent: "flex-end" }}>
                    <Btn variant="solid" onClick={() => handleProposal(lead)}>Generate Proposal</Btn>
                    <Btn onClick={() => handleMarkCalled(lead)}>Mark Called</Btn>
                    <Btn variant="ghost" onClick={() => handleCloseLead(lead)}>Close Lead</Btn>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </Card>
      <div style={{ textAlign: "center", fontSize: 12, color: T.muted, paddingTop: 14 }}>
        {filtered.length} of {leads.length} leads shown · scored by AI qualification agent
      </div>
    </div>
  );
}

/* ─── CALLS PAGE ─────────────────────────────────────────────────────────── */
function CallsPage() {
  const { apiFetch } = useAuth();
  const [calls, setCalls]     = useState([]);
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [expandedData, setExpandedData] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [callsRes, statsRes] = await Promise.allSettled([
        apiFetch("/api/calls?limit=50").then(r => r.json()),
        apiFetch("/api/calls/stats").then(r => r.json()),
      ]);
      if (callsRes.status === "fulfilled") setCalls(callsRes.value.calls || []);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
    } catch { setCalls([]); } finally { setLoading(false); }
  }, [apiFetch]);

  useEffect(() => { load(); }, [load]);

  const deriveOutcome = (call) => {
    const status = call.status || "";
    const score = call.lead_score || 0;
    if (status !== "completed") return "missed";
    if (score >= 8) return "booked";
    if (score >= 5) return "qualified";
    if (score >= 1) return "nurture";
    return "completed";
  };

  const OUTCOME_COLORS = {
    booked: T.green, qualified: T.accent, nurture: T.purple,
    missed: T.red, completed: T.teal,
  };

  const openExpand = async (call) => {
    const id = call.call_id;
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (!expandedData[id]) {
      try {
        const r = await apiFetch(`/api/calls/${id}`);
        const d = await r.json();
        setExpandedData(prev => ({ ...prev, [id]: d.call || call }));
      } catch {
        setExpandedData(prev => ({ ...prev, [id]: call }));
      }
    }
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      {/* Stats */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        <Metric label="Calls Today"    value={loading ? "—" : stats?.today?.calls ?? 0}               color={T.amber} />
        <Metric label="Calls This Week" value={loading ? "—" : stats?.this_week?.total ?? 0}          color={T.accent} />
        <Metric label="Booking Rate"   value={loading ? "—" : `${stats?.this_week?.booking_rate ?? 0}%`} color={T.green} />
        <Metric label="Avg Duration"   value={loading ? "—" : stats?.this_week?.avg_duration || "0:00"} color={T.purple} />
      </div>

      <div style={{ marginBottom: 14, display: "flex", justifyContent: "flex-end" }}>
        <Btn onClick={load}>Refresh</Btn>
      </div>

      {/* Table */}
      <Card>
        <div style={{
          display: "grid", gridTemplateColumns: "1.4fr 140px 110px 100px 100px 90px 50px",
          padding: "10px 18px", background: T.surface, borderBottom: `1px solid ${T.border}`,
        }}>
          {["Caller", "Phone", "Date", "Duration", "Outcome", "Score", ""].map(col => (
            <span key={col} style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} height={50} />)}
          </div>
        ) : calls.length === 0 ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: T.muted, fontSize: 13 }}>
            No calls recorded yet.
          </div>
        ) : calls.map(call => {
          const outcome = deriveOutcome(call);
          const outColor = OUTCOME_COLORS[outcome] || T.muted;
          const isExp = expanded === call.call_id;
          const detail = expandedData[call.call_id];

          return (
            <div key={call.call_id}>
              <div
                style={{
                  display: "grid", gridTemplateColumns: "1.4fr 140px 110px 100px 100px 90px 50px",
                  padding: "12px 18px", borderBottom: `1px solid ${T.border}`,
                  alignItems: "center", transition: "background .1s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = a(T.white, 0.015)}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.textLight }}>
                    {call.caller_name || "Unknown Caller"}
                  </div>
                  <div style={{ fontSize: 11, color: T.muted }}>
                    {(call.call_id || "").slice(0, 12)}…
                  </div>
                </div>
                <div style={{ fontSize: 12, color: T.text }}>{call.from_phone || "—"}</div>
                <div style={{ fontSize: 12, color: T.text }}>
                  {call.started_at ? new Date(call.started_at).toLocaleDateString("en-AU") : "—"}
                </div>
                <div style={{ fontSize: 13, color: T.textLight, fontFamily: "'JetBrains Mono', monospace" }}>
                  {call.duration_fmt || "0:00"}
                </div>
                <div>
                  <span style={{
                    fontSize: 10, color: outColor, fontFamily: "'JetBrains Mono', monospace",
                    background: a(outColor, 0.1), border: `1px solid ${a(outColor, 0.25)}`,
                    borderRadius: 10, padding: "2px 8px",
                  }}>
                    {outcome.toUpperCase()}
                  </span>
                </div>
                <div><ScoreBadge score={call.lead_score} /></div>
                <div>
                  <button onClick={() => openExpand(call)} style={{
                    background: "transparent", border: "none", color: T.muted,
                    cursor: "pointer", fontSize: 14, padding: "4px 8px",
                    transform: isExp ? "rotate(90deg)" : "none", transition: "transform .15s",
                  }}>›</button>
                </div>
              </div>

              {/* Expanded transcript */}
              {isExp && (
                <div style={{
                  background: a(T.accent, 0.03), borderBottom: `1px solid ${T.border}`,
                  padding: "16px 20px",
                }}>
                  <div style={{ fontSize: 11, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1, marginBottom: 12 }}>
                    TRANSCRIPT
                  </div>
                  {!detail ? (
                    <div style={{ color: T.muted, fontSize: 13 }}>Loading…</div>
                  ) : (() => {
                    const transcript = detail.transcript;
                    if (!transcript || (Array.isArray(transcript) && transcript.length === 0)) {
                      return <div style={{ color: T.muted, fontSize: 13 }}>No transcript available.</div>;
                    }
                    if (typeof transcript === "string") {
                      return <div style={{ fontSize: 13, color: T.text, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{transcript}</div>;
                    }
                    return (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {transcript.map((turn, i) => {
                          const isAgent = turn.role === "assistant" || turn.role === "agent";
                          return (
                            <div key={i} style={{ display: "flex", flexDirection: isAgent ? "row" : "row-reverse", gap: 8 }}>
                              <div style={{
                                width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                                background: isAgent ? a(T.amber, 0.15) : a(T.accent, 0.15),
                                border: `1px solid ${isAgent ? a(T.amber, 0.3) : a(T.accent, 0.3)}`,
                                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12,
                              }}>
                                {isAgent ? "A" : "C"}
                              </div>
                              <div style={{
                                background: isAgent ? a(T.amber, 0.06) : a(T.accent, 0.06),
                                border: `1px solid ${isAgent ? a(T.amber, 0.14) : a(T.accent, 0.14)}`,
                                borderRadius: 10, padding: "8px 12px", maxWidth: "75%",
                              }}>
                                <div style={{ fontSize: 10, color: isAgent ? T.amber : T.accent, marginBottom: 3, fontFamily: "'JetBrains Mono', monospace" }}>
                                  {isAgent ? "AI AGENT" : "CALLER"}
                                </div>
                                <div style={{ fontSize: 13, color: T.text, lineHeight: 1.5 }}>
                                  {turn.content || turn.text || ""}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>
          );
        })}
      </Card>
    </div>
  );
}

/* ─── EMAILS PAGE ────────────────────────────────────────────────────────── */
function EmailsPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [emails, setEmails]     = useState([]);
  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(true);
  const [tab, setTab]           = useState("pending");
  const [expanded, setExpanded] = useState(null);
  const [acting, setActing]     = useState(null);

  const loadBoth = useCallback(async () => {
    setLoading(true);
    try {
      const params = tab ? `?status=${tab}&limit=50` : "?limit=50";
      const [emailsRes, statsRes] = await Promise.allSettled([
        apiFetch(`/api/emails${params}`).then(r => r.json()),
        apiFetch("/api/emails/stats").then(r => r.json()),
      ]);
      if (emailsRes.status === "fulfilled") setEmails(emailsRes.value.emails || []);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
    } catch { setEmails([]); } finally { setLoading(false); }
  }, [apiFetch, tab]); // eslint-disable-line

  useEffect(() => { loadBoth(); }, [loadBoth]);

  const handleApprove = async (email) => {
    setActing(email.id);
    try {
      const r = await apiFetch("/gate/email-approve", {
        method: "POST",
        body: JSON.stringify({ email_id: email.id, action: "send" }),
      });
      if (!r.ok) throw new Error((await r.json()).error || "Failed");
      toast.success("Reply sent");
      setExpanded(null);
      loadBoth();
    } catch (e) { toast.error(e.message || "Failed to send"); } finally { setActing(null); }
  };

  const handleDiscard = async (email) => {
    setActing(email.id);
    try {
      await apiFetch("/gate/email-approve", {
        method: "POST",
        body: JSON.stringify({ email_id: email.id, action: "discard" }),
      });
      toast.info("Email discarded");
      setExpanded(null);
      loadBoth();
    } catch { toast.error("Failed to discard"); } finally { setActing(null); }
  };

  const TABS = [
    { value: "pending", label: "PENDING", color: T.amber },
    { value: "",        label: "ALL",     color: T.accent },
    { value: "sent",    label: "SENT",    color: T.green },
    { value: "discarded", label: "DISCARDED", color: T.muted },
  ];

  const CLASS_COLORS = {
    NEW_ENQUIRY: T.accent, QUOTE_REQUEST: T.amber, BOOKING_REQUEST: T.green,
    COMPLAINT: T.red, SPAM: T.muted, OTHER: T.purple,
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      {/* Stats */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        <Metric label="Pending Review" value={loading ? "—" : stats?.pending ?? 0}         color={T.amber} />
        <Metric label="Sent Today"     value={loading ? "—" : stats?.today_total ?? 0}     color={T.green} />
        <Metric label="All-time Sent"  value={loading ? "—" : stats?.sent ?? 0}            color={T.accent} />
        <Metric label="Auto-discarded" value={loading ? "—" : stats?.discarded_today ?? 0} color={T.muted} />
      </div>

      {/* Tabs + refresh */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <div style={{ display: "flex", gap: 5, background: T.card, border: `1px solid ${T.border}`, borderRadius: 9, padding: 4 }}>
          {TABS.map(t => {
            const active = tab === t.value;
            return (
              <button key={t.value} onClick={() => setTab(t.value)} style={{
                background: active ? a(t.color, 0.15) : "transparent",
                border: `1px solid ${active ? t.color : "transparent"}`,
                color: active ? t.color : T.muted,
                borderRadius: 6, padding: "6px 14px", cursor: "pointer",
                fontSize: 11, fontFamily: "'JetBrains Mono', monospace", transition: "all .13s",
              }}>
                {t.label}
                {t.value === "pending" && (stats?.pending || 0) > 0 && (
                  <span style={{
                    marginLeft: 6, background: a(T.amber, 0.2), border: `1px solid ${a(T.amber, 0.4)}`,
                    color: T.amber, borderRadius: 10, padding: "0 5px", fontSize: 10,
                  }}>{stats.pending}</span>
                )}
              </button>
            );
          })}
        </div>
        <Btn onClick={loadBoth} style={{ marginLeft: "auto" }}>Refresh</Btn>
      </div>

      <Card>
        <div style={{
          display: "grid", gridTemplateColumns: "52px 1.2fr 1.8fr 140px 80px 80px 100px",
          padding: "10px 16px", background: T.surface, borderBottom: `1px solid ${T.border}`,
        }}>
          {["Urg", "From", "Subject", "Type", "Status", "Date", ""].map(col => (
            <span key={col} style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} height={52} />)}
          </div>
        ) : emails.length === 0 ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: T.muted, fontSize: 13 }}>
            {tab === "pending" ? "No emails waiting — you're all caught up." : "No emails match this filter."}
          </div>
        ) : emails.map(email => {
          const urgency = email.urgency_score || 0;
          const urgColor = urgency >= 8 ? T.red : urgency >= 5 ? T.amber : T.muted;
          const isPending = email.status === "pending";
          const statusColor = { pending: T.amber, sent: T.green, discarded: T.muted }[email.status] || T.muted;
          const classColor = CLASS_COLORS[email.classification] || T.muted;
          const isExp = expanded === email.id;

          return (
            <div key={email.id}>
              <div
                style={{
                  display: "grid", gridTemplateColumns: "52px 1.2fr 1.8fr 140px 80px 80px 100px",
                  padding: "11px 16px", borderBottom: `1px solid ${T.border}`,
                  alignItems: "center", transition: "background .1s", cursor: "pointer",
                  borderLeft: `3px solid ${isPending ? urgColor : "transparent"}`,
                }}
                onClick={() => setExpanded(isExp ? null : email.id)}
                onMouseEnter={e => e.currentTarget.style.background = a(T.white, 0.015)}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: urgColor }}>
                    {urgency}/10
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: isPending ? T.textLight : T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {email.from_name || email.from_email}
                  </div>
                  {email.from_name && <div style={{ fontSize: 11, color: T.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{email.from_email}</div>}
                </div>
                <div style={{ fontSize: 13, color: isPending ? T.text : T.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 10 }}>
                  {email.subject || "(no subject)"}
                </div>
                <div>
                  <span style={{
                    fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
                    color: classColor, background: a(classColor, 0.1), border: `1px solid ${a(classColor, 0.25)}`,
                    borderRadius: 10, padding: "2px 7px",
                  }}>
                    {(email.classification || "UNKNOWN").replace(/_/g, " ")}
                  </span>
                </div>
                <div>
                  <span style={{
                    fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
                    color: statusColor, background: a(statusColor, 0.1), border: `1px solid ${a(statusColor, 0.25)}`,
                    borderRadius: 10, padding: "2px 8px",
                  }}>
                    {(email.status || "pending").toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: T.muted }}>
                  {email.received_at ? new Date(email.received_at).toLocaleDateString("en-AU") : "—"}
                </div>
                <div style={{ display: "flex", gap: 5 }}>
                  {isPending && (
                    <>
                      <button
                        onClick={e => { e.stopPropagation(); handleApprove(email); }}
                        disabled={acting === email.id}
                        style={{
                          background: a(T.green, 0.12), border: `1px solid ${a(T.green, 0.35)}`,
                          color: T.green, borderRadius: 6, padding: "4px 8px",
                          fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                          opacity: acting === email.id ? 0.5 : 1,
                        }}
                      >
                        {acting === email.id ? "…" : "SEND"}
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleDiscard(email); }}
                        disabled={acting === email.id}
                        style={{
                          background: a(T.red, 0.08), border: `1px solid ${a(T.red, 0.25)}`,
                          color: T.red, borderRadius: 6, padding: "4px 8px",
                          fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                          opacity: acting === email.id ? 0.5 : 1,
                        }}
                      >
                        ✕
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Expanded draft */}
              {isExp && (
                <div style={{
                  background: a(T.amber, 0.03), borderBottom: `1px solid ${T.border}`,
                  padding: "16px 20px",
                }}>
                  <div style={{ fontSize: 11, color: T.muted, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1, marginBottom: 10 }}>
                    AI DRAFT REPLY
                  </div>
                  <div style={{
                    background: T.card, border: `1px solid ${a(T.amber, 0.2)}`,
                    borderRadius: 10, padding: "14px 16px", fontSize: 13, color: T.text, lineHeight: 1.65,
                    whiteSpace: "pre-wrap", maxHeight: 240, overflow: "auto",
                  }}>
                    {email.draft_reply || <span style={{ color: T.muted, fontStyle: "italic" }}>No AI reply generated.</span>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </Card>
    </div>
  );
}

/* ─── AGENTS PAGE ────────────────────────────────────────────────────────── */
const AGENT_DEFS = [
  { id: "voice",         name: "Voice AI",          icon: "◎", color: T.purple, canDisable: true,  role: "AI Phone Receptionist",       schedule: "Event-driven (inbound calls)" },
  { id: "email",         name: "Email Processor",   icon: "✉", color: T.accent, canDisable: true,  role: "Email Triage & Reply Drafter", schedule: "Event-driven (GHL webhook)" },
  { id: "qualification", name: "Lead Qualification",icon: "★", color: T.orange, canDisable: true,  role: "Lead Scoring & Routing",       schedule: "Event-driven (post-call/webhook)" },
  { id: "proposal",      name: "Proposal Generator",icon: "≡", color: T.green,  canDisable: true,  role: "Solar Proposal Generator",     schedule: "Event-driven (post-qualification)" },
  { id: "crm_sync",      name: "CRM Sync",          icon: "↻", color: T.teal,   canDisable: false, role: "GoHighLevel Pipeline Sync",    schedule: "Every 30 minutes" },
];

function AgentsPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [agentState, setAgentState]   = useState({});
  const [statusData, setStatusData]   = useState({});
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [loading, setLoading]         = useState(true);
  const [saving, setSaving]           = useState(null);

  const loadStatus = useCallback(async () => {
    try {
      const [agRes, voiceRes] = await Promise.allSettled([
        apiFetch("/api/agents/status").then(r => r.ok ? r.json() : null),
        apiFetch("/api/voice/status").then(r => r.ok ? r.json() : null),
      ]);
      if (agRes.status === "fulfilled" && agRes.value) {
        const enabled = {}, stats = {};
        Object.entries(agRes.value.agents || {}).forEach(([id, info]) => {
          enabled[id] = info.enabled !== false;
          stats[id] = info;
        });
        setAgentState(enabled);
        setStatusData(stats);
      } else {
        const defaults = {};
        AGENT_DEFS.forEach(ag => { defaults[ag.id] = true; });
        setAgentState(defaults);
      }
      if (voiceRes.status === "fulfilled" && voiceRes.value) {
        setVoiceStatus(voiceRes.value);
      }
    } catch {
      const defaults = {};
      AGENT_DEFS.forEach(ag => { defaults[ag.id] = true; });
      setAgentState(defaults);
    } finally { setLoading(false); }
  }, [apiFetch]);

  useEffect(() => { loadStatus(); }, [loadStatus]);
  useEffect(() => {
    const t = setInterval(loadStatus, 30000);
    return () => clearInterval(t);
  }, [loadStatus]);

  const handleToggle = async (agent, newVal) => {
    if (!agent.canDisable) return;
    setSaving(agent.id);
    setAgentState(prev => ({ ...prev, [agent.id]: newVal }));
    try {
      const r = await apiFetch("/api/agents/status", {
        method: "PATCH",
        body: JSON.stringify({ agent_id: agent.id, enabled: newVal }),
      });
      if (!r.ok) throw new Error("Save failed");
      toast.success(`${agent.name} ${newVal ? "enabled" : "disabled"}`);
    } catch {
      setAgentState(prev => ({ ...prev, [agent.id]: !newVal }));
      toast.error("Failed to save — check API connection");
    } finally { setSaving(null); }
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Mono style={{ fontSize: 12, color: T.amber, letterSpacing: 2 }}>LOADING AGENTS…</Mono>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
        gap: 14,
      }}>
        {AGENT_DEFS.map(agent => {
          const enabled = agentState[agent.id] !== false;
          const status = statusData[agent.id];
          let agentStatus = status?.status || (enabled ? "idle" : "disabled");
          if (agent.id === "voice" && voiceStatus) {
            agentStatus = voiceStatus.agent_ready || voiceStatus.status === "active" ? "active" : "idle";
          }
          const isRunning = agentStatus === "running" || agentStatus === "active";
          const isError = agentStatus === "error";
          const dotColor = !enabled ? T.muted : isError ? T.red : isRunning ? T.green : a(agent.color, 0.7);
          const statusLabel = !enabled ? "DISABLED" : isError ? "ERROR" : isRunning ? "RUNNING" : "IDLE";
          const lastRun = status?.last_run ? new Date(status.last_run).toLocaleString("en-AU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : null;

          return (
            <div key={agent.id} style={{
              background: T.card, border: `1px solid ${enabled ? a(agent.color, 0.3) : T.border}`,
              borderRadius: 12, padding: "18px 20px", opacity: enabled ? 1 : 0.6,
              display: "flex", flexDirection: "column", gap: 14, transition: "all .15s",
            }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{
                  width: 42, height: 42, borderRadius: 10, flexShrink: 0,
                  background: a(agent.color, 0.12), border: `1px solid ${a(agent.color, enabled ? 0.3 : 0.1)}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, position: "relative",
                }}>
                  {agent.icon}
                  {isRunning && (
                    <span style={{
                      position: "absolute", top: -3, right: -3,
                      width: 8, height: 8, borderRadius: "50%",
                      background: T.green, boxShadow: `0 0 6px ${T.green}`,
                    }} />
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: enabled ? T.textLight : T.muted, marginBottom: 2 }}>
                    {agent.name}
                  </div>
                  <div style={{ fontSize: 11, color: enabled ? agent.color : T.muted }}>{agent.role}</div>
                </div>
                <Toggle
                  enabled={enabled}
                  onChange={v => handleToggle(agent, v)}
                  disabled={!agent.canDisable || saving === agent.id}
                />
              </div>
              <div style={{ fontSize: 11, color: T.muted, fontFamily: "'JetBrains Mono', monospace" }}>
                {agent.schedule}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: "50%", background: dotColor,
                    boxShadow: isRunning ? `0 0 5px ${T.green}` : "none",
                    display: "inline-block",
                  }} />
                  <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: T.muted }}>
                    {statusLabel}
                  </span>
                </div>
                {lastRun && enabled && (
                  <div style={{ fontSize: 10, color: T.muted, fontFamily: "'JetBrains Mono', monospace" }}>
                    {lastRun}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        marginTop: 20, padding: "12px 16px",
        background: T.panel, border: `1px solid ${T.border}`,
        borderRadius: 10, fontSize: 12, color: T.muted,
        display: "flex", gap: 20, flexWrap: "wrap",
      }}>
        <span><span style={{ color: T.green }}>●</span> Running</span>
        <span><span style={{ color: T.amber }}>●</span> Idle</span>
        <span><span style={{ color: T.red }}>●</span> Error</span>
        <span><span style={{ color: T.muted }}>●</span> Disabled</span>
        <span style={{ marginLeft: "auto" }}>CRM Sync cannot be disabled</span>
      </div>
    </div>
  );
}

/* ─── REPORTING PAGE ─────────────────────────────────────────────────────── */
function ReportingPage() {
  const { apiFetch } = useAuth();
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/calls/stats")
      .then(r => r.json())
      .then(d => setStats(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const total    = stats?.this_week?.total || 0;
  const completed = stats?.this_week?.completed || 0;
  const bookRate = stats?.this_week?.booking_rate || 0;
  const bookings = Math.round(total * (bookRate / 100));

  const [chartData, setChartData] = useState([]);

  useEffect(() => {
    apiFetch("/api/reports/weekly")
      .then(r => r.json())
      .then(d => setChartData(d.days || []))
      .catch(() => {});
  }, [apiFetch]);

  const maxCalls = chartData.length > 0 ? Math.max(...chartData.map(b => b.calls || 0)) : 1;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      <div style={{ display: "flex", gap: 14, marginBottom: 28, flexWrap: "wrap" }}>
        <Metric label="Total Calls (week)"   value={loading ? "—" : total}            color={T.accent} />
        <Metric label="Leads Created (week)" value={loading ? "—" : completed}        color={T.amber} />
        <Metric label="Bookings (week)"      value={loading ? "—" : bookings}         color={T.green} />
        <Metric label="Booking Rate"         value={loading ? "—" : `${bookRate}%`}   color={T.purple} />
        <Metric label="Avg Duration"         value={loading ? "—" : stats?.this_week?.avg_duration || "0:00"} color={T.teal} />
      </div>

      <Card style={{ marginBottom: 20 }}>
        <CardHeader title="Call Volume — This Week" sub="Daily activity from live data" />
        <div style={{ padding: "24px 20px" }}>
          {chartData.length === 0 ? (
            <div style={{ height: 120, display: "flex", alignItems: "center", justifyContent: "center", color: T.muted, fontSize: 13 }}>
              No activity data yet
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 120 }}>
              {chartData.map(bar => (
                <div key={bar.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                  <div style={{
                    width: "100%", background: a(T.accent, 0.7),
                    height: `${((bar.calls || 0) / maxCalls) * 100}px`,
                    borderRadius: "4px 4px 0 0",
                    display: "flex", alignItems: "flex-start", justifyContent: "center",
                    paddingTop: 4,
                  }}>
                    <span style={{ fontSize: 10, color: T.white, fontFamily: "'JetBrains Mono', monospace" }}>{bar.calls}</span>
                  </div>
                  <span style={{ fontSize: 10, color: T.muted }}>{bar.day}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card>
          <CardHeader title="Lead Quality" sub="Score distribution this week" />
          <div style={{ padding: "20px 18px" }}>
            {loading ? (
              <div style={{ color: T.muted, fontSize: 13, textAlign: "center", paddingTop: 20 }}>Loading…</div>
            ) : total === 0 ? (
              <div style={{ color: T.muted, fontSize: 13, textAlign: "center", paddingTop: 20 }}>No lead data yet</div>
            ) : (() => {
              const hot  = stats?.this_week?.hot_leads  || 0;
              const cold = stats?.this_week?.cold_leads || 0;
              const warm = Math.max(0, total - hot - cold);
              const tiers = [
                { label: "Hot (8–10)", count: hot,  color: T.green },
                { label: "Warm (5–7)", count: warm, color: T.amber },
                { label: "Cold (0–4)", count: cold, color: T.red },
              ];
              return tiers.map(row => {
                const pct = total > 0 ? Math.round((row.count / total) * 100) : 0;
                return (
                  <div key={row.label} style={{ marginBottom: 14 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: T.text }}>{row.label}</span>
                      <span style={{ fontSize: 12, color: row.color, fontFamily: "'JetBrains Mono', monospace" }}>{pct}%</span>
                    </div>
                    <div style={{ background: T.surface, borderRadius: 4, height: 6 }}>
                      <div style={{ width: `${pct}%`, background: row.color, height: "100%", borderRadius: 4 }} />
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        </Card>

        <Card>
          <CardHeader title="System Health" sub="AI agent performance" />
          <div style={{ padding: "20px 18px", display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              { label: "Calls handled",  value: loading ? "—" : total,        color: T.accent },
              { label: "Booking rate",   value: loading ? "—" : `${bookRate}%`, color: T.green },
              { label: "Avg duration",   value: loading ? "—" : stats?.this_week?.avg_duration || "0:00", color: T.purple },
              { label: "Calls today",    value: loading ? "—" : stats?.today?.calls ?? 0, color: T.amber },
            ].map(row => (
              <div key={row.label} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "8px 12px", background: T.surface, borderRadius: 8,
              }}>
                <span style={{ fontSize: 13, color: T.text }}>{row.label}</span>
                <Mono style={{ fontSize: 14, color: row.color }}>{row.value}</Mono>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ─── SETTINGS PAGE ──────────────────────────────────────────────────────── */
function SettingsPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [settings, setSettings] = useState({});
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);

  useEffect(() => {
    apiFetch("/api/settings")
      .then(r => r.json())
      .then(d => setSettings(d.settings || {}))
      .catch(() => toast.error("Failed to load settings"))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const handleChange = async (key, value) => {
    setSaving(true);
    try {
      const r = await apiFetch("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({ [key]: value }),
      });
      if (!r.ok) throw new Error((await r.json()).error);
      setSettings(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(cat => {
          next[cat] = next[cat].map(s => s.key === key ? { ...s, value } : s);
        });
        return next;
      });
      toast.success("Setting saved");
    } catch (e) {
      toast.error(e.message || "Failed to save");
    } finally { setSaving(false); }
  };

  const CATEGORY_LABELS = {
    voice: "Voice AI", agents: "Agent Toggles", crm: "CRM Sync",
    notify: "Notifications", schedule: "Scheduler", email: "Email Processing",
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
      {loading ? (
        <div style={{ color: T.muted, fontSize: 13 }}>Loading settings…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 760 }}>
          {Object.entries(settings).map(([category, rows]) => (
            <Card key={category}>
              <CardHeader
                title={CATEGORY_LABELS[category] || category}
                action={saving ? <Mono style={{ fontSize: 10, color: T.amber }}>saving…</Mono> : null}
              />
              <div>
                {rows.map(s => {
                  const isBool = s.value === "true" || s.value === "false";
                  const isNum = !isNaN(Number(s.value)) && !isBool && s.value !== "";
                  const isTA = s.key === "email.reply_prompt";
                  return (
                    <div key={s.key} style={{
                      display: "flex", alignItems: isTA ? "flex-start" : "center",
                      flexDirection: isTA ? "column" : "row",
                      padding: "12px 16px", borderBottom: `1px solid ${T.border}`, gap: isTA ? 10 : 16,
                    }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Mono style={{ fontSize: 12, color: T.accent }}>{s.key}</Mono>
                        {s.description && (
                          <div style={{ fontSize: 12, color: T.muted, marginTop: 3, lineHeight: 1.5 }}>{s.description}</div>
                        )}
                      </div>
                      <div style={{ flexShrink: 0 }}>
                        {isBool ? (
                          <button
                            onClick={() => handleChange(s.key, s.value === "true" ? "false" : "true")}
                            style={{
                              background: s.value === "true" ? a(T.green, 0.15) : a(T.muted, 0.1),
                              border: `1px solid ${s.value === "true" ? T.green : T.muted}`,
                              color: s.value === "true" ? T.green : T.muted,
                              padding: "5px 14px", borderRadius: 6, cursor: "pointer",
                              fontSize: 12, fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1,
                            }}
                          >
                            {s.value === "true" ? "ON" : "OFF"}
                          </button>
                        ) : isTA ? (
                          <textarea
                            defaultValue={s.value}
                            rows={4}
                            onBlur={e => { if (e.target.value !== s.value) handleChange(s.key, e.target.value); }}
                            style={{
                              background: T.card, border: `1px solid ${T.border}`,
                              color: T.textLight, borderRadius: 8, padding: "8px 12px",
                              fontSize: 13, width: "100%", resize: "vertical",
                              fontFamily: "inherit", lineHeight: 1.55,
                            }}
                          />
                        ) : (
                          <input
                            type={isNum ? "number" : "text"}
                            defaultValue={s.value}
                            onBlur={e => { if (e.target.value !== s.value) handleChange(s.key, e.target.value); }}
                            style={{
                              background: T.card, border: `1px solid ${T.border}`,
                              color: T.textLight, borderRadius: 6, padding: "6px 10px",
                              fontSize: 13, width: isNum ? 90 : 140,
                              fontFamily: isNum ? "'JetBrains Mono', monospace" : "inherit",
                              textAlign: isNum ? "right" : "left",
                            }}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── SIDEBAR nav item ───────────────────────────────────────────────────── */
function NavItem({ item, active, onClick, badgeCount }) {
  const [hovered, setHovered] = useState(false);
  const hasBadge = badgeCount > 0;
  return (
    <button
      onClick={() => onClick(item.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        width: "100%", padding: "8px 12px",
        background: active ? a(T.amber, 0.1) : hovered ? a(T.amber, 0.05) : "transparent",
        border: `1px solid ${active ? a(T.amber, 0.3) : "transparent"}`,
        borderRadius: 8,
        color: active ? T.amber : hovered ? T.textLight : T.muted,
        cursor: "pointer", fontSize: 13, fontWeight: active ? 600 : 400,
        textAlign: "left", transition: "all .13s",
      }}
    >
      <span style={{ fontSize: 14, width: 18, textAlign: "center", flexShrink: 0 }}>{item.icon}</span>
      <span style={{ flex: 1 }}>{item.label}</span>
      {hasBadge && (
        <span style={{
          minWidth: 18, height: 18, background: T.amber,
          borderRadius: 9, fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
          color: "#050810", display: "flex", alignItems: "center",
          justifyContent: "center", padding: "0 5px",
          boxShadow: `0 0 8px ${a(T.amber, 0.5)}`,
        }}>
          {badgeCount > 99 ? "99+" : badgeCount}
        </span>
      )}
      {!hasBadge && active && (
        <span style={{
          width: 5, height: 5, borderRadius: "50%",
          background: T.amber, boxShadow: `0 0 6px ${T.amber}`,
        }} />
      )}
    </button>
  );
}

/* ─── USER CARD with Client Preview popover ─────────────────────────────── */
function UserCard({ user, role, roleColor, onPreview }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative", marginBottom: 8 }}>
      <div
        onClick={() => setOpen(v => !v)}
        style={{
          background: T.card, border: `1px solid ${open ? a(roleColor, 0.5) : T.border}`,
          borderRadius: 10, padding: "10px 12px", cursor: "pointer",
          transition: "border-color .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = a(roleColor, 0.4)}
        onMouseLeave={e => e.currentTarget.style.borderColor = open ? a(roleColor, 0.5) : T.border}
      >
        <div style={{ fontSize: 13, color: T.white, fontWeight: 600, marginBottom: 2 }}>
          {user?.name || "User"}
        </div>
        <div style={{ fontSize: 11, color: T.muted, marginBottom: 6 }}>{user?.email}</div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{
            fontSize: 9, fontFamily: "'JetBrains Mono', monospace",
            background: a(roleColor, 0.12), border: `1px solid ${a(roleColor, 0.3)}`,
            color: roleColor, borderRadius: 20, padding: "1px 8px",
          }}>
            {role.toUpperCase()}
          </span>
          <span style={{ fontSize: 11, color: T.muted }}>{open ? "▴" : "▾"}</span>
        </div>
      </div>

      {open && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: 0, right: 0,
          background: T.panel, border: `1px solid ${T.border}`,
          borderRadius: 10, overflow: "hidden", boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
          zIndex: 100,
        }}>
          <button
            onClick={() => { setOpen(false); onPreview(); }}
            style={{
              width: "100%", display: "flex", alignItems: "center", gap: 10,
              padding: "11px 14px", background: "transparent",
              border: "none", color: T.textLight, fontSize: 13,
              cursor: "pointer", textAlign: "left", transition: "background .12s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = a(T.accent, 0.08)}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
          >
            <span style={{ fontSize: 15 }}>👁</span>
            <div>
              <div style={{ fontWeight: 500 }}>Client Preview</div>
              <div style={{ fontSize: 11, color: T.muted }}>See what your client sees</div>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── MAIN ADMIN DASHBOARD SHELL ─────────────────────────────────────────── */
export default function AdminDashboard({ currentPage, onNavigate }) {
  const { user, logout, apiFetch } = useAuth();
  const [hotLeads, setHotLeads]       = useState(0);
  const [pendingEmails, setPendingEmails] = useState(0);
  const [clock, setClock]             = useState(new Date());

  // Poll badge counts every 60s
  useEffect(() => {
    const fetchBadges = () => {
      Promise.all([
        apiFetch("/api/dashboard/summary").then(r => r.json()),
        apiFetch("/api/emails/stats").then(r => r.json()),
      ]).then(([sum, eStats]) => {
        setHotLeads(sum.hot_leads || 0);
        setPendingEmails(eStats.pending || 0);
      }).catch(() => {});
    };
    fetchBadges();
    const t = setInterval(fetchBadges, 60000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line

  // Clock
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const role = user?.role || "admin";
  const roleColors = { owner: T.amber, admin: T.accent, client: T.green };
  const roleColor = roleColors[role] || T.muted;

  // Client preview — render fullscreen, bypassing admin layout entirely
  if (currentPage === "client-view") {
    return (
      <div style={{ position: "relative" }}>
        <ClientDashboard />
        <button
          onClick={() => onNavigate("overview")}
          style={{
            position: "fixed", top: 14, right: 14, zIndex: 9999,
            background: "#0B1222", border: "1px solid #22D3EE",
            color: "#22D3EE", borderRadius: 20, padding: "7px 18px",
            fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
            cursor: "pointer", boxShadow: "0 2px 16px rgba(34,211,238,0.3)",
            letterSpacing: 1,
          }}
          onMouseEnter={e => e.currentTarget.style.background = "#112030"}
          onMouseLeave={e => e.currentTarget.style.background = "#0B1222"}
        >
          ← EXIT PREVIEW
        </button>
      </div>
    );
  }

  const meta = PAGE_META[currentPage] || { title: "Dashboard", sub: "" };

  const badgeCounts = { hotLeads, pendingEmails };

  const renderPage = () => {
    switch (currentPage) {
      case "overview":       return <OverviewPage />;
      case "leads":          return <LeadsPage />;
      case "calls":          return <CallsPage />;
      case "emails":         return <EmailsPage />;
      case "agents":         return <AgentsPage />;
      case "reporting":      return <ReportingPage />;
      case "settings":       return <SettingsPage />;
      case "knowledge-base": return <KnowledgeBasePage />;
      case "onboarding":     return <OnboardingPage onNavigate={onNavigate} />;
      case "docs":           return <DocsPage />;
      case "companies":      return <CompanyPage />;
      case "users":          return <UsersPage />;
      case "apikeys":        return <ApiKeysPage />;
      case "client-view":    return <ClientDashboard />;
      default:               return <OverviewPage />;
    }
  };

  const initials = (user?.name || "U").split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);

  const awst = clock.toLocaleTimeString("en-AU", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    timeZone: "Australia/Perth", hour12: false,
  });

  return (
    <>
      <style>{STYLES}</style>
      <div style={{ display: "flex", height: "100vh", background: T.bg, color: T.text, overflow: "hidden" }}>

        {/* ─── Sidebar ─── */}
        <aside style={{
          width: 220, flexShrink: 0,
          background: T.panel, borderRight: `1px solid ${T.border}`,
          display: "flex", flexDirection: "column", overflow: "hidden",
        }}>
          {/* Logo */}
          <div style={{
            padding: "18px 18px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <span style={{
              fontSize: 22, lineHeight: 1,
              background: `linear-gradient(135deg, ${T.amber}, ${T.orange})`,
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>☀</span>
            <div>
              <div style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: T.amber, letterSpacing: 2 }}>
                SOLAR SALES
              </div>
              <div style={{ fontSize: 9, color: T.muted, letterSpacing: 1 }}>COMMAND CENTER</div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ flex: 1, padding: "8px 8px", overflowY: "auto" }}>
            {NAV.filter(section => !section.minRole || canSee(role, section.minRole)).map(section => (
              <div key={section.section}>
                <SectionLabel label={section.section} />
                {section.items.filter(item => !item.minRole || canSee(role, item.minRole)).map(item => {
                  const badgeKey = item.badge;
                  const count = badgeKey ? (badgeCounts[badgeKey] || 0) : 0;
                  return (
                    <NavItem
                      key={item.id}
                      item={item}
                      active={currentPage === item.id}
                      onClick={onNavigate}
                      badgeCount={count}
                    />
                  );
                })}
              </div>
            ))}
          </nav>

          {/* CRM status footer */}
          <div style={{
            padding: "10px 14px", borderTop: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <StatusDot active={true} color={T.green} />
            <span style={{ fontSize: 11, color: T.muted, fontFamily: "'JetBrains Mono', monospace" }}>
              CRM CONNECTED
            </span>
          </div>

          {/* User info */}
          <div style={{ padding: "10px 14px", borderTop: `1px solid ${T.border}` }}>
            <UserCard
              user={user} role={role} roleColor={roleColor}
              onPreview={() => onNavigate("client-view")}
            />
            <button
              onClick={logout}
              style={{
                width: "100%", background: "transparent",
                border: `1px solid ${T.border}`,
                color: T.muted, padding: "7px 12px",
                borderRadius: 8, cursor: "pointer", fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace",
                transition: "all .15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = T.red; e.currentTarget.style.color = T.red; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.muted; }}
            >
              SIGN OUT
            </button>
          </div>
        </aside>

        {/* ─── Main content ─── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Topbar */}
          <div style={{
            flexShrink: 0, height: 60, background: T.panel, borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", padding: "0 24px", gap: 16,
          }}>
            {/* Page title */}
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.textLight, lineHeight: 1.2 }}>
                {meta.title}
              </div>
              {meta.sub && <div style={{ fontSize: 11, color: T.muted }}>{meta.sub}</div>}
            </div>

            {/* Clock AWST */}
            <Mono style={{ fontSize: 12, color: T.muted }}>{awst} AWST</Mono>

            {/* Hot leads alert */}
            {hotLeads > 0 && (
              <button
                onClick={() => onNavigate("leads")}
                style={{
                  background: a(T.amber, 0.12), border: `1px solid ${a(T.amber, 0.4)}`,
                  color: T.amber, borderRadius: 20, padding: "4px 12px",
                  fontSize: 11, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                  boxShadow: `0 0 10px ${a(T.amber, 0.25)}`, animation: "pulse 2s infinite",
                }}
              >
                ★ {hotLeads} HOT LEADS
              </button>
            )}

            {/* Pending emails alert */}
            {pendingEmails > 0 && (
              <button
                onClick={() => onNavigate("emails")}
                style={{
                  background: a(T.purple, 0.12), border: `1px solid ${a(T.purple, 0.4)}`,
                  color: T.purple, borderRadius: 20, padding: "4px 12px",
                  fontSize: 11, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                ✉ {pendingEmails} PENDING
              </button>
            )}

            {/* Settings cog */}
            <button
              onClick={() => onNavigate("settings")}
              title="Settings"
              style={{
                background: "transparent", border: `1px solid ${T.border}`,
                color: currentPage === "settings" ? T.amber : T.muted,
                borderRadius: 8, width: 32, height: 32, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
                transition: "all .13s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = T.borderHover; e.currentTarget.style.color = T.textLight; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = currentPage === "settings" ? T.amber : T.muted; }}
            >
              ⚙
            </button>

            {/* User avatar */}
            <div style={{
              width: 32, height: 32, borderRadius: "50%",
              background: a(roleColor, 0.15), border: `1px solid ${a(roleColor, 0.4)}`,
              color: roleColor, display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
              cursor: "default",
            }} title={user?.name}>
              {initials}
            </div>
          </div>

          {/* Page content */}
          <div key={currentPage} style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {renderPage()}
          </div>
        </div>
      </div>
    </>
  );
}
