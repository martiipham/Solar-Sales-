/**
 * CallsPage — full call log with filters, stats header, and transcript viewer.
 * Accessible to admin + owner + client roles.
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

const C = {
  bg: "#050810", panel: "#080D1A", card: "#0C1222",
  border: "#132035", borderB: "#1E3050",
  amber: "#F59E0B", cyan: "#22D3EE", green: "#4ADE80",
  red: "#F87171", orange: "#FB923C", purple: "#C084FC",
  muted: "#475569", text: "#CBD5E1", white: "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");
const SHIMMER = `@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}`;

function Skeleton({ width = "100%", height = 16, radius = 6 }) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background: `linear-gradient(90deg,${C.card} 25%,${C.border} 50%,${C.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

function StatPill({ label, value, color = C.cyan }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: "14px 20px", flex: "1 1 120px",
    }}>
      <div style={{ fontSize: 26, color, fontFamily: "'Syne Mono', monospace", marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: C.muted }}>{label}</div>
    </div>
  );
}

function ScoreBadge({ score }) {
  const color = (score || 0) >= 7 ? C.green : (score || 0) >= 4 ? C.amber : C.muted;
  return (
    <span style={{
      display: "inline-block",
      background: h(color, 0.12), border: `1px solid ${h(color, 0.3)}`,
      color, borderRadius: 6, padding: "2px 8px",
      fontSize: 12, fontFamily: "'Syne Mono', monospace",
    }}>{score ? score.toFixed(1) : "—"}</span>
  );
}

function TranscriptModal({ call, onClose }) {
  if (!call) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(5,8,16,0.88)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: C.panel, border: `1px solid ${C.borderB}`,
          borderRadius: 18, padding: 28, width: "100%", maxWidth: 600,
          maxHeight: "82vh", overflow: "auto",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: C.white }}>Call Transcript</div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              {call.from_phone || "Unknown"} · {call.started_at ? new Date(call.started_at).toLocaleString("en-AU") : "—"} · {call.duration_fmt || "0:00"}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 8, padding: "5px 12px", cursor: "pointer", fontSize: 12,
          }}>✕ Close</button>
        </div>

        {/* Meta row */}
        <div style={{
          background: C.card, border: `1px solid ${C.border}`,
          borderRadius: 10, padding: "10px 16px", marginBottom: 20,
          display: "flex", gap: 24, flexWrap: "wrap",
        }}>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>LEAD SCORE</div>
            <ScoreBadge score={call.lead_score} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>STATUS</div>
            <span style={{ fontSize: 12, color: C.text }}>{call.status || "—"}</span>
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>DURATION</div>
            <span style={{ fontSize: 12, color: C.text, fontFamily: "'Syne Mono', monospace" }}>{call.duration_fmt || "0:00"}</span>
          </div>
          {call.recording_url && (
            <div>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>RECORDING</div>
              <a href={call.recording_url} target="_blank" rel="noreferrer"
                 style={{ fontSize: 12, color: C.cyan }}>Listen ↗</a>
            </div>
          )}
        </div>

        {/* Transcript turns */}
        {call.transcript && call.transcript.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {call.transcript.map((turn, i) => {
              const isAgent = turn.role === "assistant" || turn.role === "agent";
              return (
                <div key={i} style={{ display: "flex", flexDirection: isAgent ? "row" : "row-reverse", gap: 10 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                    background: isAgent ? h(C.amber, 0.15) : h(C.cyan, 0.15),
                    border: `1px solid ${isAgent ? h(C.amber, 0.3) : h(C.cyan, 0.3)}`,
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
                  }}>
                    {isAgent ? "🤖" : "👤"}
                  </div>
                  <div style={{
                    background: isAgent ? h(C.amber, 0.06) : h(C.cyan, 0.06),
                    border: `1px solid ${isAgent ? h(C.amber, 0.15) : h(C.cyan, 0.15)}`,
                    borderRadius: 10, padding: "10px 14px", maxWidth: "78%",
                  }}>
                    <div style={{ fontSize: 10, color: isAgent ? C.amber : C.cyan, marginBottom: 5, fontFamily: "'Syne Mono', monospace" }}>
                      {isAgent ? "AI RECEPTIONIST" : "CALLER"}
                    </div>
                    <div style={{ fontSize: 13, color: C.text, lineHeight: 1.55 }}>
                      {turn.content || turn.text || ""}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ textAlign: "center", color: C.muted, fontSize: 13, padding: "30px 0" }}>
            No transcript available for this call.
          </div>
        )}
      </div>
    </div>
  );
}

