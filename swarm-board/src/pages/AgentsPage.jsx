/**
 * AgentsPage — View, understand, and control every agent in the swarm.
 *
 * Features:
 *   - Grouped by tier (Command / Department Heads / Workers / System)
 *   - Toggle each agent on or off (persisted to backend)
 *   - ℹ info panel: role, schedule, inputs, outputs, business purpose
 *   - Live last-run / next-run from backend
 */
import { useState, useEffect, useCallback } from "react";

const API = "http://localhost:5003";

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
  pink:    "#F472B6",
  teal:    "#2DD4BF",
  text:    "#CBD5E1",
  muted:   "#475569",
  dim:     "#1A2540",
  white:   "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");
const mono = { fontFamily: "'Syne Mono', monospace" };

/* ─────────────────────────────────────────────────────────────
   AGENT CATALOGUE — complete business + functional definition
───────────────────────────────────────────────────────────── */
const AGENT_CATALOGUE = [
  // ── Tier 1 ─────────────────────────────────────────────────
  {
    id:          "general",
    jobId:       "general",
    name:        "The General",
    icon:        "⚡",
    color:       C.amber,
    tier:        1,
    tierLabel:   "Command",
    schedule:    "Every 6 hours",
    canDisable:  false,
    role:        "Strategic Command & Experiment Generation",
    what:        "The top-level strategic brain of the swarm. Every 6 hours it uses GPT-4o to generate 3 new experiment ideas targeting Australian solar SMEs, scores each across 4 dimensions, then routes them automatically.",
    how: [
      "Reads active experiments + past learnings from memory",
      "Calls GPT-4o to generate 3 ranked experiment ideas",
      "Scores each idea: market signal, competitive gap, execution speed, revenue path (0–10 each)",
      "Runs Red Team counter-analysis to stress-test each idea",
      "Routes by confidence: >8.5 = auto-proceed, 5–8.5 = human gate, <5 = auto-kill",
      "Allocates budget via 25% Fractional Kelly Criterion",
      "Posts Slack alert for human-gate experiments",
    ],
    inputs:  ["Hot memory (active experiments)", "Warm memory (winning patterns)", "Kelly engine", "Red team agent"],
    outputs: ["New experiments in database", "Slack human-gate alerts", "Budget allocations", "Pheromone signals"],
    businessValue: "Core revenue engine — finds the next experiment that could close a $1,500/month retainer. Without it the swarm has no direction.",
  },

  // ── Tier 2 ─────────────────────────────────────────────────
  {
    id:          "research",
    jobId:       "department_heads",
    name:        "Research Head",
    icon:        "🔬",
    color:       C.cyan,
    tier:        2,
    tierLabel:   "Department Head",
    schedule:    "Daily 09:00 UTC (7pm AEST)",
    canDisable:  true,
    role:        "Market Intelligence & Prospect Research",
    what:        "Department head that manages the research task queue. Pulls pending research tasks, dispatches them to Tier 3 workers, and synthesises findings back into memory and pheromone signals.",
    how: [
      "Polls hot memory for next research task in queue",
      "Dispatches tasks to specialist workers: solar_research, prospect_researcher",
      "Aggregates findings into warm memory (learnings)",
      "Posts pheromone signals to reinforce high-value research areas",
      "Logs completed tasks to cold ledger",
    ],
    inputs:  ["Research task queue (hot memory)", "Knowledge graph", "Collected data pipeline"],
    outputs: ["Warm memory learnings", "Pheromone signals", "Research findings in DB"],
    businessValue: "Keeps the swarm informed about the AU solar market — competitor gaps, prospect pain points, pricing benchmarks. Drives smarter experiment ideas from The General.",
  },
  {
    id:          "content",
    jobId:       "department_heads",
    name:        "Content Head",
    icon:        "✍️",
    color:       C.purple,
    tier:        2,
    tierLabel:   "Department Head",
    schedule:    "Daily 09:00 UTC (7pm AEST)",
    canDisable:  true,
    role:        "Ad Copy, Emails & Proposals",
    what:        "Department head for all content production. Manages the content task queue and dispatches to Tier 3 workers to produce ad copy, email sequences, landing pages, and client proposals.",
    how: [
      "Polls hot memory for next content task",
      "Dispatches to content workers: proposal_agent, report_agent",
      "Uses GPT-4o with solar-specific system prompts for AU market",
      "Outputs copy directly into the task result for human review",
      "Logs completions to cold ledger",
    ],
    inputs:  ["Content task queue (hot memory)", "Company KB (client voice & tone)", "Research findings"],
    outputs: ["Ad copy", "Email sequences", "Client proposals", "Weekly reports"],
    businessValue: "Replaces $3,000+/month of copywriter spend. Every solar client gets bespoke AU-English content at near-zero marginal cost.",
  },
  {
    id:          "analytics",
    jobId:       "department_heads",
    name:        "Analytics Head",
    icon:        "📊",
    color:       C.green,
    tier:        2,
    tierLabel:   "Department Head",
    schedule:    "Daily 09:00 UTC (7pm AEST)",
    canDisable:  false,
    role:        "Performance Tracking & Circuit Breakers",
    what:        "Monitors experiment performance, lead conversion rates, and budget burn. Triggers circuit breakers when failure thresholds are hit, protecting the weekly budget.",
    how: [
      "Reads active experiments + lead conversion data from DB",
      "Calculates budget burn rate vs weekly plan",
      "Counts consecutive experiment failures",
      "Calls circuit_breaker.check_and_trigger() — Yellow/Orange/Red",
      "Synthesises pheromone signals from performance data",
      "Posts Slack alert if breaker triggers",
    ],
    inputs:  ["Active experiments (hot memory)", "Lead conversion data", "Budget tracker", "Circuit breaker state"],
    outputs: ["Circuit breaker updates", "Pheromone signals", "Performance logs", "Slack alerts"],
    businessValue: "The financial safety system. Halts all spend automatically if experiments are burning budget too fast. Critical for protecting client retainer margin.",
  },

  // ── Tier 3 ─────────────────────────────────────────────────
  {
    id:          "scout",
    jobId:       "scout_agent",
    name:        "Scout",
    icon:        "🔭",
    color:       C.blue,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Daily 08:00 UTC (4pm AEST)",
    canDisable:  true,
    role:        "Autonomous Prospect Hunter",
    what:        "Proactively discovers new Australian solar companies that are likely to need CRM automation. Scans the knowledge graph and data pipeline for buying signals, scores each prospect, and queues high-value ones for deep research.",
    how: [
      "Queries knowledge graph for solar company entities",
      "Detects buying signals: hiring, scaling, 'manual process', 'follow up', 'new office'",
      "Scores each prospect 0–10 based on signal strength and recency",
      "Filters to min score 5.0",
      "Creates opportunity records in DB",
      "Posts high-value prospects to research queue for deep profiling",
      "Sends message bus ALERT for top prospects",
    ],
    inputs:  ["Knowledge graph (kg_entities)", "Collected data pipeline", "Social signals", "Web scraper data"],
    outputs: ["Opportunity records", "Research task queue entries", "Message bus alerts"],
    businessValue: "Outbound lead generation on autopilot. Finds solar companies to pitch before they come to you — keeps the pipeline full without cold calling manually.",
  },
  {
    id:          "qualification",
    jobId:       null,
    name:        "Qualification Agent",
    icon:        "🎯",
    color:       C.orange,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Event-driven (GHL webhook on new lead)",
    canDisable:  true,
    role:        "Lead Scoring & Hot Lead Routing",
    what:        "Scores every inbound solar lead 1–10 using GPT-4o across four criteria, then routes them automatically. Hot leads (7+) trigger an immediate AI outbound call.",
    how: [
      "Triggered by GHL webhook: new-lead or form-submit",
      "Extracts: homeowner status, monthly electricity bill, roof type/age, location",
      "Calls GPT-4o with solar qualification criteria",
      "Score 7–10 → action: call_now (triggers Retell outbound call)",
      "Score 5–6 → action: nurture (enters drip email sequence)",
      "Score 1–4 → action: disqualify",
      "Writes score + reason to lead record in DB",
      "Posts Slack alert for high-value leads (masked PII)",
    ],
    inputs:  ["GHL webhook payload (lead data)", "Company KB (client thresholds)", "Retell AI API"],
    outputs: ["Lead qualification score", "Recommended action", "Outbound call trigger", "Slack alert"],
    businessValue: "Eliminates manual lead sorting. Sales team only talks to pre-qualified 7+ leads — conversion rates increase, wasted calls drop.",
  },
  {
    id:          "voice",
    jobId:       null,
    name:        "Voice AI",
    icon:        "🎙️",
    color:       C.purple,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Event-driven (inbound call / outbound trigger)",
    canDisable:  true,
    role:        "AI Phone Call Handler",
    what:        "Handles inbound and outbound solar sales calls using GPT-4o with a client-specific knowledge base. Qualifies leads conversationally, books appointments, updates the CRM in real-time, and transfers to a human when needed.",
    how: [
      "Retell AI routes call → POST /voice/call-started → POST /voice/response",
      "Loads company KB: products, FAQs, objection responses, rebates",
      "GPT-4o drives conversation with solar-specific system prompt",
      "Function calls during conversation: lookup_caller, qualify_and_score, book_appointment, send_sms, update_crm, transfer_to_human, end_call",
      "Post-call: transcript analysed, lead record updated, cost logged",
      "ElevenLabs or Retell voices — AU English accent",
    ],
    inputs:  ["Retell AI webhook (call events)", "Company KB", "Lead DB (caller lookup)", "GHL/HubSpot/Salesforce CRM"],
    outputs: ["Conversation transcript", "Lead qualification score", "CRM updates", "SMS confirmations", "Appointment bookings"],
    businessValue: "The core service delivery. One AI handles 100 calls simultaneously. Replaces a $60k/year SDR. Pays for itself on first client appointment booked.",
  },
  {
    id:          "abtester",
    jobId:       "ab_evaluator",
    name:        "A/B Evaluator",
    icon:        "⚖️",
    color:       C.green,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Daily 10:00 UTC (6pm AEST)",
    canDisable:  true,
    role:        "Split Test Lifecycle Manager",
    what:        "Manages A/B test lifecycle from creation to winner declaration. Uses statistical significance testing to declare winners and emits pheromone signals to reinforce winning strategies across the swarm.",
    how: [
      "Reads all running A/B tests from DB",
      "Checks if min sample size reached (30 leads per variant)",
      "Applies simplified chi-square p-value test (threshold p<0.05)",
      "Declares winner if statistically significant",
      "Updates test record with winner + stats",
      "Posts pheromone signal to boost winner's approach",
      "Pauses loser variant in GHL",
    ],
    inputs:  ["ab_tests table", "Lead conversion data", "GHL pipeline stats"],
    outputs: ["Winner declaration", "Pheromone signal", "Test completion log"],
    businessValue: "Turns guessing into data. Every ad headline, email subject, or call script gets tested scientifically before scaling budget behind it.",
  },
  {
    id:          "mutation",
    jobId:       "mutation_engine",
    name:        "Mutation Engine",
    icon:        "🧬",
    color:       C.red,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Monday 22:30 UTC (Tue 8:30am AEST)",
    canDisable:  true,
    role:        "Strategy Evolution & Failure Recovery",
    what:        "After the weekly retrospective, finds all failed or underperforming experiments and uses GPT-4o to generate 2 mutated variants of each. Mutants preserve what was working and address the identified failure mode.",
    how: [
      "Queries experiments with status: failed, killed in last 7 days",
      "For each failure, extracts: idea, failure_mode, budget_used",
      "Calls GPT-4o: 'generate 2 improved variants that fix this failure'",
      "Each mutant gets a new Kelly budget allocation",
      "Submits mutants to experiment queue (status: pending)",
      "Posts pheromone signal for the mutation direction",
      "Logs to cold ledger",
    ],
    inputs:  ["Failed experiments (DB)", "Warm memory (failure patterns)", "Kelly engine"],
    outputs: ["2 mutant experiments per failure", "Budget allocations", "Pheromone signals"],
    businessValue: "Prevents the swarm from repeating the same mistakes. Every failure becomes a learning that auto-generates a smarter next attempt.",
  },
  {
    id:          "retro",
    jobId:       "retrospective",
    name:        "Retrospective",
    icon:        "📖",
    color:       C.amber,
    tier:        3,
    tierLabel:   "Worker",
    schedule:    "Monday 22:00 UTC (Tue 8am AEST)",
    canDisable:  true,
    role:        "Weekly Learning Synthesis",
    what:        "Weekly analysis of all experiments, leads, and outcomes from the past 7 days. Synthesises key learnings into warm memory and posts a plain-English performance report to Slack.",
    how: [
      "Reads all experiments + outcomes from past 7 days",
      "Reads lead conversion funnel metrics",
      "Calculates: budget burn %, win rate, avg score, top performing buckets",
      "Calls GPT-4o to synthesise narrative insights",
      "Writes learnings to warm memory JSON",
      "Posts weekly report to Slack channel",
      "Resets weekly budget tracking",
    ],
    inputs:  ["Experiments (last 7 days)", "Lead data", "Budget tracker", "Cold ledger"],
    outputs: ["Warm memory update", "Slack weekly report", "Budget reset signal"],
    businessValue: "The management meeting that runs itself. Gives you a plain-English summary of what worked, what didn't, and what the swarm is trying next — every Tuesday morning.",
  },

  // ── System ─────────────────────────────────────────────────
  {
    id:          "research_engine",
    jobId:       "research_engine",
    name:        "Research Engine",
    icon:        "🔍",
    color:       C.teal,
    tier:        4,
    tierLabel:   "System",
    schedule:    "Daily 06:00 UTC (2pm AEST)",
    canDisable:  true,
    role:        "Deep Market Research Coordinator",
    what:        "Coordinates parallel research agents: market intelligence, competitive analysis, prospect profiling, and technical assessment. Synthesises all findings into the knowledge graph.",
    how: [
      "Runs: market_research, competitive_intel, prospect_researcher, technical_research agents",
      "Each sub-agent uses GPT-4o with specialist prompts",
      "All findings written to research_findings table",
      "Synthesis agent reconciles conflicting signals",
      "Key entities extracted to knowledge graph",
    ],
    inputs:  ["Research task queue", "External web data", "GHL contact data"],
    outputs: ["Research findings", "Knowledge graph updates", "Opportunity signals"],
    businessValue: "Keeps the team informed about AU solar market trends, pricing benchmarks, and competitor weaknesses — updated daily, automatically.",
  },
  {
    id:          "data_collection",
    jobId:       "data_collection",
    name:        "Data Collection",
    icon:        "📡",
    color:       C.blue,
    tier:        4,
    tierLabel:   "System",
    schedule:    "Every 4 hours",
    canDisable:  true,
    role:        "Market Data Ingestion",
    what:        "Runs four parallel collectors: web scraper (CEC installer registry), GHL API poller (contacts/pipeline), social signal monitor (LinkedIn buying signals), and price monitor (CPL benchmarks).",
    how: [
      "Checks collection_sources table for due sources",
      "web_scraper: CEC registry, solar directories",
      "api_poller: GHL contacts + pipeline counts",
      "social_signal: GPT-4o classifies LinkedIn posts for buying intent",
      "price_monitor: CPL and CPO benchmarks → time_series table",
      "All raw data written to collected_data table for pipeline processing",
    ],
    inputs:  ["Public web (CEC registry, directories)", "GHL API", "LinkedIn feeds", "Price data sources"],
    outputs: ["collected_data table", "time_series metrics", "Social buying signals"],
    businessValue: "The sensory system of the swarm. Without fresh data, agents work on stale assumptions. 4-hour refresh keeps market intelligence current.",
  },
  {
    id:          "pipeline",
    jobId:       "pipeline_processor",
    name:        "Pipeline Processor",
    icon:        "⚙️",
    color:       C.teal,
    tier:        4,
    tierLabel:   "System",
    schedule:    "Every 4 hours (+30 min after collection)",
    canDisable:  true,
    role:        "Data Deduplication & Enrichment",
    what:        "Processes raw collected data: deduplicates records, enriches with derived fields, routes signals to the message bus for agent consumption.",
    how: [
      "Reads collected_data records since last run",
      "Deduplicates by source + identifier",
      "Enriches: normalises phone/email formats, geocodes suburbs",
      "Routes signals to message bus by type (opportunity, price, social)",
      "Marks records as normalized=1",
    ],
    inputs:  ["collected_data table (raw)", "Knowledge graph (dedup reference)"],
    outputs: ["Normalised data records", "Message bus signals", "Knowledge graph updates"],
    businessValue: "Garbage in, garbage out prevention. Ensures agents act on clean, deduplicated data rather than duplicate records inflating prospect counts.",
  },
  {
    id:          "explore_monitor",
    jobId:       "explore_monitor",
    name:        "Explore Monitor",
    icon:        "🕐",
    color:       C.orange,
    tier:        4,
    tierLabel:   "System",
    schedule:    "Every 2 hours",
    canDisable:  false,
    role:        "72-Hour Explore Experiment Lifecycle",
    what:        "Monitors all 'explore bucket' experiments through a 6-phase 72-hour lifecycle. Automatically transitions phases, triggers paid spend when CTR threshold is met, and kills expired experiments.",
    how: [
      "Phase 0–12h (asset creation): post Slack update",
      "Phase 12–24h (distribution): emit pheromone, post update",
      "Phase 24–48h (signal observation): check CTR from analytics",
      "Phase 48–60h (decision point): CTR ≥2% → activate paid spend; else log no-trigger",
      "Phase 60–72h (final assessment): collect all metrics",
      "Phase >72h (expired): auto-kill, emit pheromone, Slack alert",
    ],
    inputs:  ["Explore experiments (DB)", "Analytics data", "Portfolio manager"],
    outputs: ["Phase transitions", "Paid spend activation", "Auto-kill signals", "Pheromone updates"],
    businessValue: "Enforces the 72-hour prove-or-kill discipline. Prevents experiments from running indefinitely without results — protecting the weekly budget.",
  },
  {
    id:          "crm_sync",
    jobId:       "crm_sync",
    name:        "CRM Sync",
    icon:        "🔄",
    color:       C.green,
    tier:        4,
    tierLabel:   "System",
    schedule:    "Every 30 minutes",
    canDisable:  true,
    role:        "Live CRM Data Sync to Dashboard",
    what:        "Pulls live pipeline and contact data from the connected CRM (GHL, HubSpot, or Salesforce) every 30 minutes and writes it to board-state.json for the dashboard to display.",
    how: [
      "Calls crm_router.get_pipeline_stages() for current contact counts",
      "Calls crm_router.get_recent_contacts() for contact list",
      "Writes pipeline stage data to board-state.json",
      "Updates SQLite cache for offline fallback",
    ],
    inputs:  ["GoHighLevel / HubSpot / Salesforce API"],
    outputs: ["board-state.json", "SQLite CRM cache", "Dashboard pipeline view"],
    businessValue: "Keeps the dashboard reflecting reality. Without this, the board shows stale data and you can't track where leads are in the pipeline.",
  },
];

