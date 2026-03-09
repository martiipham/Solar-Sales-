import { useState, useEffect, useRef, useCallback } from "react";
import Confirm from "./components/Confirm";
import InfoTip from "./components/InfoTip";

/* ═══════════════════════════════════════════════════════════════
   SOLAR SWARM — AGENT COMMAND BOARD
   Standalone web app  ·  localStorage persistence
   Aesthetic: Dark ops terminal × mission control
═══════════════════════════════════════════════════════════════ */

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

// ── localStorage wrapper (replaces window.storage) ───────────
const store = {
  get: (key) => {
    try { const v = localStorage.getItem(key); return v ? { value: v } : null; }
    catch { return null; }
  },
  set: (key, value) => {
    try { localStorage.setItem(key, value); return true; }
    catch { return false; }
  },
};

// ── Agents ───────────────────────────────────────────────────
const AGENTS = [
  { id: "general",       name: "The General",      icon: "⚡", color: C.amber,  tier: 1, role: "Strategic Command"    },
  { id: "research",      name: "Research Head",    icon: "🔬", color: C.cyan,   tier: 2, role: "Market Intelligence"  },
  { id: "content",       name: "Content Head",     icon: "✍️",  color: C.purple, tier: 2, role: "Copy & Creative"      },
  { id: "analytics",     name: "Analytics Head",   icon: "📊", color: C.green,  tier: 2, role: "Performance Analysis" },
  { id: "scout",         name: "Scout",            icon: "🔭", color: C.blue,   tier: 3, role: "Prospect Hunter"      },
  { id: "qualification", name: "Qualification",    icon: "🎯", color: C.orange, tier: 3, role: "Lead Scorer"          },
  { id: "voice",         name: "Voice AI",         icon: "🎙️", color: C.purple, tier: 3, role: "Outbound Caller"      },
  { id: "proposal",      name: "Proposal",         icon: "📄", color: C.cyan,   tier: 3, role: "Proposal Generator"   },
  { id: "abtester",      name: "A/B Evaluator",    icon: "⚖️", color: C.green,  tier: 3, role: "Test Evaluator"       },
  { id: "mutation",      name: "Mutation Engine",  icon: "🧬", color: C.red,    tier: 3, role: "Strategy Evolver"     },
  { id: "retro",         name: "Retrospective",    icon: "📖", color: C.amber,  tier: 3, role: "Learning Synthesis"   },
  { id: "pipeline",      name: "Pipeline Proc.",   icon: "⚙️", color: C.teal,   tier: 3, role: "Data Processor"       },
  { id: "unassigned",    name: "Unassigned",       icon: "👤", color: C.muted,  tier: 0, role: "Not yet assigned"     },
];

const COLUMNS = [
  { id: "backlog",    label: "BACKLOG",     color: C.muted,  icon: "◫",  limit: null },
  { id: "queued",     label: "QUEUED",      color: C.blue,   icon: "⏳", limit: 8    },
  { id: "inprogress", label: "IN PROGRESS", color: C.amber,  icon: "▶",  limit: 4    },
  { id: "review",     label: "REVIEW",      color: C.purple, icon: "👁", limit: 4    },
  { id: "done",       label: "DONE",        color: C.green,  icon: "✓",  limit: null },
  { id: "blocked",    label: "BLOCKED",     color: C.red,    icon: "⛔", limit: null },
];

const PRIORITIES = [
  { id: "critical", label: "CRITICAL", color: C.red    },
  { id: "high",     label: "HIGH",     color: C.orange },
  { id: "normal",   label: "NORMAL",   color: C.blue   },
  { id: "low",      label: "LOW",      color: C.muted  },
];

const CATEGORIES = [
  "Lead Pipeline","Experiment","Research","Content","Infrastructure",
  "Client Delivery","Capital","Integration","Bug Fix","Feature",
];

const SEED_TASKS = [
  { id:"t1",  col:"inprogress", agent:"qualification", title:"Wire async lead queue to prevent GHL retries",         priority:"critical", cat:"Infrastructure",  tags:["webhook","async"],         desc:"Move qualify() out of Flask request thread. GHL retries on >8s response create duplicate leads."  },
  { id:"t2",  col:"inprogress", agent:"general",       title:"Add X-API-Key auth to Human Gate API",                priority:"critical", cat:"Infrastructure",  tags:["security","auth"],         desc:"Protect port 5000 — one header check before any request is processed."                          },
  { id:"t3",  col:"queued",     agent:"research",      title:"Australian solar SME market size deep-dive",          priority:"high",     cat:"Research",        tags:["market","AU"],             desc:"Estimate TAM/SAM/SOM for solar CRM automation. Feed pheromone map."                             },
  { id:"t4",  col:"queued",     agent:"scout",         title:"Identify 20 GHL solar companies in Perth + Sydney",   priority:"high",     cat:"Lead Pipeline",   tags:["prospecting"],             desc:"ABN lookup + LinkedIn filter for companies with 5-15 salespeople already on GHL."               },
  { id:"t5",  col:"queued",     agent:"content",       title:"Write 3-touch email follow-up sequence",             priority:"high",     cat:"Content",         tags:["email","sequence"],         desc:"D1 proposal intro, D3 case study, D7 urgency close — personalised by qualification score."       },
  { id:"t6",  col:"backlog",    agent:"unassigned",    title:"Build client onboarding workflow",                    priority:"high",     cat:"Client Delivery", tags:["onboarding"],              desc:"Steps 8-10 of lead pipeline: sign → onboard → activate automations."                           },
  { id:"t7",  col:"backlog",    agent:"unassigned",    title:"Client-facing dashboard (Flask route)",               priority:"high",     cat:"Client Delivery", tags:["dashboard","client"],      desc:"Wire dashboard.py to /clients/<id>/dashboard with lead count + avg score."                      },
  { id:"t8",  col:"backlog",    agent:"mutation",      title:"Run first mutation cycle on failed experiments",      priority:"normal",   cat:"Experiment",      tags:["mutation","learning"],     desc:"Feed failed experiment rows into mutation engine, generate next-gen variants."                  },
  { id:"t9",  col:"backlog",    agent:"abtester",      title:"Set up A/B test for proposal CTA variants",          priority:"normal",   cat:"Experiment",      tags:["ab-test","conversion"],    desc:"Test 'Book a call' vs 'Get free quote' CTA in proposal PDF."                                   },
  { id:"t10", col:"backlog",    agent:"analytics",     title:"Monthly automated PDF report for clients",            priority:"normal",   cat:"Client Delivery", tags:["reporting","pdf"],         desc:"Auto-generate performance PDF at end of each calendar month."                                  },
  { id:"t11", col:"backlog",    agent:"pipeline",      title:"Replace hardcoded since_minutes=260 with watermark",  priority:"normal",   cat:"Infrastructure",  tags:["bug","pipeline"],          desc:"DB-persisted cursor prevents double-processing on scheduler restart."                           },
  { id:"t12", col:"backlog",    agent:"unassigned",    title:"Add pytest unit tests for kelly_engine.py",           priority:"normal",   cat:"Infrastructure",  tags:["testing","capital"],       desc:"Test Kelly fraction calculation with known p/b/q inputs — circuit breaker too."               },
  { id:"t13", col:"backlog",    agent:"voice",         title:"Configure ElevenLabs voice persona for solar ICP",    priority:"normal",   cat:"Integration",     tags:["voice","persona"],         desc:"Tune voice character to match Australian solar SME decision makers."                            },
  { id:"t14", col:"backlog",    agent:"unassigned",    title:"Migrate pytz → zoneinfo (Python 3.11 stdlib)",        priority:"low",      cat:"Infrastructure",  tags:["refactor","deps"],         desc:"Remove pytz dependency, use Python 3.11 built-in zoneinfo throughout."                         },
  { id:"t15", col:"done",       agent:"qualification", title:"Implement 5-signal GPT-4o lead scoring",             priority:"critical", cat:"Lead Pipeline",   tags:["ai","scoring"],            desc:"Score leads 0-10 on homeowner, bill, roof, location, urgency."                                 },
  { id:"t16", col:"done",       agent:"general",       title:"Build Kelly Criterion capital allocator",             priority:"critical", cat:"Capital",         tags:["kelly","capital"],         desc:"f* = (b·p - q)/b at 25% fractional with 25% max single bet."                                  },
  { id:"t17", col:"blocked",    agent:"unassigned",    title:"DocuSign/PandaDoc e-sign integration",                priority:"high",     cat:"Client Delivery", tags:["integration","contracts"], desc:"Blocked: need to decide on e-sign provider before building."                                   },
];

