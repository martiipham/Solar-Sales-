/**
 * ClientDashboard — simplified client-facing view for solar SME clients.
 * Shows: AI agent status, call activity, KPIs, pipeline, recent leads + calls.
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

const C = {
  bg:      "#050810",
  panel:   "#080D1A",
  card:    "#0C1222",
  border:  "#132035",
  borderB: "#1E3050",
  amber:   "#F59E0B",
  cyan:    "#22D3EE",
  green:   "#4ADE80",
  red:     "#F87171",
  orange:  "#FB923C",
  purple:  "#C084FC",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

const SHIMMER = `
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
`;

function Skeleton({ width = "100%", height = 16, radius = 6 }) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background: `linear-gradient(90deg, ${C.card} 25%, ${C.border} 50%, ${C.card} 75%)`,
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
    }} />
  );
}

function StatCard({ label, value, sub, color = C.cyan, icon }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "20px 22px", flex: "1 1 150px",
    }}>
      {icon && <div style={{ fontSize: 20, marginBottom: 8 }}>{icon}</div>}
      <div style={{ fontSize: 30, color, lineHeight: 1, marginBottom: 5, fontFamily: "'Syne Mono', monospace" }}>
        {value}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 3 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: C.muted }}>{sub}</div>}
    </div>
  );
}

function ScoreBadge({ score }) {
  const color = score >= 7 ? C.green : score >= 4 ? C.amber : C.red;
  return (
    <span style={{
      display: "inline-block",
      background: h(color, 0.15), border: `1px solid ${h(color, 0.35)}`,
      color, borderRadius: 6, padding: "2px 8px",
      fontSize: 12, fontFamily: "'Syne Mono', monospace",
    }}>{score?.toFixed(1) ?? "—"}</span>
  );
}

function StatusDot({ status }) {
  const color = status === "live" ? C.green : status === "needs_setup" ? C.amber : C.red;
  const label = status === "live" ? "LIVE" : status === "needs_setup" ? "SETUP NEEDED" : "OFFLINE";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{
        width: 9, height: 9, borderRadius: "50%", background: color,
        boxShadow: status === "live" ? `0 0 8px ${color}` : "none",
        animation: status === "live" ? "pulse 2s infinite" : "none",
      }} />
      <span style={{ fontSize: 11, fontFamily: "'Syne Mono', monospace", color, letterSpacing: 1 }}>
        {label}
      </span>
    </div>
  );
}

function AIAgentCard({ voiceStatus, callStats, loading }) {
  const status = voiceStatus?.status || "offline";
  const statusColor = status === "live" ? C.green : status === "needs_setup" ? C.amber : C.red;

  return (
    <div style={{
      background: C.panel, border: `1px solid ${h(statusColor, 0.4)}`,
      borderRadius: 14, padding: "20px 24px",
      display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center",
      boxShadow: status === "live" ? `0 0 20px ${h(statusColor, 0.08)}` : "none",
    }}>
      {/* Icon + status */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, flex: "0 0 auto" }}>
        <div style={{
          width: 52, height: 52, borderRadius: 14,
          background: h(statusColor, 0.12), border: `1px solid ${h(statusColor, 0.3)}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 24,
        }}>🤖</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: C.white, marginBottom: 5 }}>
            AI Receptionist
          </div>
          {loading ? <Skeleton width={100} height={12} /> : <StatusDot status={status} />}
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 40, background: C.border, flex: "0 0 auto" }} />

      {/* Today's numbers */}
      <div style={{ display: "flex", gap: 28, flex: 1, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 24, color: statusColor, fontFamily: "'Syne Mono', monospace" }}>
            {loading ? "—" : callStats?.today?.calls ?? 0}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>Calls today</div>
        </div>
        <div>
          <div style={{ fontSize: 24, color: C.cyan, fontFamily: "'Syne Mono', monospace" }}>
            {loading ? "—" : callStats?.this_week?.calls ?? 0}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>This week</div>
        </div>
        <div>
          <div style={{ fontSize: 24, color: C.purple, fontFamily: "'Syne Mono', monospace" }}>
            {loading ? "—" : (callStats?.this_week?.booking_rate ?? 0) + "%"}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>Booking rate</div>
        </div>
        <div>
          <div style={{ fontSize: 24, color: C.amber, fontFamily: "'Syne Mono', monospace" }}>
            {loading ? "—" : callStats?.this_week?.avg_duration ?? "0:00"}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>Avg call length</div>
        </div>
      </div>

      {/* Right: last activity */}
      {!loading && status === "live" && (
        <div style={{
          fontSize: 11, color: C.green, background: h(C.green, 0.08),
          border: `1px solid ${h(C.green, 0.2)}`, borderRadius: 20,
          padding: "4px 12px", flex: "0 0 auto",
        }}>
          Answering calls 24/7
        </div>
      )}
      {!loading && status === "needs_setup" && (
        <div style={{
          fontSize: 11, color: C.amber, background: h(C.amber, 0.08),
          border: `1px solid ${h(C.amber, 0.2)}`, borderRadius: 20,
          padding: "4px 12px", flex: "0 0 auto",
        }}>
          Complete setup to go live
        </div>
      )}
    </div>
  );
}

function RecentCallsTable({ calls, loading, onViewCall }) {
  if (loading) {
    return (
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
        {[1, 2, 3].map(i => <Skeleton key={i} height={44} />)}
      </div>
    );
  }
  if (!calls.length) {
    return (
      <div style={{ padding: "36px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
        No calls yet — your AI receptionist will log every inbound call here.
      </div>
    );
  }
  return (
    <>
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 90px 80px 100px 80px",
        padding: "10px 20px", background: C.card, borderBottom: `1px solid ${C.border}`,
      }}>
        {["Caller", "Duration", "Score", "Outcome", ""].map(col => (
          <span key={col} style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1 }}>
            {col}
          </span>
        ))}
      </div>
      {calls.map(call => {
        const scoreColor = (call.lead_score || 0) >= 7 ? C.green : (call.lead_score || 0) >= 4 ? C.amber : C.muted;
        const statusColor = call.status === "completed" ? C.green : call.status === "failed" ? C.red : C.muted;
        return (
          <div key={call.call_id} style={{
            display: "grid", gridTemplateColumns: "1fr 90px 80px 100px 80px",
            padding: "12px 20px", borderBottom: `1px solid ${C.border}`,
            alignItems: "center",
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>
                {call.from_phone || "Unknown"}
              </div>
              <div style={{ fontSize: 11, color: C.muted }}>
                {call.started_at ? new Date(call.started_at).toLocaleString("en-AU", { dateStyle: "short", timeStyle: "short" }) : "—"}
              </div>
            </div>
            <div style={{ fontSize: 13, color: C.text, fontFamily: "'Syne Mono', monospace" }}>
              {call.duration_fmt || "0:00"}
            </div>
            <div>
              {call.lead_score ? (
                <span style={{
                  fontSize: 12, color: scoreColor,
                  background: h(scoreColor, 0.12), border: `1px solid ${h(scoreColor, 0.3)}`,
                  borderRadius: 6, padding: "2px 8px",
                  fontFamily: "'Syne Mono', monospace",
                }}>
                  {call.lead_score.toFixed(1)}
                </span>
              ) : <span style={{ color: C.muted }}>—</span>}
            </div>
            <div>
              <span style={{
                fontSize: 10, color: statusColor,
                background: h(statusColor, 0.1), border: `1px solid ${h(statusColor, 0.25)}`,
                borderRadius: 10, padding: "2px 9px",
                fontFamily: "'Syne Mono', monospace",
              }}>
                {(call.status || "unknown").toUpperCase()}
              </span>
            </div>
            <div>
              <button
                onClick={() => onViewCall(call)}
                style={{
                  background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.25)}`,
                  color: C.cyan, borderRadius: 6, padding: "4px 10px",
                  fontSize: 11, cursor: "pointer",
                }}
              >
                View
              </button>
            </div>
          </div>
        );
      })}
    </>
  );
}

