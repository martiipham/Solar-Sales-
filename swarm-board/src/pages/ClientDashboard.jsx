/**
 * ClientDashboard — simplified, client-facing view for solar SME clients.
 * Shows their company info, lead stats, pipeline performance, and recent leads.
 * No swarm internals, no jargon — clean and professional.
 */
import { useState, useEffect } from "react";
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

function StatCard({ label, value, sub, color = C.cyan, icon }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "22px 24px",
      flex: "1 1 160px",
    }}>
      {icon && <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>}
      <div className="mono" style={{ fontSize: 32, color, lineHeight: 1, marginBottom: 6 }}>{value}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: C.muted }}>{sub}</div>}
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
    }}>
      {score?.toFixed(1) ?? "—"}
    </span>
  );
}

function Skeleton({ width = "100%", height = 16, radius = 6 }) {
  return (
    <div style={{
      width, height,
      borderRadius: radius,
      background: `linear-gradient(90deg, ${C.card} 25%, ${C.border} 50%, ${C.card} 75%)`,
      backgroundSize: "200% 100%",
      animation: "shimmer 1.5s infinite",
    }} />
  );
}

const SHIMMER = `
  @keyframes shimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
`;

export default function ClientDashboard() {
  const { apiFetch, user } = useAuth();
  const [company, setCompany]   = useState(null);
  const [leads, setLeads]       = useState([]);
  const [metrics, setMetrics]   = useState(null);
  const [pipeline, setPipeline] = useState([]);
  const [loading, setLoading]   = useState(true);

  const clientId = user?.client_id;
  const accentColor = company?.primary_color || C.amber;

  useEffect(() => {
    const loadAll = async () => {
      try {
        const [companyRes, leadsRes, metricsRes, pipelineRes] = await Promise.allSettled([
          clientId
            ? apiFetch(`/api/companies/${clientId}`).then(r => r.ok ? r.json() : null)
            : Promise.resolve(null),
          apiFetch("/api/swarm/leads?limit=10").then(r => r.json()),
          apiFetch("/api/crm/metrics").then(r => r.json()),
          apiFetch("/api/crm/pipeline").then(r => r.json()),
        ]);
        if (companyRes.status === "fulfilled" && companyRes.value?.company) {
          setCompany(companyRes.value.company);
        }
        if (leadsRes.status === "fulfilled") setLeads(leadsRes.value.leads || []);
        if (metricsRes.status === "fulfilled") setMetrics(metricsRes.value.metrics || {});
        if (pipelineRes.status === "fulfilled") setPipeline(pipelineRes.value.stages || []);
      } finally {
        setLoading(false);
      }
    };
    loadAll();
  }, [clientId]); // eslint-disable-line

  const qualifiedLeads = leads.filter(l => (l.qualification_score || 0) >= 7);
  const avgScore = leads.length
    ? (leads.reduce((s, l) => s + (l.qualification_score || 0), 0) / leads.length).toFixed(1)
    : "—";

  return (
    <div style={{ flex: 1, overflow: "auto", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Company header banner */}
      <div style={{
        background: C.panel,
        borderBottom: `1px solid ${C.border}`,
        padding: "24px 32px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {company?.logo_url ? (
            <img
              src={company.logo_url}
              alt={company.name}
              style={{ height: 48, width: 48, objectFit: "contain", borderRadius: 10,
                       border: `1px solid ${C.border}` }}
            />
          ) : (
            <div style={{
              width: 48, height: 48, borderRadius: 10,
              background: h(accentColor, 0.15),
              border: `1px solid ${h(accentColor, 0.3)}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22,
            }}>☀️</div>
          )}
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: C.white }}>
              {loading ? <Skeleton width={200} height={22} /> : (company?.name || "Your Dashboard")}
            </div>
            <div style={{ fontSize: 13, color: C.muted, marginTop: 4 }}>
              {company?.address || "Solar Automation Platform"}
            </div>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right" }}>
            <div style={{ fontSize: 11, color: C.muted }}>Powered by</div>
            <div className="mono" style={{ fontSize: 13, color: accentColor }}>SOLAR SWARM</div>
          </div>
        </div>
      </div>

      <div style={{ padding: "28px 32px", display: "flex", flexDirection: "column", gap: 28 }}>

        {/* KPI cards */}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          {loading ? (
            [1,2,3,4].map(i => (
              <div key={i} style={{ flex: "1 1 160px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "22px 24px" }}>
                <Skeleton height={32} width={60} radius={4} />
                <div style={{ marginTop: 10 }}><Skeleton height={14} width={100} /></div>
              </div>
            ))
          ) : (
            <>
              <StatCard icon="👥" label="Total Leads" value={leads.length} sub="all time" color={accentColor} />
              <StatCard icon="⭐" label="Hot Leads" value={qualifiedLeads.length} sub="score 7+" color={C.green} />
              <StatCard icon="📊" label="Avg Score" value={avgScore} sub="out of 10" color={C.cyan} />
              <StatCard icon="🔄" label="CRM Contacts" value={metrics?.total_contacts || 0} sub={`+${metrics?.new_this_week || 0} this week`} color={C.purple} />
            </>
          )}
        </div>

        {/* Pipeline stages */}
        {pipeline.length > 0 && (
          <div style={{
            background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: "20px 24px",
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.white, marginBottom: 16 }}>
              Lead Pipeline
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {pipeline.map((stage, i) => {
                const cnt = stage.opportunityCount || stage.count || 0;
                const maxCnt = Math.max(...pipeline.map(s => s.opportunityCount || s.count || 0), 1);
                const pct = Math.round((cnt / maxCnt) * 100);
                const stageColor = [accentColor, C.cyan, C.green, C.purple, C.orange][i % 5];
                return (
                  <div key={i} style={{ flex: "1 1 120px", minWidth: 100 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: stageColor, fontWeight: 600,
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "75%" }}>
                        {stage.name || stage.stageName || `Stage ${i + 1}`}
                      </span>
                      <span className="mono" style={{ fontSize: 13, color: stageColor }}>{cnt}</span>
                    </div>
                    <div style={{ height: 8, background: C.border, borderRadius: 4 }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: stageColor,
                        borderRadius: 4, opacity: 0.8, transition: "width .5s ease" }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Recent leads table */}
        <div style={{
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 14, overflow: "hidden",
        }}>
          <div style={{ padding: "16px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.white }}>Recent Leads</div>
            <div style={{ fontSize: 12, color: C.muted }}>Last 10</div>
          </div>

          {loading ? (
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
              {[1,2,3].map(i => <Skeleton key={i} height={40} />)}
            </div>
          ) : leads.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
              No leads yet. Your AI automation will start delivering leads once configured.
            </div>
          ) : (
            <>
              {/* Table header */}
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 100px 140px 110px",
                padding: "10px 20px", background: C.card,
                borderBottom: `1px solid ${C.border}`,
              }}>
                {["Name", "Score", "Recommendation", "Status"].map(col => (
                  <span key={col} className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{col}</span>
                ))}
              </div>
              {leads.map(lead => (
                <div key={lead.id} style={{
                  display: "grid", gridTemplateColumns: "1fr 100px 140px 110px",
                  padding: "13px 20px", borderBottom: `1px solid ${C.border}`,
                  alignItems: "center",
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{lead.name || "Unknown"}</div>
                    <div style={{ fontSize: 11, color: C.muted }}>
                      {new Date(lead.created_at).toLocaleDateString("en-AU")}
                    </div>
                  </div>
                  <div><ScoreBadge score={lead.qualification_score} /></div>
                  <div style={{ fontSize: 12, color: C.text }}>
                    {lead.recommended_action || "—"}
                  </div>
                  <div>
                    <span style={{
                      fontSize: 10, fontFamily: "'Syne Mono', monospace",
                      color: lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted,
                      background: h(lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted, 0.1),
                      border: `1px solid ${h(lead.status === "converted" ? C.green : lead.status === "new" ? C.cyan : C.muted, 0.25)}`,
                      borderRadius: 10, padding: "2px 9px",
                    }}>
                      {(lead.status || "new").toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", fontSize: 12, color: C.muted, paddingBottom: 12 }}>
          Data refreshes every 30 seconds · Powered by Solar Swarm AI Automation
        </div>
      </div>
    </div>
  );
}
