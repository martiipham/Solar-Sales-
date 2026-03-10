/**
 * AgentsPage — Monitor and control the 5 active Solar Admin AI agents.
 *
 * Agents:
 *   Voice AI          — answers calls 24/7, qualifies leads via Retell
 *   Email Processor   — classifies emails, drafts replies, routes approvals
 *   Lead Qualification — scores leads 1-10 via GPT-4o or rule-based fallback
 *   Proposal Generator — generates solar installation proposals as HTML emails
 *   CRM Sync          — pulls GHL pipeline data every 30 minutes
 *
 * Fetches from: GET /api/agents/status
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

const C = {
  bg:      "#050810",
  panel:   "#080D1A",
  card:    "#0C1222",
  cardHov: "#101828",
  border:  "#132035",
  borderB: "#1E3050",
  amber:   "#F59E0B",
  amberL:  "#FCD34D",
  cyan:    "#22D3EE",
  green:   "#4ADE80",
  red:     "#F87171",
  orange:  "#FB923C",
  purple:  "#C084FC",
  blue:    "#60A5FA",
  teal:    "#2DD4BF",
  text:    "#CBD5E1",
  muted:   "#475569",
  dim:     "#1A2540",
  white:   "#F8FAFC",
};
const h   = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");
const mono = { fontFamily: "'Syne Mono', monospace" };

/* ─── Agent catalogue ─────────────────────────────────────────────────────── */
const AGENTS = [
  {
    id:         "voice",
    name:       "Voice AI",
    icon:       "🎙️",
    color:      C.purple,
    canDisable: true,
    schedule:   "Event-driven (inbound & outbound calls)",
    role:       "AI Phone Receptionist",
    what:       "Handles inbound and outbound solar sales calls 24/7 using Retell AI. Answers questions, qualifies leads conversationally, books assessments, and updates the CRM in real-time.",
    how: [
      "Retell AI routes inbound call → POST /voice/call-started",
      "Loads company KB: products, FAQs, objection scripts, rebates",
      "GPT-4o drives conversation with solar-specific system prompt",
      "Functions: qualify_lead, book_appointment, send_sms, update_crm, transfer_human",
      "Post-call: transcript analysed, lead scored, CRM updated, cost logged",
    ],
    inputs:  ["Retell AI webhook (call events)", "Company knowledge base", "Lead DB (caller lookup)"],
    outputs: ["Transcript + lead score", "CRM updates", "Booked appointments", "SMS confirmations"],
    businessValue: "One AI handles 100 calls simultaneously, 24/7. Replaces a $60k/yr receptionist. Hot leads are scored and escalated before a human ever picks up the phone.",
    statKey: "calls_today",
    statLabel: "Calls today",
  },
  {
    id:         "email",
    name:       "Email Processor",
    icon:       "📧",
    color:      C.cyan,
    canDisable: true,
    schedule:   "Event-driven (GHL inbound message webhook)",
    role:       "Email Triage & Reply Drafter",
    what:       "Classifies every inbound email by intent (quote request, complaint, booking, spam), scores urgency, drafts a reply using the company voice, and routes to the human approval queue for review before sending.",
    how: [
      "GHL webhook fires on new inbound message",
      "GPT-4o classifies: intent, urgency, sentiment",
      "Drafts reply using company KB tone and FAQs",
      "Score < 5 → Slack alert, human approval required before send",
      "Score ≥ 5 + safe intent → auto-queued for 15-minute send delay",
      "All emails logged to email_logs table",
    ],
    inputs:  ["GHL inbound message webhook", "Company KB (tone, FAQs, pricing)"],
    outputs: ["Classified intent + urgency", "Draft reply", "Approval queue entry", "Slack alert (high urgency)"],
    businessValue: "Eliminates manual email triage. Every lead gets a response in minutes, not hours. Admin staff only touch emails that genuinely need human judgment.",
    statKey: "emails_today",
    statLabel: "Emails today",
    statKey2: "pending_approvals",
    statLabel2: "Pending approvals",
  },
  {
    id:         "qualification",
    name:       "Lead Qualification",
    icon:       "🎯",
    color:      C.orange,
    canDisable: true,
    schedule:   "Event-driven (GHL webhook on new lead or post-call)",
    role:       "Lead Scoring & Hot Lead Routing",
    what:       "Scores every inbound solar lead 1–10 using GPT-4o across four criteria. Routes hot leads (score ≥ 7) to call_now, mid-range to nurture, low-value to disqualify. Score ≥ 8 fires a Slack HOT LEAD alert.",
    how: [
      "Triggered by GHL webhook or qualify_from_call() after a voice call",
      "Criteria: homeowner status (+3), monthly bill (+3), roof type (+2), location (+2)",
      "GPT-4o returns score, reason (2 sentences), recommended_action, key_signals",
      "Fallback: rule-based scoring when OpenAI unavailable",
      "Score ≥ 7 → call_now (triggers Retell outbound if configured)",
      "Score ≥ 8 → HOT LEAD Slack alert fired",
      "Result written to leads.score + recommended_action",
    ],
    inputs:  ["GHL webhook payload or call transcript", "Company KB (thresholds)"],
    outputs: ["Lead score 1–10", "recommended_action", "Slack alert (score ≥ 8)", "DB update"],
    businessValue: "Eliminates manual lead sorting. Sales team only talks to pre-qualified 7+ leads — conversion rates increase, wasted calls drop.",
    statKey: "leads_today",
    statLabel: "Leads scored today",
    statKey2: "avg_score",
    statLabel2: "Avg score today",
  },
  {
    id:         "proposal",
    name:       "Proposal Generator",
    icon:       "📄",
    color:      C.green,
    canDisable: true,
    schedule:   "Event-driven (called after lead qualifies)",
    role:       "Solar Installation Proposal Generator",
    what:       "Generates a tailored solar installation proposal for each qualified lead. Calculates system size from their bill, annual savings, STC rebate by state, payback period, and recommended equipment. Outputs a clean HTML email.",
    how: [
      "Triggered by generate_from_lead(lead_id) after qualification",
      "Calculates system_kw from monthly bill + state peak sun hours",
      "Calculates STC rebate: system_kw × deeming_years × zone_factor × $38",
      "Calculates annual savings and payback period",
      "Renders branded HTML email with KPI grid, equipment table, pricing range",
      "Saves to proposals table (status: draft)",
    ],
    inputs:  ["Lead record (monthly_bill, state, suburb, name)", "STC zone tables"],
    outputs: ["HTML proposal email", "Proposal DB record", "system_size_kw, est_annual_savings, payback_years"],
    businessValue: "Every qualified lead receives a personalised proposal automatically — no quotes sitting in someone's drafts folder. Proposal-to-call conversion improves when leads already have numbers.",
    statKey: "proposals_today",
    statLabel: "Proposals generated",
  },
  {
    id:         "crm_sync",
    name:       "CRM Sync",
    icon:       "🔄",
    color:      C.teal,
    canDisable: false,
    schedule:   "Every 30 minutes",
    role:       "GoHighLevel Pipeline Sync",
    what:       "Pulls live contact and pipeline data from GoHighLevel every 30 minutes. Writes to the local SQLite cache so the dashboard always reflects the current state of the CRM without hammering the GHL API.",
    how: [
      "APScheduler fires crm_sync every 30 minutes",
      "Calls GHL API: /contacts (recent), /pipelines (stage counts)",
      "Writes pipeline stage data to crm_cache table",
      "Logs sync run to agent_run_log",
      "Dashboard reads from cache — no live GHL calls needed for display",
    ],
    inputs:  ["GoHighLevel REST API (contacts, pipeline stages)"],
    outputs: ["crm_cache table", "agent_run_log entry", "Dashboard pipeline widget data"],
    businessValue: "Keeps the dashboard reflecting reality. Without this, the board shows stale data and you can't track where leads are in the pipeline.",
    statKey: "contacts_synced",
    statLabel: "Contacts in cache",
  },
];

