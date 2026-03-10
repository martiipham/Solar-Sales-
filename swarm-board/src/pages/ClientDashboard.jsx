/**
 * ClientDashboard — multi-tab client view for Solar Admin AI.
 *
 * Tabs: Overview · Leads · Calls · Emails · Agents
 *
 * APIs:
 *   GET  /api/dashboard/summary    — today's aggregated KPIs
 *   GET  /api/voice/status         — AI receptionist live/offline
 *   GET  /api/calls/stats          — call stats (today / week)
 *   GET  /api/calls                — call log (paginated)
 *   GET  /api/calls/:id            — call detail + transcript
 *   GET  /api/leads                — lead list
 *   GET  /api/crm/pipeline         — GHL pipeline stages
 *   GET  /api/emails               — email queue
 *   GET  /api/emails/stats         — email counts
 *   GET  /api/emails/:id           — email detail + body
 *   POST /gate/email-approve       — approve / discard / edit email
 *   POST /api/emails/bulk-discard  — bulk discard selected
 *   GET  /api/agents/status        — agent status
 *   PATCH /api/agents/status       — toggle agent enabled
 *   GET  /api/companies/:id        — company branding
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../AuthContext";

/* ─── Theme ─────────────────────────────────────────────────────────────────── */
const C = {
  bg: "#03060F", panel: "#070C18", card: "#0A1020", cardHov: "#0E1628",
  border: "#0F1C30", borderB: "#1A2E4A",
  amber: "#F59E0B", amberL: "#FCD34D", cyan: "#22D3EE", green: "#4ADE80",
  red: "#F87171", orange: "#FB923C", purple: "#C084FC", blue: "#60A5FA",
  teal: "#2DD4BF", text: "#CBD5E1", muted: "#3D5070", dim: "#111A2E",
  white: "#F0F4FA",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
  @keyframes pulse   { 0%,100%{opacity:1} 50%{opacity:.35} }
  @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  @keyframes fadeUp  { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:#03060F; font-family:'DM Sans',sans-serif; }
  ::-webkit-scrollbar { width:3px; height:3px; }
  ::-webkit-scrollbar-track { background:#070C18; }
  ::-webkit-scrollbar-thumb { background:#1A2E4A; border-radius:2px; }
  .slide { animation: slideIn 0.22s ease both; }
  .row-h:hover { background: rgba(255,255,255,0.022) !important; cursor:pointer; }
  input,select,textarea { outline:none; }
  input:focus,select:focus,textarea:focus { border-color:#22D3EE !important; }
`;

/* ─── Shared helpers ─────────────────────────────────────────────────────────── */
function Skeleton({ w = "100%", h: ht = 16, r = 6 }) {
  return (
    <div style={{
      width: w, height: ht, borderRadius: r,
      background: `linear-gradient(90deg,${C.card} 25%,${C.border} 50%,${C.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

function ScoreBadge({ score }) {
  const v = score != null ? Number(score) : null;
  const col = v == null ? C.muted : v >= 7 ? C.green : v >= 4 ? C.amber : C.red;
  return (
    <span style={{
      display: "inline-block",
      background: h(col, 0.15), border: `1px solid ${h(col, 0.35)}`,
      color: col, borderRadius: 6, padding: "2px 8px",
      fontSize: 11, fontFamily: "'Space Mono',monospace",
    }}>{v != null ? v.toFixed(1) : "—"}</span>
  );
}

function Pill({ label, color = C.muted }) {
  return (
    <span style={{
      fontSize: 9, fontFamily: "'Space Mono',monospace",
      color, background: h(color, 0.1), border: `1px solid ${h(color, 0.25)}`,
      borderRadius: 10, padding: "2px 8px", whiteSpace: "nowrap",
    }}>{label}</span>
  );
}

function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div style={{
      position: "fixed", bottom: 28, right: 28, zIndex: 3000,
      background: C.panel, border: `1px solid ${h(toast.color, 0.45)}`,
      color: toast.color, borderRadius: 10, padding: "11px 20px",
      fontSize: 12, fontFamily: "'Space Mono',monospace",
      boxShadow: `0 4px 24px ${h(toast.color, 0.22)}`,
      animation: "fadeUp .2s ease",
    }}>{toast.msg}</div>
  );
}

function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/* ─── Tab nav ────────────────────────────────────────────────────────────────── */
const TABS = [
  { id: "overview", label: "Overview",   icon: "◈" },
  { id: "leads",    label: "Leads",      icon: "◎" },
  { id: "calls",    label: "Calls",      icon: "◐" },
  { id: "emails",   label: "Emails",     icon: "◻" },
  { id: "agents",   label: "Agents",     icon: "◆" },
];

function TabNav({ tab, setTab, pendingEmails }) {
  return (
    <div style={{
      display: "flex", gap: 2, padding: "4px",
      background: C.panel, borderBottom: `1px solid ${C.border}`,
      flexShrink: 0,
    }}>
      {TABS.map(t => {
        const active = tab === t.id;
        return (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            display: "flex", alignItems: "center", gap: 6,
            background: active ? h(C.amber, 0.1) : "transparent",
            border: `1px solid ${active ? h(C.amber, 0.35) : "transparent"}`,
            color: active ? C.amber : C.muted,
            borderRadius: 7, padding: "8px 16px",
            cursor: "pointer", fontSize: 12, fontFamily: "'DM Sans',sans-serif",
            fontWeight: active ? 600 : 400,
            transition: "all .15s",
          }}>
            <span style={{ fontFamily: "'Space Mono',monospace", fontSize: 11 }}>{t.icon}</span>
            {t.label}
            {t.id === "emails" && pendingEmails > 0 && (
              <span style={{
                background: C.amber, color: "#000", borderRadius: "50%",
                width: 16, height: 16, fontSize: 9, fontFamily: "'Space Mono',monospace",
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontWeight: 700,
              }}>{pendingEmails > 9 ? "9+" : pendingEmails}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   OVERVIEW TAB
═══════════════════════════════════════════════════════════════════════════════ */
function StatusDot({ status }) {
  const color = status === "live" ? C.green : status === "needs_setup" ? C.amber : C.red;
  const label = status === "live" ? "LIVE" : status === "needs_setup" ? "SETUP NEEDED" : "OFFLINE";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{
        width: 8, height: 8, borderRadius: "50%", background: color,
        boxShadow: status === "live" ? `0 0 8px ${color}` : "none",
        animation: status === "live" ? "pulse 2s infinite" : "none",
      }} />
      <span style={{ fontSize: 10, fontFamily: "'Space Mono',monospace", color, letterSpacing: 1 }}>{label}</span>
    </div>
  );
}

function KpiCard({ icon, label, value, sub, color = C.cyan }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: "18px 20px", flex: "1 1 140px",
    }}>
      <div style={{ fontSize: 18, marginBottom: 6 }}>{icon}</div>
      <div style={{ fontSize: 26, color, fontFamily: "'Space Mono',monospace", lineHeight: 1, marginBottom: 5 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 3 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: C.muted }}>{sub}</div>}
    </div>
  );
}

function OverviewTab({ apiFetch, onTabChange, accentColor }) {
  const [summary,     setSummary]     = useState(null);
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [callStats,   setCallStats]   = useState(null);
  const [recentCalls, setRecentCalls] = useState([]);
  const [leads,       setLeads]       = useState([]);
  const [pipeline,    setPipeline]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [viewCall,    setViewCall]    = useState(null);

  const load = useCallback(async () => {
    const [summaryR, voiceR, callStatsR, callsR, leadsR, pipeR] = await Promise.allSettled([
      apiFetch("/api/dashboard/summary").then(r => r.json()),
      apiFetch("/api/voice/status").then(r => r.json()),
      apiFetch("/api/calls/stats").then(r => r.json()),
      apiFetch("/api/calls?limit=5").then(r => r.json()),
      apiFetch("/api/leads?limit=8").then(r => r.json()),
      apiFetch("/api/crm/pipeline").then(r => r.json()),
    ]);
    if (summaryR.status   === "fulfilled") setSummary(summaryR.value || {});
    if (voiceR.status     === "fulfilled") setVoiceStatus(voiceR.value);
    if (callStatsR.status === "fulfilled") setCallStats(callStatsR.value);
    if (callsR.status     === "fulfilled") setRecentCalls(callsR.value.calls || []);
    if (leadsR.status     === "fulfilled") setLeads(leadsR.value.leads || []);
    if (pipeR.status      === "fulfilled") setPipeline(pipeR.value.stages || []);
    setLoading(false);
  }, []); // eslint-disable-line

  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const voiceSt    = voiceStatus?.status || "offline";
  const stColor    = voiceSt === "live" ? C.green : voiceSt === "needs_setup" ? C.amber : C.red;
  const hotLeads   = summary?.hot_leads ?? leads.filter(l => (l.qualification_score || 0) >= 7).length;

  return (
    <div className="slide" style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>

      {/* AI Receptionist hero */}
      <div style={{
        background: C.panel, border: `1px solid ${h(stColor, 0.4)}`,
        borderRadius: 14, padding: "20px 24px",
        display: "flex", gap: 20, flexWrap: "wrap", alignItems: "center",
        boxShadow: voiceSt === "live" ? `0 0 24px ${h(stColor, 0.07)}` : "none",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flex: "0 0 auto" }}>
          <div style={{
            width: 48, height: 48, borderRadius: 13,
            background: h(stColor, 0.12), border: `1px solid ${h(stColor, 0.3)}`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
          }}>🤖</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.white, marginBottom: 4 }}>AI Receptionist</div>
            {loading ? <Skeleton w={100} h={12} /> : <StatusDot status={voiceSt} />}
          </div>
        </div>
        <div style={{ width: 1, height: 36, background: C.border, flex: "0 0 auto" }} />
        <div style={{ display: "flex", gap: 28, flex: 1, flexWrap: "wrap" }}>
          {[
            { val: loading ? "—" : callStats?.today?.calls ?? 0,                            label: "Calls today",    color: stColor   },
            { val: loading ? "—" : callStats?.this_week?.calls ?? 0,                        label: "This week",     color: C.cyan    },
            { val: loading ? "—" : (callStats?.this_week?.booking_rate ?? 0) + "%",          label: "Booking rate",  color: C.purple  },
            { val: loading ? "—" : (callStats?.this_week?.avg_duration ?? "0:00"),           label: "Avg duration",  color: C.amber   },
          ].map(({ val, label, color }) => (
            <div key={label}>
              <div style={{ fontSize: 22, color, fontFamily: "'Space Mono',monospace" }}>{val}</div>
              <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>
        {!loading && voiceSt === "live" && (
          <div style={{
            fontSize: 10, color: C.green, background: h(C.green, 0.07),
            border: `1px solid ${h(C.green, 0.2)}`, borderRadius: 20, padding: "4px 12px",
          }}>Answering calls 24/7</div>
        )}
      </div>

      {/* KPIs */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {loading ? [1,2,3,4,5,6].map(i => (
          <div key={i} style={{ flex: "1 1 130px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "18px 20px" }}>
            <Skeleton w={50} h={26} r={4} />
            <div style={{ marginTop: 8 }}><Skeleton w={80} h={11} /></div>
          </div>
        )) : <>
          <KpiCard icon="📞" label="Calls Today"    value={summary?.calls_today ?? callStats?.today?.calls ?? 0}   sub={`${summary?.calls_this_week ?? callStats?.this_week?.calls ?? 0} this week`}       color={accentColor} />
          <KpiCard icon="✉️" label="Emails Today"   value={summary?.emails_today ?? 0}    sub={summary?.pending_approvals ? `${summary.pending_approvals} need review` : "all processed"}  color={C.cyan}   />
          <KpiCard icon="🆕" label="New Leads"       value={summary?.leads_today ?? 0}     sub="from calls & webhooks"    color={C.orange}  />
          <KpiCard icon="🔥" label="Hot Leads"       value={hotLeads}                       sub="score 7+"                 color={C.green}   />
          <KpiCard icon="📄" label="Proposals"       value={summary?.proposals_sent ?? 0}   sub="generated today"          color={C.purple}  />
          <KpiCard icon="🔄" label="CRM Sync"        value={summary?.crm_last_sync ? timeAgo(summary.crm_last_sync) : "—"} sub={`${summary?.contacts_total ?? 0} contacts`} color={C.teal} />
        </>}
      </div>

      {/* Pipeline */}
      {pipeline.length > 0 && (
        <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, padding: "16px 20px" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.white, marginBottom: 14, letterSpacing: .5 }}>Lead Pipeline</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {pipeline.map((stage, i) => {
              const cnt = stage.opportunityCount || stage.count || 0;
              const max = Math.max(...pipeline.map(s => s.opportunityCount || s.count || 0), 1);
              const pct = Math.round((cnt / max) * 100);
              const col = [accentColor, C.cyan, C.green, C.purple, C.orange][i % 5];
              return (
                <div key={i} style={{ flex: "1 1 100px", minWidth: 80 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: col, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "75%" }}>
                      {stage.name || stage.stageName || `Stage ${i + 1}`}
                    </span>
                    <span style={{ fontSize: 11, color: col, fontFamily: "'Space Mono',monospace" }}>{cnt}</span>
                  </div>
                  <div style={{ height: 6, background: C.border, borderRadius: 4 }}>
                    <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 4, opacity: 0.8 }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Two columns: recent calls + recent leads */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* Recent Calls */}
        <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{
            padding: "12px 16px", borderBottom: `1px solid ${C.border}`,
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>Recent Calls</div>
            <button onClick={() => onTabChange("calls")} style={{ background: "transparent", border: "none", color: C.cyan, fontSize: 10, cursor: "pointer", fontFamily: "'Space Mono',monospace" }}>All →</button>
          </div>
          {loading ? (
            <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
              {[1,2,3].map(i => <Skeleton key={i} h={38} />)}
            </div>
          ) : recentCalls.length === 0 ? (
            <div style={{ padding: "28px 16px", textAlign: "center", color: C.muted, fontSize: 12 }}>
              No calls yet — your AI receptionist will log every inbound call here.
            </div>
          ) : recentCalls.map(call => {
            return (
              <div key={call.call_id} className="row-h" onClick={() => setViewCall(call)} style={{
                padding: "10px 16px", borderBottom: `1px solid ${C.border}`,
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>{call.from_phone || "Unknown"}</div>
                  <div style={{ fontSize: 10, color: C.muted }}>{call.started_at ? new Date(call.started_at).toLocaleString("en-AU", { dateStyle: "short", timeStyle: "short" }) : "—"}</div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontSize: 11, fontFamily: "'Space Mono',monospace", color: C.text }}>{call.duration_fmt || "0:00"}</span>
                  {call.lead_score ? <ScoreBadge score={call.lead_score} /> : null}
                </div>
              </div>
            );
          })}
        </div>

        {/* Recent Leads */}
        <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{
            padding: "12px 16px", borderBottom: `1px solid ${C.border}`,
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>Recent Leads</div>
            <button onClick={() => onTabChange("leads")} style={{ background: "transparent", border: "none", color: C.cyan, fontSize: 10, cursor: "pointer", fontFamily: "'Space Mono',monospace" }}>All →</button>
          </div>
          {loading ? (
            <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
              {[1,2,3].map(i => <Skeleton key={i} h={38} />)}
            </div>
          ) : leads.length === 0 ? (
            <div style={{ padding: "28px 16px", textAlign: "center", color: C.muted, fontSize: 12 }}>
              No leads yet. Your AI receptionist will populate this automatically.
            </div>
          ) : leads.map(lead => (
            <div key={lead.id} style={{
              padding: "10px 16px", borderBottom: `1px solid ${C.border}`,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                <div style={{ fontSize: 10, color: C.muted }}>
                  {new Date(lead.created_at).toLocaleDateString("en-AU")}
                  {lead.suburb ? ` · ${lead.suburb}` : ""}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <ScoreBadge score={lead.qualification_score} />
                <Pill label={(lead.status || "new").toUpperCase()} color={lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Transcript modal */}
      {viewCall && (
        <div onClick={() => setViewCall(null)} style={{
          position: "fixed", inset: 0, background: "rgba(3,6,15,.88)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: C.panel, border: `1px solid ${C.borderB}`,
            borderRadius: 16, padding: 26, width: "100%", maxWidth: 560, maxHeight: "80vh", overflow: "auto",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.white }}>Call Transcript</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 3 }}>
                  {viewCall.from_phone} · {viewCall.started_at ? new Date(viewCall.started_at).toLocaleString("en-AU") : "—"} · {viewCall.duration_fmt || "0:00"}
                </div>
              </div>
              <button onClick={() => setViewCall(null)} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 7, padding: "4px 10px", cursor: "pointer", fontSize: 11 }}>✕</button>
            </div>
            {viewCall.transcript?.length > 0 ? viewCall.transcript.map((turn, i) => {
              const isAI = turn.role === "assistant" || turn.role === "agent";
              return (
                <div key={i} style={{ display: "flex", flexDirection: isAI ? "row" : "row-reverse", gap: 8, marginBottom: 10 }}>
                  <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: isAI ? h(C.amber, 0.15) : h(C.cyan, 0.15), border: `1px solid ${isAI ? h(C.amber, 0.3) : h(C.cyan, 0.3)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>
                    {isAI ? "🤖" : "👤"}
                  </div>
                  <div style={{ background: isAI ? h(C.amber, 0.06) : h(C.cyan, 0.06), border: `1px solid ${isAI ? h(C.amber, 0.14) : h(C.cyan, 0.14)}`, borderRadius: 9, padding: "8px 12px", maxWidth: "78%" }}>
                    <div style={{ fontSize: 9, color: isAI ? C.amber : C.cyan, marginBottom: 3, fontFamily: "'Space Mono',monospace" }}>{isAI ? "AI RECEPTIONIST" : "CALLER"}</div>
                    <div style={{ fontSize: 12, color: C.text, lineHeight: 1.55 }}>{turn.content || turn.text || ""}</div>
                  </div>
                </div>
              );
            }) : (
              <div style={{ textAlign: "center", color: C.muted, fontSize: 12, padding: "20px 0" }}>No transcript available.</div>
            )}
          </div>
        </div>
      )}

      <div style={{ textAlign: "center", fontSize: 10, color: C.muted, fontFamily: "'Space Mono',monospace", paddingBottom: 4 }}>
        AUTO-REFRESH EVERY 30S · SOLAR ADMIN AI
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   LEADS TAB
═══════════════════════════════════════════════════════════════════════════════ */
const LEAD_SCORE_RANGES = [
  { label: "All",     min: 0, max: 10 },
  { label: "Hot 7+",  min: 7, max: 10 },
  { label: "Warm 4–6",min: 4, max: 6.9 },
  { label: "Cold <4", min: 0, max: 3.9 },
];
const LEAD_STATUS_OPTS  = ["all", "new", "qualified", "converted", "rejected"];
const LEAD_ACTION_OPTS  = ["all", "call_now", "schedule_call", "send_proposal", "nurture", "disqualify"];

function LeadModal({ lead, onClose, onAction }) {
  if (!lead) return null;
  const fields = lead.extracted_data || {};
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(3,6,15,.88)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: C.panel, border: `1px solid ${C.borderB}`, borderRadius: 16, padding: 26, width: "100%", maxWidth: 540, maxHeight: "84vh", overflow: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: C.white }}>{lead.name || "Unknown Lead"}</div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 3 }}>{lead.phone || "—"} · {lead.suburb || "—"}</div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 7, padding: "4px 10px", cursor: "pointer", fontSize: 11 }}>✕</button>
        </div>

        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: "11px 14px", marginBottom: 18, display: "flex", gap: 20, flexWrap: "wrap" }}>
          {[
            { label: "SCORE",  node: <ScoreBadge score={lead.qualification_score} /> },
            { label: "STATUS", node: <Pill label={(lead.status || "new").toUpperCase()} color={{ converted: C.green, new: C.cyan, qualified: C.amber, rejected: C.red }[lead.status] || C.muted} /> },
            { label: "ACTION", node: <Pill label={(lead.recommended_action || "—").toUpperCase().replace(/_/g, " ")} color={{ call_now: C.green, schedule_call: C.cyan, send_proposal: C.amber, nurture: C.purple, disqualify: C.red }[(lead.recommended_action || "").toLowerCase().replace(/\s+/g, "_")] || C.muted} /> },
            { label: "SOURCE", node: <span style={{ fontSize: 12, color: C.text }}>{lead.source || "—"}</span> },
          ].map(({ label, node }) => (
            <div key={label}>
              <div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>{label}</div>
              {node}
            </div>
          ))}
        </div>

        {Object.keys(fields).length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1, marginBottom: 8 }}>EXTRACTED DATA</div>
            {Object.entries(fields).map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", background: C.card, border: `1px solid ${C.border}`, borderRadius: 7, padding: "7px 11px", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: C.muted }}>{k.replace(/_/g, " ")}</span>
                <span style={{ fontSize: 11, color: C.text }}>{String(v)}</span>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => onAction("proposal", lead)} style={{ flex: 1, background: h(C.amber, 0.1), border: `1px solid ${h(C.amber, 0.3)}`, color: C.amber, borderRadius: 8, padding: "10px 14px", cursor: "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace" }}>
            ✦ GENERATE PROPOSAL
          </button>
          <button onClick={() => onAction("called", lead)} style={{ flex: 1, background: h(C.green, 0.08), border: `1px solid ${h(C.green, 0.25)}`, color: C.green, borderRadius: 8, padding: "10px 14px", cursor: "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace" }}>
            ✓ MARK CALLED
          </button>
        </div>
      </div>
    </div>
  );
}

function LeadsTab({ apiFetch }) {
  const [leads,       setLeads]       = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [statusFil,   setStatusFil]   = useState("all");
  const [actionFil,   setActionFil]   = useState("all");
  const [scoreRange,  setScoreRange]  = useState(0);
  const [search,      setSearch]      = useState("");
  const [limit,       setLimit]       = useState(50);
  const [selected,    setSelected]    = useState(null);
  const [toast,       setToast]       = useState(null);

  const showToast = (msg, color = C.green) => {
    setToast({ msg, color });
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ limit });
      if (statusFil !== "all") p.set("status", statusFil);
      const r = await apiFetch(`/api/leads?${p}`);
      const d = await r.json();
      setLeads(d.leads || []);
    } catch { setLeads([]); } finally { setLoading(false); }
  }, [apiFetch, statusFil, limit]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const handleAction = async (type, lead) => {
    setSelected(null);
    if (type === "proposal") {
      try {
        await apiFetch(`/api/leads/${lead.id}/proposal`, { method: "POST" });
        showToast("Proposal generation triggered");
      } catch { showToast("Failed to trigger proposal", C.red); }
    } else if (type === "called") {
      try {
        await apiFetch(`/api/leads/${lead.id}/mark-called`, { method: "POST" });
        showToast("Lead marked as called");
        load();
      } catch { showToast("Failed to update lead", C.red); }
    }
  };

  const range    = LEAD_SCORE_RANGES[scoreRange];
  const filtered = leads.filter(l => {
    const s = l.qualification_score || 0;
    if (s < range.min || s > range.max) return false;
    if (actionFil !== "all" && (l.recommended_action || "").toLowerCase().replace(/\s+/g,"_") !== actionFil) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (l.name||"").toLowerCase().includes(q) || (l.phone||"").includes(q) || (l.suburb||"").toLowerCase().includes(q);
  });

  const hot = filtered.filter(l => (l.qualification_score || 0) >= 7).length;
  const avg = filtered.length ? (filtered.reduce((s, l) => s + (l.qualification_score || 0), 0) / filtered.length).toFixed(1) : "—";

  return (
    <div className="slide" style={{ padding: "22px 28px" }}>
      <Toast toast={toast} />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 2, marginBottom: 5 }}>LEAD PIPELINE</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: C.white, marginBottom: 2 }}>Leads</div>
          <div style={{ fontSize: 12, color: C.muted }}>{filtered.length} leads · avg {avg} · {hot} hot</div>
        </div>
        <button onClick={load} style={{ background: h(C.cyan, 0.08), border: `1px solid ${h(C.cyan, 0.25)}`, color: C.cyan, padding: "8px 16px", borderRadius: 7, cursor: "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace" }}>↻ REFRESH</button>
      </div>

      {/* KPI row */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { label: "Total",     value: filtered.length, color: C.cyan   },
          { label: "Hot (7+)",  value: hot,             color: C.green  },
          { label: "Avg Score", value: avg,             color: C.amber  },
          { label: "Converted", value: filtered.filter(l => l.status === "converted").length, color: C.purple },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 18px", flex: "1 1 110px" }}>
            <div style={{ fontSize: 24, color, fontFamily: "'Space Mono',monospace", lineHeight: 1, marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 11, color: C.muted }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, phone, suburb…"
          style={{ background: C.card, border: `1px solid ${C.border}`, color: C.text, borderRadius: 7, padding: "7px 12px", fontSize: 12, width: 210 }} />
        <div style={{ display: "flex", gap: 4 }}>
          {LEAD_SCORE_RANGES.map((r, i) => {
            const a = scoreRange === i;
            const col = i === 1 ? C.green : i === 2 ? C.amber : i === 3 ? C.red : C.muted;
            return <button key={i} onClick={() => setScoreRange(i)} style={{ background: a ? h(col, 0.12) : "transparent", border: `1px solid ${a ? col : C.border}`, color: a ? col : C.muted, borderRadius: 6, padding: "6px 10px", cursor: "pointer", fontSize: 10, fontFamily: "'Space Mono',monospace" }}>{r.label}</button>;
          })}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {LEAD_STATUS_OPTS.map(s => {
            const a = statusFil === s;
            const col = { converted: C.green, new: C.cyan, qualified: C.amber, rejected: C.red }[s] || C.muted;
            return <button key={s} onClick={() => setStatusFil(s)} style={{ background: a ? h(col, 0.12) : "transparent", border: `1px solid ${a ? col : C.border}`, color: a ? col : C.muted, borderRadius: 6, padding: "6px 9px", cursor: "pointer", fontSize: 9, fontFamily: "'Space Mono',monospace" }}>{s.toUpperCase()}</button>;
          })}
        </div>
        <select value={actionFil} onChange={e => setActionFil(e.target.value)} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "6px 9px", fontSize: 11, marginLeft: "auto" }}>
          {LEAD_ACTION_OPTS.map(a => <option key={a} value={a}>{a === "all" ? "All Actions" : a.replace(/_/g, " ")}</option>)}
        </select>
        <select value={limit} onChange={e => setLimit(Number(e.target.value))} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "6px 9px", fontSize: 11 }}>
          {[20, 50, 100, 200].map(n => <option key={n} value={n}>Last {n}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 110px 110px 72px 150px 92px 110px 100px", padding: "9px 14px", background: C.card, borderBottom: `1px solid ${C.border}` }}>
          {["Name", "Phone", "Suburb", "Score", "Action", "Status", "Source", "Created"].map(col => (
            <span key={col} style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>
        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} h={44} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "40px 16px", textAlign: "center", color: C.muted, fontSize: 12 }}>
            {leads.length === 0 ? "No leads yet — the qualification agent will score inbound leads as they arrive." : "No leads match this filter."}
          </div>
        ) : filtered.map(lead => {
          const actionCol = { call_now: C.green, schedule_call: C.cyan, send_proposal: C.amber, nurture: C.purple, disqualify: C.red }[(lead.recommended_action || "").toLowerCase().replace(/\s+/g,"_")] || C.muted;
          return (
            <div key={lead.id} className="row-h" onClick={() => setSelected(lead)} style={{
              display: "grid", gridTemplateColumns: "1.4fr 110px 110px 72px 150px 92px 110px 100px",
              padding: "11px 14px", borderBottom: `1px solid ${C.border}`, alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                <div style={{ fontSize: 10, color: C.muted }}>#{lead.id}</div>
              </div>
              <div style={{ fontSize: 11, color: C.text }}>{lead.phone || "—"}</div>
              <div style={{ fontSize: 11, color: C.text }}>{lead.suburb || "—"}</div>
              <div><ScoreBadge score={lead.qualification_score} /></div>
              <div><Pill label={(lead.recommended_action || "—").toUpperCase().replace(/_/g," ")} color={actionCol} /></div>
              <div><Pill label={(lead.status || "new").toUpperCase()} color={{ converted: C.green, new: C.cyan, qualified: C.amber, rejected: C.red }[lead.status] || C.muted} /></div>
              <div style={{ fontSize: 10, color: C.muted }}>{lead.source || "—"}</div>
              <div style={{ fontSize: 10, color: C.muted }}>{lead.created_at ? new Date(lead.created_at).toLocaleDateString("en-AU") : "—"}</div>
            </div>
          );
        })}
      </div>
      <div style={{ fontSize: 11, color: C.muted, textAlign: "center", paddingTop: 12 }}>{filtered.length} of {leads.length} shown</div>
      <LeadModal lead={selected} onClose={() => setSelected(null)} onAction={handleAction} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   CALLS TAB
═══════════════════════════════════════════════════════════════════════════════ */
const CALL_DATE_FILTERS = [
  { label: "All Time", value: "" }, { label: "Today", value: "today" },
  { label: "This Week", value: "week" }, { label: "This Month", value: "month" },
];
const CALL_OUTCOME_OPTS = ["all", "completed", "booked", "voicemail", "no_answer", "failed"];
const CALL_SCORE_RANGES = [
  { label: "All", min: 0, max: 10 }, { label: "Hot 7+", min: 7, max: 10 },
  { label: "Warm 4–6", min: 4, max: 6.9 }, { label: "Cold <4", min: 0, max: 3.9 },
];

function CallTranscriptPanel({ call, onClose }) {
  if (!call) return null;
  const fields = call.extracted_data || {};
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(3,6,15,.88)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: C.panel, border: `1px solid ${C.borderB}`, borderRadius: 16, padding: 26, width: "100%", maxWidth: 640, maxHeight: "85vh", overflow: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.white }}>Call Detail</div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 3 }}>
              {call.caller_name || call.from_phone || "Unknown"} · {call.from_phone || ""} · {call.started_at ? new Date(call.started_at).toLocaleString("en-AU") : "—"}
            </div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 7, padding: "4px 10px", cursor: "pointer", fontSize: 11 }}>✕</button>
        </div>
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: "10px 14px", marginBottom: 18, display: "flex", gap: 18, flexWrap: "wrap" }}>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>SCORE</div><ScoreBadge score={call.lead_score} /></div>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>OUTCOME</div><span style={{ fontSize: 11, color: C.text }}>{call.outcome || call.status || "—"}</span></div>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>DURATION</div><span style={{ fontSize: 11, color: C.text, fontFamily: "'Space Mono',monospace" }}>{call.duration_fmt || "0:00"}</span></div>
          {call.recording_url && <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>RECORDING</div><a href={call.recording_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: C.cyan }}>Listen ↗</a></div>}
        </div>
        {Object.keys(fields).length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1, marginBottom: 8 }}>EXTRACTED DATA</div>
            {Object.entries(fields).map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, padding: "6px 10px", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: C.muted }}>{k.replace(/_/g, " ")}</span>
                <span style={{ fontSize: 11, color: C.text }}>{String(v)}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1, marginBottom: 10 }}>TRANSCRIPT</div>
        {call.transcript?.length > 0 ? call.transcript.map((turn, i) => {
          const isAI = turn.role === "assistant" || turn.role === "agent";
          return (
            <div key={i} style={{ display: "flex", flexDirection: isAI ? "row" : "row-reverse", gap: 8, marginBottom: 10 }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", flexShrink: 0, background: isAI ? h(C.amber, 0.15) : h(C.cyan, 0.15), border: `1px solid ${isAI ? h(C.amber, 0.3) : h(C.cyan, 0.3)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12 }}>
                {isAI ? "🤖" : "👤"}
              </div>
              <div style={{ background: isAI ? h(C.amber, 0.06) : h(C.cyan, 0.06), border: `1px solid ${isAI ? h(C.amber, 0.14) : h(C.cyan, 0.14)}`, borderRadius: 9, padding: "8px 12px", maxWidth: "78%" }}>
                <div style={{ fontSize: 9, color: isAI ? C.amber : C.cyan, marginBottom: 3, fontFamily: "'Space Mono',monospace" }}>{isAI ? "AI RECEPTIONIST" : "CALLER"}</div>
                <div style={{ fontSize: 12, color: C.text, lineHeight: 1.55 }}>{turn.content || turn.text || ""}</div>
              </div>
            </div>
          );
        }) : <div style={{ textAlign: "center", color: C.muted, fontSize: 12, padding: "20px 0" }}>No transcript available.</div>}
      </div>
    </div>
  );
}

function CallsTab({ apiFetch }) {
  const [calls,       setCalls]       = useState([]);
  const [stats,       setStats]       = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [dateFil,     setDateFil]     = useState("");
  const [outcomeFil,  setOutcomeFil]  = useState("all");
  const [scoreRange,  setScoreRange]  = useState(0);
  const [page,        setPage]        = useState(0);
  const [total,       setTotal]       = useState(0);
  const [selected,    setSelected]    = useState(null);
  const [loadingCall, setLoadingCall] = useState(false);
  const LIMIT = 25;

  const sinceParam = () => {
    const now = new Date();
    if (dateFil === "today") return now.toISOString().split("T")[0];
    if (dateFil === "week")  { const d = new Date(now); d.setDate(d.getDate() - 7); return d.toISOString(); }
    if (dateFil === "month") { const d = new Date(now); d.setMonth(d.getMonth() - 1); return d.toISOString(); }
    return "";
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const since = sinceParam();
      const p = new URLSearchParams({ limit: LIMIT, offset: page * LIMIT });
      if (since) p.set("since", since);
      if (outcomeFil !== "all") p.set("outcome", outcomeFil);
      const [callsR, statsR] = await Promise.allSettled([
        apiFetch(`/api/calls?${p}`).then(r => r.json()),
        apiFetch("/api/calls/stats").then(r => r.json()),
      ]);
      if (callsR.status === "fulfilled") { setCalls(callsR.value.calls || []); setTotal(callsR.value.total || 0); }
      if (statsR.status === "fulfilled") setStats(statsR.value);
    } finally { setLoading(false); }
  }, [dateFil, outcomeFil, page]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const openCall = async (call) => {
    if (call.transcript) { setSelected(call); return; }
    setLoadingCall(true);
    try {
      const r = await apiFetch(`/api/calls/${call.call_id}`);
      const d = await r.json();
      setSelected(d.call || call);
    } finally { setLoadingCall(false); }
  };

  const range    = CALL_SCORE_RANGES[scoreRange];
  const filtered = calls.filter(c => { const s = c.lead_score || 0; return s >= range.min && s <= range.max; });
  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="slide" style={{ padding: "22px 28px" }}>

      {/* Stats */}
      <div style={{ display: "flex", gap: 12, marginBottom: 22, flexWrap: "wrap" }}>
        {loading ? [1,2,3,4].map(i => <div key={i} style={{ flex: "1 1 110px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 18px" }}><Skeleton w={60} h={24} r={4} /><div style={{ marginTop: 8 }}><Skeleton w={80} h={10} /></div></div>) : <>
          {[
            { label: "Calls Today",    value: stats?.today?.calls ?? 0,                       color: C.amber  },
            { label: "Calls This Week",value: stats?.this_week?.calls ?? 0,                   color: C.cyan   },
            { label: "Booking Rate",   value: (stats?.this_week?.booking_rate ?? 0) + "%",    color: C.green  },
            { label: "Avg Duration",   value: stats?.this_week?.avg_duration || "0:00",       color: C.purple },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 18px", flex: "1 1 110px" }}>
              <div style={{ fontSize: 22, color, fontFamily: "'Space Mono',monospace", marginBottom: 4 }}>{value}</div>
              <div style={{ fontSize: 10, color: C.muted }}>{label}</div>
            </div>
          ))}
        </>}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4 }}>
          {CALL_DATE_FILTERS.map(f => <button key={f.value} onClick={() => { setDateFil(f.value); setPage(0); }} style={{ background: dateFil === f.value ? h(C.amber, 0.1) : "transparent", border: `1px solid ${dateFil === f.value ? h(C.amber, 0.35) : C.border}`, color: dateFil === f.value ? C.amber : C.muted, borderRadius: 6, padding: "6px 11px", cursor: "pointer", fontSize: 10, fontFamily: "'Space Mono',monospace" }}>{f.label}</button>)}
        </div>
        <select value={outcomeFil} onChange={e => { setOutcomeFil(e.target.value); setPage(0); }} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "6px 9px", fontSize: 11 }}>
          {CALL_OUTCOME_OPTS.map(o => <option key={o} value={o}>{o === "all" ? "All Outcomes" : o.replace(/_/g, " ")}</option>)}
        </select>
        <div style={{ display: "flex", gap: 4 }}>
          {CALL_SCORE_RANGES.map((r, i) => {
            const a = scoreRange === i;
            const col = i === 1 ? C.green : i === 2 ? C.amber : i === 3 ? C.red : C.muted;
            return <button key={i} onClick={() => setScoreRange(i)} style={{ background: a ? h(col, 0.12) : "transparent", border: `1px solid ${a ? col : C.border}`, color: a ? col : C.muted, borderRadius: 6, padding: "6px 10px", cursor: "pointer", fontSize: 9, fontFamily: "'Space Mono',monospace" }}>{r.label}</button>;
          })}
        </div>
        <div style={{ marginLeft: "auto", fontSize: 10, color: C.muted, fontFamily: "'Space Mono',monospace" }}>{total} total calls</div>
      </div>

      {/* Table */}
      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.3fr 130px 105px 95px 88px 88px 72px", padding: "9px 18px", background: C.card, borderBottom: `1px solid ${C.border}` }}>
          {["Caller Name", "Phone", "Date", "Duration", "Outcome", "Score", ""].map(col => (
            <span key={col} style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>
        {loading ? (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} h={48} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "40px 16px", textAlign: "center", color: C.muted, fontSize: 12 }}>
            {dateFil || outcomeFil !== "all" || scoreRange > 0 ? "No calls match this filter." : "No calls yet — calls will appear here once your AI receptionist goes live."}
          </div>
        ) : filtered.map(call => {
          const outcome = call.outcome || call.status || "unknown";
          const outCol  = { completed: C.green, booked: C.cyan, failed: C.red, voicemail: C.purple, no_answer: C.muted }[outcome] || C.muted;
          return (
            <div key={call.call_id} className="row-h" style={{ display: "grid", gridTemplateColumns: "1.3fr 130px 105px 95px 88px 88px 72px", padding: "11px 18px", borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.white }}>{call.caller_name || "Unknown"}</div>
                <div style={{ fontSize: 10, color: C.muted }}>{(call.call_id || "").slice(0,8)}…</div>
              </div>
              <div style={{ fontSize: 11, color: C.text }}>{call.from_phone || "—"}</div>
              <div style={{ fontSize: 11, color: C.text }}>{call.started_at ? new Date(call.started_at).toLocaleDateString("en-AU", { dateStyle: "short" }) : "—"}</div>
              <div style={{ fontSize: 12, color: C.text, fontFamily: "'Space Mono',monospace" }}>{call.duration_fmt || "0:00"}</div>
              <div><Pill label={outcome.toUpperCase().replace(/_/g," ")} color={outCol} /></div>
              <div><ScoreBadge score={call.lead_score} /></div>
              <div>
                <button onClick={() => openCall(call)} style={{ background: h(C.cyan, 0.08), border: `1px solid ${h(C.cyan, 0.22)}`, color: C.cyan, borderRadius: 6, padding: "4px 10px", fontSize: 10, cursor: "pointer", fontFamily: "'Space Mono',monospace" }}>
                  {loadingCall ? "…" : "VIEW"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, paddingTop: 16 }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ background: "transparent", border: `1px solid ${C.border}`, color: page === 0 ? C.muted : C.text, borderRadius: 7, padding: "6px 14px", cursor: page === 0 ? "not-allowed" : "pointer", fontSize: 12 }}>← Prev</button>
          <span style={{ fontSize: 12, color: C.muted, display: "flex", alignItems: "center" }}>Page {page + 1} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={{ background: "transparent", border: `1px solid ${C.border}`, color: page >= totalPages - 1 ? C.muted : C.text, borderRadius: 7, padding: "6px 14px", cursor: page >= totalPages - 1 ? "not-allowed" : "pointer", fontSize: 12 }}>Next →</button>
        </div>
      )}

      <CallTranscriptPanel call={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   EMAILS TAB
═══════════════════════════════════════════════════════════════════════════════ */
const EMAIL_TABS  = [{ label: "PENDING", value: "pending" }, { label: "ALL", value: "" }, { label: "SENT", value: "sent" }, { label: "DISCARDED", value: "discarded" }];
const CLASS_OPTS  = ["", "NEW_ENQUIRY", "QUOTE_REQUEST", "BOOKING_REQUEST", "COMPLAINT", "SPAM", "OTHER"];

function UrgencyBar({ score }) {
  const v = score != null ? Number(score) : 0;
  const col = v >= 8 ? C.red : v >= 5 ? C.amber : C.muted;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{ width: 3, height: 28, borderRadius: 2, background: col, boxShadow: v >= 8 ? `0 0 5px ${col}` : "none", flexShrink: 0 }} />
      <div>
        <div style={{ fontSize: 10, fontFamily: "'Space Mono',monospace", color: col }}>{v}/10</div>
        <div style={{ fontSize: 8, color: C.muted, letterSpacing: 1 }}>{v >= 8 ? "HIGH" : v >= 5 ? "MED" : "LOW"}</div>
      </div>
    </div>
  );
}

function EmailModal({ email, onClose, onSend, onDiscard, acting }) {
  const [edited,   setEdited]   = useState(email?.draft_reply || "");
  const [editing,  setEditing]  = useState(false);
  const [full,     setFull]     = useState(email);
  const [loading,  setLoading]  = useState(false);
  const { apiFetch } = useAuth();

  useEffect(() => {
    setEdited(email?.draft_reply || "");
    setEditing(false);
    setFull(email);
    if (email && !email.body) {
      setLoading(true);
      apiFetch(`/api/emails/${email.id}`).then(r => r.json()).then(d => { if (d.email) { setFull(d.email); setEdited(d.email.draft_reply || ""); } }).catch(() => {}).finally(() => setLoading(false));
    }
  }, [email]); // eslint-disable-line

  if (!email) return null;
  const isPending = full?.status === "pending";
  const classColor = { NEW_ENQUIRY: C.cyan, QUOTE_REQUEST: C.amber, BOOKING_REQUEST: C.green, COMPLAINT: C.red, SPAM: C.muted, OTHER: C.purple }[full?.classification] || C.muted;

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(3,6,15,.9)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2000, padding: 24 }}>
      <div onClick={e => e.stopPropagation()} style={{ background: C.panel, border: `1px solid ${C.borderB}`, borderRadius: 16, padding: 26, width: "100%", maxWidth: 680, maxHeight: "90vh", overflow: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
          <div style={{ flex: 1, minWidth: 0, paddingRight: 14 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: C.white, marginBottom: 4 }}>{full?.subject || "(no subject)"}</div>
            <div style={{ fontSize: 11, color: C.muted }}>From: <span style={{ color: C.text }}>{full?.from_name || full?.from_email}</span>{full?.received_at && <> · {new Date(full.received_at).toLocaleString("en-AU")}</>}</div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 7, padding: "4px 10px", cursor: "pointer", fontSize: 11, flexShrink: 0 }}>✕</button>
        </div>
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: "10px 14px", marginBottom: 18, display: "flex", gap: 18, flexWrap: "wrap" }}>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>TYPE</div><Pill label={(full?.classification || "UNKNOWN").replace(/_/g," ")} color={classColor} /></div>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 3, fontFamily: "'Space Mono',monospace" }}>URGENCY</div><UrgencyBar score={full?.urgency_score} /></div>
          <div><div style={{ fontSize: 9, color: C.muted, marginBottom: 4, fontFamily: "'Space Mono',monospace" }}>STATUS</div><Pill label={(full?.status || "pending").toUpperCase()} color={{ pending: C.amber, sent: C.green, discarded: C.muted }[full?.status] || C.muted} /></div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1, marginBottom: 8 }}>ORIGINAL EMAIL</div>
          {loading ? <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{[1,2,3].map(i => <Skeleton key={i} h={13} />)}</div> : (
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: "12px 14px", fontSize: 12, color: C.text, lineHeight: 1.65, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 200, overflow: "auto" }}>
              {full?.body || "(no body available)"}
            </div>
          )}
        </div>
        <div style={{ marginBottom: 22 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>AI DRAFT REPLY</div>
            {isPending && <button onClick={() => setEditing(v => !v)} style={{ background: editing ? h(C.amber, 0.1) : "transparent", border: `1px solid ${editing ? C.amber : C.border}`, color: editing ? C.amber : C.muted, borderRadius: 5, padding: "3px 10px", cursor: "pointer", fontSize: 10, fontFamily: "'Space Mono',monospace" }}>{editing ? "✓ DONE" : "✎ EDIT"}</button>}
          </div>
          {editing ? (
            <textarea value={edited} onChange={e => setEdited(e.target.value)} rows={9} style={{ width: "100%", background: C.card, border: `1px solid ${C.amber}`, color: C.text, borderRadius: 9, padding: "11px 13px", fontSize: 12, lineHeight: 1.65, resize: "vertical", fontFamily: "inherit", outline: "none" }} />
          ) : (
            <div style={{ background: h(C.amber, 0.04), border: `1px solid ${h(C.amber, 0.16)}`, borderRadius: 9, padding: "12px 14px", fontSize: 12, color: C.text, lineHeight: 1.65, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 260, overflow: "auto" }}>
              {edited || <span style={{ color: C.muted, fontStyle: "italic" }}>No AI reply generated yet.</span>}
            </div>
          )}
        </div>
        {isPending ? (
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => onSend(full, edited)} disabled={acting} style={{ flex: 2, background: h(C.green, 0.1), border: `1px solid ${h(C.green, 0.35)}`, color: C.green, borderRadius: 8, padding: "11px 18px", cursor: acting ? "not-allowed" : "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace", opacity: acting ? 0.6 : 1 }}>
              {acting ? "SENDING…" : "✓ APPROVE & SEND"}
            </button>
            <button onClick={() => onDiscard(full)} disabled={acting} style={{ flex: 1, background: h(C.red, 0.07), border: `1px solid ${h(C.red, 0.22)}`, color: C.red, borderRadius: 8, padding: "11px 18px", cursor: acting ? "not-allowed" : "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace", opacity: acting ? 0.6 : 1 }}>
              ✕ DISCARD
            </button>
          </div>
        ) : (
          <div style={{ textAlign: "center", fontSize: 11, color: C.muted, fontFamily: "'Space Mono',monospace", padding: "6px 0" }}>
            EMAIL {(full?.status || "").toUpperCase()} — NO FURTHER ACTION NEEDED
          </div>
        )}
      </div>
    </div>
  );
}

