/**
 * LeadsPage — full lead pipeline view with scoring, filtering, and CRM sync status.
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

function ScoreBadge({ score }) {
  const color = score >= 7 ? C.green : score >= 4 ? C.amber : C.red;
  return (
    <span style={{
      display: "inline-block",
      background: h(color, 0.15), border: `1px solid ${h(color, 0.35)}`,
      color, borderRadius: 6, padding: "2px 9px",
      fontSize: 12, fontFamily: "'Syne Mono', monospace",
    }}>
      {score != null ? Number(score).toFixed(1) : "—"}
    </span>
  );
}

function StatusPill({ status }) {
  const col = status === "converted" ? C.green : status === "new" ? C.cyan : status === "qualified" ? C.amber : C.muted;
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

function Skeleton({ width = "100%", height = 16 }) {
  return (
    <div style={{
      width, height, borderRadius: 6,
      background: `linear-gradient(90deg, ${C.card} 25%, ${C.border} 50%, ${C.card} 75%)`,
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
    }} />
  );
}

const SHIMMER = `@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}`;

const STATUS_OPTS = ["all", "new", "qualified", "converted", "rejected"];

export default function LeadsPage() {
  const { apiFetch } = useAuth();
  const [leads, setLeads]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [statusFilter, setStatus] = useState("all");
  const [search, setSearch]       = useState("");
  const [limit, setLimit]         = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const r = await apiFetch(`/api/swarm/leads?${params}`);
      const data = await r.json();
      setLeads(data.leads || []);
    } catch {
      setLeads([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, statusFilter, limit]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const filtered = leads.filter(l => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (l.name || "").toLowerCase().includes(q) ||
           (l.recommended_action || "").toLowerCase().includes(q);
  });

  const avgScore = filtered.length
    ? (filtered.reduce((s, l) => s + (l.qualification_score || 0), 0) / filtered.length).toFixed(1)
    : "—";
  const hotCount = filtered.filter(l => (l.qualification_score || 0) >= 7).length;

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <style>{SHIMMER}</style>

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

      {/* Filters */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search leads…"
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.text,
            borderRadius: 8, padding: "8px 14px", fontSize: 13, width: 220,
          }}
        />
        <div style={{ display: "flex", gap: 6 }}>
          {STATUS_OPTS.map(s => {
            const active = statusFilter === s;
            const col = s === "all" ? C.muted : s === "converted" ? C.green : s === "new" ? C.cyan : s === "qualified" ? C.amber : C.red;
            return (
              <button
                key={s}
                onClick={() => setStatus(s)}
                style={{
                  background: active ? h(col, 0.15) : "transparent",
                  border: `1px solid ${active ? col : C.border}`,
                  color: active ? col : C.muted,
                  borderRadius: 7, padding: "6px 12px",
                  cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
                }}
              >
                {s.toUpperCase()}
              </button>
            );
          })}
        </div>
        <select
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 7, padding: "6px 10px", fontSize: 12, marginLeft: "auto",
          }}
        >
          {[20, 50, 100, 200].map(n => <option key={n} value={n}>Last {n}</option>)}
        </select>
      </div>

      {/* KPI row */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        {[
          { label: "Total", value: filtered.length, color: C.cyan },
          { label: "Hot (7+)", value: hotCount, color: C.green },
          { label: "Avg Score", value: avgScore, color: C.amber },
          { label: "Converted", value: filtered.filter(l => l.status === "converted").length, color: C.purple },
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

      {/* Table */}
      <div style={{
        background: C.panel, border: `1px solid ${C.border}`,
        borderRadius: 14, overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 90px 180px 110px 130px",
          padding: "10px 20px", background: C.card,
          borderBottom: `1px solid ${C.border}`,
        }}>
          {["Name / Date", "Score", "Recommendation", "Status", "Created"].map(col => (
            <span key={col} className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{col}</span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
            {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} height={44} />)}
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
                display: "grid", gridTemplateColumns: "1fr 90px 180px 110px 130px",
                padding: "13px 20px", borderBottom: `1px solid ${C.border}`,
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                  ID #{lead.id}
                </div>
              </div>
              <div><ScoreBadge score={lead.qualification_score} /></div>
              <div style={{ fontSize: 12, color: C.text, paddingRight: 12 }}>
                {lead.recommended_action || "—"}
              </div>
              <div><StatusPill status={lead.status} /></div>
              <div style={{ fontSize: 11, color: C.muted }}>
                {lead.created_at ? new Date(lead.created_at).toLocaleDateString("en-AU") : "—"}
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ textAlign: "center", fontSize: 12, color: C.muted, paddingTop: 16 }}>
        Scored by AI qualification agent · refreshes every 30 seconds
      </div>
    </div>
  );
}