/* ─── Toggle switch ───────────────────────────────────────────────────────── */
function Toggle({ enabled, onChange, disabled }) {
  return (
    <button
      onClick={() => !disabled && onChange(!enabled)}
      title={disabled ? "This agent cannot be disabled" : enabled ? "Click to disable" : "Click to enable"}
      style={{
        position: "relative",
        width: 40, height: 22,
        background: enabled ? (disabled ? C.muted : C.green) : C.dim,
        borderRadius: 11,
        border: `1px solid ${enabled ? (disabled ? C.muted : C.green) : C.border}`,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "all .2s",
        flexShrink: 0,
        opacity: disabled ? 0.5 : 1,
        padding: 0,
      }}
    >
      <span style={{
        position: "absolute",
        top: 2, left: enabled ? 20 : 2,
        width: 16, height: 16,
        background: C.white,
        borderRadius: "50%",
        transition: "left .2s",
        boxShadow: "0 1px 3px rgba(0,0,0,.4)",
      }} />
    </button>
  );
}

/* ─── Info panel (side sheet) ─────────────────────────────────────────────── */
function InfoPanel({ agent, isActive, onClose }) {
  if (!agent) return null;
  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0,
        background: "rgba(5,8,16,.7)", zIndex: 100,
      }} />
      <div style={{
        position: "fixed", top: 0, right: 0,
        width: 480, height: "100vh",
        background: C.panel,
        borderLeft: `1px solid ${C.borderB}`,
        zIndex: 101, overflowY: "auto",
        padding: "28px 28px 40px",
      }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <div style={{
              width: 48, height: 48, borderRadius: 12,
              background: h(agent.color, 0.12),
              border: `1px solid ${h(agent.color, 0.3)}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22,
            }}>
              {agent.icon}
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: C.white, marginBottom: 2 }}>
                {agent.name}
              </div>
              <span style={{
                fontSize: 10, ...mono,
                background: h(isActive ? agent.color : C.muted, 0.12),
                border: `1px solid ${h(isActive ? agent.color : C.muted, 0.25)}`,
                color: isActive ? agent.color : C.muted,
                borderRadius: 20, padding: "2px 8px",
              }}>
                {isActive ? "ACTIVE" : "DISABLED"}
              </span>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: `1px solid ${C.border}`,
            color: C.muted, borderRadius: 6, padding: "4px 8px",
            cursor: "pointer", fontSize: 16, lineHeight: 1,
          }}>×</button>
        </div>

        <PanelSection label="Role" color={agent.color}>
          <p style={{ margin: 0, color: C.text, fontSize: 14, lineHeight: 1.6 }}>{agent.role}</p>
        </PanelSection>

        <PanelSection label="Schedule" color={agent.color}>
          <div style={{
            ...mono, fontSize: 12,
            background: C.dim, border: `1px solid ${C.border}`,
            borderRadius: 6, padding: "8px 12px", color: C.amberL,
          }}>
            {agent.schedule}
          </div>
        </PanelSection>

        <PanelSection label="What it does" color={agent.color}>
          <p style={{ margin: 0, color: C.text, fontSize: 14, lineHeight: 1.7 }}>{agent.what}</p>
        </PanelSection>

        <PanelSection label="How it works" color={agent.color}>
          <ol style={{ margin: 0, paddingLeft: 18, color: C.text, fontSize: 13, lineHeight: 1.8 }}>
            {agent.how.map((step, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{step}</li>
            ))}
          </ol>
        </PanelSection>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <IOBox label="Inputs"  items={agent.inputs}  color={C.blue} />
          <IOBox label="Outputs" items={agent.outputs} color={C.green} />
        </div>

        <PanelSection label="Business value" color={C.amber}>
          <div style={{
            background: h(C.amber, 0.06),
            border: `1px solid ${h(C.amber, 0.2)}`,
            borderRadius: 8, padding: "12px 14px",
            color: C.amberL, fontSize: 13, lineHeight: 1.6,
          }}>
            {agent.businessValue}
          </div>
        </PanelSection>

        {!agent.canDisable && (
          <div style={{
            background: h(C.red, 0.06),
            border: `1px solid ${h(C.red, 0.2)}`,
            borderRadius: 8, padding: "12px 14px",
            color: C.red, fontSize: 12, marginTop: 4,
          }}>
            ⚠ This agent cannot be disabled — it is required for the dashboard.
          </div>
        )}
      </div>
    </>
  );
}

function PanelSection({ label, color, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 10, ...mono, color, letterSpacing: 2,
        marginBottom: 8, textTransform: "uppercase",
      }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function IOBox({ label, items, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, ...mono, color, letterSpacing: 2, marginBottom: 8 }}>
        {label.toUpperCase()}
      </div>
      <div style={{
        background: C.card, border: `1px solid ${C.border}`,
        borderRadius: 8, padding: "10px 12px",
      }}>
        {items.map((item, i) => (
          <div key={i} style={{
            fontSize: 12, color: C.text, lineHeight: 1.5,
            paddingBottom: i < items.length - 1 ? 6 : 0,
            marginBottom: i < items.length - 1 ? 6 : 0,
            borderBottom: i < items.length - 1 ? `1px solid ${C.dim}` : "none",
          }}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Agent card ──────────────────────────────────────────────────────────── */
function AgentCard({ agent, enabled, status, onToggle, onInfo }) {
  const [hov, setHov] = useState(false);
  const agentStatus = status?.status || (enabled ? "idle" : "disabled");
  const isRunning   = agentStatus === "running" || agentStatus === "active";
  const isError     = agentStatus === "error";
  const dotColor    = !enabled ? C.muted : isError ? C.red : isRunning ? C.green : h(agent.color, 0.7);
  const statusLabel = !enabled ? "DISABLED" : isError ? "ERROR" : isRunning ? "RUNNING" : "IDLE";

  const lastRun = status?.last_run
    ? new Date(status.last_run).toLocaleString("en-AU", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
      })
    : null;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.cardHov : C.card,
        border: `1px solid ${enabled ? h(agent.color, 0.3) : C.border}`,
        borderRadius: 12, padding: "18px 20px",
        transition: "all .15s",
        opacity: enabled ? 1 : 0.55,
        display: "flex", flexDirection: "column", gap: 14,
      }}
    >
      {/* Top row */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{
          width: 42, height: 42, borderRadius: 10, flexShrink: 0,
          background: h(agent.color, 0.12),
          border: `1px solid ${h(agent.color, enabled ? 0.3 : 0.1)}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, position: "relative",
        }}>
          {agent.icon}
          {isRunning && (
            <span style={{
              position: "absolute", top: -3, right: -3,
              width: 8, height: 8, borderRadius: "50%",
              background: C.green, boxShadow: `0 0 6px ${C.green}`,
            }} />
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 14, fontWeight: 600,
            color: enabled ? C.white : C.muted,
            marginBottom: 2,
          }}>
            {agent.name}
          </div>
          <div style={{ fontSize: 11, color: enabled ? agent.color : C.muted }}>
            {agent.role}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <button
            onClick={() => onInfo(agent)}
            title="View agent details"
            style={{
              background: "transparent",
              border: `1px solid ${hov ? C.border : "transparent"}`,
              color: C.muted, borderRadius: 6,
              width: 26, height: 26, padding: 0,
              cursor: "pointer", fontSize: 13,
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all .15s",
            }}
          >
            ℹ
          </button>
          <Toggle
            enabled={enabled}
            onChange={onToggle}
            disabled={!agent.canDisable}
          />
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {agent.statKey && (
          <StatChip
            value={status?.[agent.statKey] ?? "—"}
            label={agent.statLabel}
            color={agent.color}
            enabled={enabled}
          />
        )}
        {agent.statKey2 && (
          <StatChip
            value={status?.[agent.statKey2] ?? "—"}
            label={agent.statLabel2}
            color={agent.color}
            enabled={enabled}
          />
        )}
      </div>

      {/* Bottom row: status + last run */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: dotColor,
            boxShadow: isRunning ? `0 0 5px ${C.green}` : "none",
          }} />
          <span style={{ fontSize: 10, ...mono, color: C.muted }}>
            {statusLabel}
          </span>
        </div>
        {lastRun && enabled && (
          <div style={{ fontSize: 10, color: C.muted, ...mono }}>
            Last run: {lastRun}
          </div>
        )}
      </div>
    </div>
  );
}