function EmailsTab({ apiFetch, onPendingChange }) {
  const [emails,    setEmails]    = useState([]);
  const [stats,     setStats]     = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [tab,       setTab]       = useState("pending");
  const [classFil,  setClassFil]  = useState("");
  const [search,    setSearch]    = useState("");
  const [limit,     setLimit]     = useState(50);
  const [offset,    setOffset]    = useState(0);
  const [total,     setTotal]     = useState(0);
  const [selected,  setSelected]  = useState(new Set());
  const [modal,     setModal]     = useState(null);
  const [acting,    setActing]    = useState(false);
  const [toast,     setToast]     = useState(null);
  const timerRef                  = useRef(null);

  const showToast = (msg, color = C.green) => {
    clearTimeout(timerRef.current);
    setToast({ msg, color });
    timerRef.current = setTimeout(() => setToast(null), 3200);
  };

  const loadStats = useCallback(async () => {
    try { const r = await apiFetch("/api/emails/stats"); const d = await r.json(); setStats(d); onPendingChange(d.pending ?? 0); } catch {}
  }, [apiFetch]); // eslint-disable-line

  const load = useCallback(async () => {
    setLoading(true);
    setSelected(new Set());
    try {
      const p = new URLSearchParams({ limit, offset });
      if (tab) p.set("status", tab);
      if (classFil) p.set("classification", classFil);
      if (search) p.set("search", search);
      const r = await apiFetch(`/api/emails?${p}`);
      const d = await r.json();
      setEmails(d.emails || []);
      setTotal(d.total || 0);
    } catch { setEmails([]); } finally { setLoading(false); }
  }, [apiFetch, tab, classFil, search, limit, offset]); // eslint-disable-line

  useEffect(() => { load(); loadStats(); }, [load]); // eslint-disable-line

  const handleSend = async (email, editedBody) => {
    setActing(true);
    try {
      const action = editedBody?.trim() && editedBody !== email.draft_reply ? "edit" : "send";
      const r = await apiFetch("/gate/email-approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email_id: email.id, action, edited_body: editedBody }) });
      if (!r.ok) throw new Error((await r.json()).error || "Send failed");
      showToast("Reply sent successfully");
      setModal(null); load(); loadStats();
    } catch (e) { showToast(e.message || "Failed to send", C.red); } finally { setActing(false); }
  };

  const handleDiscard = async (email) => {
    setActing(true);
    try {
      await apiFetch("/gate/email-approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email_id: email.id, action: "discard" }) });
      showToast("Email discarded", C.muted);
      setModal(null); load(); loadStats();
    } catch { showToast("Failed to discard", C.red); } finally { setActing(false); }
  };

  const handleBulkDiscard = async () => {
    if (selected.size === 0) return;
    setActing(true);
    try {
      const r = await apiFetch("/api/emails/bulk-discard", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: [...selected] }) });
      const d = await r.json();
      showToast(`Discarded ${d.discarded} email${d.discarded !== 1 ? "s" : ""}`, C.muted);
      setSelected(new Set()); load(); loadStats();
    } catch { showToast("Bulk discard failed", C.red); } finally { setActing(false); }
  };

  const toggleAll = () => selected.size === emails.length ? setSelected(new Set()) : setSelected(new Set(emails.filter(e => e.status === "pending").map(e => e.id)));
  const toggleOne = (id) => setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const pendingCount = stats?.pending ?? 0;
  const totalPages   = Math.ceil(total / limit);
  const curPage      = Math.floor(offset / limit);

  return (
    <div className="slide" style={{ padding: "22px 28px" }}>
      <Toast toast={toast} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 2, marginBottom: 5 }}>EMAIL QUEUE</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 3 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.white }}>Emails</div>
            {pendingCount > 0 && <div style={{ background: h(C.amber, 0.14), border: `1px solid ${C.amber}`, color: C.amber, borderRadius: 20, padding: "2px 10px", fontSize: 11, fontFamily: "'Space Mono',monospace", boxShadow: `0 0 8px ${h(C.amber, 0.25)}` }}>{pendingCount} pending</div>}
          </div>
          <div style={{ fontSize: 11, color: C.muted }}>{stats ? `${stats.today_total ?? 0} today · ${stats.sent ?? 0} sent all-time · ${stats.discarded_today ?? 0} discarded today` : "Loading…"}</div>
        </div>
        <button onClick={() => { load(); loadStats(); }} style={{ background: h(C.cyan, 0.08), border: `1px solid ${h(C.cyan, 0.25)}`, color: C.cyan, padding: "8px 16px", borderRadius: 7, cursor: "pointer", fontSize: 11, fontFamily: "'Space Mono',monospace" }}>↻ REFRESH</button>
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { label: "Pending Review",value: stats?.pending ?? "—",         color: C.amber },
          { label: "Sent Today",    value: stats?.today_total ?? "—",     color: C.green },
          { label: "All-time Sent", value: stats?.sent ?? "—",            color: C.cyan  },
          { label: "Discarded",     value: stats?.discarded_today ?? "—", color: C.muted },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 18px", flex: "1 1 110px" }}>
            <div style={{ fontSize: 22, color, fontFamily: "'Space Mono',monospace", lineHeight: 1, marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 10, color: C.muted }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Tab + filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 3, background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 3 }}>
          {EMAIL_TABS.map(t => {
            const a   = tab === t.value;
            const col = t.value === "pending" ? C.amber : t.value === "sent" ? C.green : t.value === "discarded" ? C.muted : C.cyan;
            return (
              <button key={t.value} onClick={() => { setTab(t.value); setOffset(0); }} style={{ background: a ? h(col, 0.14) : "transparent", border: `1px solid ${a ? col : "transparent"}`, color: a ? col : C.muted, borderRadius: 5, padding: "5px 13px", cursor: "pointer", fontSize: 10, fontFamily: "'Space Mono',monospace" }}>
                {t.label}
                {t.value === "pending" && pendingCount > 0 && <span style={{ marginLeft: 5, background: h(C.amber, 0.18), border: `1px solid ${h(C.amber, 0.35)}`, color: C.amber, borderRadius: 9, padding: "0 5px", fontSize: 9 }}>{pendingCount}</span>}
              </button>
            );
          })}
        </div>
        <input value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} placeholder="Search sender, subject…" style={{ background: C.card, border: `1px solid ${C.border}`, color: C.text, borderRadius: 7, padding: "7px 12px", fontSize: 12, width: 195 }} />
        <select value={classFil} onChange={e => { setClassFil(e.target.value); setOffset(0); }} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "6px 9px", fontSize: 11 }}>
          {CLASS_OPTS.map(c => <option key={c} value={c}>{c === "" ? "All Types" : c.replace(/_/g, " ")}</option>)}
        </select>
        <select value={limit} onChange={e => { setLimit(Number(e.target.value)); setOffset(0); }} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "6px 9px", fontSize: 11, marginLeft: "auto" }}>
          {[25, 50, 100].map(n => <option key={n} value={n}>Show {n}</option>)}
        </select>
      </div>

      {selected.size > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, background: h(C.amber, 0.07), border: `1px solid ${h(C.amber, 0.28)}`, borderRadius: 9, padding: "9px 14px", marginBottom: 12, animation: "fadeUp .2s ease" }}>
          <span style={{ fontSize: 12, color: C.amber, fontFamily: "'Space Mono',monospace" }}>{selected.size} selected</span>
          <button onClick={handleBulkDiscard} disabled={acting} style={{ background: h(C.red, 0.09), border: `1px solid ${h(C.red, 0.28)}`, color: C.red, borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 10, fontFamily: "'Space Mono',monospace" }}>✕ DISCARD SELECTED</button>
          <button onClick={() => setSelected(new Set())} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 6, padding: "5px 10px", cursor: "pointer", fontSize: 10 }}>Clear</button>
        </div>
      )}

      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "30px 48px 1.1fr 1.6fr 130px 72px 72px 82px", padding: "9px 14px", background: C.card, borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
          <input type="checkbox" checked={selected.size > 0 && selected.size === emails.filter(e => e.status === "pending").length} onChange={toggleAll} style={{ accentColor: C.amber, width: 13, height: 13 }} />
          {["URG", "From", "Subject", "Type", "Status", "Date", ""].map(col => (
            <span key={col} style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>
        {loading ? (
          <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} h={50} />)}
          </div>
        ) : emails.length === 0 ? (
          <div style={{ padding: "44px 16px", textAlign: "center" }}>
            <div style={{ fontSize: 26, marginBottom: 10 }}>{tab === "pending" ? "📬" : "✉️"}</div>
            <div style={{ color: C.muted, fontSize: 12 }}>{tab === "pending" ? "No emails waiting — you're all caught up." : "No emails match this filter."}</div>
          </div>
        ) : emails.map(email => {
          const isPending  = email.status === "pending";
          const urgency    = email.urgency_score || 0;
          const urgCol     = urgency >= 8 ? C.red : urgency >= 5 ? C.amber : C.muted;
          const isSelected = selected.has(email.id);
          const classColor = { NEW_ENQUIRY: C.cyan, QUOTE_REQUEST: C.amber, BOOKING_REQUEST: C.green, COMPLAINT: C.red, SPAM: C.muted, OTHER: C.purple }[email.classification] || C.muted;
          return (
            <div key={email.id} className="row-h" onClick={() => setModal(email)} style={{
              display: "grid", gridTemplateColumns: "30px 48px 1.1fr 1.6fr 130px 72px 72px 82px",
              padding: "10px 14px", borderBottom: `1px solid ${C.border}`, alignItems: "center",
              background: isSelected ? h(C.amber, 0.04) : "transparent",
              borderLeft: `3px solid ${isPending ? urgCol : "transparent"}`,
            }}>
              <div onClick={e => e.stopPropagation()}>
                {isPending && <input type="checkbox" checked={isSelected} onChange={() => toggleOne(email.id)} style={{ accentColor: C.amber, width: 13, height: 13 }} />}
              </div>
              <div onClick={() => setModal(email)}><UrgencyBar score={email.urgency_score} /></div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: isPending ? C.white : C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{email.from_name || email.from_email}</div>
                {email.from_name && <div style={{ fontSize: 10, color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{email.from_email}</div>}
              </div>
              <div style={{ fontSize: 12, color: isPending ? C.text : C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 10 }}>{email.subject || "(no subject)"}</div>
              <div><Pill label={(email.classification || "UNKNOWN").replace(/_/g," ")} color={classColor} /></div>
              <div><Pill label={(email.status || "pending").toUpperCase()} color={{ pending: C.amber, sent: C.green, discarded: C.muted }[email.status] || C.muted} /></div>
              <div style={{ fontSize: 10, color: C.muted }}>{email.received_at ? new Date(email.received_at).toLocaleDateString("en-AU", { dateStyle: "short" }) : "—"}</div>
              <div>
                <button onClick={() => setModal(email)} style={{ background: isPending ? h(C.amber, 0.1) : h(C.cyan, 0.08), border: `1px solid ${isPending ? h(C.amber, 0.28) : h(C.cyan, 0.2)}`, color: isPending ? C.amber : C.cyan, borderRadius: 6, padding: "4px 9px", fontSize: 9, cursor: "pointer", fontFamily: "'Space Mono',monospace" }}>
                  {isPending ? "REVIEW" : "VIEW"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 8, paddingTop: 16 }}>
          <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0} style={{ background: "transparent", border: `1px solid ${C.border}`, color: offset === 0 ? C.muted : C.text, borderRadius: 7, padding: "6px 13px", cursor: offset === 0 ? "not-allowed" : "pointer", fontSize: 12 }}>← Prev</button>
          <span style={{ fontSize: 11, color: C.muted }}>Page {curPage + 1} of {totalPages} · {total} total</span>
          <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total} style={{ background: "transparent", border: `1px solid ${C.border}`, color: offset + limit >= total ? C.muted : C.text, borderRadius: 7, padding: "6px 13px", cursor: offset + limit >= total ? "not-allowed" : "pointer", fontSize: 12 }}>Next →</button>
        </div>
      )}

      <EmailModal email={modal} onClose={() => setModal(null)} onSend={handleSend} onDiscard={handleDiscard} acting={acting} />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   AGENTS TAB
═══════════════════════════════════════════════════════════════════════════════ */
const AGENTS = [
  {
    id: "voice", name: "Voice AI", icon: "🎙️", color: C.purple, canToggle: true,
    schedule: "Event-driven — inbound & outbound calls",
    role: "AI Phone Receptionist",
    what: "Handles all inbound solar sales calls 24/7 using Retell AI. Answers questions, qualifies leads conversationally, books site assessments, and updates the CRM in real-time.",
    how: ["Retell AI routes inbound call → voice handler", "Loads your company KB: products, FAQs, objection scripts", "GPT-4o drives the conversation with a solar-specific prompt", "Functions: qualify lead, book appointment, send SMS, update CRM", "Post-call: transcript analysed, lead scored, CRM updated"],
    inputs: ["Inbound call (via Retell AI)", "Company knowledge base", "Lead database"],
    outputs: ["Call transcript + lead score", "CRM stage update", "Booked appointments", "SMS confirmation"],
    value: "One AI handles calls simultaneously, 24/7. Hot leads are scored and escalated before a human picks up the phone.",
    statKey: "calls_today", statLabel: "Calls today",
  },
  {
    id: "email", name: "Email Processor", icon: "📧", color: C.cyan, canToggle: true,
    schedule: "Event-driven — GHL inbound message webhook",
    role: "Email Triage & Reply Drafter",
    what: "Classifies every inbound email by intent, scores urgency, drafts a reply in your company voice, and routes to the approval queue before sending.",
    how: ["GHL webhook fires on new inbound message", "GPT-4o classifies: intent, urgency, sentiment", "Draft reply generated using company tone and FAQs", "High urgency → Slack alert, approval required before send", "All emails logged and tracked"],
    inputs: ["GHL inbound message webhook", "Company KB (tone, FAQs, pricing)"],
    outputs: ["Classified intent + urgency score", "AI draft reply", "Approval queue entry", "Slack alert (high urgency)"],
    value: "Every lead gets a response in minutes. Your team only handles emails that genuinely need human judgment.",
    statKey: "emails_today", statLabel: "Emails today", statKey2: "pending_approvals", statLabel2: "Awaiting approval",
  },
  {
    id: "qualification", name: "Lead Scoring", icon: "🎯", color: C.orange, canToggle: true,
    schedule: "Event-driven — GHL webhook on new lead or post-call",
    role: "Lead Scoring & Hot Lead Routing",
    what: "Scores every inbound solar lead 1–10 using GPT-4o across four criteria. Routes hot leads (7+) to call_now, mid-range to nurture, and low-value to disqualify. Score ≥ 8 fires a Slack HOT LEAD alert.",
    how: ["Triggered by GHL webhook or after each voice call", "Criteria: homeowner status, monthly bill, roof type, location", "GPT-4o returns score, reason, recommended action, key signals", "Fallback: rule-based scoring when AI unavailable", "Score ≥ 7 → call_now, Score ≥ 8 → HOT LEAD Slack alert"],
    inputs: ["GHL webhook payload or call transcript", "Company qualification thresholds"],
    outputs: ["Lead score 1–10", "Recommended action", "Slack alert (score ≥ 8)", "DB update"],
    value: "Your sales team only talks to pre-qualified leads — conversion rates improve, wasted calls drop.",
    statKey: "leads_today", statLabel: "Leads scored today",
  },
  {
    id: "proposal", name: "Proposal Generator", icon: "📄", color: C.green, canToggle: true,
    schedule: "Event-driven — triggered after lead qualifies",
    role: "Solar Installation Proposal Generator",
    what: "Generates a tailored solar installation proposal for each qualified lead. Calculates system size, annual savings, STC rebate by state, payback period, and equipment recommendation. Outputs a branded HTML email.",
    how: ["Triggered after lead qualification completes", "Calculates system size from monthly bill + peak sun hours", "Calculates STC rebate by state (deeming period × zone factor × $38)", "Renders KPI grid, equipment table, and pricing range", "Saves to proposals table as draft"],
    inputs: ["Lead record (bill, state, suburb, name)", "STC zone tables"],
    outputs: ["HTML proposal email", "Proposal record", "System size, annual savings, payback period"],
    value: "Every qualified lead receives a personalised proposal automatically — no quotes sitting in drafts folders.",
    statKey: "proposals_today", statLabel: "Proposals generated",
  },
  {
    id: "crm_sync", name: "CRM Sync", icon: "🔄", color: C.teal, canToggle: false,
    schedule: "Every 30 minutes",
    role: "GoHighLevel Pipeline Sync",
    what: "Pulls live contact and pipeline data from GoHighLevel every 30 minutes. Writes to the local cache so the dashboard always reflects current CRM state without hammering the GHL API.",
    how: ["Scheduler fires every 30 minutes", "Calls GHL API: contacts (recent), pipelines (stage counts)", "Writes pipeline stage data to cache", "Dashboard reads from cache — no live GHL calls needed"],
    inputs: ["GoHighLevel REST API (contacts, pipeline stages)"],
    outputs: ["CRM cache table", "Dashboard pipeline data", "Sync log entry"],
    value: "Keeps the dashboard reflecting reality. Without this, the board shows stale data.",
    statKey: "contacts_synced", statLabel: "Contacts in cache",
  },
];

function AgentInfoPanel({ agent, onClose }) {
  if (!agent) return null;
  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(3,6,15,.7)", zIndex: 100 }} />
      <div style={{ position: "fixed", top: 0, right: 0, width: 460, height: "100vh", background: C.panel, borderLeft: `1px solid ${C.borderB}`, zIndex: 101, overflowY: "auto", padding: "26px 26px 40px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ width: 44, height: 44, borderRadius: 11, background: h(agent.color, 0.12), border: `1px solid ${h(agent.color, 0.3)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>{agent.icon}</div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: C.white, marginBottom: 3 }}>{agent.name}</div>
              <Pill label="ACTIVE AGENT" color={agent.color} />
            </div>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 5, padding: "3px 8px", cursor: "pointer", fontSize: 15 }}>×</button>
        </div>
        {[
          { label: "Role", content: <p style={{ margin: 0, color: C.text, fontSize: 13, lineHeight: 1.6 }}>{agent.role}</p> },
          { label: "Schedule", content: <div style={{ fontFamily: "'Space Mono',monospace", fontSize: 11, background: C.dim, border: `1px solid ${C.border}`, borderRadius: 5, padding: "7px 11px", color: C.amberL }}>{agent.schedule}</div> },
          { label: "What it does", content: <p style={{ margin: 0, color: C.text, fontSize: 13, lineHeight: 1.65 }}>{agent.what}</p> },
          { label: "How it works", content: <ol style={{ margin: 0, paddingLeft: 16, color: C.text, fontSize: 12, lineHeight: 1.8 }}>{agent.how.map((step, i) => <li key={i} style={{ marginBottom: 3 }}>{step}</li>)}</ol> },
        ].map(({ label, content }) => (
          <div key={label} style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 9, fontFamily: "'Space Mono',monospace", color: agent.color, letterSpacing: 2, marginBottom: 7 }}>{label.toUpperCase()}</div>
            {content}
          </div>
        ))}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 18 }}>
          {[{ label: "Inputs", items: agent.inputs, col: C.blue }, { label: "Outputs", items: agent.outputs, col: C.green }].map(({ label, items, col }) => (
            <div key={label}>
              <div style={{ fontSize: 9, fontFamily: "'Space Mono',monospace", color: col, letterSpacing: 2, marginBottom: 7 }}>{label.toUpperCase()}</div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 7, padding: "9px 11px" }}>
                {items.map((item, i) => <div key={i} style={{ fontSize: 11, color: C.text, lineHeight: 1.5, paddingBottom: i < items.length - 1 ? 5 : 0, marginBottom: i < items.length - 1 ? 5 : 0, borderBottom: i < items.length - 1 ? `1px solid ${C.dim}` : "none" }}>{item}</div>)}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 9, fontFamily: "'Space Mono',monospace", color: C.amber, letterSpacing: 2, marginBottom: 7 }}>BUSINESS VALUE</div>
          <div style={{ background: h(C.amber, 0.05), border: `1px solid ${h(C.amber, 0.18)}`, borderRadius: 7, padding: "11px 13px", color: C.amberL, fontSize: 12, lineHeight: 1.6 }}>{agent.value}</div>
        </div>
        {!agent.canToggle && (
          <div style={{ background: h(C.red, 0.05), border: `1px solid ${h(C.red, 0.18)}`, borderRadius: 7, padding: "11px 13px", color: C.red, fontSize: 11 }}>
            ⚠ This agent cannot be disabled — it is required for dashboard operation.
          </div>
        )}
      </div>
    </>
  );
}

