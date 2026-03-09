/**
 * ExperimentsPage — full experiment management view.
 * Shows active, paused, and completed experiments with confidence scores,
 * budget allocation, and status filtering.
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

const STATUS_META = {
  running:   { color: C.green,  label: "RUNNING"   },
  paused:    { color: C.amber,  label: "PAUSED"    },
  completed: { color: C.cyan,   label: "COMPLETED" },
  failed:    { color: C.red,    label: "FAILED"    },
  killed:    { color: C.muted,  label: "KILLED"    },
  pending:   { color: C.orange, label: "PENDING"   },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { color: C.muted, label: (status || "unknown").toUpperCase() };
  return (
    <span style={{
      fontSize: 10, fontFamily: "'Syne Mono', monospace",
      color: meta.color, background: h(meta.color, 0.1), border: `1px solid ${h(meta.color, 0.25)}`,
      borderRadius: 10, padding: "2px 9px",
    }}>
      {meta.label}
    </span>
  );
}

function ConfidenceBar({ score }) {
  const pct = Math.min(100, Math.round((score || 0) * 10));
  const col = score >= 8.5 ? C.green : score >= 5 ? C.amber : C.red;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: C.border, borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: col, borderRadius: 3, transition: "width .5s" }} />
      </div>
      <span className="mono" style={{ fontSize: 11, color: col, minWidth: 28 }}>
        {score != null ? Number(score).toFixed(1) : "—"}
      </span>
    </div>
  );
}

function Skeleton({ height = 16 }) {
  return (
    <div style={{
      width: "100%", height, borderRadius: 6,
      background: `linear-gradient(90deg, ${C.card} 25%, ${C.border} 50%, ${C.card} 75%)`,
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
    }} />
  );
}

const SHIMMER = `@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}`;

const ALL_STATUSES = ["all", "running", "paused", "pending", "completed", "failed", "killed"];

export default function ExperimentsPage() {
  const { apiFetch } = useAuth();
  const [experiments, setExperiments] = useState([]);
  const [loading, setLoading]         = useState(true);
  const [statusFilter, setStatus]     = useState("all");
  const [search, setSearch]           = useState("");
  const [limit, setLimit]             = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit });
      if (statusFilter !== "all") params.set("status", statusFilter);
      const r = await apiFetch(`/api/swarm/experiments?${params}`);
      const data = await r.json();
      setExperiments(data.experiments || []);
    } catch {
      setExperiments([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, statusFilter, limit]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const filtered = experiments.filter(e => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (e.name || e.title || "").toLowerCase().includes(q) ||
           (e.hypothesis || e.description || "").toLowerCase().includes(q);
  });

  const running = filtered.filter(e => e.status === "running").length;
  const totalBudget = filtered.reduce((s, e) => s + (e.budget_allocated || 0), 0);
  const avgConf = filtered.length
    ? (filtered.reduce((s, e) => s + (e.confidence_score || 0), 0) / filtered.length).toFixed(1)
    : "—";

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            EXPERIMENT LAB
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>
            Experiments{" "}
            <InfoTip text="Each experiment tests one variable in the solar lead gen process. Confidence score 0–10 determines auto-routing: 8.5+ auto-proceeds, 5–8.5 requires human approval, below 5 auto-kills." />
          </div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {running} running · {filtered.length} total · avg confidence {avgConf} · ${totalBudget.toFixed(0)} AUD allocated
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
          placeholder="Search experiments…"
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.text,
            borderRadius: 8, padding: "8px 14px", fontSize: 13, width: 240,
          }}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {ALL_STATUSES.map(s => {
            const active = statusFilter === s;
            const meta = STATUS_META[s] || { color: C.muted };
            const col = s === "all" ? C.muted : meta.color;
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
          {[20, 50, 100].map(n => <option key={n} value={n}>Last {n}</option>)}
        </select>
      </div>

      {/* KPI row */}
      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        {[
          { label: "Running",   value: running,                                               color: C.green  },
          { label: "Avg Conf",  value: avgConf,                                               color: C.amber  },
          { label: "Budget",    value: `$${totalBudget.toFixed(0)}`,                          color: C.cyan   },
          { label: "Completed", value: filtered.filter(e => e.status === "completed").length, color: C.purple },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: "16px 20px", flex: "1 1 120px",
          }}>
            <div className="mono" style={{ fontSize: 26, color, lineHeight: 1, marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 12, color: C.muted }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Cards grid */}
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
              <Skeleton height={18} />
              <div style={{ marginTop: 10 }}><Skeleton height={14} /></div>
              <div style={{ marginTop: 8 }}><Skeleton height={10} /></div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div style={{
          textAlign: "center", padding: "56px 20px",
          background: C.panel, border: `1px dashed ${C.border}`,
          borderRadius: 14, color: C.muted,
        }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>⚗</div>
          <div style={{ fontSize: 14, color: C.text, marginBottom: 6 }}>
            {experiments.length === 0 ? "No experiments yet" : "No experiments match this filter"}
          </div>
          <div style={{ fontSize: 13 }}>
            The General agent creates experiments automatically during each cycle.
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {filtered.map((exp, i) => {
            const title = exp.name || exp.title || `Experiment #${exp.id || i + 1}`;
            const desc  = exp.hypothesis || exp.description || "";
            const created = exp.created_at ? new Date(exp.created_at).toLocaleDateString("en-AU") : "—";
            const updated = exp.updated_at ? new Date(exp.updated_at).toLocaleDateString("en-AU") : null;
            return (
              <div
                key={exp.id || i}
                style={{
                  background: C.panel, border: `1px solid ${C.border}`,
                  borderRadius: 12, padding: "18px 20px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: C.white, marginBottom: 4 }}>{title}</div>
                    {desc && (
                      <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{desc}</div>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
                    <StatusBadge status={exp.status} />
                    {exp.budget_allocated > 0 && (
                      <span className="mono" style={{ fontSize: 11, color: C.amber }}>
                        ${exp.budget_allocated} AUD
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>
                    CONFIDENCE SCORE{" "}
                    <InfoTip text="Confidence 8.5+ = auto-proceeds · 5–8.5 = human gate required · below 5 = auto-killed" />
                  </div>
                  <ConfidenceBar score={exp.confidence_score} />
                </div>

                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  {exp.category && (
                    <span style={{ fontSize: 11, color: C.muted }}>
                      Category: <span style={{ color: C.text }}>{exp.category}</span>
                    </span>
                  )}
                  {exp.agent && (
                    <span style={{ fontSize: 11, color: C.muted }}>
                      Agent: <span style={{ color: C.cyan }}>{exp.agent}</span>
                    </span>
                  )}
                  <span style={{ fontSize: 11, color: C.muted }}>
                    Created: <span style={{ color: C.text }}>{created}</span>
                  </span>
                  {updated && updated !== created && (
                    <span style={{ fontSize: 11, color: C.muted }}>
                      Updated: <span style={{ color: C.text }}>{updated}</span>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ textAlign: "center", fontSize: 12, color: C.muted, paddingTop: 20 }}>
        Managed by The General agent · Kelly Criterion capital allocation
      </div>
    </div>
  );
}