function StatChip({ value, label, color, enabled }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{
        fontSize: 18, fontWeight: 700, ...mono,
        color: enabled ? color : C.muted,
        lineHeight: 1,
      }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{label}</div>
    </div>
  );
}

/* ─── Main page ───────────────────────────────────────────────────────────── */
export default function AgentsPage() {
  const { apiFetch } = useAuth();
  const [agentState,    setAgentState]    = useState({});
  const [statusData,    setStatusData]    = useState({});
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [saving,        setSaving]        = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [toast,         setToast]         = useState(null);

  const loadStatus = useCallback(async () => {
    try {
      const r = await apiFetch("/api/agents/status");
      if (r.ok) {
        const data = await r.json();
        const enabled = {};
        const stats   = {};
        Object.entries(data.agents || {}).forEach(([id, info]) => {
          enabled[id] = info.enabled !== false;
          stats[id]   = info;
        });
        setAgentState(enabled);
        setStatusData(stats);
      } else {
        const defaults = {};
        AGENTS.forEach(a => { defaults[a.id] = true; });
        setAgentState(defaults);
      }
    } catch {
      const defaults = {};
      AGENTS.forEach(a => { defaults[a.id] = true; });
      setAgentState(defaults);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);
  useEffect(() => {
    const t = setInterval(loadStatus, 30000);
    return () => clearInterval(t);
  }, [loadStatus]);

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

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
      showToast(`${agent.name} ${newVal ? "enabled" : "disabled"}`);
    } catch {
      setAgentState(prev => ({ ...prev, [agent.id]: !newVal }));
      showToast("Failed to save — check API connection", false);
    } finally {
      setSaving(null);
    }
  };

  const activeCount = AGENTS.filter(a => agentState[a.id] !== false).length;

  if (loading) {
    return (
      <div style={{
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
        background: C.bg,
      }}>
        <div style={{ ...mono, fontSize: 12, color: C.amber, letterSpacing: 2 }}>
          LOADING AGENTS…
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: C.bg, overflow: "hidden" }}>

      {/* Header */}
      <div style={{
        padding: "20px 28px 16px",
        borderBottom: `1px solid ${C.border}`,
        flexShrink: 0,
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
      }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: C.white }}>
            AI Agents
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: C.muted }}>
            Monitor, understand, and control the 5 active agents. Refreshes every 30 seconds.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Pill color={C.green}>{activeCount} Active</Pill>
          {activeCount < AGENTS.length && (
            <Pill color={C.muted}>{AGENTS.length - activeCount} Disabled</Pill>
          )}
        </div>
      </div>

      {/* Grid */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px 40px" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 14,
        }}>
          {AGENTS.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              enabled={agentState[agent.id] !== false}
              status={statusData[agent.id]}
              onToggle={v => handleToggle(agent, v)}
              onInfo={a => setSelectedAgent(a)}
            />
          ))}
        </div>

        {/* Legend */}
        <div style={{
          marginTop: 24, padding: "14px 18px",
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 10, fontSize: 12, color: C.muted,
          display: "flex", gap: 24, flexWrap: "wrap",
        }}>
          <span><span style={{ color: C.green }}>●</span> Running — currently executing</span>
          <span><span style={{ color: C.amber }}>●</span> Idle — waiting for next trigger</span>
          <span><span style={{ color: C.red }}>●</span> Error — check logs</span>
          <span><span style={{ color: C.muted }}>●</span> Disabled — skipped when triggered</span>
          <span style={{ marginLeft: "auto" }}>⚠ CRM Sync cannot be disabled</span>
        </div>
      </div>

      <InfoPanel agent={selectedAgent} isActive={selectedAgent ? agentState[selectedAgent.id] !== false : true} onClose={() => setSelectedAgent(null)} />

      {toast && (
        <div style={{
          position: "fixed", bottom: 28, right: 28, zIndex: 200,
          background: toast.ok ? h(C.green, 0.15) : h(C.red, 0.15),
          border: `1px solid ${toast.ok ? h(C.green, 0.4) : h(C.red, 0.4)}`,
          color: toast.ok ? C.green : C.red,
          borderRadius: 8, padding: "10px 18px",
          fontSize: 13, ...mono,
          boxShadow: "0 4px 20px rgba(0,0,0,.4)",
        }}>
          {toast.ok ? "✓" : "✗"} {toast.msg}
        </div>
      )}
    </div>
  );
}

function Pill({ color, children }) {
  return (
    <span style={{
      fontSize: 11, ...mono,
      background: h(color, 0.1),
      border: `1px solid ${h(color, 0.25)}`,
      color, borderRadius: 20, padding: "3px 12px",
    }}>
      {children}
    </span>
  );
}