function TranscriptModal({ call, onClose }) {
  if (!call) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(5,8,16,0.85)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 1000, padding: 24,
    }} onClick={onClose}>
      <div style={{
        background: C.panel, border: `1px solid ${C.borderB}`,
        borderRadius: 18, padding: 28, width: "100%", maxWidth: 580,
        maxHeight: "80vh", overflow: "auto",
      }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: C.white }}>
              Call Transcript
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              {call.from_phone} · {call.started_at ? new Date(call.started_at).toLocaleString("en-AU") : "—"} · {call.duration_fmt}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: `1px solid ${C.border}`,
            color: C.muted, borderRadius: 8, padding: "4px 10px",
            cursor: "pointer", fontSize: 12,
          }}>✕ Close</button>
        </div>

        {/* Lead score row */}
        {call.lead_score && (
          <div style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 10, padding: "10px 14px", marginBottom: 18,
            display: "flex", gap: 20,
          }}>
            <div>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 2 }}>LEAD SCORE</div>
              <ScoreBadge score={call.lead_score} />
            </div>
            <div>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 2 }}>STATUS</div>
              <span style={{ fontSize: 12, color: C.text }}>{call.status}</span>
            </div>
            {call.recording_url && (
              <div>
                <div style={{ fontSize: 10, color: C.muted, marginBottom: 2 }}>RECORDING</div>
                <a href={call.recording_url} target="_blank" rel="noreferrer"
                   style={{ fontSize: 12, color: C.cyan }}>Listen ↗</a>
              </div>
            )}
          </div>
        )}

        {/* Transcript */}
        {call.transcript && call.transcript.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {call.transcript.map((turn, i) => {
              const isAgent = turn.role === "assistant" || turn.role === "agent";
              return (
                <div key={i} style={{
                  display: "flex", flexDirection: isAgent ? "row" : "row-reverse", gap: 10,
                }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
                    background: isAgent ? h(C.amber, 0.15) : h(C.cyan, 0.15),
                    border: `1px solid ${isAgent ? h(C.amber, 0.3) : h(C.cyan, 0.3)}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 13,
                  }}>
                    {isAgent ? "🤖" : "👤"}
                  </div>
                  <div style={{
                    background: isAgent ? h(C.amber, 0.06) : h(C.cyan, 0.06),
                    border: `1px solid ${isAgent ? h(C.amber, 0.15) : h(C.cyan, 0.15)}`,
                    borderRadius: 10, padding: "9px 13px",
                    maxWidth: "78%",
                  }}>
                    <div style={{ fontSize: 10, color: isAgent ? C.amber : C.cyan, marginBottom: 4, fontFamily: "'Syne Mono', monospace" }}>
                      {isAgent ? "AI RECEPTIONIST" : "CALLER"}
                    </div>
                    <div style={{ fontSize: 13, color: C.text, lineHeight: 1.5 }}>
                      {turn.content || turn.text || ""}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ textAlign: "center", color: C.muted, fontSize: 13, padding: "24px 0" }}>
            No transcript available for this call.
          </div>
        )}
      </div>
    </div>
  );
}

function MonthlyHighlights({ report, loading }) {
  if (loading) return <Skeleton height={60} />;
  if (!report?.highlights?.length) return null;

  return (
    <div style={{
      background: h(C.cyan, 0.05), border: `1px solid ${h(C.cyan, 0.2)}`,
      borderRadius: 12, padding: "14px 18px",
    }}>
      <div style={{ fontSize: 12, color: C.cyan, fontWeight: 600, marginBottom: 10, fontFamily: "'Syne Mono', monospace" }}>
        {report?.period?.label?.toUpperCase() || "THIS MONTH"} — HIGHLIGHTS
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {report.highlights.map((h_text, i) => (
          <div key={i} style={{ fontSize: 13, color: C.text, display: "flex", gap: 8 }}>
            <span style={{ color: C.cyan, flexShrink: 0 }}>›</span>
            {h_text}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ClientDashboard({ onNavigate }) {
  const { apiFetch, user } = useAuth();
  const [company, setCompany]         = useState(null);
  const [leads, setLeads]             = useState([]);
  const [metrics, setMetrics]         = useState(null);
  const [pipeline, setPipeline]       = useState([]);
  const [callStats, setCallStats]     = useState(null);
  const [recentCalls, setRecentCalls] = useState([]);
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [monthReport, setMonthReport] = useState(null);
  const [loading, setLoading]         = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);

  const clientId = user?.client_id;
  const accentColor = company?.primary_color || C.amber;

  const loadAll = useCallback(async () => {
    try {
      const [
        companyRes, leadsRes, metricsRes, pipelineRes,
        callStatsRes, recentCallsRes, voiceRes, reportRes,
      ] = await Promise.allSettled([
        clientId
          ? apiFetch(`/api/companies/${clientId}`).then(r => r.ok ? r.json() : null)
          : Promise.resolve(null),
        apiFetch("/api/swarm/leads?limit=8").then(r => r.json()),
        apiFetch("/api/crm/metrics").then(r => r.json()),
        apiFetch("/api/crm/pipeline").then(r => r.json()),
        apiFetch("/api/calls/stats").then(r => r.json()),
        apiFetch("/api/calls?limit=5").then(r => r.json()),
        apiFetch("/api/voice/status").then(r => r.json()),
        apiFetch("/api/reports/monthly").then(r => r.json()),
      ]);

      if (companyRes.status === "fulfilled" && companyRes.value?.company) {
        setCompany(companyRes.value.company);
      }
      if (leadsRes.status === "fulfilled")       setLeads(leadsRes.value.leads || []);
      if (metricsRes.status === "fulfilled")     setMetrics(metricsRes.value.metrics || {});
      if (pipelineRes.status === "fulfilled")    setPipeline(pipelineRes.value.stages || []);
      if (callStatsRes.status === "fulfilled")   setCallStats(callStatsRes.value);
      if (recentCallsRes.status === "fulfilled") setRecentCalls(recentCallsRes.value.calls || []);
      if (voiceRes.status === "fulfilled")       setVoiceStatus(voiceRes.value);
      if (reportRes.status === "fulfilled")      setMonthReport(reportRes.value);
    } finally {
      setLoading(false);
    }
  }, [clientId]); // eslint-disable-line

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, [loadAll]);

  const qualifiedLeads = leads.filter(l => (l.qualification_score || 0) >= 7);
  const avgScore = leads.length
    ? (leads.reduce((s, l) => s + (l.qualification_score || 0), 0) / leads.length).toFixed(1)
    : "—";

  return (
    <div style={{ flex: 1, overflow: "auto", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Company header */}
      <div style={{
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        padding: "20px 32px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          {company?.logo_url ? (
            <img src={company.logo_url} alt={company.name}
              style={{ height: 44, width: 44, objectFit: "contain", borderRadius: 10, border: `1px solid ${C.border}` }}
            />
          ) : (
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: h(accentColor, 0.15), border: `1px solid ${h(accentColor, 0.3)}`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20,
            }}>☀️</div>
          )}
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.white }}>
              {loading ? <Skeleton width={180} height={20} /> : (company?.name || "Your Dashboard")}
            </div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>
              {company?.address || "Solar Automation Platform"}
            </div>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right" }}>
            <div style={{ fontSize: 10, color: C.muted }}>Powered by</div>
            <div style={{ fontSize: 12, color: accentColor, fontFamily: "'Syne Mono', monospace" }}>SOLAR SWARM</div>
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 32px", display: "flex", flexDirection: "column", gap: 24 }}>

        {/* AI Agent status card — hero element */}
        <AIAgentCard voiceStatus={voiceStatus} callStats={callStats} loading={loading} />

        {/* Monthly highlights */}
        <MonthlyHighlights report={monthReport} loading={loading} />

        {/* KPI cards */}
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          {loading ? (
            [1, 2, 3, 4].map(i => (
              <div key={i} style={{ flex: "1 1 150px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
                <Skeleton height={30} width={60} radius={4} />
                <div style={{ marginTop: 10 }}><Skeleton height={13} width={90} /></div>
              </div>
            ))
          ) : (
            <>
              <StatCard icon="📞" label="Calls This Month" value={monthReport?.calls?.current?.calls ?? 0}
                sub={monthReport?.calls?.vs_prior ? `${monthReport.calls.vs_prior} vs last month` : "all time"}
                color={accentColor} />
              <StatCard icon="⭐" label="Hot Leads" value={qualifiedLeads.length} sub="score 7+" color={C.green} />
              <StatCard icon="📊" label="Avg Lead Score" value={avgScore} sub="out of 10" color={C.cyan} />
              <StatCard icon="🔄" label="CRM Contacts" value={metrics?.total_contacts || 0}
                sub={`+${metrics?.new_this_week || 0} this week`} color={C.purple} />
            </>
          )}
        </div>

        {/* Pipeline stages */}
        {pipeline.length > 0 && (
          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 22px" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.white, marginBottom: 14 }}>Lead Pipeline</div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {pipeline.map((stage, i) => {
                const cnt = stage.opportunityCount || stage.count || 0;
                const maxCnt = Math.max(...pipeline.map(s => s.opportunityCount || s.count || 0), 1);
                const pct = Math.round((cnt / maxCnt) * 100);
                const stageColor = [accentColor, C.cyan, C.green, C.purple, C.orange][i % 5];
                return (
                  <div key={i} style={{ flex: "1 1 110px", minWidth: 90 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                      <span style={{ fontSize: 11, color: stageColor, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "75%" }}>
                        {stage.name || stage.stageName || `Stage ${i + 1}`}
                      </span>
                      <span style={{ fontSize: 12, color: stageColor, fontFamily: "'Syne Mono', monospace" }}>{cnt}</span>
                    </div>
                    <div style={{ height: 7, background: C.border, borderRadius: 4 }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: stageColor, borderRadius: 4, opacity: 0.8 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Two-column: recent calls + recent leads */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>

          {/* Recent Calls */}
          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
            <div style={{
              padding: "14px 18px", borderBottom: `1px solid ${C.border}`,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>Recent Calls</div>
              {onNavigate && (
                <button onClick={() => onNavigate("calls")} style={{
                  background: "transparent", border: "none", color: C.cyan,
                  fontSize: 11, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                }}>View All →</button>
              )}
            </div>
            <RecentCallsTable calls={recentCalls} loading={loading} onViewCall={setSelectedCall} />
          </div>

          {/* Recent Leads */}
          <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
            <div style={{
              padding: "14px 18px", borderBottom: `1px solid ${C.border}`,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>Recent Leads</div>
              <div style={{ fontSize: 11, color: C.muted }}>Last 8</div>
            </div>
            {loading ? (
              <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                {[1, 2, 3].map(i => <Skeleton key={i} height={40} />)}
              </div>
            ) : leads.length === 0 ? (
              <div style={{ padding: "32px 16px", textAlign: "center", color: C.muted, fontSize: 13 }}>
                No leads yet. Your AI receptionist will populate this automatically.
              </div>
            ) : leads.map(lead => (
              <div key={lead.id} style={{
                padding: "11px 18px", borderBottom: `1px solid ${C.border}`,
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                  <div style={{ fontSize: 11, color: C.muted }}>
                    {new Date(lead.created_at).toLocaleDateString("en-AU")}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <ScoreBadge score={lead.qualification_score} />
                  <span style={{
                    fontSize: 10, color: lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted,
                    background: h(lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted, 0.1),
                    border: `1px solid ${h(lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted, 0.25)}`,
                    borderRadius: 10, padding: "2px 8px", fontFamily: "'Syne Mono', monospace",
                  }}>
                    {(lead.status || "new").toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", fontSize: 11, color: C.muted, paddingBottom: 8 }}>
          Refreshes every 30 seconds · Solar Swarm AI Automation
        </div>
      </div>

      {/* Transcript modal */}
      <TranscriptModal call={selectedCall} onClose={() => setSelectedCall(null)} />
    </div>
  );
}