const TIERS = [
  { id: 1, label: "Tier 1 — Command",          color: C.amber,  desc: "Strategic decision-making and budget allocation" },
  { id: 2, label: "Tier 2 — Department Heads", color: C.cyan,   desc: "Domain specialists managing their task queues" },
  { id: 3, label: "Tier 3 — Workers",          color: C.green,  desc: "Specialist agents triggered by events or schedules" },
  { id: 4, label: "System",                    color: C.muted,  desc: "Infrastructure: data collection, sync, lifecycle management" },
];

/* ─────────────────────────────────────────────────────────────
   TOGGLE SWITCH
───────────────────────────────────────────────────────────── */
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

/* ─────────────────────────────────────────────────────────────
   INFO PANEL (side sheet)
───────────────────────────────────────────────────────────── */
function InfoPanel({ agent, onClose }) {
  if (!agent) return null;
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(5,8,16,.7)",
          zIndex: 100,
        }}
      />
      {/* Sheet */}
      <div style={{
        position: "fixed", top: 0, right: 0,
        width: 480, height: "100vh",
        background: C.panel,
        borderLeft: `1px solid ${C.borderB}`,
        zIndex: 101,
        overflowY: "auto",
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
                background: h(agent.color, 0.12),
                border: `1px solid ${h(agent.color, 0.25)}`,
                color: agent.color,
                borderRadius: 20, padding: "2px 8px",
              }}>
                {agent.tierLabel.toUpperCase()}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: C.muted, borderRadius: 6, padding: "4px 8px",
              cursor: "pointer", fontSize: 16, lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Role */}
        <Section label="Role" color={agent.color}>
          <p style={{ margin: 0, color: C.text, fontSize: 14, lineHeight: 1.6 }}>{agent.role}</p>
        </Section>

        {/* Schedule */}
        <Section label="Schedule" color={agent.color}>
          <div style={{
            ...mono, fontSize: 12,
            background: C.dim, border: `1px solid ${C.border}`,
            borderRadius: 6, padding: "8px 12px", color: C.amberL,
          }}>
            {agent.schedule}
          </div>
        </Section>

        {/* What it does */}
        <Section label="What it does" color={agent.color}>
          <p style={{ margin: 0, color: C.text, fontSize: 14, lineHeight: 1.7 }}>{agent.what}</p>
        </Section>

        {/* How it works */}
        <Section label="How it works" color={agent.color}>
          <ol style={{ margin: 0, paddingLeft: 18, color: C.text, fontSize: 13, lineHeight: 1.8 }}>
            {agent.how.map((step, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{step}</li>
            ))}
          </ol>
        </Section>

        {/* Inputs / Outputs */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <IOBox label="Inputs" items={agent.inputs} color={C.blue} />
          <IOBox label="Outputs" items={agent.outputs} color={C.green} />
        </div>

        {/* Business Value */}
        <Section label="Business value" color={C.amber}>
          <div style={{
            background: h(C.amber, 0.06),
            border: `1px solid ${h(C.amber, 0.2)}`,
            borderRadius: 8, padding: "12px 14px",
            color: C.amberL, fontSize: 13, lineHeight: 1.6,
          }}>
            {agent.businessValue}
          </div>
        </Section>

        {/* Cannot disable warning */}
        {!agent.canDisable && (
          <div style={{
            background: h(C.red, 0.06),
            border: `1px solid ${h(C.red, 0.2)}`,
            borderRadius: 8, padding: "12px 14px",
            color: C.red, fontSize: 12, marginTop: 4,
          }}>
            ⚠ This agent cannot be disabled — it is critical to the swarm's operation.
          </div>
        )}
      </div>
    </>
  );
}

