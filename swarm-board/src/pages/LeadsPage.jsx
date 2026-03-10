/**
 * LeadsPage — lead pipeline with scoring, actions, and per-lead operations.
 * Fetches from GET /api/leads
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";
import InfoTip from "../components/InfoTip";

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

function Skeleton({ width = "100%", height = 16 }) {
  return (
    <div style={{
      width, height, borderRadius: 6,
      background: `linear-gradient(90deg,${C.card} 25%,${C.border} 50%,${C.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

function ScoreBadge({ score }) {
  const val = score != null ? Number(score) : null;
  const color = val == null ? C.muted : val >= 7 ? C.green : val >= 4 ? C.amber : C.red;
  return (
    <span style={{
      display: "inline-block",
      background: h(color, 0.15), border: `1px solid ${h(color, 0.35)}`,
      color, borderRadius: 6, padding: "2px 9px",
      fontSize: 12, fontFamily: "'Syne Mono', monospace",
    }}>
      {val != null ? val.toFixed(1) : "—"}
    </span>
  );
}

function ActionPill({ action }) {
  const colorMap = {
    "call_now":        C.green,
    "schedule_call":   C.cyan,
    "send_proposal":   C.amber,
    "nurture":         C.purple,
    "disqualify":      C.red,
  };
  const key = (action || "").toLowerCase().replace(/\s+/g, "_");
  const color = colorMap[key] || C.muted;
  return (
    <span style={{
      fontSize: 10, fontFamily: "'Syne Mono', monospace",
      color, background: h(color, 0.1), border: `1px solid ${h(color, 0.25)}`,
      borderRadius: 10, padding: "2px 9px", whiteSpace: "nowrap",
    }}>
      {action ? action.toUpperCase().replace(/_/g, " ") : "—"}
    </span>
  );
}

function StatusPill({ status }) {
  const colorMap = { converted: C.green, new: C.cyan, qualified: C.amber, rejected: C.red };
  const col = colorMap[status] || C.muted;
  return (
    <span style={{
      fontSize: 10, fontFamily: "'Syne Mono', monospace",
      color: col, background: h(col, 0.1), border: `1px solid ${h(col, 0.25)}`,
      borderRadius: 10, padding: "2px 9px",
    }}>
      {(status || "new").toUpperCase()}
    </span>
  );
}

function LeadDetailModal({ lead, onClose, onAction }) {
  if (!lead) return null;
  const fields = lead.extracted_data || {};
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
          borderRadius: 18, padding: 28, width: "100%", maxWidth: 560,
          maxHeight: "84vh", overflow: "auto",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, color: C.white }}>{lead.name || "Unknown Lead"}</div>
            <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
              {lead.phone || "—"} · {lead.suburb || "—"}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 8, padding: "5px 12px", cursor: "pointer", fontSize: 12,
          }}>✕ Close</button>
        </div>

        {/* Score + status row */}
        <div style={{
          background: C.card, border: `1px solid ${C.border}`,
          borderRadius: 10, padding: "12px 16px", marginBottom: 20,
          display: "flex", gap: 24, flexWrap: "wrap",
        }}>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>SCORE</div>
            <ScoreBadge score={lead.qualification_score} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>STATUS</div>
            <StatusPill status={lead.status} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>ACTION</div>
            <ActionPill action={lead.recommended_action} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>SOURCE</div>
            <span style={{ fontSize: 12, color: C.text }}>{lead.source || "—"}</span>
          </div>
        </div>

        {/* Extracted data */}
        {Object.keys(fields).length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1, marginBottom: 10 }}>
              EXTRACTED DATA
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {Object.entries(fields).map(([k, v]) => (
                <div key={k} style={{
                  display: "flex", justifyContent: "space-between",
                  background: C.card, border: `1px solid ${C.border}`,
                  borderRadius: 8, padding: "8px 12px",
                }}>
                  <span style={{ fontSize: 12, color: C.muted }}>{k.replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 12, color: C.text }}>{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button
            onClick={() => onAction("proposal", lead)}
            style={{
              flex: 1, background: h(C.amber, 0.12), border: `1px solid ${h(C.amber, 0.35)}`,
              color: C.amber, borderRadius: 8, padding: "10px 16px",
              cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
            }}
          >
            ✦ GENERATE PROPOSAL
          </button>
          <button
            onClick={() => onAction("called", lead)}
            style={{
              flex: 1, background: h(C.green, 0.1), border: `1px solid ${h(C.green, 0.3)}`,
              color: C.green, borderRadius: 8, padding: "10px 16px",
              cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
            }}
          >
            ✓ MARK CALLED
          </button>
        </div>
      </div>
    </div>
  );
}

const STATUS_OPTS = ["all", "new", "qualified", "converted", "rejected"];
const ACTION_OPTS = ["all", "call_now", "schedule_call", "send_proposal", "nurture", "disqualify"];
const SCORE_RANGES = [
  { label: "All Scores", min: 0,  max: 10 },
  { label: "Hot (7–10)",  min: 7,  max: 10 },
  { label: "Warm (4–6)",  min: 4,  max: 6.9 },
  { label: "Cold (0–3)",  min: 0,  max: 3.9 },
];

export default function LeadsPage() {
  const { apiFetch } = useAuth();
  const [leads, setLeads]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [statusFilter, setStatus]   = useState("all");
  const [actionFilter, setAction]   = useState("all");
  const [scoreRange, setScoreRange] = useState(0);
  const [search, setSearch]         = useState("");
  const [limit, setLimit]           = useState(50);
  const [selectedLead, setSelected] = useState(null);
  const [toast, setToast]           = useState(null);

  const showToast = (msg, color = C.green) => {
    setToast({ msg, color });
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const r = await apiFetch(`/api/leads?${params}`);
      const data = await r.json();
      setLeads(data.leads || []);
    } catch {
      setLeads([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, statusFilter, limit]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const handleAction = async (type, lead) => {
    setSelected(null);
    if (type === "proposal") {
      try {
        await apiFetch(`/api/leads/${lead.id}/proposal`, { method: "POST" });
        showToast("Proposal generation triggered");
      } catch {
        showToast("Failed to generate proposal", C.red);
      }
    } else if (type === "called") {
      try {
        await apiFetch(`/api/leads/${lead.id}/mark-called`, { method: "POST" });
        showToast("Lead marked as called");
        load();
      } catch {
        showToast("Failed to update lead", C.red);
      }
    }
  };

  const range = SCORE_RANGES[scoreRange];
  const filtered = leads.filter(l => {
    const score = l.qualification_score || 0;
    if (score < range.min || score > range.max) return false;
    if (actionFilter !== "all") {
      const act = (l.recommended_action || "").toLowerCase().replace(/\s+/g, "_");
      if (act !== actionFilter) return false;
    }
    if (!search) return true;
    const q = search.toLowerCase();
    return (l.name || "").toLowerCase().includes(q) ||
           (l.phone || "").includes(q) ||
           (l.suburb || "").toLowerCase().includes(q) ||
           (l.source || "").toLowerCase().includes(q);
  });

  const avgScore = filtered.length
    ? (filtered.reduce((s, l) => s + (l.qualification_score || 0), 0) / filtered.length).toFixed(1)
    : "—";
  const hotCount = filtered.filter(l => (l.qualification_score || 0) >= 7).length;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 28, right: 28, zIndex: 2000,
          background: C.panel, border: `1px solid ${h(toast.color, 0.4)}`,
          color: toast.color, borderRadius: 10, padding: "12px 20px",
          fontSize: 13, fontFamily: "'Syne Mono', monospace",
          boxShadow: `0 4px 20px ${h(toast.color, 0.2)}`,
        }}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            LEAD PIPELINE
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>
            Leads{" "}
            <InfoTip text="Inbound leads scored 0–10 by the AI qualification agent using 5 signals: homeowner status, power bill size, roof suitability, location, and urgency." />
          </div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {filtered.length} leads · avg score {avgScore} · {hotCount} hot (7+)
          </div>
        </div>
        <button
          onClick={load}
          style={{
            background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.3)}`,
            color: C.cyan, padding: "9px 18px", borderRadius: 8,
            cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
          }}
        >
          ↻ REFRESH
        </button>
      </div>

      {/* KPI row */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        {[
          { label: "Total",     value: filtered.length,                                                    color: C.cyan   },
          { label: "Hot (7+)",  value: hotCount,                                                           color: C.green  },
          { label: "Avg Score", value: avgScore,                                                           color: C.amber  },
          { label: "Converted", value: filtered.filter(l => l.status === "converted").length,              color: C.purple },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: "16px 20px", flex: "1 1 120px",
          }}>
            <div className="mono" style={{ fontSize: 28, color, lineHeight: 1, marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 12, color: C.muted }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search name, phone, suburb…"
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.text,
            borderRadius: 8, padding: "8px 14px", fontSize: 13, width: 220,
            outline: "none",
          }}
        />

        {/* Score range */}
        <div style={{ display: "flex", gap: 6 }}>
          {SCORE_RANGES.map((r, i) => {
            const active = scoreRange === i;
            const col = i === 1 ? C.green : i === 2 ? C.amber : i === 3 ? C.red : C.muted;
            return (
              <button key={i} onClick={() => setScoreRange(i)} style={{
                background: active ? h(col, 0.15) : "transparent",
                border: `1px solid ${active ? col : C.border}`,
                color: active ? col : C.muted,
                borderRadius: 7, padding: "6px 11px",
                cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
              }}>
                {r.label}
              </button>
            );
          })}
        </div>

        {/* Status */}
        <div style={{ display: "flex", gap: 5 }}>
          {STATUS_OPTS.map(s => {
            const active = statusFilter === s;
            const col = { converted: C.green, new: C.cyan, qualified: C.amber, rejected: C.red }[s] || C.muted;
            return (
              <button key={s} onClick={() => setStatus(s)} style={{
                background: active ? h(col, 0.15) : "transparent",
                border: `1px solid ${active ? col : C.border}`,
                color: active ? col : C.muted,
                borderRadius: 7, padding: "6px 11px",
                cursor: "pointer", fontSize: 10, fontFamily: "'Syne Mono', monospace",
              }}>
                {s.toUpperCase()}
              </button>
            );
          })}
        </div>

        {/* Action filter */}
        <select
          value={actionFilter}
          onChange={e => setAction(e.target.value)}
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 7, padding: "7px 10px", fontSize: 12,
          }}
        >
          {ACTION_OPTS.map(a => (
            <option key={a} value={a}>{a === "all" ? "All Actions" : a.replace(/_/g, " ")}</option>
          ))}
        </select>

        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 7, padding: "7px 10px", fontSize: 12, marginLeft: "auto",
          }}
        >
          {[20, 50, 100, 200].map(n => <option key={n} value={n}>Last {n}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={{
        background: C.panel, border: `1px solid ${C.border}`,
        borderRadius: 14, overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1.4fr 120px 120px 80px 160px 100px 110px 110px 120px",
          padding: "10px 16px", background: C.card, borderBottom: `1px solid ${C.border}`,
        }}>
          {["Name", "Phone", "Suburb", "Score", "Recommended Action", "Status", "Source", "Created At", "Actions"].map(col => (
            <span key={col} className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{col}</span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
            {[1,2,3,4,5].map(i => <Skeleton key={i} height={46} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
            {leads.length === 0
              ? "No leads yet. The qualification agent will score inbound leads as they arrive."
              : "No leads match this filter."}
          </div>
        ) : (
          filtered.map(lead => (
            <div
              key={lead.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1.4fr 120px 120px 80px 160px 100px 110px 110px 120px",
                padding: "12px 16px", borderBottom: `1px solid ${C.border}`,
                alignItems: "center", transition: "background .1s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = h(C.white, 0.015)}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                <div style={{ fontSize: 11, color: C.muted }}>ID #{lead.id}</div>
              </div>
              <div style={{ fontSize: 12, color: C.text }}>{lead.phone || "—"}</div>
              <div style={{ fontSize: 12, color: C.text }}>{lead.suburb || "—"}</div>
              <div><ScoreBadge score={lead.qualification_score} /></div>
              <div><ActionPill action={lead.recommended_action} /></div>
              <div><StatusPill status={lead.status} /></div>
              <div style={{ fontSize: 11, color: C.muted }}>{lead.source || "—"}</div>
              <div style={{ fontSize: 11, color: C.muted }}>
                {lead.created_at ? new Date(lead.created_at).toLocaleDateString("en-AU") : "—"}
              </div>
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                <button
                  onClick={() => setSelected(lead)}
                  style={{
                    background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.25)}`,
                    color: C.cyan, borderRadius: 6, padding: "4px 9px",
                    fontSize: 10, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                  }}
                >
                  VIEW
                </button>
                <button
                  onClick={() => handleAction("proposal", lead)}
                  style={{
                    background: h(C.amber, 0.1), border: `1px solid ${h(C.amber, 0.25)}`,
                    color: C.amber, borderRadius: 6, padding: "4px 9px",
                    fontSize: 10, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                  }}
                >
                  PROP
                </button>
                <button
                  onClick={() => handleAction("called", lead)}
                  style={{
                    background: h(C.green, 0.08), border: `1px solid ${h(C.green, 0.25)}`,
                    color: C.green, borderRadius: 6, padding: "4px 9px",
                    fontSize: 10, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                  }}
                >
                  ✓
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ textAlign: "center", fontSize: 12, color: C.muted, paddingTop: 16 }}>
        Scored by AI qualification agent · {filtered.length} of {leads.length} shown
      </div>

      <LeadDetailModal lead={selectedLead} onClose={() => setSelected(null)} onAction={handleAction} />
    </div>
  );
}