const FILTERS = [
  { label: "All Time", value: "" },
  { label: "Today",    value: "today" },
  { label: "This Week",  value: "week" },
];

export default function CallsPage() {
  const { apiFetch } = useAuth();
  const [calls, setCalls]         = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [filter, setFilter]       = useState("");
  const [page, setPage]           = useState(0);
  const [total, setTotal]         = useState(0);
  const [selectedCall, setSelectedCall] = useState(null);
  const [loadingCall, setLoadingCall] = useState(false);

  const LIMIT = 20;

  const sinceParam = () => {
    const now = new Date();
    if (filter === "today") return now.toISOString().split("T")[0];
    if (filter === "week") {
      const d = new Date(now); d.setDate(d.getDate() - 7);
      return d.toISOString();
    }
    return "";
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const since = sinceParam();
      const params = new URLSearchParams({ limit: LIMIT, offset: page * LIMIT });
      if (since) params.set("since", since);

      const [callsRes, statsRes] = await Promise.allSettled([
        apiFetch(`/api/calls?${params}`).then(r => r.json()),
        apiFetch("/api/calls/stats").then(r => r.json()),
      ]);

      if (callsRes.status === "fulfilled") {
        setCalls(callsRes.value.calls || []);
        setTotal(callsRes.value.total || 0);
      }
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
    } finally {
      setLoading(false);
    }
  }, [filter, page]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const openCall = async (call) => {
    // If transcript already loaded, show immediately
    if (call.transcript) { setSelectedCall(call); return; }
    setLoadingCall(true);
    try {
      const res = await apiFetch(`/api/calls/${call.call_id}`);
      const data = await res.json();
      setSelectedCall(data.call || call);
    } finally {
      setLoadingCall(false);
    }
  };

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div style={{ flex: 1, overflow: "auto", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Page header */}
      <div style={{
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        padding: "20px 32px", display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.white }}>Call Logs</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>
            Every inbound call handled by your AI receptionist
          </div>
        </div>
        <div style={{ fontSize: 12, color: C.muted, fontFamily: "'Syne Mono', monospace" }}>
          {total} total calls
        </div>
      </div>

      <div style={{ padding: "24px 32px", display: "flex", flexDirection: "column", gap: 22 }}>

        {/* Stats row */}
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          {loading ? [1,2,3,4].map(i => (
            <div key={i} style={{ flex: "1 1 120px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 20px" }}>
              <Skeleton height={26} width={60} radius={4} />
              <div style={{ marginTop: 8 }}><Skeleton height={11} width={80} /></div>
            </div>
          )) : (
            <>
              <StatPill label="Calls Today" value={stats?.today?.calls ?? 0} color={C.amber} />
              <StatPill label="Calls This Week" value={stats?.this_week?.calls ?? 0} color={C.cyan} />
              <StatPill label="Booking Rate" value={(stats?.this_week?.booking_rate ?? 0) + "%"} color={C.green} />
              <StatPill label="Avg Duration" value={stats?.this_week?.avg_duration || "0:00"} color={C.purple} />
            </>
          )}
        </div>

        {/* Filter tabs */}
        <div style={{ display: "flex", gap: 8 }}>
          {FILTERS.map(f => (
            <button key={f.value} onClick={() => { setFilter(f.value); setPage(0); }}
              style={{
                background: filter === f.value ? h(C.amber, 0.12) : "transparent",
                border: `1px solid ${filter === f.value ? h(C.amber, 0.4) : C.border}`,
                color: filter === f.value ? C.amber : C.muted,
                borderRadius: 8, padding: "6px 16px", cursor: "pointer", fontSize: 12,
                transition: "all .15s",
              }}>
              {f.label}
            </button>
          ))}
        </div>

        {/* Calls table */}
        <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
          {/* Table header */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 160px 90px 100px 100px 80px",
            padding: "10px 20px", background: C.card, borderBottom: `1px solid ${C.border}`,
          }}>
            {["Caller", "Date & Time", "Duration", "Score", "Status", ""].map(col => (
              <span key={col} style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1 }}>
                {col}
              </span>
            ))}
          </div>

          {loading ? (
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
              {[1,2,3,4,5].map(i => <Skeleton key={i} height={50} />)}
            </div>
          ) : calls.length === 0 ? (
            <div style={{ padding: "48px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
              {filter ? "No calls in this time period." : "No calls recorded yet. Calls will appear here once your AI receptionist goes live."}
            </div>
          ) : calls.map(call => {
            const scoreColor = (call.lead_score || 0) >= 7 ? C.green : (call.lead_score || 0) >= 4 ? C.amber : C.muted;
            const statusColor = call.status === "completed" ? C.green : call.status === "failed" ? C.red : C.muted;
            return (
              <div key={call.call_id} style={{
                display: "grid", gridTemplateColumns: "1fr 160px 90px 100px 100px 80px",
                padding: "13px 20px", borderBottom: `1px solid ${C.border}`,
                alignItems: "center", transition: "background .1s",
              }}
                onMouseEnter={e => e.currentTarget.style.background = h(C.white, 0.02)}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{call.from_phone || "Unknown"}</div>
                  <div style={{ fontSize: 11, color: C.muted }}>ID: {call.call_id?.slice(0, 8)}…</div>
                </div>
                <div style={{ fontSize: 12, color: C.text }}>
                  {call.started_at ? new Date(call.started_at).toLocaleString("en-AU", { dateStyle: "short", timeStyle: "short" }) : "—"}
                </div>
                <div style={{ fontSize: 13, color: C.text, fontFamily: "'Syne Mono', monospace" }}>
                  {call.duration_fmt || "0:00"}
                </div>
                <div>
                  {call.lead_score ? (
                    <span style={{
                      fontSize: 12, color: scoreColor,
                      background: h(scoreColor, 0.12), border: `1px solid ${h(scoreColor, 0.3)}`,
                      borderRadius: 6, padding: "2px 8px", fontFamily: "'Syne Mono', monospace",
                    }}>{call.lead_score.toFixed(1)}</span>
                  ) : <span style={{ color: C.muted, fontSize: 12 }}>—</span>}
                </div>
                <div>
                  <span style={{
                    fontSize: 10, color: statusColor,
                    background: h(statusColor, 0.1), border: `1px solid ${h(statusColor, 0.25)}`,
                    borderRadius: 10, padding: "2px 9px", fontFamily: "'Syne Mono', monospace",
                  }}>{(call.status || "unknown").toUpperCase()}</span>
                </div>
                <div>
                  <button onClick={() => openCall(call)} style={{
                    background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.25)}`,
                    color: C.cyan, borderRadius: 6, padding: "5px 12px",
                    fontSize: 11, cursor: "pointer",
                  }}>
                    {loadingCall ? "…" : "View"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              style={{
                background: "transparent", border: `1px solid ${C.border}`,
                color: page === 0 ? C.muted : C.text,
                borderRadius: 8, padding: "6px 14px", cursor: page === 0 ? "not-allowed" : "pointer",
                fontSize: 12,
              }}>← Prev</button>
            <span style={{ fontSize: 12, color: C.muted, display: "flex", alignItems: "center" }}>
              Page {page + 1} of {totalPages}
            </span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              style={{
                background: "transparent", border: `1px solid ${C.border}`,
                color: page >= totalPages - 1 ? C.muted : C.text,
                borderRadius: 8, padding: "6px 14px",
                cursor: page >= totalPages - 1 ? "not-allowed" : "pointer",
                fontSize: 12,
              }}>Next →</button>
          </div>
        )}
      </div>

      <TranscriptModal call={selectedCall} onClose={() => setSelectedCall(null)} />
    </div>
  );
}