function Section({ label, color, children }) {
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
      <div style={{ fontSize: 10, ...mono, color, letterSpacing: 2, marginBottom: 8 }}>{label.toUpperCase()}</div>
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

/* ─────────────────────────────────────────────────────────────
   AGENT CARD
───────────────────────────────────────────────────────────── */
function AgentCard({ agent, enabled, onToggle, onInfo, scheduleInfo }) {
  const [hov, setHov] = useState(false);
  const isRunning = scheduleInfo?.running;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.cardHov : C.card,
        border: `1px solid ${enabled ? h(agent.color, 0.3) : C.border}`,
        borderRadius: 12,
        padding: "16px 18px",
        transition: "all .15s",
        opacity: enabled ? 1 : 0.55,
        display: "flex", flexDirection: "column", gap: 12,
      }}
    >
      {/* Top row: icon + name + toggle */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {/* Icon */}
        <div style={{
          width: 40, height: 40, borderRadius: 10, flexShrink: 0,
          background: h(agent.color, 0.12),
          border: `1px solid ${h(agent.color, enabled ? 0.3 : 0.1)}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, position: "relative",
        }}>
          {agent.icon}
          {/* Running indicator */}
          {isRunning && (
            <span style={{
              position: "absolute", top: -3, right: -3,
              width: 8, height: 8, borderRadius: "50%",
              background: C.green, boxShadow: `0 0 6px ${C.green}`,
            }} />
          )}
        </div>

        {/* Name + role */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 14, fontWeight: 600, color: enabled ? C.white : C.muted,
            marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {agent.name}
          </div>
          <div style={{ fontSize: 11, color: enabled ? agent.color : C.muted }}>
            {agent.role.split("&")[0].trim()}
          </div>
        </div>

        {/* Controls */}
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

      {/* Schedule chip */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{
          fontSize: 10, ...mono,
          background: C.dim, border: `1px solid ${C.border}`,
          borderRadius: 20, padding: "3px 10px",
          color: enabled ? C.muted : "#2A3450",
        }}>
          {agent.schedule}
        </div>

        {/* Status */}
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: !enabled ? C.muted : isRunning ? C.green : h(agent.color, 0.7),
            boxShadow: isRunning ? `0 0 5px ${C.green}` : "none",
          }} />
          <span style={{ fontSize: 10, ...mono, color: C.muted }}>
            {!enabled ? "DISABLED" : isRunning ? "RUNNING" : "IDLE"}
          </span>
        </div>
      </div>

      {/* Last run */}
      {scheduleInfo?.last_run && enabled && (
        <div style={{ fontSize: 10, color: C.muted, ...mono }}>
          Last run: {new Date(scheduleInfo.last_run).toLocaleString("en-AU", {
            day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
          })}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MAIN PAGE
───────────────────────────────────────────────────────────── */
export default function AgentsPage() {
  const [agentState, setAgentState]   = useState({});   // { [id]: boolean }
  const [scheduleInfo, setScheduleInfo] = useState({}); // { [jobId]: {last_run, running} }
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [saving, setSaving]           = useState(null);
  const [loading, setLoading]         = useState(true);
  const [toast, setToast]             = useState(null);

  // ── Load agent config from backend ──
  const loadConfig = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/agents/config`, { credentials: "include" });
      if (r.ok) {
        const data = await r.json();
        setAgentState(data.agents || {});
        setScheduleInfo(data.schedule || {});
      } else {
        // Fallback: all enabled
        const defaults = {};
        AGENT_CATALOGUE.forEach(a => { defaults[a.id] = true; });
        setAgentState(defaults);
      }
    } catch {
      const defaults = {};
      AGENT_CATALOGUE.forEach(a => { defaults[a.id] = true; });
      setAgentState(defaults);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  // Poll schedule info every 30s
  useEffect(() => {
    const t = setInterval(loadConfig, 30000);
    return () => clearInterval(t);
  }, [loadConfig]);

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Toggle agent ──
  const handleToggle = async (agent, newVal) => {
    if (!agent.canDisable) return;
    setSaving(agent.id);
    // Optimistic update
    setAgentState(prev => ({ ...prev, [agent.id]: newVal }));
    try {
      const r = await fetch(`${API}/api/agents/config`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agent.id, enabled: newVal }),
      });
      if (!r.ok) throw new Error("Save failed");
      showToast(`${agent.name} ${newVal ? "enabled" : "disabled"}`);
    } catch {
      // Rollback
      setAgentState(prev => ({ ...prev, [agent.id]: !newVal }));
      showToast(`Failed to save — check API connection`, false);
    } finally {
      setSaving(null);
    }
  };

  const enabledCount  = AGENT_CATALOGUE.filter(a => agentState[a.id] !== false).length;
  const disabledCount = AGENT_CATALOGUE.length - enabledCount;

  if (loading) {
    return (
      <div style={{
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
        background: C.bg,
      }}>
        <div style={{ ...mono, fontSize: 12, color: C.amber, letterSpacing: 2 }}>LOADING AGENTS…</div>
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
            Agent Control
          </h1>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: C.muted }}>
            Manage which agents run, understand what each one does, and control the swarm.
          </p>
        </div>
        {/* Summary pills */}
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Pill color={C.green}>{enabledCount} Active</Pill>
          {disabledCount > 0 && <Pill color={C.muted}>{disabledCount} Disabled</Pill>}
        </div>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px 40px" }}>

        {TIERS.map(tier => {
          const agents = AGENT_CATALOGUE.filter(a => a.tier === tier.id);
          return (
            <div key={tier.id} style={{ marginBottom: 36 }}>
              {/* Tier header */}
              <div style={{
                display: "flex", alignItems: "center", gap: 12,
                marginBottom: 16,
              }}>
                <div style={{
                  height: 1, background: h(tier.color, 0.3), flex: 0, width: 20,
                }} />
                <span style={{
                  fontSize: 11, ...mono, color: tier.color,
                  letterSpacing: 3, textTransform: "uppercase",
                }}>
                  {tier.label}
                </span>
                <div style={{ height: 1, background: C.border, flex: 1 }} />
                <span style={{ fontSize: 11, color: C.muted }}>{tier.desc}</span>
              </div>

              {/* Cards grid */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 12,
              }}>
                {agents.map(agent => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    enabled={agentState[agent.id] !== false}
                    onToggle={v => handleToggle(agent, v)}
                    onInfo={a => setSelectedAgent(a)}
                    scheduleInfo={agent.jobId ? scheduleInfo[agent.jobId] : null}
                  />
                ))}
              </div>
            </div>
          );
        })}

        {/* Legend */}
        <div style={{
          marginTop: 8, padding: "14px 18px",
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 10, fontSize: 12, color: C.muted,
          display: "flex", gap: 24, flexWrap: "wrap",
        }}>
          <span>
            <span style={{ color: C.green }}>●</span> Running — currently executing
          </span>
          <span>
            <span style={{ color: C.amber }}>●</span> Idle — scheduled, waiting for next trigger
          </span>
          <span>
            <span style={{ color: C.muted }}>●</span> Disabled — skipped when scheduled
          </span>
          <span style={{ marginLeft: "auto" }}>
            ⚠ Core agents (grey toggle) cannot be disabled
          </span>
        </div>
      </div>

      {/* Info panel */}
      <InfoPanel agent={selectedAgent} onClose={() => setSelectedAgent(null)} />

      {/* Toast */}
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
      color,
      borderRadius: 20, padding: "3px 12px",
    }}>
      {children}
    </span>
  );
}
