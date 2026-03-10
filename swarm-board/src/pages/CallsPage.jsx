/**
 * CallsPage — call log with filters (date range, outcome, score), stats,
 * and expandable transcript/extracted data panel.
 * Fetches from GET /api/calls and GET /api/calls/:id
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
  const val = score != null ? Number(score) : null;
  const color = val == null ? C.muted : val >= 7 ? C.green : val >= 4 ? C.amber : C.red;
  return (
    <span style={{
      display: "inline-block",
      background: h(color, 0.12), border: `1px solid ${h(color, 0.3)}`,
      color, borderRadius: 6, padding: "2px 8px",
      fontSize: 12, fontFamily: "'Syne Mono', monospace",
    }}>
      {val != null ? val.toFixed(1) : "—"}
    </span>
  );
}

function TranscriptPanel({ call, onClose }) {
  if (!call) return null;
  const fields = call.extracted_data || {};
  const qualResult = call.qualification_result;

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
          borderRadius: 18, padding: 28, width: "100%", maxWidth: 660,
          maxHeight: "85vh", overflow: "auto",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: C.white }}>Call Detail</div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              {call.caller_name || call.from_phone || "Unknown"} · {call.from_phone || ""} ·{" "}
              {call.started_at ? new Date(call.started_at).toLocaleString("en-AU") : "—"}
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
          display: "flex", gap: 20, flexWrap: "wrap",
        }}>
          {[
            { label: "SCORE",    node: <ScoreBadge score={call.lead_score} /> },
            { label: "OUTCOME",  node: <span style={{ fontSize: 12, color: C.text }}>{call.outcome || call.status || "—"}</span> },
            { label: "DURATION", node: <span style={{ fontSize: 12, color: C.text, fontFamily: "'Syne Mono', monospace" }}>{call.duration_fmt || "0:00"}</span> },
          ].map(({ label, node }) => (
            <div key={label}>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>{label}</div>
              {node}
            </div>
          ))}
          {call.recording_url && (
            <div>
              <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>RECORDING</div>
              <a href={call.recording_url} target="_blank" rel="noreferrer"
                 style={{ fontSize: 12, color: C.cyan }}>Listen ↗</a>
            </div>
          )}
        </div>

        {/* Extracted data */}
        {Object.keys(fields).length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1, marginBottom: 10 }}>
              EXTRACTED DATA
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {Object.entries(fields).map(([k, v]) => (
                <div key={k} style={{
                  display: "flex", justifyContent: "space-between",
                  background: C.card, border: `1px solid ${C.border}`,
                  borderRadius: 7, padding: "7px 12px",
                }}>
                  <span style={{ fontSize: 12, color: C.muted }}>{k.replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 12, color: C.text }}>{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Qualification result */}
        {qualResult && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1, marginBottom: 10 }}>
              QUALIFICATION RESULT
            </div>
            <div style={{
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 10, padding: "12px 14px", fontSize: 13, color: C.text, lineHeight: 1.6,
            }}>
              {typeof qualResult === "string" ? qualResult : JSON.stringify(qualResult, null, 2)}
            </div>
          </div>
        )}

        {/* Transcript */}
        <div>
          <div style={{ fontSize: 11, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1, marginBottom: 12 }}>
            TRANSCRIPT
          </div>
          {call.transcript && call.transcript.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {call.transcript.map((turn, i) => {
                const isAgent = turn.role === "assistant" || turn.role === "agent";
                return (
                  <div key={i} style={{ display: "flex", flexDirection: isAgent ? "row" : "row-reverse", gap: 10 }}>
                    <div style={{
                      width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
                      background: isAgent ? h(C.amber, 0.15) : h(C.cyan, 0.15),
                      border: `1px solid ${isAgent ? h(C.amber, 0.3) : h(C.cyan, 0.3)}`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13,
                    }}>
                      {isAgent ? "🤖" : "👤"}
                    </div>
                    <div style={{
                      background: isAgent ? h(C.amber, 0.06) : h(C.cyan, 0.06),
                      border: `1px solid ${isAgent ? h(C.amber, 0.14) : h(C.cyan, 0.14)}`,
                      borderRadius: 10, padding: "9px 13px", maxWidth: "78%",
                    }}>
                      <div style={{ fontSize: 10, color: isAgent ? C.amber : C.cyan, marginBottom: 4, fontFamily: "'Syne Mono', monospace" }}>
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
            <div style={{ textAlign: "center", color: C.muted, fontSize: 13, padding: "24px 0" }}>
              No transcript available for this call.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const DATE_FILTERS = [
  { label: "All Time",   value: "" },
  { label: "Today",      value: "today" },
  { label: "This Week",  value: "week" },
  { label: "This Month", value: "month" },
];

const OUTCOME_OPTS = ["all", "completed", "booked", "voicemail", "no_answer", "failed"];
const SCORE_RANGES = [
  { label: "All",       min: 0, max: 10 },
  { label: "Hot 7+",   min: 7, max: 10 },
  { label: "Warm 4–6", min: 4, max: 6.9 },
  { label: "Cold <4",  min: 0, max: 3.9 },
];

export default function CallsPage() {
  const { apiFetch } = useAuth();
  const [calls, setCalls]         = useState([]);
  const [stats, setStats]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [dateFilter, setDate]     = useState("");
  const [outcomeFilter, setOutcome] = useState("all");
  const [scoreRange, setScoreRange] = useState(0);
  const [page, setPage]           = useState(0);
  const [total, setTotal]         = useState(0);
  const [selectedCall, setSelected] = useState(null);
  const [loadingCall, setLoadingCall] = useState(false);

  const LIMIT = 25;

  const sinceParam = () => {
    const now = new Date();
    if (dateFilter === "today") return now.toISOString().split("T")[0];
    if (dateFilter === "week")  { const d = new Date(now); d.setDate(d.getDate() - 7); return d.toISOString(); }
    if (dateFilter === "month") { const d = new Date(now); d.setMonth(d.getMonth() - 1); return d.toISOString(); }
    return "";
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const since = sinceParam();
      const params = new URLSearchParams({ limit: LIMIT, offset: page * LIMIT });
      if (since) params.set("since", since);
      if (outcomeFilter !== "all") params.set("outcome", outcomeFilter);

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
  }, [dateFilter, outcomeFilter, page]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const openCall = async (call) => {
    if (call.transcript) { setSelected(call); return; }
    setLoadingCall(true);
    try {
      const res = await apiFetch(`/api/calls/${call.call_id}`);
      const data = await res.json();
      setSelected(data.call || call);
    } finally {
      setLoadingCall(false);
    }
  };

  // Client-side score filter on top of server results
  const range = SCORE_RANGES[scoreRange];
  const filtered = calls.filter(c => {
    const s = c.lead_score || 0;
    return s >= range.min && s <= range.max;
  });

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

      <div style={{ padding: "24px 32px", display: "flex", flexDirection: "column", gap: 20 }}>

        {/* Stats row */}
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          {loading ? [1,2,3,4].map(i => (
            <div key={i} style={{ flex: "1 1 120px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 20px" }}>
              <Skeleton height={26} width={60} radius={4} />
              <div style={{ marginTop: 8 }}><Skeleton height={11} width={80} /></div>
            </div>
          )) : (
            <>
              <StatPill label="Calls Today"     value={stats?.today?.calls ?? 0}                        color={C.amber}  />
              <StatPill label="Calls This Week"  value={stats?.this_week?.calls ?? 0}                    color={C.cyan}   />
              <StatPill label="Booking Rate"     value={(stats?.this_week?.booking_rate ?? 0) + "%"}     color={C.green}  />
              <StatPill label="Avg Duration"     value={stats?.this_week?.avg_duration || "0:00"}        color={C.purple} />
            </>
          )}
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          {/* Date */}
          <div style={{ display: "flex", gap: 6 }}>
            {DATE_FILTERS.map(f => (
              <button key={f.value} onClick={() => { setDate(f.value); setPage(0); }} style={{
                background: dateFilter === f.value ? h(C.amber, 0.12) : "transparent",
                border: `1px solid ${dateFilter === f.value ? h(C.amber, 0.4) : C.border}`,
                color: dateFilter === f.value ? C.amber : C.muted,
                borderRadius: 8, padding: "6px 13px", cursor: "pointer", fontSize: 11,
                fontFamily: "'Syne Mono', monospace",
              }}>
                {f.label}
              </button>
            ))}
          </div>

          {/* Outcome */}
          <select
            value={outcomeFilter}
            onChange={e => { setOutcome(e.target.value); setPage(0); }}
            style={{
              background: C.card, border: `1px solid ${C.border}`, color: C.muted,
              borderRadius: 7, padding: "7px 10px", fontSize: 12,
            }}
          >
            {OUTCOME_OPTS.map(o => (
              <option key={o} value={o}>{o === "all" ? "All Outcomes" : o.replace(/_/g, " ")}</option>
            ))}
          </select>

          {/* Score range */}
          <div style={{ display: "flex", gap: 5 }}>
            {SCORE_RANGES.map((r, i) => {
              const active = scoreRange === i;
              const col = i === 1 ? C.green : i === 2 ? C.amber : i === 3 ? C.red : C.muted;
              return (
                <button key={i} onClick={() => setScoreRange(i)} style={{
                  background: active ? h(col, 0.14) : "transparent",
                  border: `1px solid ${active ? col : C.border}`,
                  color: active ? col : C.muted,
                  borderRadius: 7, padding: "6px 11px",
                  cursor: "pointer", fontSize: 10, fontFamily: "'Syne Mono', monospace",
                }}>
                  {r.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Calls table */}
        <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "1.4fr 140px 110px 100px 90px 90px 80px",
            padding: "10px 20px", background: C.card, borderBottom: `1px solid ${C.border}`,
          }}>
            {["Caller Name", "Phone", "Date", "Duration", "Outcome", "Score", ""].map(col => (
              <span key={col} style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1 }}>
                {col}
              </span>
            ))}
          </div>

          {loading ? (
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
              {[1,2,3,4,5].map(i => <Skeleton key={i} height={50} />)}
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: "48px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
              {dateFilter || outcomeFilter !== "all" || scoreRange > 0
                ? "No calls match this filter."
                : "No calls recorded yet. Calls will appear here once your AI receptionist goes live."}
            </div>
          ) : filtered.map(call => {
            const outcome = call.outcome || call.status || "unknown";
            const outcomeColor = {
              completed: C.green, booked: C.cyan, failed: C.red, voicemail: C.purple, no_answer: C.muted,
            }[outcome] || C.muted;

            return (
              <div
                key={call.call_id}
                style={{
                  display: "grid", gridTemplateColumns: "1.4fr 140px 110px 100px 90px 90px 80px",
                  padding: "12px 20px", borderBottom: `1px solid ${C.border}`,
                  alignItems: "center", transition: "background .1s",
                }}
                onMouseEnter={e => e.currentTarget.style.background = h(C.white, 0.015)}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>
                    {call.caller_name || "Unknown"}
                  </div>
                  <div style={{ fontSize: 11, color: C.muted }}>ID: {(call.call_id || "").slice(0, 8)}…</div>
                </div>
                <div style={{ fontSize: 12, color: C.text }}>{call.from_phone || "—"}</div>
                <div style={{ fontSize: 12, color: C.text }}>
                  {call.started_at
                    ? new Date(call.started_at).toLocaleDateString("en-AU", { dateStyle: "short" })
                    : "—"}
                </div>
                <div style={{ fontSize: 13, color: C.text, fontFamily: "'Syne Mono', monospace" }}>
                  {call.duration_fmt || "0:00"}
                </div>
                <div>
                  <span style={{
                    fontSize: 10, color: outcomeColor,
                    background: h(outcomeColor, 0.1), border: `1px solid ${h(outcomeColor, 0.25)}`,
                    borderRadius: 10, padding: "2px 8px", fontFamily: "'Syne Mono', monospace",
                  }}>
                    {outcome.toUpperCase().replace(/_/g, " ")}
                  </span>
                </div>
                <div><ScoreBadge score={call.lead_score} /></div>
                <div>
                  <button onClick={() => openCall(call)} style={{
                    background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.25)}`,
                    color: C.cyan, borderRadius: 6, padding: "5px 12px",
                    fontSize: 11, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                  }}>
                    {loadingCall ? "…" : "VIEW"}
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
                borderRadius: 8, padding: "6px 14px", cursor: page === 0 ? "not-allowed" : "pointer", fontSize: 12,
              }}>← Prev</button>
            <span style={{ fontSize: 12, color: C.muted, display: "flex", alignItems: "center" }}>
              Page {page + 1} of {totalPages}
            </span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              style={{
                background: "transparent", border: `1px solid ${C.border}`,
                color: page >= totalPages - 1 ? C.muted : C.text,
                borderRadius: 8, padding: "6px 14px",
                cursor: page >= totalPages - 1 ? "not-allowed" : "pointer", fontSize: 12,
              }}>Next →</button>
          </div>
        )}
      </div>

      <TranscriptPanel call={selectedCall} onClose={() => setSelected(null)} />
    </div>
  );
}