// ── CSS ───────────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Syne+Mono&family=DM+Sans:wght@300;400;500;600;700&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; background: #050810; }
  body { font-family: 'DM Sans', sans-serif; color: #CBD5E1; }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #050810; }
  ::-webkit-scrollbar-thumb { background: #1E3050; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #2a4070; }
  @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
  @keyframes spin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
  @keyframes slideIn { from{opacity:0;transform:translateX(-8px)} to{opacity:1;transform:translateX(0)} }
  @keyframes pulse { 0%,100%{box-shadow:0 0 0 0 transparent} 50%{box-shadow:0 0 0 3px currentColor} }
  .card-enter { animation: fadeUp .18s ease; }
  .mono { font-family: 'Syne Mono', monospace; }
  input, textarea, select { font-family: 'DM Sans', sans-serif; }
  input:focus, textarea:focus, select:focus { outline: 2px solid #F59E0B44; outline-offset: 0; }
  button { font-family: 'DM Sans', sans-serif; }
`;

// ── Helpers ───────────────────────────────────────────────────
const uid = () => "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const agentById = id => AGENTS.find(a => a.id === id) || AGENTS[AGENTS.length - 1];
const prioById  = id => PRIORITIES.find(p => p.id === id) || PRIORITIES[2];
const colById   = id => COLUMNS.find(c => c.id === id);

function Tag({ label, color, small }) {
  return (
    <span className="mono" style={{
      background: h(color, 0.12), color, border: `1px solid ${h(color, 0.28)}`,
      borderRadius: 4, padding: small ? "0px 5px" : "1px 7px",
      fontSize: small ? 9 : 10, whiteSpace: "nowrap", lineHeight: "18px",
      display: "inline-block",
    }}>{label}</span>
  );
}

function AgentPill({ agentId, compact }) {
  const ag = agentById(agentId);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 5,
      background: h(ag.color, 0.1), border: `1px solid ${h(ag.color, 0.25)}`,
      borderRadius: 20, padding: compact ? "2px 8px" : "3px 10px", width: "fit-content",
    }}>
      <span style={{ fontSize: compact ? 10 : 12 }}>{ag.icon}</span>
      <span style={{ fontSize: compact ? 9 : 10, color: ag.color, fontWeight: 600 }}>{ag.name}</span>
    </div>
  );
}

// ── AI Task Generator ────────────────────────────────────────
async function generateTasksAI(context, existingTasks, apiKey) {
  const existingTitles = existingTasks.map(t => t.title).join("\n- ");
  const prompt = `You are orchestrating the Solar Swarm — an autonomous AI agent system that automates sales for Australian solar companies. Agents: The General (strategic command, every 6h), Research Head (market intel, daily), Content Head (copy/email, daily), Analytics Head (performance, daily), Scout (prospecting), Qualification (GPT-4o lead scoring), Voice AI (Retell outbound calls), Proposal (PDF generation), A/B Evaluator, Mutation Engine, Retrospective, Pipeline Processor.

User's context: "${context}"

Existing tasks (don't duplicate these):
- ${existingTitles}

Generate exactly 5 new, specific, actionable tasks. Make them technical and immediately actionable by a developer.

Respond ONLY with a raw JSON array — no markdown fences, no preamble, no trailing text:
[{"title":"...","agent":"general|research|content|analytics|scout|qualification|voice|proposal|abtester|mutation|retro|pipeline|unassigned","priority":"critical|high|normal|low","cat":"Lead Pipeline|Experiment|Research|Content|Infrastructure|Client Delivery|Capital|Integration|Bug Fix|Feature","tags":["tag1","tag2"],"desc":"one concise sentence"}]`;

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true" },
    body: JSON.stringify({ model: "claude-sonnet-4-20250514", max_tokens: 1200, messages: [{ role: "user", content: prompt }] }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error?.message || `API error ${res.status}`); }
  const data = await res.json();
  const text = data.content?.[0]?.text || "[]";
  const match = text.match(/\[[\s\S]*\]/);
  return JSON.parse(match ? match[0] : "[]");
}

// ── Claude URL Builder ────────────────────────────────────────
const AGENT_CONTEXT = {
  general:       "You are The General — the strategic command agent of Solar Swarm. You allocate capital using the Kelly Criterion, score experiments by confidence (0-10), and orchestrate the full agent hierarchy. You think in systems, probabilities, and expected value.",
  research:      "You are the Research Head of Solar Swarm. Your job is deep market intelligence for Australian solar SMEs — competitor analysis, TAM sizing, lead source quality, and feeding insights into the pheromone map.",
  content:       "You are the Content Head of Solar Swarm. You write high-converting copy for Australian solar companies — email sequences, SMS follow-ups, proposal narratives, and A/B test variants. Voice: direct, benefit-led, no fluff.",
  analytics:     "You are the Analytics Head of Solar Swarm. You analyse campaign performance data, calculate ROI per channel, surface winning patterns, and recommend budget reallocation.",
  scout:         "You are the Scout agent of Solar Swarm. You identify and qualify solar company prospects in Australia using ABN lookups, LinkedIn, and GHL data. You output structured lead lists with company name, size, CRM stack, and contact.",
  qualification: "You are the Qualification agent of Solar Swarm. You score inbound leads 0-10 using 5 signals: homeowner status, power bill size, roof suitability, location, and urgency. You use GPT-4o function calls and output a JSON score with reasoning.",
  voice:         "You are the Voice AI agent of Solar Swarm, powered by Retell + ElevenLabs. You design outbound call scripts, voice personas, and objection-handling trees for Australian solar prospects.",
  proposal:      "You are the Proposal agent of Solar Swarm. You generate personalised PDF proposals for solar leads — system size recommendation, ROI projection, payback period, and a tailored close.",
  abtester:      "You are the A/B Evaluator of Solar Swarm. You design statistically valid split tests, calculate significance, declare winners, and write up learnings for the retrospective memory.",
  mutation:      "You are the Mutation Engine of Solar Swarm. You take failed or stalled experiments and generate evolved variants — changing one variable at a time, informed by pheromone decay weights and retrospective findings.",
  retro:         "You are the Retrospective agent of Solar Swarm. Every Monday you synthesise the week's wins, losses, and surprises into structured learnings that update the warm memory JSON files.",
  pipeline:      "You are the Pipeline Processor of Solar Swarm. You maintain the GHL lead pipeline — moving contacts between stages, triggering automations, flagging stale leads, and ensuring data integrity.",
  unassigned:    "You are a senior full-stack developer and AI systems engineer working on Solar Swarm — an autonomous agent system that automates sales for Australian solar SMEs.",
};

function buildClaudeUrl(task) {
  const ag = agentById(task.agent);
  const pr = prioById(task.priority);
  const agentCtx = AGENT_CONTEXT[task.agent] || AGENT_CONTEXT.unassigned;

  const prompt = `${agentCtx}

---
## TASK: ${task.title}
**Priority:** ${pr.label}
**Category:** ${task.cat}
**Tags:** ${(task.tags || []).join(", ") || "none"}
${task.desc ? `**Context:** ${task.desc}` : ""}

---

Please complete this task now. Be specific, technical, and produce ready-to-use output (code, copy, analysis, plan — whatever this task calls for). If you need clarifying information, ask one focused question before proceeding.`;

  return `https://claude.ai/new?q=${encodeURIComponent(prompt)}`;
}

// ── Settings Modal ────────────────────────────────────────────
function SettingsModal({ onClose }) {
  const [key, setKey] = useState(() => localStorage.getItem("swarm-api-key") || "");
  const [saved, setSaved] = useState(false);

  const save = () => {
    localStorage.setItem("swarm-api-key", key.trim());
    setSaved(true);
    setTimeout(() => { setSaved(false); onClose(); }, 800);
  };

  return (
    <div style={{ position:"fixed",inset:0,background:"rgba(5,8,16,.88)",zIndex:1000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(4px)" }}
      onClick={e => { if(e.target===e.currentTarget) onClose(); }}>
      <div style={{ background:C.panel,border:`1px solid ${C.borderB}`,borderRadius:14,
        padding:28,width:480,boxShadow:"0 20px 60px rgba(0,0,0,.6)",animation:"fadeUp .2s ease" }}>
        <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20 }}>
          <span className="mono" style={{ fontSize:12,color:C.amber,letterSpacing:2 }}>⚙ SETTINGS</span>
          <button onClick={onClose} style={{ background:"none",border:"none",color:C.muted,cursor:"pointer",fontSize:18 }}>✕</button>
        </div>

        <label className="mono" style={{ fontSize:9,color:C.muted,letterSpacing:1.5,textTransform:"uppercase",display:"block",marginBottom:6 }}>
          Anthropic API Key
        </label>
        <input
          type="password"
          value={key}
          onChange={e => setKey(e.target.value)}
          placeholder="sk-ant-api03-…"
          style={{ width:"100%",background:C.card,border:`1px solid ${C.borderB}`,color:C.text,
            borderRadius:8,padding:"10px 12px",fontSize:12,marginBottom:8 }}
        />
        <p style={{ fontSize:11,color:C.muted,lineHeight:1.6,marginBottom:16 }}>
          Stored only in your browser's localStorage. Never sent anywhere except Anthropic's API when you use ✦ AI Tasks.
          Get a key at <a href="https://console.anthropic.com" target="_blank" rel="noreferrer"
            style={{ color:C.amber }}>console.anthropic.com</a>.
        </p>

        <div style={{ display:"flex",justifyContent:"flex-end",gap:8 }}>
          <button onClick={onClose} style={{ background:"transparent",border:`1px solid ${C.border}`,
            color:C.muted,padding:"8px 16px",borderRadius:6,cursor:"pointer",fontSize:11 }}>
            Cancel
          </button>
          <button onClick={save} style={{ background:saved?h(C.green,0.15):h(C.amber,0.15),
            border:`1px solid ${saved?C.green:C.amber}`,color:saved?C.green:C.amber,
            padding:"8px 20px",borderRadius:6,cursor:"pointer",fontSize:11,
            fontFamily:"'Syne Mono',monospace",transition:"all .2s" }}>
            {saved ? "✓ SAVED" : "SAVE"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Task Card ─────────────────────────────────────────────────
function TaskCard({ task, onDragStart, onClick }) {
  const [hovered, setHovered] = useState(false);
  const ag = agentById(task.agent);
  const pr = prioById(task.priority);

  const handleRun = (e) => {
    e.stopPropagation();
    window.open(buildClaudeUrl(task), "_blank");
  };

  return (
    <div
      draggable
      onDragStart={e => onDragStart(e, task.id)}
      onClick={() => onClick(task)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="card-enter"
      style={{
        background: hovered ? C.cardHov : C.card,
        border: `1px solid ${hovered ? C.borderB : C.border}`,
        borderLeft: `3px solid ${ag.color}`,
        borderRadius: 8, padding: "10px 12px",
        cursor: "grab", transition: "all .15s",
        boxShadow: hovered ? `0 4px 20px ${h(ag.color, 0.1)}` : "none",
        userSelect: "none", position: "relative",
      }}>
      <div style={{ display:"flex",alignItems:"center",gap:5,marginBottom:6,flexWrap:"wrap" }}>
        <Tag label={pr.label} color={pr.color} small />
        <span style={{ fontSize:9,color:C.muted }}>{task.cat}</span>
      </div>
      <div style={{ fontSize:12,fontWeight:600,color:C.white,lineHeight:1.4,marginBottom:7 }}>{task.title}</div>
      <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:4 }}>
        <AgentPill agentId={task.agent} compact />
        <div style={{ display:"flex",gap:3,alignItems:"center" }}>
          {(task.tags||[]).slice(0,2).map(t=><Tag key={t} label={t} color={C.muted} small />)}
        </div>
      </div>

      {/* RUN button — always visible, brightens on hover */}
      <button
        onClick={handleRun}
        title="Open this task in Claude"
        style={{
          position:"absolute", top:8, right:8,
          background: hovered ? h(ag.color, 0.35) : h(ag.color, 0.15),
          border: `1px solid ${hovered ? ag.color : h(ag.color, 0.45)}`,
          color: hovered ? ag.color : h(ag.color, 0.7),
          borderRadius: 5, padding: "2px 8px",
          cursor: "pointer", fontSize: 10,
          fontFamily: "'Syne Mono', monospace",
          letterSpacing: 0.5,
          display: "flex", alignItems: "center", gap: 4,
          transition: "all .15s",
          boxShadow: hovered ? `0 0 8px ${h(ag.color, 0.3)}` : "none",
        }}
      >
        ▶ RUN
      </button>
    </div>
  );
}

// ── Task Modal ─────────────────────────────────────────────────
function TaskModal({ task, onSave, onDelete, onClose }) {
  const isNew = !task.id;
  const [form, setForm] = useState({
    title: task.title||"", desc: task.desc||"",
    agent: task.agent||"unassigned", priority: task.priority||"normal",
    col: task.col||"backlog", cat: task.cat||"Feature",
    tags: (task.tags||[]).join(", "),
  });
  const set = (k,v) => setForm(f=>({...f,[k]:v}));

  const handleSave = () => {
    if (!form.title.trim()) return;
    onSave({ ...task, id:task.id||uid(), ...form,
      tags: form.tags.split(",").map(t=>t.trim()).filter(Boolean),
      createdAt: task.createdAt||Date.now(), updatedAt: Date.now() });
  };

  const iS = { background:C.panel,border:`1px solid ${C.border}`,color:C.text,
    borderRadius:6,padding:"8px 10px",fontSize:12,width:"100%" };
  const lS = { fontSize:10,color:C.muted,fontFamily:"'Syne Mono',monospace",letterSpacing:1,
    textTransform:"uppercase",display:"block",marginBottom:5 };

  return (
    <div style={{ position:"fixed",inset:0,background:"rgba(5,8,16,.85)",zIndex:1000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(4px)" }}
      onClick={e=>{ if(e.target===e.currentTarget) onClose(); }}>
      <div style={{ background:C.panel,border:`1px solid ${C.borderB}`,borderRadius:14,
        padding:24,width:"90vw",maxWidth:520,maxHeight:"90vh",overflowY:"auto",
        boxShadow:"0 20px 60px rgba(0,0,0,.6)",animation:"fadeUp .2s ease" }}>
        <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20 }}>
          <span className="mono" style={{ fontSize:12,color:C.amber,letterSpacing:2 }}>{isNew?"NEW TASK":"EDIT TASK"}</span>
          <button onClick={onClose} style={{ background:"none",border:"none",color:C.muted,cursor:"pointer",fontSize:18 }}>✕</button>
        </div>
        <div style={{ display:"flex",flexDirection:"column",gap:14 }}>
          <div>
            <label style={lS}>Title *</label>
            <input value={form.title} onChange={e=>set("title",e.target.value)} placeholder="What needs to be done?" style={iS} autoFocus />
          </div>
          <div>
            <label style={lS}>Description</label>
            <textarea value={form.desc} onChange={e=>set("desc",e.target.value)} placeholder="Context, acceptance criteria, links…" rows={3} style={{...iS,resize:"vertical"}}/>
          </div>
          <div style={{ display:"grid",gridTemplateColumns:"1fr 1fr",gap:12 }}>
            <div>
              <label style={lS}>Assign Agent</label>
              <select value={form.agent} onChange={e=>set("agent",e.target.value)} style={{...iS,cursor:"pointer"}}>
                {AGENTS.map(a=><option key={a.id} value={a.id}>{a.icon} {a.name}</option>)}
              </select>
            </div>
            <div>
              <label style={lS}>Priority</label>
              <select value={form.priority} onChange={e=>set("priority",e.target.value)} style={{...iS,cursor:"pointer"}}>
                {PRIORITIES.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display:"grid",gridTemplateColumns:"1fr 1fr",gap:12 }}>
            <div>
              <label style={lS}>Column</label>
              <select value={form.col} onChange={e=>set("col",e.target.value)} style={{...iS,cursor:"pointer"}}>
                {COLUMNS.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label style={lS}>Category</label>
              <select value={form.cat} onChange={e=>set("cat",e.target.value)} style={{...iS,cursor:"pointer"}}>
                {CATEGORIES.map(c=><option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={lS}>Tags (comma-separated)</label>
            <input value={form.tags} onChange={e=>set("tags",e.target.value)} placeholder="auth, webhook, gpt-4o…" style={iS}/>
          </div>

          {/* Agent preview */}
          <div style={{ padding:"10px 12px",background:C.card,borderRadius:8,
            border:`1px solid ${h(agentById(form.agent).color,0.3)}`,
            display:"flex",alignItems:"center",gap:10 }}>
            <span style={{ fontSize:20 }}>{agentById(form.agent).icon}</span>
            <div>
              <div style={{ fontSize:12,color:agentById(form.agent).color,fontWeight:600 }}>{agentById(form.agent).name}</div>
              <div style={{ fontSize:10,color:C.muted }}>{agentById(form.agent).role}</div>
            </div>
            <Tag label={`Tier ${agentById(form.agent).tier||"—"}`} color={agentById(form.agent).color} small />
          </div>

          <div style={{ display:"flex",justifyContent:"space-between",paddingTop:8,borderTop:`1px solid ${C.border}` }}>
            <div>{!isNew&&<button onClick={()=>onDelete(task.id)} style={{ background:h(C.red,0.1),border:`1px solid ${h(C.red,0.3)}`,color:C.red,padding:"8px 14px",borderRadius:6,cursor:"pointer",fontSize:11,fontFamily:"'Syne Mono',monospace" }}>DELETE</button>}</div>
            <div style={{ display:"flex",gap:8 }}>
              <button onClick={onClose} style={{ background:"transparent",border:`1px solid ${C.border}`,color:C.muted,padding:"8px 16px",borderRadius:6,cursor:"pointer",fontSize:11 }}>CANCEL</button>
              {!isNew && (
                <button
                  onClick={() => window.open(buildClaudeUrl(task), "_blank")}
                  style={{ background:h(C.green,0.15),border:`1px solid ${C.green}`,color:C.green,
                    padding:"8px 18px",borderRadius:6,cursor:"pointer",fontSize:11,
                    fontFamily:"'Syne Mono',monospace",display:"flex",alignItems:"center",gap:6,
                    boxShadow:`0 0 12px ${h(C.green,0.2)}` }}>
                  ▶ RUN IN CLAUDE
                </button>
              )}
              <button onClick={handleSave} style={{ background:h(C.amber,0.15),border:`1px solid ${C.amber}`,color:C.amber,padding:"8px 20px",borderRadius:6,cursor:"pointer",fontSize:11,fontFamily:"'Syne Mono',monospace" }}>{isNew?"CREATE":"SAVE"}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Column ────────────────────────────────────────────────────
function KanbanColumn({ col, tasks, onDrop, onDragStart, onCardClick, onAddTask }) {
  const [dragOver, setDragOver] = useState(false);
  const overLimit = col.limit && tasks.length >= col.limit;

  return (
    <div
      onDragOver={e=>{ e.preventDefault(); setDragOver(true); }}
      onDragLeave={()=>setDragOver(false)}
      onDrop={e=>{ e.preventDefault(); setDragOver(false); onDrop(e, col.id); }}
      style={{
        flex:"1 1 200px",minWidth:180,maxWidth:340,display:"flex",flexDirection:"column",
        background: dragOver ? h(col.color,0.06) : C.panel,
        border:`1px solid ${dragOver?col.color:C.border}`,
        borderRadius:12,overflow:"hidden",flexShrink:0,transition:"all .15s",
        boxShadow: dragOver ? `0 0 20px ${h(col.color,0.15)}` : "none",
      }}>
      <div style={{ padding:"12px 14px",borderBottom:`1px solid ${C.border}`,background:h(col.color,0.07) }}>
        <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between" }}>
          <div style={{ display:"flex",alignItems:"center",gap:7 }}>
            <span style={{ fontSize:13,color:col.color }}>{col.icon}</span>
            <span className="mono" style={{ fontSize:10,color:col.color,letterSpacing:1.5 }}>{col.label}</span>
          </div>
          <div style={{ background:overLimit?h(C.red,0.2):h(col.color,0.15),
            color:overLimit?C.red:col.color,border:`1px solid ${overLimit?h(C.red,0.4):h(col.color,0.3)}`,
            borderRadius:10,padding:"1px 8px",fontSize:10,fontFamily:"'Syne Mono',monospace" }}>
            {tasks.length}{col.limit?`/${col.limit}`:""}
          </div>
        </div>
        {overLimit&&<div style={{ fontSize:9,color:C.red,marginTop:4 }}>⚠ WIP limit reached</div>}
      </div>

      <div style={{ flex:1,overflowY:"auto",padding:"10px",display:"flex",flexDirection:"column",gap:8,minHeight:80 }}>
        {tasks.length===0&&<div style={{ textAlign:"center",padding:"24px 0",color:C.muted,fontSize:11,opacity:.5 }}>Drop here</div>}
        {tasks.map(t=><TaskCard key={t.id} task={t} onDragStart={onDragStart} onClick={onCardClick}/>)}
      </div>

      {col.id!=="done"&&col.id!=="blocked"&&(
        <div style={{ padding:"8px 10px",borderTop:`1px solid ${C.border}` }}>
          <button onClick={()=>onAddTask(col.id)}
            style={{ width:"100%",background:"transparent",border:`1px dashed ${h(col.color,0.3)}`,
              color:h(col.color,0.6),borderRadius:6,padding:"6px",cursor:"pointer",fontSize:11,transition:"all .15s" }}
            onMouseEnter={e=>{e.target.style.background=h(col.color,0.08);e.target.style.color=col.color;}}
            onMouseLeave={e=>{e.target.style.background="transparent";e.target.style.color=h(col.color,0.6);}}>
            + Add task
          </button>
        </div>
      )}
    </div>
  );
}

// ── AI Panel ──────────────────────────────────────────────────
function AIPanel({ tasks, onAddTasks, onClose }) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(new Set());
  const apiKey = localStorage.getItem("swarm-api-key") || "";

  const generate = async () => {
    if (!prompt.trim()) return;
    if (!apiKey) { setError("No API key set. Click ⚙ Settings to add your Anthropic key."); return; }
    setLoading(true); setError(""); setSuggestions([]);
    try {
      const result = await generateTasksAI(prompt, tasks, apiKey);
      setSuggestions(result);
      setSelected(new Set(result.map((_,i)=>i)));
    } catch(e) {
      setError("Generation failed: " + e.message);
    } finally { setLoading(false); }
  };

  const addSelected = () => {
    const toAdd = suggestions.filter((_,i)=>selected.has(i))
      .map(s=>({...s,id:uid(),col:"backlog",createdAt:Date.now(),updatedAt:Date.now()}));
    onAddTasks(toAdd); onClose();
  };

  const toggleSel = i => setSelected(prev=>{ const n=new Set(prev); n.has(i)?n.delete(i):n.add(i); return n; });

  return (
    <div style={{ position:"fixed",inset:0,background:"rgba(5,8,16,.88)",zIndex:1000,
      display:"flex",alignItems:"center",justifyContent:"center",backdropFilter:"blur(6px)" }}
      onClick={e=>{if(e.target===e.currentTarget)onClose();}}>
      <div style={{ background:C.panel,border:`1px solid ${C.borderB}`,borderRadius:16,
        padding:28,width:"90vw",maxWidth:600,maxHeight:"88vh",overflowY:"auto",
        boxShadow:"0 24px 80px rgba(0,0,0,.7)",animation:"fadeUp .2s ease" }}>
        <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20 }}>
          <div>
            <div className="mono" style={{ fontSize:13,color:C.amber,letterSpacing:2 }}>✦ AI TASK GENERATOR</div>
            <div style={{ fontSize:11,color:C.muted,marginTop:3 }}>Describe what you're working on — Claude generates tasks</div>
          </div>
          <button onClick={onClose} style={{ background:"none",border:"none",color:C.muted,cursor:"pointer",fontSize:18 }}>✕</button>
        </div>

        {!apiKey&&(
          <div style={{ background:h(C.orange,0.1),border:`1px solid ${h(C.orange,0.3)}`,borderRadius:8,
            padding:"10px 14px",color:C.orange,fontSize:11,marginBottom:14 }}>
            ⚠ No API key configured. Add your Anthropic key in <strong>⚙ Settings</strong> to use AI generation.
          </div>
        )}

        <textarea value={prompt} onChange={e=>setPrompt(e.target.value)}
          placeholder="e.g. 'Launch first paid Perth solar campaign' or 'Set up voice AI workflow' or 'Fix all security issues'…"
          rows={3} style={{ width:"100%",background:C.card,border:`1px solid ${C.borderB}`,color:C.text,
            borderRadius:8,padding:"10px 12px",fontSize:12,resize:"vertical",marginBottom:10 }}/>
        <button onClick={generate} disabled={loading||!prompt.trim()}
          style={{ background:loading?C.dim:h(C.amber,0.15),border:`1px solid ${loading?C.border:C.amber}`,
            color:loading?C.muted:C.amber,padding:"9px 20px",borderRadius:8,cursor:loading?"wait":"pointer",
            fontSize:11,fontFamily:"'Syne Mono',monospace",letterSpacing:1,
            display:"flex",alignItems:"center",gap:8 }}>
          {loading?<><span style={{ display:"inline-block",animation:"spin 1s linear infinite" }}>◌</span>GENERATING…</>:"✦ GENERATE TASKS"}
        </button>

        {error&&<div style={{ background:h(C.red,0.1),border:`1px solid ${h(C.red,0.3)}`,borderRadius:8,
          padding:"10px 14px",color:C.red,fontSize:11,marginTop:12 }}>{error}</div>}

        {suggestions.length>0&&(
          <>
            <div className="mono" style={{ fontSize:10,color:C.cyan,letterSpacing:1.5,margin:"16px 0 10px",textTransform:"uppercase" }}>
              {suggestions.length} tasks — select to add:
            </div>
            <div style={{ display:"flex",flexDirection:"column",gap:8,marginBottom:16 }}>
              {suggestions.map((s,i)=>{
                const ag=agentById(s.agent); const pr=prioById(s.priority); const sel=selected.has(i);
                return (
                  <div key={i} onClick={()=>toggleSel(i)} style={{ background:sel?h(ag.color,0.08):C.card,
                    border:`1px solid ${sel?h(ag.color,0.35):C.border}`,borderLeft:`3px solid ${sel?ag.color:C.border}`,
                    borderRadius:8,padding:"10px 14px",cursor:"pointer",transition:"all .15s",animation:"slideIn .2s ease" }}>
                    <div style={{ display:"flex",alignItems:"flex-start",gap:10 }}>
                      <div style={{ width:18,height:18,borderRadius:4,flexShrink:0,marginTop:1,
                        background:sel?ag.color:"transparent",border:`1.5px solid ${sel?ag.color:C.muted}`,
                        display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,color:"#000" }}>{sel?"✓":""}</div>
                      <div style={{ flex:1 }}>
                        <div style={{ display:"flex",gap:6,marginBottom:4,flexWrap:"wrap" }}>
                          <Tag label={pr.label} color={pr.color} small/>
                          <Tag label={s.cat} color={C.muted} small/>
                        </div>
                        <div style={{ fontSize:12,fontWeight:600,color:C.white,marginBottom:4 }}>{s.title}</div>
                        <div style={{ fontSize:11,color:C.muted,lineHeight:1.5 }}>{s.desc}</div>
                        <div style={{ marginTop:6 }}><AgentPill agentId={s.agent} compact/></div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",paddingTop:12,borderTop:`1px solid ${C.border}` }}>
              <span style={{ fontSize:11,color:C.muted }}>{selected.size} of {suggestions.length} selected</span>
              <button onClick={addSelected} disabled={selected.size===0}
                style={{ background:h(C.green,0.15),border:`1px solid ${C.green}`,color:C.green,
                  padding:"9px 20px",borderRadius:8,cursor:"pointer",fontSize:11,fontFamily:"'Syne Mono',monospace" }}>
                ADD {selected.size} TO BACKLOG
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Stats Bar ─────────────────────────────────────────────────
function StatsBar({ tasks }) {
  const done  = tasks.filter(t=>t.col==="done").length;
  const total = tasks.length;
  const pct   = total>0 ? Math.round((done/total)*100) : 0;
  const crits = tasks.filter(t=>t.priority==="critical"&&t.col!=="done").length;
  const blkd  = tasks.filter(t=>t.col==="blocked").length;
  const infly = tasks.filter(t=>t.col==="inprogress").length;

  return (
    <div style={{ display:"flex",gap:18,alignItems:"center",flexWrap:"wrap" }}>
      {[["TOTAL",total,C.text],["IN FLIGHT",infly,C.amber],["DONE",done,C.green],
        ["CRITICAL",crits,crits>0?C.red:C.muted],["BLOCKED",blkd,blkd>0?C.red:C.muted]].map(([l,v,c])=>(
        <div key={l} style={{ textAlign:"center" }}>
          <div className="mono" style={{ fontSize:16,color:c,lineHeight:1 }}>{v}</div>
          <div style={{ fontSize:11,color:C.muted,letterSpacing:1.5,textTransform:"uppercase" }}>{l}</div>
        </div>
      ))}
      <div style={{ display:"flex",alignItems:"center",gap:8,marginLeft:4 }}>
        <div style={{ width:72,height:4,background:C.dim,borderRadius:2 }}>
          <div style={{ width:`${pct}%`,height:"100%",background:`linear-gradient(90deg,${C.green},${C.cyan})`,borderRadius:2,transition:"width .5s" }}/>
        </div>
        <span className="mono" style={{ fontSize:10,color:C.green }}>{pct}%</span>
      </div>
    </div>
  );
}

// ── Agent Sidebar ─────────────────────────────────────────────
function AgentSidebar({ tasks, filterAgent, onFilterAgent, onResetBoard, lastSaved, saving }) {
  return (
    <div style={{ display:"flex",flexDirection:"column",gap:3,height:"100%" }}>
      <div className="mono" style={{ fontSize:9,color:C.muted,letterSpacing:2,textTransform:"uppercase",padding:"0 4px",marginBottom:8 }}>
        FILTER BY AGENT
      </div>
      <button onClick={()=>onFilterAgent(null)} style={{
        display:"flex",alignItems:"center",justifyContent:"space-between",
        background:filterAgent===null?h(C.amber,0.12):"transparent",
        border:`1px solid ${filterAgent===null?C.amber:C.border}`,
        borderRadius:7,padding:"6px 10px",cursor:"pointer",
        color:filterAgent===null?C.amber:C.muted,fontSize:11,transition:"all .12s" }}>
        <span>All agents</span>
        <span className="mono" style={{ fontSize:10 }}>{tasks.length}</span>
      </button>
      {AGENTS.filter(a=>a.id!=="unassigned").map(ag=>{
        const count=tasks.filter(t=>t.agent===ag.id).length;
        const active=filterAgent===ag.id;
        return (
          <button key={ag.id} onClick={()=>onFilterAgent(active?null:ag.id)} style={{
            display:"flex",alignItems:"center",justifyContent:"space-between",
            background:active?h(ag.color,0.12):"transparent",
            border:`1px solid ${active?ag.color:C.border}`,
            borderRadius:7,padding:"6px 10px",cursor:"pointer",
            color:active?ag.color:C.muted,fontSize:11,transition:"all .12s",
            opacity:count===0?0.4:1 }}>
            <div style={{ display:"flex",alignItems:"center",gap:6 }}>
              <span style={{ fontSize:12 }}>{ag.icon}</span><span>{ag.name}</span>
            </div>
            {count>0&&<span className="mono" style={{ fontSize:9,background:h(ag.color,0.15),color:ag.color,borderRadius:8,padding:"0 6px" }}>{count}</span>}
          </button>
        );
      })}
      <div style={{ marginTop:"auto",paddingTop:16,borderTop:`1px solid ${C.border}` }}>
        <div style={{ fontSize:9,color:C.muted,marginBottom:8 }}>
          {saving?"⟳ Saving…":lastSaved?`✓ Saved ${lastSaved.toLocaleTimeString()}`:"Auto-saves on change"}
        </div>
        <button onClick={onResetBoard} style={{ width:"100%",background:"transparent",border:`1px solid ${C.border}`,
          color:C.muted,padding:"5px 10px",borderRadius:5,cursor:"pointer",fontSize:9,fontFamily:"'Syne Mono',monospace" }}>
          RESET TO DEFAULT
        </button>
      </div>
    </div>
  );
}

// ── Overview Panel ────────────────────────────────────────────
const DASH_API = "http://localhost:5003";

function useApiData(path, interval = 30000) {
  const [data, setData]   = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    const load = () =>
      fetch(`${DASH_API}${path}`)
        .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(d => { if (active) { setData(d); setError(false); } })
        .catch(() => { if (active) setError(true); });
    load();
    const t = setInterval(load, interval);
    return () => { active = false; clearInterval(t); };
  }, [path, interval]);
  return { data, error };
}

function OverviewPanel({ tasks }) {
  const [boardState, setBoardState] = useState(null);

  // Live API feeds
  const { data: health,    error: apiDown }  = useApiData("/api/health",         15000);
  const { data: crmStatus }                  = useApiData("/api/crm/status",      30000);
  const { data: pipeline }                   = useApiData("/api/crm/pipeline",    60000);
  const { data: crmMetrics }                 = useApiData("/api/crm/metrics",     60000);
  const { data: experiments }                = useApiData("/api/swarm/experiments", 30000);
  const { data: leads }                      = useApiData("/api/swarm/leads",     30000);
  const { data: liveBoard }                  = useApiData("/api/board/state",     30000);

  const apiOnline = !apiDown && !!health;

  useEffect(() => {
    fetch("/board-state.json").then(r => r.json()).then(setBoardState).catch(() => {});
  }, []);

  const total    = tasks.length;
  const done     = tasks.filter(t => t.col === "done").length;
  const inprog   = tasks.filter(t => t.col === "inprogress").length;
  const blocked  = tasks.filter(t => t.col === "blocked").length;
  const critical = tasks.filter(t => t.priority === "critical" && t.col !== "done").length;
  const pct      = total > 0 ? Math.round((done / total) * 100) : 0;

  // Per-agent workload
  const agentCounts = AGENTS.filter(a => a.id !== "unassigned").map(ag => ({
    ...ag,
    total: tasks.filter(t => t.agent === ag.id).length,
    done:  tasks.filter(t => t.agent === ag.id && t.col === "done").length,
    active:tasks.filter(t => t.agent === ag.id && ["inprogress","queued","review"].includes(t.col)).length,
  })).filter(a => a.total > 0).sort((a, b) => b.total - a.total);

  const maxAgentCount = Math.max(...agentCounts.map(a => a.total), 1);

  // Per-column counts
  const colCounts = COLUMNS.map(col => ({
    ...col,
    count: tasks.filter(t => t.col === col.id).length,
  }));
  const maxColCount = Math.max(...colCounts.map(c => c.count), 1);

  // Per-priority counts
  const prioCounts = PRIORITIES.map(p => ({
    ...p,
    count: tasks.filter(t => t.priority === p.id && t.col !== "done").length,
  }));

  // Per-category counts (top 6)
  const catMap = {};
  tasks.filter(t => t.col !== "done").forEach(t => { catMap[t.cat] = (catMap[t.cat] || 0) + 1; });
  const catCounts = Object.entries(catMap).sort((a,b) => b[1]-a[1]).slice(0, 8);
  const maxCat = Math.max(...catCounts.map(([,v]) => v), 1);

  // Suggested next from board-state.json
  const suggestedId = boardState?.suggestedNext;
  const suggestedTask = suggestedId
    ? (boardState?.columns?.backlog || []).find(t => t.id === suggestedId)
    : null;

  const card = (label, value, colour, sub) => (
    <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,
      padding:"18px 20px",flex:"1 1 140px" }}>
      <div className="mono" style={{ fontSize:28,color:colour,lineHeight:1,marginBottom:4 }}>{value}</div>
      <div className="mono" style={{ fontSize:9,color:C.muted,letterSpacing:1.5,textTransform:"uppercase" }}>{label}</div>
      {sub && <div style={{ fontSize:10,color:C.muted,marginTop:4 }}>{sub}</div>}
    </div>
  );

  // Derived CRM data from API
  const activeCrm    = crmStatus?.active || "none";
  const crmNames     = { ghl:"GoHighLevel", hubspot:"HubSpot", salesforce:"Salesforce", none:"Not connected" };
  const crmColors    = { ghl:C.green, hubspot:C.orange, salesforce:C.blue, none:C.muted };
  const metrics      = crmMetrics?.metrics || {};
  const pipelineStages = pipeline?.stages || [];
  const maxStageCount  = Math.max(...pipelineStages.map(s => s.opportunityCount || s.count || 0), 1);
  const expList      = experiments?.experiments || [];
  const leadList     = leads?.leads || [];
  const liveStats    = liveBoard?.liveStats || {};
  const expCounts    = liveStats.experiments || {};

  const EXP_STATUS_COLORS = {
    running:"#4ADE80", approved:C.cyan, pending:C.amber,
    complete:C.blue,   killed:C.red,    rejected:C.muted,
  };

  return (
    <div style={{ flex:1,overflow:"auto",padding:"20px 24px",display:"flex",flexDirection:"column",gap:20 }}>

      {/* API status bar */}
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",
        background:C.card,border:`1px solid ${apiOnline ? h(C.green,0.3) : h(C.muted,0.2)}`,
        borderRadius:10,padding:"8px 16px" }}>
        <div style={{ display:"flex",alignItems:"center",gap:8 }}>
          <span style={{ width:7,height:7,borderRadius:"50%",
            background: apiOnline ? C.green : C.red,
            boxShadow: apiOnline ? `0 0 6px ${C.green}` : `0 0 6px ${C.red}`,
            display:"inline-block" }}/>
          <span className="mono" style={{ fontSize:11,color: apiOnline ? C.green : C.red }}>
            {apiOnline ? "SWARM API ONLINE" : "SWARM API OFFLINE"}
          </span>
          {!apiOnline && (
            <span style={{ fontSize:11,color:C.muted }}>
              — Start the backend: <code style={{ color:C.amber,fontFamily:"monospace" }}>python main.py</code>
            </span>
          )}
        </div>
        <div style={{ display:"flex",alignItems:"center",gap:16 }}>
          <span style={{ fontSize:10,color:crmColors[activeCrm] }}>
            ◈ {crmNames[activeCrm]}
          </span>
          {apiOnline && metrics.synced_at && (
            <span className="mono" style={{ fontSize:9,color:C.muted }}>
              synced {new Date(metrics.synced_at).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Stat cards — board tasks + live CRM if available */}
      <div style={{ display:"flex",gap:12,flexWrap:"wrap" }}>
        {card("Total Tasks",   total,    C.text,   "on this board")}
        {card("Completed",     done,     C.green,  `${pct}% done`)}
        {card("In Progress",   inprog,   C.amber,  "active now")}
        {card("Critical",      critical, critical>0?C.red:C.muted, "open items")}
        {/* Skeleton placeholders while API loads */}
        {!health && !apiDown && [1,2].map(i => (
          <div key={i} style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,
            padding:"18px 20px",flex:"1 1 140px" }}>
            <div style={{ height:28,width:50,borderRadius:4,background:C.dim,marginBottom:8,
              animation:"pulse 1.5s ease-in-out infinite" }}/>
            <div style={{ height:10,width:80,borderRadius:4,background:C.dim }}/>
          </div>
        ))}
        {apiOnline && metrics.total_contacts > 0 && card("CRM Contacts", metrics.total_contacts, C.cyan, `+${metrics.new_this_week||0} this week`)}
        {apiOnline && metrics.conversion_rate > 0 && card("Conversion", `${metrics.conversion_rate}%`, C.purple, "of contacts")}
        {!apiOnline && card("Blocked", blocked, blocked>0?C.red:C.muted, "tasks")}
      </div>

      {/* CRM pipeline stages — only when API online */}
      {apiOnline && pipelineStages.length > 0 && (
        <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"16px 20px" }}>
          <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:14 }}>
            <span className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1 }}>
              CRM PIPELINE — {crmNames[activeCrm].toUpperCase()}
            </span>
            <span className="mono" style={{ fontSize:9,color:C.muted }}>
              {pipelineStages.reduce((s,st) => s+(st.opportunityCount||st.count||0),0)} total
            </span>
          </div>
          <div style={{ display:"flex",gap:12,flexWrap:"wrap" }}>
            {pipelineStages.map((stage,i) => {
              const cnt = stage.opportunityCount || stage.count || 0;
              const pct2 = Math.round((cnt / maxStageCount) * 100);
              const stageColor = [C.cyan,C.amber,C.green,C.purple,C.blue,C.orange,C.pink,C.teal][i % 8];
              return (
                <div key={stage.id||i} style={{ flex:"1 1 120px",minWidth:100 }}>
                  <div style={{ display:"flex",justifyContent:"space-between",marginBottom:5 }}>
                    <span style={{ fontSize:9,color:stageColor,fontWeight:600,
                      whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:"80%" }}>
                      {stage.name||stage.stageName||"Stage"}
                    </span>
                    <span className="mono" style={{ fontSize:11,color:stageColor }}>{cnt}</span>
                  </div>
                  <div style={{ height:6,background:C.dim,borderRadius:3 }}>
                    <div style={{ width:`${pct2}%`,height:"100%",background:stageColor,
                      borderRadius:3,opacity:0.8,transition:"width .5s ease" }}/>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"16px 20px" }}>
        <div style={{ display:"flex",justifyContent:"space-between",marginBottom:8 }}>
          <span className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1 }}>OVERALL TASK PROGRESS</span>
          <span className="mono" style={{ fontSize:10,color:C.green }}>{pct}%</span>
        </div>
        <div style={{ height:8,background:C.dim,borderRadius:4,overflow:"hidden" }}>
          <div style={{ width:`${pct}%`,height:"100%",background:`linear-gradient(90deg,${C.green},${C.cyan})`,
            borderRadius:4,transition:"width .6s ease" }}/>
        </div>
        <div style={{ display:"flex",gap:16,marginTop:12,flexWrap:"wrap" }}>
          {colCounts.map(col => (
            <div key={col.id} style={{ flex:"1 1 80px" }}>
              <div style={{ display:"flex",justifyContent:"space-between",marginBottom:3 }}>
                <span style={{ fontSize:9,color:col.color }}>{col.icon} {col.label}</span>
                <span className="mono" style={{ fontSize:9,color:C.muted }}>{col.count}</span>
              </div>
              <div style={{ height:3,background:C.dim,borderRadius:2 }}>
                <div style={{ width:`${(col.count/maxColCount)*100}%`,height:"100%",
                  background:col.color,borderRadius:2,opacity:0.7 }}/>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display:"flex",gap:16,flexWrap:"wrap" }}>
        {/* Agent workload */}
        <div style={{ flex:"2 1 320px",background:C.card,border:`1px solid ${C.border}`,
          borderRadius:12,padding:"16px 20px" }}>
          <div style={{ display:"flex",alignItems:"center",gap:6,marginBottom:14 }}>
            <span className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1 }}>AGENT WORKLOAD</span>
            <InfoTip text="Tasks assigned to each agent across all columns. Tier 1 = The General (strategy), Tier 2 = Department Heads, Tier 3 = Workers." />
          </div>
          {agentCounts.length === 0
            ? <div style={{ color:C.muted,fontSize:11 }}>No tasks assigned</div>
            : agentCounts.map(ag => (
              <div key={ag.id} style={{ marginBottom:10 }}>
                <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4 }}>
                  <div style={{ display:"flex",alignItems:"center",gap:6 }}>
                    <span style={{ fontSize:12 }}>{ag.icon}</span>
                    <span style={{ fontSize:11,color:ag.color,fontWeight:600 }}>{ag.name}</span>
                    <span style={{ fontSize:9,color:C.muted }}>T{ag.tier}</span>
                  </div>
                  <div style={{ display:"flex",gap:8 }}>
                    <span style={{ fontSize:9,color:C.amber }}>{ag.active} active</span>
                    <span style={{ fontSize:9,color:C.green }}>{ag.done} done</span>
                    <span className="mono" style={{ fontSize:9,color:C.muted }}>{ag.total}</span>
                  </div>
                </div>
                <div style={{ height:4,background:C.dim,borderRadius:2 }}>
                  <div style={{ width:`${(ag.total/maxAgentCount)*100}%`,height:"100%",
                    background:ag.color,borderRadius:2,opacity:0.8 }}/>
                </div>
              </div>
            ))
          }
        </div>

        {/* Priority + Category */}
        <div style={{ flex:"1 1 220px",display:"flex",flexDirection:"column",gap:16 }}>
          <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"16px 20px" }}>
            <div style={{ display:"flex",alignItems:"center",gap:6,marginBottom:12 }}>
              <span className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1 }}>PRIORITY BREAKDOWN</span>
              <InfoTip text="Active tasks only (excludes Done). CRITICAL = blocks revenue or security. HIGH = this week. NORMAL = this sprint. LOW = backlog." />
            </div>
            {prioCounts.map(p => (
              <div key={p.id} style={{ display:"flex",justifyContent:"space-between",alignItems:"center",
                marginBottom:8,padding:"6px 10px",borderRadius:6,
                background:p.count>0?h(p.color,0.07):"transparent",
                border:`1px solid ${p.count>0?h(p.color,0.2):C.border}` }}>
                <span className="mono" style={{ fontSize:10,color:p.count>0?p.color:C.muted }}>{p.label}</span>
                <span className="mono" style={{ fontSize:14,color:p.count>0?p.color:C.muted,fontWeight:600 }}>{p.count}</span>
              </div>
            ))}
          </div>

          <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"16px 20px",flex:1 }}>
            <div className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1,marginBottom:12 }}>TOP CATEGORIES</div>
            {catCounts.map(([cat, count]) => (
              <div key={cat} style={{ marginBottom:8 }}>
                <div style={{ display:"flex",justifyContent:"space-between",marginBottom:2 }}>
                  <span style={{ fontSize:10,color:C.text }}>{cat}</span>
                  <span className="mono" style={{ fontSize:9,color:C.muted }}>{count}</span>
                </div>
                <div style={{ height:2,background:C.dim,borderRadius:1 }}>
                  <div style={{ width:`${(count/maxCat)*100}%`,height:"100%",
                    background:C.cyan,borderRadius:1,opacity:0.6 }}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live experiments + recent leads — only when API online */}
      {apiOnline && (expList.length > 0 || leadList.length > 0) && (
        <div style={{ display:"flex",gap:16,flexWrap:"wrap" }}>

          {/* Experiments */}
          {expList.length > 0 && (
            <div style={{ flex:"1 1 300px",background:C.card,border:`1px solid ${C.border}`,
              borderRadius:12,padding:"16px 20px" }}>
              <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12 }}>
                <span style={{ display:"flex",alignItems:"center",gap:6 }}>
                <span className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1 }}>LIVE EXPERIMENTS</span>
                <InfoTip text="Experiments are marketing/sales strategies run by the swarm. Confidence score (0–10): above 8.5 = auto-approved, 5–8.5 = needs human review, below 5 = auto-killed." position="left" />
              </span>
                <div style={{ display:"flex",gap:6,flexWrap:"wrap" }}>
                  {Object.entries(expCounts).map(([st, cnt]) => (
                    <span key={st} className="mono" style={{ fontSize:9,
                      color:EXP_STATUS_COLORS[st]||C.muted,
                      background:h(EXP_STATUS_COLORS[st]||C.muted,0.1),
                      borderRadius:8,padding:"1px 7px" }}>
                      {st} {cnt}
                    </span>
                  ))}
                </div>
              </div>
              {expList.slice(0,6).map(exp => (
                <div key={exp.id} style={{ display:"flex",alignItems:"flex-start",gap:8,marginBottom:8,
                  padding:"7px 10px",borderRadius:6,
                  background:h(EXP_STATUS_COLORS[exp.status]||C.muted,0.05),
                  border:`1px solid ${h(EXP_STATUS_COLORS[exp.status]||C.muted,0.15)}` }}>
                  <div style={{ flex:1,minWidth:0 }}>
                    <div style={{ fontSize:11,color:C.text,fontWeight:600,
                      whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis" }}>
                      {exp.idea_text?.slice(0,60)||"Experiment"}
                    </div>
                    <div style={{ display:"flex",gap:8,marginTop:3 }}>
                      <span style={{ fontSize:9,color:C.muted }}>{exp.vertical||exp.bucket||""}</span>
                      {exp.confidence_score && (
                        <span className="mono" style={{ fontSize:9,color:C.cyan }}>conf {exp.confidence_score}</span>
                      )}
                      {exp.budget_allocated > 0 && (
                        <span className="mono" style={{ fontSize:9,color:C.amber }}>${exp.budget_allocated} AUD</span>
                      )}
                    </div>
                  </div>
                  <span className="mono" style={{ fontSize:9,whiteSpace:"nowrap",
                    color:EXP_STATUS_COLORS[exp.status]||C.muted,
                    background:h(EXP_STATUS_COLORS[exp.status]||C.muted,0.12),
                    borderRadius:8,padding:"2px 8px" }}>
                    {exp.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Recent leads */}
          {leadList.length > 0 && (
            <div style={{ flex:"1 1 260px",background:C.card,border:`1px solid ${C.border}`,
              borderRadius:12,padding:"16px 20px" }}>
              <div className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1,marginBottom:12 }}>
                RECENT LEADS
                <span style={{ color:C.cyan,marginLeft:8 }}>{liveStats.totalLeads||0} total</span>
              </div>
              {leadList.slice(0,6).map(lead => (
                <div key={lead.id} style={{ display:"flex",alignItems:"center",gap:8,marginBottom:7,
                  padding:"6px 10px",borderRadius:6,
                  background:h(C.cyan,0.04),border:`1px solid ${h(C.cyan,0.1)}` }}>
                  <div style={{ flex:1,minWidth:0 }}>
                    <div style={{ fontSize:11,color:C.text,fontWeight:600,
                      whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis" }}>
                      {lead.name||"Unknown"}
                    </div>
                    <div style={{ fontSize:9,color:C.muted }}>{lead.recommended_action||lead.status||""}</div>
                  </div>
                  {lead.qualification_score != null && (
                    <span className="mono" style={{ fontSize:10,
                      color: lead.qualification_score >= 7 ? C.green : lead.qualification_score >= 4 ? C.amber : C.red }}>
                      {lead.qualification_score}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Agent hierarchy */}
      <div style={{ background:C.card,border:`1px solid ${C.border}`,borderRadius:12,padding:"16px 20px" }}>
        <div className="mono" style={{ fontSize:10,color:C.muted,letterSpacing:1,marginBottom:16 }}>AGENT HIERARCHY</div>
        <div style={{ display:"flex",flexDirection:"column",gap:12 }}>
          {[1,2,3].map(tier => {
            const agents = AGENTS.filter(a => a.tier === tier);
            const tierLabel = {1:"TIER 1 — GENERAL",2:"TIER 2 — DEPARTMENT HEADS",3:"TIER 3 — WORKERS"}[tier];
            const tierColour = {1:C.amber,2:C.cyan,3:C.text}[tier];
            return (
              <div key={tier}>
                <div className="mono" style={{ fontSize:8,color:tierColour,letterSpacing:2,marginBottom:8,opacity:0.7 }}>{tierLabel}</div>
                <div style={{ display:"flex",gap:8,flexWrap:"wrap" }}>
                  {agents.map(ag => {
                    const count = tasks.filter(t => t.agent === ag.id && t.col !== "done").length;
                    return (
                      <div key={ag.id} style={{ background:h(ag.color,0.08),border:`1px solid ${h(ag.color,0.25)}`,
                        borderRadius:8,padding:"8px 12px",display:"flex",alignItems:"center",gap:7,
                        minWidth:130,flex:"0 0 auto" }}>
                        <span style={{ fontSize:14 }}>{ag.icon}</span>
                        <div>
                          <div style={{ fontSize:11,color:ag.color,fontWeight:600 }}>{ag.name}</div>
                          <div style={{ fontSize:9,color:C.muted }}>{ag.role}</div>
                        </div>
                        {count > 0 && (
                          <span className="mono" style={{ marginLeft:"auto",fontSize:10,color:ag.color,
                            background:h(ag.color,0.15),borderRadius:10,padding:"1px 7px" }}>{count}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Suggested next + recent done */}
      <div style={{ display:"flex",gap:16,flexWrap:"wrap" }}>
        {suggestedTask && (
          <div style={{ flex:"1 1 280px",background:h(C.amber,0.06),
            border:`1px solid ${h(C.amber,0.3)}`,borderRadius:12,padding:"16px 20px" }}>
            <div className="mono" style={{ fontSize:9,color:C.amber,letterSpacing:2,marginBottom:10 }}>SUGGESTED NEXT</div>
            <div style={{ fontSize:13,fontWeight:600,color:C.white,marginBottom:6 }}>{suggestedTask.title}</div>
            <div style={{ fontSize:11,color:C.muted,lineHeight:1.5,marginBottom:10 }}>{suggestedTask.description}</div>
            <div style={{ display:"flex",gap:6,flexWrap:"wrap" }}>
              <Tag label={suggestedTask.priority?.toUpperCase()||"?"} color={C.red} small/>
              {(suggestedTask.touchedFiles||[]).slice(0,3).map(f => (
                <Tag key={f} label={f.split("/").pop()} color={C.muted} small/>
              ))}
            </div>
          </div>
        )}

        <div style={{ flex:"1 1 280px",background:C.card,border:`1px solid ${C.border}`,
          borderRadius:12,padding:"16px 20px" }}>
          <div className="mono" style={{ fontSize:9,color:C.green,letterSpacing:2,marginBottom:10 }}>RECENTLY DONE</div>
          {tasks.filter(t => t.col === "done").slice(0, 5).map(t => {
            const ag2 = agentById(t.agent);
            return (
              <div key={t.id} style={{ display:"flex",alignItems:"center",gap:8,marginBottom:8,
                padding:"6px 10px",background:h(C.green,0.05),borderRadius:6,
                border:`1px solid ${h(C.green,0.1)}` }}>
                <span style={{ fontSize:11 }}>{ag2.icon}</span>
                <span style={{ fontSize:11,color:C.text,flex:1 }}>{t.title}</span>
                <Tag label={t.priority} color={prioById(t.priority).color} small/>
              </div>
            );
          })}
          {tasks.filter(t => t.col === "done").length === 0 && (
            <div style={{ fontSize:11,color:C.muted }}>No completed tasks yet</div>
          )}
        </div>
      </div>

    </div>
  );
}

// ── App ───────────────────────────────────────────────────────
export default function App({ initialView = "board" }) {
  const [tasks,        setTasks]        = useState(SEED_TASKS);
  const [view,         setView]         = useState(initialView);
  const [loaded,       setLoaded]       = useState(false);
  const [draggingId,   setDraggingId]   = useState(null);
  const [editTask,     setEditTask]     = useState(null);
  const [showAI,       setShowAI]       = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [filterAgent,  setFilterAgent]  = useState(null);
  const [filterPrio,   setFilterPrio]   = useState(null);
  const [search,       setSearch]       = useState("");
  const [showSidebar,   setShowSidebar]  = useState(true);
  const [saving,        setSaving]       = useState(false);
  const [lastSaved,     setLastSaved]    = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null); // task id to delete
  const [confirmReset,  setConfirmReset]  = useState(false);

  // Load from localStorage
  useEffect(() => {
    const stored = store.get("swarm-kanban-tasks");
    if (stored?.value) {
      try {
        const parsed = JSON.parse(stored.value);
        if (Array.isArray(parsed) && parsed.length > 0) setTasks(parsed);
      } catch {}
    }
    setLoaded(true);
  }, []);

  const saveTasks = useCallback((newTasks) => {
    setSaving(true);
    setTimeout(() => {
      store.set("swarm-kanban-tasks", JSON.stringify(newTasks));
      setLastSaved(new Date());
      setSaving(false);
    }, 100);
  }, []);

  const updateTasks = useCallback((newTasks) => {
    setTasks(newTasks);
    saveTasks(newTasks);
  }, [saveTasks]);

  const handleDragStart = useCallback((e, id) => {
    e.dataTransfer.setData("taskId", id);
    setDraggingId(id);
  }, []);

  const handleDrop = useCallback((e, colId) => {
    const id = e.dataTransfer.getData("taskId");
    if (!id) return;
    updateTasks(tasks.map(t => t.id===id ? {...t,col:colId,updatedAt:Date.now()} : t));
  }, [tasks, updateTasks]);

  const handleSaveTask = useCallback((task) => {
    const exists = tasks.find(t=>t.id===task.id);
    updateTasks(exists ? tasks.map(t=>t.id===task.id?task:t) : [...tasks,task]);
    setEditTask(null);
  }, [tasks, updateTasks]);

  const handleDeleteTask = useCallback((id) => {
    setConfirmDelete(id);
  }, []);

  const doDeleteTask = useCallback(() => {
    if (!confirmDelete) return;
    updateTasks(tasks.filter(t => t.id !== confirmDelete));
    setEditTask(null);
    setConfirmDelete(null);
  }, [confirmDelete, tasks, updateTasks]);

  const handleAddTasks = useCallback((newTasks) => {
    updateTasks([...tasks,...newTasks]);
  }, [tasks, updateTasks]);

  const resetBoard = () => setConfirmReset(true);

  const doResetBoard = () => {
    updateTasks(SEED_TASKS);
    setConfirmReset(false);
  };

  const visible = tasks.filter(t => {
    if (filterAgent && t.agent !== filterAgent) return false;
    if (filterPrio  && t.priority !== filterPrio) return false;
    if (search && !t.title.toLowerCase().includes(search.toLowerCase()) &&
        !(t.desc||"").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  if (!loaded) return (
    <div style={{ background:C.bg,height:"100vh",display:"flex",alignItems:"center",justifyContent:"center" }}>
      <div className="mono" style={{ color:C.amber,fontSize:12,letterSpacing:2,animation:"blink 1s step-end infinite" }}>
        LOADING BOARD…
      </div>
    </div>
  );

  return (
    <div style={{ background:C.bg,height:"100vh",display:"flex",flexDirection:"column",color:C.text }}>
      <style>{STYLES}</style>

      {/* Header */}
      <header style={{ background:C.panel,borderBottom:`1px solid ${C.border}`,padding:"11px 20px",
        display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,flexWrap:"wrap",flexShrink:0 }}>
        <div style={{ display:"flex",alignItems:"center",gap:14 }}>
          <div style={{ display:"flex",alignItems:"center",gap:8 }}>
            <span style={{ fontSize:22 }}>☀️</span>
            <div>
              <div className="mono" style={{ fontSize:14,color:C.amber,letterSpacing:2 }}>SOLAR SWARM</div>
              <div style={{ fontSize:9,color:C.muted,letterSpacing:1.5,textTransform:"uppercase" }}>Agent Command Board</div>
            </div>
          </div>
          <div style={{ width:1,height:30,background:C.border }}/>
          <StatsBar tasks={tasks}/>
        </div>

        {/* Tab switcher */}
        <div style={{ display:"flex",gap:4,background:C.dim,borderRadius:8,padding:3 }}>
          {[["board","◫ BOARD"],["overview","◈ OVERVIEW"]].map(([v,label]) => (
            <button key={v} onClick={()=>setView(v)} className="mono" style={{
              background:view===v?C.panel:"transparent",
              border:`1px solid ${view===v?C.borderB:"transparent"}`,
              color:view===v?C.amber:C.muted,
              padding:"5px 14px",borderRadius:6,cursor:"pointer",
              fontSize:10,letterSpacing:1,transition:"all .15s",
            }}>{label}</button>
          ))}
        </div>

        <div style={{ display:"flex",gap:8,alignItems:"center",flexWrap:"wrap" }}>
          <div style={{ position:"relative" }}>
            <span style={{ position:"absolute",left:9,top:"50%",transform:"translateY(-50%)",color:C.muted,fontSize:11 }}>🔍</span>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search tasks…"
              style={{ background:C.card,border:`1px solid ${C.border}`,color:C.text,borderRadius:7,
                padding:"6px 10px 6px 27px",fontSize:11,width:"clamp(120px, 12vw, 180px)" }}/>
          </div>

          <select value={filterPrio||""} onChange={e=>setFilterPrio(e.target.value||null)}
            style={{ background:C.card,border:`1px solid ${C.border}`,color:filterPrio?C.amber:C.muted,
              borderRadius:7,padding:"6px 10px",fontSize:11,cursor:"pointer" }}>
            <option value="">All priorities</option>
            {PRIORITIES.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}
          </select>

          <button onClick={()=>setShowSidebar(s=>!s)} style={{ background:showSidebar?h(C.cyan,0.12):"transparent",
            border:`1px solid ${showSidebar?C.cyan:C.border}`,color:showSidebar?C.cyan:C.muted,
            padding:"6px 12px",borderRadius:7,cursor:"pointer",fontSize:11,fontFamily:"'Syne Mono',monospace" }}>
            AGENTS
          </button>

          <button onClick={()=>setShowAI(true)} style={{ background:h(C.purple,0.15),border:`1px solid ${C.purple}`,
            color:C.purple,padding:"6px 14px",borderRadius:7,cursor:"pointer",fontSize:11,
            fontFamily:"'Syne Mono',monospace",display:"flex",alignItems:"center",gap:6 }}>
            ✦ AI TASKS
          </button>

          <button onClick={()=>setEditTask({col:"backlog"})} style={{ background:h(C.amber,0.15),
            border:`1px solid ${C.amber}`,color:C.amber,padding:"6px 16px",borderRadius:7,
            cursor:"pointer",fontSize:11,fontFamily:"'Syne Mono',monospace" }}>
            + NEW TASK
          </button>

          <button onClick={()=>setShowSettings(true)} style={{ background:"transparent",
            border:`1px solid ${C.border}`,color:C.muted,padding:"6px 10px",borderRadius:7,
            cursor:"pointer",fontSize:14 }}>
            ⚙
          </button>
        </div>
      </header>

      {/* Active filters strip */}
      {(filterAgent||filterPrio||search)&&(
        <div style={{ background:h(C.amber,0.06),borderBottom:`1px solid ${C.border}`,
          padding:"5px 20px",display:"flex",alignItems:"center",gap:8 }}>
          <span className="mono" style={{ fontSize:9,color:C.muted,letterSpacing:1 }}>FILTERED:</span>
          {filterAgent&&<Tag label={agentById(filterAgent).name} color={agentById(filterAgent).color} small/>}
          {filterPrio&&<Tag label={prioById(filterPrio).label} color={prioById(filterPrio).color} small/>}
          {search&&<Tag label={`"${search}"`} color={C.amber} small/>}
          <button onClick={()=>{setFilterAgent(null);setFilterPrio(null);setSearch("");}}
            style={{ background:"none",border:"none",color:C.muted,cursor:"pointer",fontSize:10,
              fontFamily:"'Syne Mono',monospace",letterSpacing:1 }}>CLEAR ✕</button>
        </div>
      )}

      {/* Body */}
      <div style={{ flex:1,display:"flex",overflow:"hidden" }}>
        {view === "overview" ? (
          <OverviewPanel tasks={tasks}/>
        ) : (
          <>
            {showSidebar&&(
              <div style={{ width:"clamp(160px, 16vw, 220px)",borderRight:`1px solid ${C.border}`,background:C.panel,
                padding:"14px 10px",overflowY:"auto",flexShrink:0 }}>
                <AgentSidebar tasks={tasks} filterAgent={filterAgent} onFilterAgent={setFilterAgent}
                  onResetBoard={resetBoard} lastSaved={lastSaved} saving={saving}/>
              </div>
            )}
            <div style={{ flex:1,overflow:"auto",padding:"14px 16px" }}>
              <div style={{ display:"flex",gap:12,alignItems:"flex-start",width:"100%",paddingBottom:16 }}>
                {COLUMNS.map(col=>(
                  <KanbanColumn key={col.id} col={col} tasks={visible.filter(t=>t.col===col.id)}
                    onDrop={handleDrop} onDragStart={handleDragStart}
                    onCardClick={setEditTask} onAddTask={c=>setEditTask({col:c})}/>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Modals */}
      {editTask    &&<TaskModal    task={editTask} onSave={handleSaveTask} onDelete={handleDeleteTask} onClose={()=>setEditTask(null)}/>}
      {showAI      &&<AIPanel      tasks={tasks} onAddTasks={handleAddTasks} onClose={()=>setShowAI(false)}/>}
      {showSettings&&<SettingsModal onClose={()=>setShowSettings(false)}/>}

      {/* Confirm: delete task */}
      <Confirm
        open={!!confirmDelete}
        title="Delete this task?"
        message="This task will be permanently removed from the board."
        confirmLabel="DELETE"
        danger
        onConfirm={doDeleteTask}
        onCancel={()=>setConfirmDelete(null)}
      />

      {/* Confirm: reset board */}
      <Confirm
        open={confirmReset}
        title="Reset board to defaults?"
        message="All current tasks will be replaced with the default seed tasks. This cannot be undone."
        confirmLabel="RESET"
        danger
        onConfirm={doResetBoard}
        onCancel={()=>setConfirmReset(false)}
      />
    </div>
  );
}