function Toggle({ enabled, onChange, disabled }) {
  return (
    <button onClick={() => !disabled && onChange(!enabled)} style={{
      position: "relative", width: 38, height: 20,
      background: enabled ? (disabled ? C.muted : C.green) : C.dim,
      borderRadius: 10, border: `1px solid ${enabled ? (disabled ? C.muted : C.green) : C.border}`,
      cursor: disabled ? "not-allowed" : "pointer", transition: "all .2s",
      flexShrink: 0, opacity: disabled ? 0.45 : 1, padding: 0,
    }}>
      <span style={{ position: "absolute", top: 2, left: enabled ? 18 : 2, width: 14, height: 14, background: C.white, borderRadius: "50%", transition: "left .2s", boxShadow: "0 1px 3px rgba(0,0,0,.35)" }} />
    </button>
  );
}

function AgentsTab({ apiFetch }) {
  const [agentState,  setAgentState]  = useState({});
  const [statusData,  setStatusData]  = useState({});
  const [loading,     setLoading]     = useState(true);
  const [infoAgent,   setInfoAgent]   = useState(null);
  const [saving,      setSaving]      = useState(null);
  const [toast,       setToast]       = useState(null);

  const loadStatus = useCallback(async () => {
    try {
      const r = await apiFetch("/api/agents/status");
      if (r.ok) {
        const data = await r.json();
        const en = {}, st = {};
        Object.entries(data.agents || {}).forEach(([id, info]) => { en[id] = info.enabled !== false; st[id] = info; });
        setAgentState(en); setStatusData(st);
      } else {
        const d = {}; AGENTS.forEach(a => { d[a.id] = true; }); setAgentState(d);
      }
    } catch { const d = {}; AGENTS.forEach(a => { d[a.id] = true; }); setAgentState(d); } finally { setLoading(false); }
  }, [apiFetch]);

  useEffect(() => { loadStatus(); const t = setInterval(loadStatus, 30000); return () => clearInterval(t); }, [loadStatus]);

  const handleToggle = async (agent, newVal) => {
    if (!agent.canToggle) return;
    setSaving(agent.id);
    setAgentState(prev => ({ ...prev, [agent.id]: newVal }));
    try {
      const r = await apiFetch("/api/agents/status", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agent_id: agent.id, enabled: newVal }) });
      if (!r.ok) throw new Error();
      setToast({ msg: `${agent.name} ${newVal ? "enabled" : "disabled"}`, ok: true });
    } catch {
      setAgentState(prev => ({ ...prev, [agent.id]: !newVal }));
      setToast({ msg: "Failed to save — check connection", ok: false });
    } finally { setSaving(null); setTimeout(() => setToast(null), 3000); }
  };

  const activeCount = AGENTS.filter(a => agentState[a.id] !== false).length;

  if (loading) {
    return <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: C.bg }}><div style={{ fontFamily: "'Space Mono',monospace", fontSize: 11, color: C.amber, letterSpacing: 2 }}>LOADING AGENTS…</div></div>;
  }

  return (
    <div className="slide" style={{ padding: "22px 28px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 22 }}>
        <div>
          <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace", letterSpacing: 2, marginBottom: 5 }}>SYSTEM STATUS</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: C.white, marginBottom: 3 }}>AI Agents</div>
          <div style={{ fontSize: 12, color: C.muted }}>Monitor and control your 5 active agents. Refreshes every 30s.</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Pill label={`${activeCount} ACTIVE`} color={C.green} />
          {activeCount < AGENTS.length && <Pill label={`${AGENTS.length - activeCount} DISABLED`} color={C.muted} />}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 12 }}>
        {AGENTS.map(agent => {
          const enabled    = agentState[agent.id] !== false;
          const status     = statusData[agent.id];
          const agSt       = status?.status || (enabled ? "idle" : "disabled");
          const isRunning  = agSt === "running" || agSt === "active";
          const isError    = agSt === "error";
          const dotCol     = !enabled ? C.muted : isError ? C.red : isRunning ? C.green : h(agent.color, 0.7);
          const stLabel    = !enabled ? "DISABLED" : isError ? "ERROR" : isRunning ? "RUNNING" : "IDLE";
          const lastRun    = status?.last_run ? new Date(status.last_run).toLocaleString("en-AU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : null;
          return (
            <div key={agent.id} style={{
              background: C.card, border: `1px solid ${enabled ? h(agent.color, 0.28) : C.border}`,
              borderRadius: 11, padding: "16px 18px", opacity: enabled ? 1 : 0.55,
              display: "flex", flexDirection: "column", gap: 12, transition: "all .15s",
            }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <div style={{ width: 40, height: 40, borderRadius: 9, flexShrink: 0, background: h(agent.color, 0.12), border: `1px solid ${h(agent.color, enabled ? 0.28 : 0.1)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, position: "relative" }}>
                  {agent.icon}
                  {isRunning && <span style={{ position: "absolute", top: -2, right: -2, width: 7, height: 7, borderRadius: "50%", background: C.green, boxShadow: `0 0 5px ${C.green}` }} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: enabled ? C.white : C.muted, marginBottom: 2 }}>{agent.name}</div>
                  <div style={{ fontSize: 10, color: enabled ? agent.color : C.muted }}>{agent.role}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                  <button onClick={() => setInfoAgent(agent)} style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 5, width: 24, height: 24, padding: 0, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>ℹ</button>
                  <Toggle enabled={enabled} onChange={v => handleToggle(agent, v)} disabled={!agent.canToggle || saving === agent.id} />
                </div>
              </div>
              {(agent.statKey || agent.statKey2) && (
                <div style={{ display: "flex", gap: 16 }}>
                  {agent.statKey && <div><div style={{ fontSize: 16, fontWeight: 700, color: enabled ? agent.color : C.muted, fontFamily: "'Space Mono',monospace", lineHeight: 1 }}>{status?.[agent.statKey] ?? "—"}</div><div style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>{agent.statLabel}</div></div>}
                  {agent.statKey2 && <div><div style={{ fontSize: 16, fontWeight: 700, color: enabled ? agent.color : C.muted, fontFamily: "'Space Mono',monospace", lineHeight: 1 }}>{status?.[agent.statKey2] ?? "—"}</div><div style={{ fontSize: 9, color: C.muted, marginTop: 2 }}>{agent.statLabel2}</div></div>}
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: dotCol, boxShadow: isRunning ? `0 0 4px ${C.green}` : "none" }} />
                  <span style={{ fontSize: 9, fontFamily: "'Space Mono',monospace", color: C.muted }}>{stLabel}</span>
                </div>
                {lastRun && enabled && <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace" }}>Last: {lastRun}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 20, padding: "12px 16px", background: C.panel, border: `1px solid ${C.border}`, borderRadius: 9, fontSize: 11, color: C.muted, display: "flex", gap: 20, flexWrap: "wrap" }}>
        <span><span style={{ color: C.green }}>●</span> Running</span>
        <span><span style={{ color: C.amber }}>●</span> Idle</span>
        <span><span style={{ color: C.red }}>●</span> Error — check logs</span>
        <span><span style={{ color: C.muted }}>●</span> Disabled</span>
        <span style={{ marginLeft: "auto" }}>⚠ CRM Sync cannot be disabled</span>
      </div>

      <AgentInfoPanel agent={infoAgent} onClose={() => setInfoAgent(null)} />

      {toast && (
        <div style={{ position: "fixed", bottom: 28, right: 28, zIndex: 200, background: toast.ok ? h(C.green, 0.14) : h(C.red, 0.14), border: `1px solid ${toast.ok ? h(C.green, 0.38) : h(C.red, 0.38)}`, color: toast.ok ? C.green : C.red, borderRadius: 8, padding: "9px 16px", fontSize: 12, fontFamily: "'Space Mono',monospace" }}>
          {toast.ok ? "✓" : "✗"} {toast.msg}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════════════════════════════ */
export default function ClientDashboard() {
  const { apiFetch, user }     = useAuth();
  const [tab,         setTab]  = useState("overview");
  const [company,     setCompany] = useState(null);
  const [pendingEmails, setPending] = useState(0);

  const clientId    = user?.client_id;
  const accentColor = company?.primary_color || C.amber;

  useEffect(() => {
    if (!clientId) return;
    apiFetch(`/api/companies/${clientId}`).then(r => r.ok ? r.json() : null).then(d => { if (d?.company) setCompany(d.company); }).catch(() => {});
  }, [clientId]); // eslint-disable-line

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: C.bg, overflow: "hidden" }}>
      <style>{STYLES}</style>

      {/* Company header */}
      <div style={{ background: C.panel, borderBottom: `1px solid ${C.border}`, padding: "14px 24px", display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
        {company?.logo_url ? (
          <img src={company.logo_url} alt={company.name} style={{ height: 38, width: 38, objectFit: "contain", borderRadius: 9, border: `1px solid ${C.border}` }} />
        ) : (
          <div style={{ width: 38, height: 38, borderRadius: 9, background: h(accentColor, 0.14), border: `1px solid ${h(accentColor, 0.3)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>☀️</div>
        )}
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.white }}>{company?.name || "Your Dashboard"}</div>
          <div style={{ fontSize: 11, color: C.muted }}>{company?.address || "Solar Automation Platform"}</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: 9, color: C.muted, fontFamily: "'Space Mono',monospace" }}>POWERED BY</div>
          <div style={{ fontSize: 11, color: accentColor, fontFamily: "'Space Mono',monospace", letterSpacing: 1 }}>SOLAR ADMIN AI</div>
        </div>
      </div>

      {/* Tab navigation */}
      <TabNav tab={tab} setTab={setTab} pendingEmails={pendingEmails} />

      {/* Tab content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {tab === "overview" && <OverviewTab apiFetch={apiFetch} onTabChange={setTab} company={company} accentColor={accentColor} />}
        {tab === "leads"    && <LeadsTab    apiFetch={apiFetch} />}
        {tab === "calls"    && <CallsTab    apiFetch={apiFetch} />}
        {tab === "emails"   && <EmailsTab   apiFetch={apiFetch} onPendingChange={setPending} />}
        {tab === "agents"   && <AgentsTab   apiFetch={apiFetch} />}
      </div>
    </div>
  );
}
