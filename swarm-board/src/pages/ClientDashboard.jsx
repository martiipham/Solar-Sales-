/**
 * ClientDashboard — client portal (solar-dashboard-v3 design).
 *
 * Design: JetBrains Mono + Plus Jakarta Sans, #04070E bg, #22D3EE accent
 * APIs:   /api/voice/status · /api/calls/stats · /api/calls · /api/swarm/leads
 *         /api/agents/config (GET+PATCH) · /api/reports/monthly · /api/reports/weekly
 * Auth:   useAuth() → { user, logout, apiFetch }
 */
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../AuthContext";

// ─── Design tokens ─────────────────────────────────────────────────────────
const T = {
  bg:         "#04070E",
  panel:      "#080D1A",
  card:       "#0B1222",
  surface:    "#111C30",
  border:     "#12203A",
  borderHov:  "#1E3558",
  accent:     "#22D3EE",
  amber:      "#F5A623",
  green:      "#34D399",
  red:        "#F87171",
  orange:     "#FB923C",
  purple:     "#A78BFA",
  blue:       "#60A5FA",
  teal:       "#2DD4BF",
  white:      "#F1F5F9",
  text:       "#94A3B8",
  textLight:  "#CBD5E1",
  muted:      "#475569",
  dim:        "#0F172A",
};
const a = (c, o) => c + Math.round(o * 255).toString(16).padStart(2, "0");

// ─── Global styles ──────────────────────────────────────────────────────────
const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
  * { box-sizing:border-box; margin:0; padding:0; }
  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:${T.border}; border-radius:4px; }
  ::-webkit-scrollbar-thumb:hover { background:${T.borderHov}; }
  @keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  @keyframes breathe { 0%,100%{box-shadow:0 0 4px ${a(T.green,.4)}} 50%{box-shadow:0 0 12px ${a(T.green,.7)}} }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  @keyframes tooltipIn { from{opacity:0;transform:translateY(4px) scale(.97)} to{opacity:1;transform:translateY(0) scale(1)} }
  .fadeUp { animation:fadeUp .3s ease both; }
  .fadeUp-1{animation-delay:.04s} .fadeUp-2{animation-delay:.08s}
  .fadeUp-3{animation-delay:.12s} .fadeUp-4{animation-delay:.16s}
  .row-hover { transition:background .12s; }
  .row-hover:hover { background:${a(T.accent,.04)} !important; cursor:pointer; }
  .nav-btn { transition:all .15s; }
  .nav-btn:hover { background:${a(T.accent,.06)} !important; color:${T.accent} !important; }
  input,select,textarea { outline:none; font-family:'Plus Jakarta Sans',sans-serif; }
  input:focus,select:focus,textarea:focus { border-color:${T.accent}!important; box-shadow:0 0 0 3px ${a(T.accent,.1)}!important; }
  .toggle-track { position:relative;width:40px;height:22px;border-radius:11px;cursor:pointer;transition:all .2s;flex-shrink:0; }
  .toggle-track.off { background:${T.surface};border:1px solid ${T.border}; }
  .toggle-track.on  { background:${a(T.accent,.25)};border:1px solid ${a(T.accent,.5)}; }
  .toggle-knob { position:absolute;top:2px;width:16px;height:16px;border-radius:50%;transition:all .2s cubic-bezier(.34,1.56,.64,1); }
  .toggle-track.off .toggle-knob { left:2px;background:${T.muted}; }
  .toggle-track.on  .toggle-knob { left:20px;background:${T.accent};box-shadow:0 0 8px ${a(T.accent,.5)}; }
  .slider-wrap input[type=range] { -webkit-appearance:none;width:100%;height:4px;background:${T.surface};border-radius:2px;border:none!important;box-shadow:none!important; }
  .slider-wrap input[type=range]::-webkit-slider-thumb { -webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:${T.accent};cursor:pointer;border:2px solid ${T.bg};box-shadow:0 0 6px ${a(T.accent,.4)}; }
`;

// ─── MOCK / demo data ───────────────────────────────────────────────────────
const MOCK = {
  voiceStatus: { active: true },
  stats: {
    this_week:  { calls: 47, completed: 38, avg_duration: "3:42", booking_rate: 24, avg_score: 71 },
    this_month: { calls: 183, completed: 149 },
    today:      { calls: 9 },
  },
  leads: [
    { id:1, name:"James Whitfield", phone:"0412 334 891", suburb:"Balcatta",  state:"WA",  qualification_score:9.2, recommended_action:"call_now",   status:"new",       source:"voice", created_at:"2026-03-09T08:12:00Z", monthly_bill:380, homeowner:true,  score_reason:"Homeowner, $380/mo bill, north-facing Colorbond roof, strong buying signals." },
    { id:2, name:"Priya Sharma",    phone:"0455 771 230", suburb:"Prospect",  state:"SA",  qualification_score:8.5, recommended_action:"call_now",   status:"contacted", source:"voice", created_at:"2026-03-09T08:05:00Z", monthly_bill:340, homeowner:true,  score_reason:"Homeowner, new roof installed 2025, motivated buyer, $340/mo bill." },
    { id:3, name:"Sarah Chen",      phone:"0498 221 047", suburb:"Doncaster", state:"VIC", qualification_score:7.8, recommended_action:"nurture",    status:"new",       source:"email", created_at:"2026-03-09T07:52:00Z", monthly_bill:290, homeowner:true,  score_reason:"Homeowner, $290/mo, needs partner approval before booking." },
    { id:4, name:"Mark Torres",     phone:"0421 009 334", suburb:"Sunnybank", state:"QLD", qualification_score:6.1, recommended_action:"nurture",    status:"new",       source:"voice", created_at:"2026-03-08T14:22:00Z", monthly_bill:220, homeowner:false, score_reason:"Renter, long-term interest, $220/mo bill." },
    { id:5, name:"Tom Nguyen",      phone:"0403 118 556", suburb:"Capalaba",  state:"QLD", qualification_score:4.3, recommended_action:"nurture",    status:"new",       source:"email", created_at:"2026-03-08T11:30:00Z", monthly_bill:180, homeowner:false },
    { id:6, name:"Lisa Bowen",      phone:"0477 340 882", suburb:"Mandurah",  state:"WA",  qualification_score:2.1, recommended_action:"disqualify", status:"closed",    source:"voice", created_at:"2026-03-07T09:15:00Z", monthly_bill:90,  homeowner:false },
  ],
  calls: [
    { call_id:"c001", from_phone:"0412 334 891", to_phone:"1800 SOLAR1", status:"completed", duration_seconds:272, duration_fmt:"4:32", lead_score:87, started_at:"2026-03-09T08:14:00Z", transcript:[
      { role:"agent", content:"Hi, thanks for calling Solar Sales! I'm your AI assistant. How can I help you today?" },
      { role:"user",  content:"Hi, I saw your ad — I'm interested in going solar for my home in Balcatta." },
      { role:"agent", content:"Great choice! Balcatta gets excellent sun year-round. What's your approximate monthly power bill?" },
      { role:"user",  content:"Around $380, maybe a bit more in summer." },
      { role:"agent", content:"Perfect — that usage would suit a 6.6kW system nicely, cutting your bill by roughly $1,400/year. Are you the homeowner?" },
      { role:"user",  content:"Yes, I own the house." },
      { role:"agent", content:"Wonderful. I'll book a free assessment — does this Thursday 2pm work?" },
      { role:"user",  content:"Thursday 2pm is perfect." },
      { role:"agent", content:"Booked! You'll get a confirmation SMS shortly. Looking forward to helping you go solar, James." },
    ]},
    { call_id:"c002", from_phone:"0455 771 230", to_phone:"1800 SOLAR1", status:"completed", duration_seconds:322, duration_fmt:"5:22", lead_score:85, started_at:"2026-03-09T08:05:00Z", transcript:[
      { role:"agent", content:"Hi, thanks for calling Solar Sales!" },
      { role:"user",  content:"Hi, I want to get a solar quote for my home in Prospect." },
    ]},
    { call_id:"c003", from_phone:"0498 221 047", to_phone:"1800 SOLAR1", status:"completed", duration_seconds:198, duration_fmt:"3:18", lead_score:72, started_at:"2026-03-09T07:52:00Z", transcript:[] },
    { call_id:"c004", from_phone:"0421 009 334", to_phone:"1800 SOLAR1", status:"failed",    duration_seconds:18,  duration_fmt:"0:18", lead_score:20, started_at:"2026-03-08T14:22:00Z", transcript:[] },
    { call_id:"c005", from_phone:"0403 118 556", to_phone:"1800 SOLAR1", status:"completed", duration_seconds:241, duration_fmt:"4:01", lead_score:68, started_at:"2026-03-08T11:30:00Z", transcript:[] },
    { call_id:"c006", from_phone:"0477 340 882", to_phone:"1800 SOLAR1", status:"completed", duration_seconds:87,  duration_fmt:"1:27", lead_score:34, started_at:"2026-03-07T09:15:00Z", transcript:[] },
  ],
  monthly: {
    period:     { label:"March 2026" },
    calls:      { current:{ calls:183 }, vs_prior:"+12%" },
    leads:      { current:{ conversion_rate:24.4, avg_score:71, hot:18 }, vs_prior:"+8%" },
    highlights: [
      "183 inbound calls handled — up 12% on February",
      "24.4% booking conversion rate, best month on record",
      "18 high-priority leads (score ≥ 80) identified",
      "Average call duration improved to 3m 42s",
    ],
  },
  weekly: {
    totals: { calls:47, leads:31, hot_leads:8, conversions:11 },
    days: Array.from({ length:30 }, (_, i) => {
      const d = new Date("2026-02-09"); d.setDate(d.getDate() + i);
      return { date:d.toISOString().slice(0,10), calls:Math.floor(Math.random()*12)+(i%7<5?3:0) };
    }),
    funnel: [
      { label:"Calls Received",    value:47, color:T.accent },
      { label:"Leads Created",     value:31, color:T.blue   },
      { label:"Qualified (≥5)",    value:22, color:T.amber  },
      { label:"Hot Leads (≥8)",    value:8,  color:T.orange },
      { label:"Booked Assessment", value:5,  color:T.green  },
    ],
  },
  // Default Retell AI config (client can adjust)
  retell: {
    voice: {
      greeting:    "Hi, thanks for calling Solar Sales! I'm your AI assistant. I can help you with solar quotes, book a free assessment, or connect you with the team. How can I help?",
      model:       "eleven_turbo_v2",
      language:    "en-AU",
      temperature: "1.0",
      speed:       "1.0",
      emotion:     "friendly",
      dynSpeed:    true,
      normalize:   true,
    },
    behavior: {
      responsiveness:  "0.8",
      dynRespond:      true,
      interruptSens:   "0.7",
      backchannel:     true,
      backchFreq:      "0.8",
      backchWords:     "yeah,uh-huh,right,sure,mmhmm",
      reminderMs:      "10000",
      reminderMax:     "2",
      beginDelay:      "1000",
      ambientSound:    "office",
      ambientVol:      "0.4",
    },
    calls: {
      maxDuration:      "300000",
      silenceTimeout:   "30000",
      vmDetect:         true,
      vmMessage:        "Hi, this is Solar Sales AI. One of our team members will call you back shortly — thanks!",
      escalateKeywords: "manager,complaint,angry,urgent,speak to a person",
      hotScore:         "8",
      allowDtmf:        false,
    },
    transcription: {
      sttMode:  "fast",
      keywords: "solar,Colorbond,inverter,kW,kilowatt,STC,feed-in tariff",
    },
    analysis: {
      model:         "gpt-4.1-mini",
      successPrompt: "The agent successfully qualified the caller, captured their details (name, suburb, bill, homeowner status), and either booked an assessment or moved them to nurture.",
      summaryPrompt: "Summarize in 2-3 sentences: caller name, location, monthly bill, system interest, homeowner status, and outcome (booked/nurture/disqualified).",
      customFields:  '[{"type":"string","name":"caller_name"},{"type":"string","name":"suburb"},{"type":"number","name":"monthly_bill"},{"type":"boolean","name":"is_homeowner"},{"type":"string","name":"outcome"}]',
    },
    notifications: {
      slackEnabled:  true,
      hotLeadAlert:  true,
      dailyBrief:    true,
      emailApproval: false,
      slackWebhook:  "",
    },
    sync: {
      syncInterval: "15",
      autoQualify:  true,
      autoPushGHL:  true,
    },
  },
};

// ─── InfoTip ────────────────────────────────────────────────────────────────
function InfoTip({ text }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  return (
    <span ref={ref} style={{ position:"relative", display:"inline-flex", alignItems:"center", marginLeft:5 }}>
      <span
        onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        style={{
          width:15, height:15, borderRadius:"50%", cursor:"help",
          background: open ? a(T.accent,.15) : a(T.muted,.15),
          border:`1px solid ${open ? a(T.accent,.35) : a(T.muted,.25)}`,
          display:"inline-flex", alignItems:"center", justifyContent:"center",
          fontSize:8, fontWeight:700, fontFamily:"JetBrains Mono",
          color: open ? T.accent : T.muted, transition:"all .15s",
        }}
      >?</span>
      {open && (
        <div style={{
          position:"absolute", bottom:"calc(100% + 8px)", left:"50%", transform:"translateX(-50%)",
          background:T.panel, border:`1px solid ${T.borderHov}`, borderRadius:8,
          padding:"10px 14px", width:240, zIndex:9999,
          boxShadow:`0 8px 32px ${a("#000",.5)}`, animation:"tooltipIn .15s ease",
        }}>
          <div style={{ position:"absolute", bottom:-5, left:"50%", transform:"translateX(-50%) rotate(45deg)", width:8, height:8, background:T.panel, borderRight:`1px solid ${T.borderHov}`, borderBottom:`1px solid ${T.borderHov}` }} />
          <div style={{ color:T.textLight, fontSize:12, lineHeight:1.6 }}>{text}</div>
        </div>
      )}
    </span>
  );
}

// ─── Atoms ──────────────────────────────────────────────────────────────────
const Mono = ({ children, style }) => (
  <span style={{ fontFamily:"'JetBrains Mono',monospace", ...style }}>{children}</span>
);

const ScoreBadge = ({ score }) => {
  if (score == null) return <Mono style={{ color:T.muted, fontSize:11 }}>—</Mono>;
  const n = Number(score);
  const color = n >= 80 ? T.green : n >= 50 ? T.amber : T.red;
  // normalise: API returns 0-100, MOCK uses 0-10
  const display = n > 10 ? n : (n * 10).toFixed(0);
  return (
    <span style={{
      background:a(color,.1), border:`1px solid ${a(color,.25)}`,
      color, borderRadius:6, padding:"2px 9px",
      fontSize:11, fontFamily:"'JetBrains Mono',monospace", fontWeight:600,
    }}>{display}</span>
  );
};

const ActionPill = ({ action }) => {
  const s = (action||"").toLowerCase();
  let color = T.muted, label = action || "—";
  if (s.includes("call"))     { color = T.green;  label = "CALL NOW"; }
  else if (s.includes("nurt")) { color = T.purple; label = "NURTURE"; }
  else if (s.includes("dis"))  { color = T.red;    label = "DISQUALIFY"; }
  return (
    <span style={{
      background:a(color,.08), border:`1px solid ${a(color,.2)}`,
      color, borderRadius:6, padding:"2px 9px",
      fontSize:10, fontFamily:"'JetBrains Mono',monospace", fontWeight:500,
    }}>{label}</span>
  );
};

const StatusDot = ({ active, color: c }) => {
  const col = c || (active ? T.green : T.muted);
  return (
    <span style={{
      display:"inline-block", width:7, height:7, borderRadius:"50%", background:col,
      animation: active ? "breathe 2.5s ease infinite" : "none",
    }} />
  );
};

const Metric = ({ label, value, color = T.accent, sub, prefix = "", info, delay = "" }) => (
  <div className={`fadeUp ${delay}`} style={{
    background:T.card, border:`1px solid ${T.border}`, borderTop:`2px solid ${a(color,.6)}`,
    borderRadius:10, padding:"18px 20px", flex:1, minWidth:130,
  }}>
    <div style={{ display:"flex", alignItems:"center", marginBottom:10 }}>
      <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".12em", textTransform:"uppercase" }}>{label}</Mono>
      {info && <InfoTip text={info} />}
    </div>
    <div style={{ color, fontSize:26, fontFamily:"'JetBrains Mono',monospace", fontWeight:700, letterSpacing:"-.02em" }}>
      {prefix}{value ?? "—"}
    </div>
    {sub && <div style={{ color:T.muted, fontSize:12, marginTop:6 }}>{sub}</div>}
  </div>
);

const ToggleSwitch = ({ on, onChange }) => (
  <div className={`toggle-track ${on?"on":"off"}`} onClick={() => onChange(!on)}>
    <div className="toggle-knob" />
  </div>
);

const SectionLabel = ({ children, info, style }) => (
  <div style={{ display:"flex", alignItems:"center", marginBottom:14, paddingBottom:10, borderBottom:`1px solid ${T.border}`, ...style }}>
    <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".14em", textTransform:"uppercase" }}>{children}</Mono>
    {info && <InfoTip text={info} />}
  </div>
);

const SubLabel = ({ children, info }) => (
  <div style={{ display:"flex", alignItems:"center", marginBottom:8, marginTop:16 }}>
    <Mono style={{ color:a(T.textLight,.7), fontSize:9, letterSpacing:".1em", textTransform:"uppercase" }}>{children}</Mono>
    {info && <InfoTip text={info} />}
  </div>
);

const Field = ({ label, value, onChange, type="text", rows, info, placeholder, mono }) => (
  <div style={{ marginBottom:16 }}>
    <div style={{ display:"flex", alignItems:"center", marginBottom:6 }}>
      <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".1em", textTransform:"uppercase" }}>{label}</Mono>
      {info && <InfoTip text={info} />}
    </div>
    {rows ? (
      <textarea value={value} onChange={e=>onChange(e.target.value)} rows={rows} placeholder={placeholder}
        style={{ width:"100%", background:T.dim, border:`1px solid ${T.border}`, borderRadius:8,
          padding:"10px 14px", color:T.textLight, fontSize:13, fontFamily: mono?"'JetBrains Mono',monospace":"inherit",
          resize:"vertical", lineHeight:1.7, transition:"all .15s" }} />
    ) : (
      <input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder={placeholder}
        style={{ width:"100%", background:T.dim, border:`1px solid ${T.border}`, borderRadius:8,
          padding:"10px 14px", color:T.textLight, fontSize:13, fontFamily: mono?"'JetBrains Mono',monospace":"inherit",
          transition:"all .15s" }} />
    )}
  </div>
);

const SelectField = ({ label, value, onChange, options, info }) => (
  <div style={{ marginBottom:16 }}>
    <div style={{ display:"flex", alignItems:"center", marginBottom:6 }}>
      <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".1em", textTransform:"uppercase" }}>{label}</Mono>
      {info && <InfoTip text={info} />}
    </div>
    <select value={value} onChange={e=>onChange(e.target.value)} style={{
      width:"100%", background:T.dim, border:`1px solid ${T.border}`, borderRadius:8,
      padding:"10px 14px", color:T.textLight, fontSize:13, cursor:"pointer", transition:"all .15s",
      appearance:"none", backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='none' stroke='%23475569' stroke-width='2'%3E%3Cpath d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
      backgroundRepeat:"no-repeat", backgroundPosition:"right 12px center",
    }}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  </div>
);

const Slider = ({ label, value, onChange, min, max, step=0.1, info, unit="" }) => (
  <div style={{ marginBottom:16 }}>
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:6 }}>
      <div style={{ display:"flex", alignItems:"center" }}>
        <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".1em", textTransform:"uppercase" }}>{label}</Mono>
        {info && <InfoTip text={info} />}
      </div>
      <Mono style={{ color:T.accent, fontSize:12, fontWeight:600 }}>{value}{unit}</Mono>
    </div>
    <div className="slider-wrap" style={{ display:"flex", alignItems:"center", gap:10 }}>
      <Mono style={{ color:T.muted, fontSize:9 }}>{min}</Mono>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e=>onChange(e.target.value)} />
      <Mono style={{ color:T.muted, fontSize:9 }}>{max}</Mono>
    </div>
  </div>
);

const ToggleRow = ({ label, desc, on, onChange, info }) => (
  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"13px 0", borderBottom:`1px solid ${T.border}` }}>
    <div style={{ flex:1 }}>
      <div style={{ display:"flex", alignItems:"center", gap:4 }}>
        <span style={{ color:T.textLight, fontSize:13, fontWeight:500 }}>{label}</span>
        {info && <InfoTip text={info} />}
      </div>
      {desc && <div style={{ color:T.muted, fontSize:11, marginTop:2 }}>{desc}</div>}
    </div>
    <ToggleSwitch on={on} onChange={onChange} />
  </div>
);

const Btn = ({ children, onClick, color = T.accent, variant = "default", style, icon }) => {
  const styles = {
    default: { background:a(color,.1), border:`1px solid ${a(color,.3)}`, color },
    solid:   { background:color, border:`1px solid ${color}`, color:T.bg },
    ghost:   { background:"transparent", border:`1px solid ${T.border}`, color:T.muted },
  };
  return (
    <button onClick={onClick} style={{
      ...styles[variant], borderRadius:7, padding:"7px 16px", fontSize:11,
      fontFamily:"'JetBrains Mono',monospace", fontWeight:500, cursor:"pointer",
      display:"inline-flex", alignItems:"center", gap:6, transition:"opacity .15s", ...style,
    }}
      onMouseEnter={e=>e.currentTarget.style.opacity=".75"}
      onMouseLeave={e=>e.currentTarget.style.opacity="1"}
    >
      {icon && <span>{icon}</span>}{children}
    </button>
  );
};

const Card = ({ children, style, glow }) => (
  <div style={{
    background:T.card, border:`1px solid ${T.border}`, borderRadius:12, overflow:"hidden",
    boxShadow: glow ? `0 0 20px ${a(glow,.06)}, inset 0 1px 0 ${a(glow,.05)}` : "none",
    ...style,
  }}>{children}</div>
);

const CardHeader = ({ title, sub, right, info }) => (
  <div style={{
    display:"flex", alignItems:"center", justifyContent:"space-between",
    padding:"14px 18px", borderBottom:`1px solid ${T.border}`,
  }}>
    <div>
      <div style={{ display:"flex", alignItems:"center", gap:6 }}>
        <span style={{ fontSize:14, fontWeight:600, color:T.textLight }}>{title}</span>
        {info && <InfoTip text={info} />}
      </div>
      {sub && <div style={{ fontSize:11, color:T.muted, marginTop:2 }}>{sub}</div>}
    </div>
    {right}
  </div>
);

// ─── Nav ────────────────────────────────────────────────────────────────────
const NAV = [
  { section:"OPERATIONS", items:[
    { id:"overview",   label:"Overview",   icon:"◈" },
    { id:"leads",      label:"Leads",      icon:"◎", badge:"hotLeads" },
    { id:"calls",      label:"Calls",      icon:"◷" },
    { id:"emails",     label:"Emails",     icon:"◻" },
  ]},
  { section:"SYSTEM", items:[
    { id:"agents",     label:"Agents",     icon:"◬" },
    { id:"reporting",  label:"Reporting",  icon:"◫" },
  ]},
  { section:"CONFIG", items:[
    { id:"settings",   label:"Settings",   icon:"◯" },
  ]},
];

// ─── Overview ───────────────────────────────────────────────────────────────
function OverviewPage({ apiFetch, onNavigate }) {
  const [voiceStatus, setVoiceStatus] = useState(null);
  const [stats, setStats]             = useState(null);
  const [leads, setLeads]             = useState([]);
  const [calls, setCalls]             = useState([]);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    if (!apiFetch) {
      setVoiceStatus(MOCK.voiceStatus); setStats(MOCK.stats);
      setLeads(MOCK.leads.slice(0,3)); setCalls(MOCK.calls.slice(0,4));
      setLoading(false); return;
    }
    setLoading(true);
    Promise.all([
      apiFetch("/api/voice/status").then(r=>r.json()).catch(()=>null),
      apiFetch("/api/calls/stats").then(r=>r.json()).catch(()=>null),
      apiFetch("/api/swarm/leads?limit=3").then(r=>r.json()).catch(()=>null),
      apiFetch("/api/calls?limit=4").then(r=>r.json()).catch(()=>null),
    ]).then(([vs,st,ld,cl]) => {
      setVoiceStatus(vs ?? MOCK.voiceStatus); setStats(st ?? MOCK.stats);
      const ll = ld?.leads||(Array.isArray(ld)?ld:[]); setLeads(ll.length?ll:MOCK.leads.slice(0,3));
      const cls = cl?.calls||(Array.isArray(cl)?cl:[]); setCalls(cls.length?cls:MOCK.calls.slice(0,4));
      setLoading(false);
    });
  }, [apiFetch]);

  const aiActive = voiceStatus?.active === true || voiceStatus?.status === "active";
  const week     = stats?.this_week || {};
  const hot      = leads.filter(l => (l.qualification_score ?? 0) >= 8);

  return (
    <div style={{ padding:24 }}>
      {/* Metric row */}
      <div style={{ display:"flex", gap:10, marginBottom:18, flexWrap:"wrap" }}>
        <Metric label="Calls This Week" value={loading?"…":week.calls??0}    color={T.accent}  delay="fadeUp-1" info="Total inbound calls handled by the AI receptionist this week." />
        <Metric label="Completed"       value={loading?"…":week.completed??0} color={T.green}   delay="fadeUp-2" info="Calls where the AI successfully collected lead details." />
        <Metric label="Avg Duration"    value={loading?"…":week.avg_duration??"—"} color={T.amber} delay="fadeUp-3" info="Average call length. Longer calls typically indicate higher engagement." />
        <Metric label="Booking Rate"    value={loading?"…":week.booking_rate??0} color={T.purple} delay="fadeUp-4" unit="%" info="Percentage of qualified calls that result in a booked consultation." />
        <Metric label="AI Status"       value={aiActive?"ONLINE":"OFFLINE"} color={aiActive?T.green:T.muted} delay="fadeUp-4" info="Current status of the AI voice receptionist." />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginBottom:14 }}>
        {/* Recent calls */}
        <Card>
          <CardHeader title="Recent Calls" right={<Btn variant="ghost" onClick={()=>onNavigate("calls")} style={{padding:"4px 10px",fontSize:10}}>VIEW ALL →</Btn>} info="Last 4 calls handled by the AI. Click a row to see the transcript." />
          {calls.map((c, i) => {
            const sc  = c.lead_score ?? 0;
            const col = sc >= 80 ? T.green : sc >= 50 ? T.amber : T.muted;
            return (
              <div key={c.call_id} className="row-hover" style={{
                display:"flex", alignItems:"center", gap:12, padding:"11px 18px",
                borderBottom: i < calls.length-1 ? `1px solid ${T.border}` : "none",
              }}>
                <div style={{ width:32, height:32, borderRadius:8, background:a(c.status==="completed"?T.green:T.red,.08), border:`1px solid ${a(c.status==="completed"?T.green:T.red,.15)}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:14, flexShrink:0 }}>◷</div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ color:T.white, fontSize:13, fontWeight:500, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{c.from_phone}</div>
                  <Mono style={{ color:T.muted, fontSize:10 }}>{c.duration_fmt} · {c.started_at ? new Date(c.started_at).toLocaleTimeString("en-AU",{hour:"2-digit",minute:"2-digit"}) : "—"}</Mono>
                </div>
                <span style={{ background:a(col,.1), border:`1px solid ${a(col,.25)}`, color:col, borderRadius:6, padding:"2px 9px", fontSize:11, fontFamily:"'JetBrains Mono',monospace", fontWeight:600 }}>{sc >= 10 ? sc : (sc*10).toFixed(0)}</span>
              </div>
            );
          })}
        </Card>

        {/* Recent leads */}
        <Card>
          <CardHeader title="Recent Leads" right={<Btn variant="ghost" onClick={()=>onNavigate("leads")} style={{padding:"4px 10px",fontSize:10}}>VIEW ALL →</Btn>} info="Latest prospects scored by the AI." />
          {leads.map((l, i) => (
            <div key={l.id||i} className="row-hover" style={{
              display:"flex", alignItems:"center", gap:12, padding:"11px 18px",
              borderBottom: i < leads.length-1 ? `1px solid ${T.border}` : "none",
            }}>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ color:T.white, fontSize:13, fontWeight:500 }}>{l.name||l.contact_name||"Unknown"}</div>
                <Mono style={{ color:T.muted, fontSize:10 }}>{l.phone||l.email||"—"} · {l.suburb||""}</Mono>
              </div>
              <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                <ScoreBadge score={l.qualification_score} />
                <ActionPill action={l.recommended_action||l.status} />
              </div>
            </div>
          ))}
        </Card>
      </div>

      {/* Hot leads banner */}
      {hot.length > 0 && (
        <Card glow={T.amber} style={{ borderColor:a(T.amber,.25) }}>
          <CardHeader title={`⚡ ${hot.length} Hot Lead${hot.length>1?"s":""} — Call Now`}
            right={<Btn color={T.amber} onClick={()=>onNavigate("leads")} style={{fontSize:10,padding:"4px 10px"}}>ALL LEADS →</Btn>}
            info="These leads scored 8+ — speed to call is the #1 conversion factor in solar sales." />
          <div style={{ display:"flex", gap:12, padding:"14px 18px", flexWrap:"wrap" }}>
            {hot.map(l => (
              <div key={l.id} style={{ flex:1, minWidth:240, background:a(T.amber,.03), border:`1px solid ${a(T.amber,.12)}`, borderRadius:8, padding:"14px 16px" }}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:8 }}>
                  <div>
                    <div style={{ color:T.white, fontWeight:600, fontSize:14 }}>{l.name}</div>
                    <Mono style={{ color:T.muted, fontSize:10 }}>{l.suburb}, {l.state}</Mono>
                  </div>
                  <ScoreBadge score={l.qualification_score} />
                </div>
                <div style={{ display:"flex", gap:6, marginBottom:12 }}>
                  {l.monthly_bill && <Mono style={{ color:T.text, fontSize:10, background:a(T.accent,.06), padding:"2px 8px", borderRadius:4 }}>${l.monthly_bill}/mo</Mono>}
                  {l.homeowner && <Mono style={{ color:T.green, fontSize:10, background:a(T.green,.06), padding:"2px 8px", borderRadius:4 }}>HOMEOWNER</Mono>}
                </div>
                <Btn color={T.green} style={{ width:"100%", justifyContent:"center" }}>CALL {l.phone}</Btn>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ─── Leads ──────────────────────────────────────────────────────────────────
function LeadsPage({ apiFetch }) {
  const [leads, setLeads]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!apiFetch) { setLeads(MOCK.leads); setLoading(false); return; }
    apiFetch("/api/swarm/leads?limit=100")
      .then(r=>r.json())
      .then(d => { const l = d?.leads||(Array.isArray(d)?d:[]); setLeads(l.length?l:MOCK.leads); setLoading(false); })
      .catch(() => { setLeads(MOCK.leads); setLoading(false); });
  }, [apiFetch]);

  const norm = act => {
    const s = (act||"").toLowerCase();
    if (s.includes("call")) return "call_now";
    if (s.includes("nurt")) return "nurture";
    if (s.includes("dis"))  return "disqualify";
    return "other";
  };

  const filtered = filter === "all" ? leads : leads.filter(l => norm(l.recommended_action||l.status) === filter);
  const FILTERS = [
    { id:"all",       label:"All",          count:leads.length,                                                    color:T.accent },
    { id:"call_now",  label:"Call Now",      count:leads.filter(l=>norm(l.recommended_action||l.status)==="call_now").length,  color:T.green  },
    { id:"nurture",   label:"Nurture",       count:leads.filter(l=>norm(l.recommended_action||l.status)==="nurture").length,   color:T.purple },
    { id:"disqualify",label:"Disqualified",  count:leads.filter(l=>norm(l.recommended_action||l.status)==="disqualify").length, color:T.muted  },
  ];

  const statusColor = s => ({ converted:T.green, new:T.accent, contacted:T.amber, closed:T.muted, rejected:T.red }[s]||T.muted);

  return (
    <div style={{ padding:24 }}>
      {/* Filter bar */}
      <div style={{ display:"flex", gap:8, marginBottom:16, flexWrap:"wrap" }}>
        {FILTERS.map(f => (
          <button key={f.id} onClick={()=>setFilter(f.id)} style={{
            background: filter===f.id ? a(f.color,.12) : "transparent",
            border:`1px solid ${filter===f.id ? f.color : T.border}`,
            color: filter===f.id ? f.color : T.muted,
            borderRadius:7, padding:"7px 14px", fontSize:11,
            fontFamily:"'JetBrains Mono',monospace", cursor:"pointer", display:"flex", alignItems:"center", gap:6,
          }}>
            {f.label}
            <span style={{ background:a(filter===f.id?f.color:T.muted,.15), padding:"1px 6px", borderRadius:4, fontSize:9 }}>{f.count}</span>
          </button>
        ))}
      </div>

      <Card style={{ padding:0 }}>
        {/* Table header */}
        <div style={{ display:"grid", gridTemplateColumns:"1.5fr 1fr 80px 120px 80px 80px 36px", padding:"10px 18px", background:T.surface, borderBottom:`1px solid ${T.border}` }}>
          {["Name / Phone","Location","Score","Action","Status","Source",""].map(col => (
            <Mono key={col} style={{ color:T.muted, fontSize:9, letterSpacing:".1em" }}>{col}</Mono>
          ))}
        </div>

        {loading ? (
          <div style={{ padding:24, color:T.muted, fontSize:13 }}>Loading…</div>
        ) : filtered.map(l => {
          const isExp = expanded === l.id;
          return (
            <React.Fragment key={l.id}>
              <div
                className="row-hover"
                onClick={() => setExpanded(isExp ? null : l.id)}
                style={{ display:"grid", gridTemplateColumns:"1.5fr 1fr 80px 120px 80px 80px 36px", padding:"12px 18px", borderBottom:`1px solid ${T.border}`, alignItems:"center", background:isExp?a(T.accent,.03):"transparent" }}
              >
                <div>
                  <div style={{ color:T.white, fontWeight:500, fontSize:13 }}>{l.name||l.contact_name||"Unknown"}</div>
                  <Mono style={{ color:T.muted, fontSize:10 }}>{l.phone||l.email||"—"}</Mono>
                </div>
                <div style={{ fontSize:12, color:T.text }}>{l.suburb||"—"}{l.state?`, ${l.state}`:""}</div>
                <ScoreBadge score={l.qualification_score} />
                <ActionPill action={l.recommended_action||l.status} />
                <Mono style={{ color:statusColor(l.status), fontSize:10, textTransform:"uppercase", fontWeight:500 }}>{l.status||"new"}</Mono>
                <span style={{ background:a(l.source==="voice"?T.accent:T.purple,.08), color:l.source==="voice"?T.accent:T.purple, borderRadius:5, padding:"2px 8px", fontSize:10, fontFamily:"'JetBrains Mono',monospace" }}>{l.source||"—"}</span>
                <span style={{ color:T.muted, fontSize:12, transition:"transform .2s", display:"inline-block", transform:isExp?"rotate(90deg)":"rotate(0)" }}>›</span>
              </div>
              {isExp && (
                <div style={{ background:a(T.accent,.02), borderBottom:`1px solid ${T.border}`, padding:"16px 20px" }}>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:14 }}>
                    <div style={{ background:T.panel, borderRadius:8, padding:"14px 16px", border:`1px solid ${T.border}` }}>
                      <SubLabel>Lead Details</SubLabel>
                      {[["Monthly Bill", l.monthly_bill ? `$${l.monthly_bill}/mo` : "—", T.amber],["Homeowner", l.homeowner==null?"—":l.homeowner?"Yes":"No", l.homeowner?T.green:T.red],["Created", l.created_at?new Date(l.created_at).toLocaleDateString("en-AU"):"—", T.text]].map(([k,v,c])=>(
                        <div key={k} style={{ display:"flex", justifyContent:"space-between", padding:"5px 0" }}>
                          <span style={{ color:T.muted, fontSize:12 }}>{k}</span>
                          <Mono style={{ color:c, fontSize:12, fontWeight:600 }}>{v}</Mono>
                        </div>
                      ))}
                    </div>
                    <div style={{ background:T.panel, borderRadius:8, padding:"14px 16px", border:`1px solid ${T.border}` }}>
                      <SubLabel>Score Reasoning</SubLabel>
                      <div style={{ fontSize:12, color:T.text, lineHeight:1.6 }}>
                        {l.score_reason || "No reasoning available for this lead."}
                      </div>
                    </div>
                    <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                      <SubLabel>Actions</SubLabel>
                      <Btn color={T.green} style={{ justifyContent:"center" }}>Generate Proposal</Btn>
                      <Btn color={T.accent} style={{ justifyContent:"center" }}>Mark Called</Btn>
                      <Btn variant="ghost"  style={{ justifyContent:"center" }}>Close Lead</Btn>
                    </div>
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </Card>
    </div>
  );
}

// ─── Calls ──────────────────────────────────────────────────────────────────
function CallsPage({ apiFetch }) {
  const [calls, setCalls]   = useState([]);
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState({});

  useEffect(() => {
    if (!apiFetch) { setCalls(MOCK.calls); setStats(MOCK.stats); setLoading(false); return; }
    Promise.all([
      apiFetch("/api/calls?limit=50").then(r=>r.json()).catch(()=>null),
      apiFetch("/api/calls/stats").then(r=>r.json()).catch(()=>null),
    ]).then(([cl,st]) => {
      const l = cl?.calls||(Array.isArray(cl)?cl:[]);
      setCalls(l.length?l:MOCK.calls); setStats(st??MOCK.stats); setLoading(false);
    });
  }, [apiFetch]);

  const openCall = useCallback(id => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    // Try to use MOCK transcript first for demo
    const mock = MOCK.calls.find(c => c.call_id === id);
    if (mock?.transcript?.length) { setDetail(d => ({ ...d, [id]: mock.transcript })); }
    if (!apiFetch) return;
    apiFetch(`/api/calls/${id}`).then(r=>r.json())
      .then(d => { const t = d?.call?.transcript || d?.transcript; if (t?.length) setDetail(prev=>({...prev,[id]:t})); })
      .catch(()=>{});
  }, [apiFetch, expanded]);

  const week = stats?.this_week || {};
  const outcomeLabel = c => {
    const sc = c.lead_score ?? 0;
    if (c.status !== "completed") return ["MISSED",T.muted];
    if (sc >= 80) return ["BOOKED",T.green];
    if (sc >= 50) return ["QUALIFIED",T.accent];
    return ["NURTURE",T.purple];
  };

  return (
    <div style={{ padding:24 }}>
      <div style={{ display:"flex", gap:10, marginBottom:18, flexWrap:"wrap" }}>
        <Metric label="This Week"    value={week.calls??0}        color={T.accent}  info="Total calls this week." />
        <Metric label="Completed"    value={week.completed??0}    color={T.green}   info="Calls where the AI collected lead details." />
        <Metric label="Avg Duration" value={week.avg_duration??"—"} color={T.amber} info="Average call length." />
        <Metric label="Avg Score"    value={week.avg_score??0}    color={T.purple}  info="Average lead qualification score this week." />
      </div>

      <Card style={{ padding:0 }}>
        <div style={{ display:"grid", gridTemplateColumns:"1.5fr 120px 100px 100px 80px 36px", padding:"10px 18px", background:T.surface, borderBottom:`1px solid ${T.border}` }}>
          {["Caller","Date","Duration","Outcome","Score",""].map(col=>(
            <Mono key={col} style={{ color:T.muted, fontSize:9, letterSpacing:".1em" }}>{col}</Mono>
          ))}
        </div>

        {loading ? (
          <div style={{ padding:24, color:T.muted, fontSize:13 }}>Loading…</div>
        ) : calls.map(c => {
          const isExp = expanded === c.call_id;
          const [outLabel, outColor] = outcomeLabel(c);
          const transcript = detail[c.call_id] || c.transcript || [];
          return (
            <React.Fragment key={c.call_id}>
              <div
                className="row-hover"
                onClick={() => openCall(c.call_id)}
                style={{ display:"grid", gridTemplateColumns:"1.5fr 120px 100px 100px 80px 36px", padding:"12px 18px", borderBottom:`1px solid ${T.border}`, alignItems:"center", background:isExp?a(T.accent,.03):"transparent" }}
              >
                <div>
                  <Mono style={{ color:T.white, fontSize:13, fontWeight:500 }}>{c.from_phone||"Unknown"}</Mono>
                  <div style={{ color:T.muted, fontSize:11, marginTop:1 }}>{c.call_id}</div>
                </div>
                <Mono style={{ color:T.text, fontSize:12 }}>{c.started_at?new Date(c.started_at).toLocaleDateString("en-AU"):"—"}</Mono>
                <Mono style={{ color:T.textLight, fontSize:13 }}>{c.duration_fmt||"—"}</Mono>
                <span style={{ background:a(outColor,.08), border:`1px solid ${a(outColor,.2)}`, color:outColor, borderRadius:6, padding:"2px 9px", fontSize:10, fontFamily:"'JetBrains Mono',monospace", fontWeight:500 }}>{outLabel}</span>
                <ScoreBadge score={c.lead_score} />
                <span style={{ color:T.muted, fontSize:12, transition:"transform .2s", display:"inline-block", transform:isExp?"rotate(90deg)":"rotate(0)" }}>›</span>
              </div>
              {isExp && (
                <div style={{ background:a(T.accent,.02), borderBottom:`1px solid ${T.border}`, padding:"16px 20px" }}>
                  <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".12em", display:"block", marginBottom:10 }}>TRANSCRIPT</Mono>
                  {transcript.length === 0 ? (
                    <div style={{ color:T.muted, fontSize:12 }}>No transcript available for this call.</div>
                  ) : (
                    <div style={{ display:"flex", flexDirection:"column", gap:8, maxHeight:320, overflowY:"auto" }}>
                      {transcript.map((t, i) => {
                        const isAgent = (t.role||"").toLowerCase() !== "user";
                        return (
                          <div key={i} style={{ display:"flex", flexDirection:isAgent?"row":"row-reverse", gap:8 }}>
                            <div style={{ width:26, height:26, borderRadius:"50%", flexShrink:0, background:isAgent?a(T.amber,.12):a(T.accent,.12), border:`1px solid ${isAgent?a(T.amber,.25):a(T.accent,.25)}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, fontFamily:"'JetBrains Mono',monospace", color:isAgent?T.amber:T.accent }}>
                              {isAgent?"AI":"C"}
                            </div>
                            <div style={{ background:isAgent?a(T.amber,.05):a(T.accent,.05), border:`1px solid ${isAgent?a(T.amber,.12):a(T.accent,.12)}`, borderRadius:8, padding:"8px 12px", maxWidth:"80%" }}>
                              <Mono style={{ fontSize:9, color:isAgent?T.amber:T.accent, display:"block", marginBottom:3, textTransform:"uppercase" }}>{t.role}</Mono>
                              <div style={{ fontSize:12, color:T.text, lineHeight:1.6 }}>{t.content||t.text||""}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </Card>
    </div>
  );
}

// ─── Emails ─────────────────────────────────────────────────────────────────
function EmailsPage() {
  return (
    <div style={{ padding:24 }}>
      <h2 style={{ margin:"0 0 20px", fontSize:20, fontWeight:700, color:T.white }}>Email Inbox</h2>
      <Card>
        <div style={{ padding:48, textAlign:"center", display:"flex", flexDirection:"column", alignItems:"center", gap:16 }}>
          <div style={{ fontSize:40, opacity:.2 }}>◻</div>
          <div style={{ fontSize:14, fontWeight:600, color:T.muted }}>No email inbox connected yet</div>
          <div style={{ fontSize:12, color:T.muted, maxWidth:320, lineHeight:1.6 }}>
            Email automation will appear here once your inbox is connected.
            Contact your account manager to enable email integration.
          </div>
        </div>
      </Card>
    </div>
  );
}

// ─── Agents ─────────────────────────────────────────────────────────────────
function AgentsPage({ apiFetch }) {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);

  const AGENT_META = {
    receptionist:   { icon:"◷", color:T.accent,  desc:"Handles inbound calls 24/7 and qualifies leads via conversation." },
    lead_qualifier: { icon:"◎", color:T.amber,   desc:"Scores leads by urgency, bill size, homeownership, and roof suitability." },
    follow_up:      { icon:"◈", color:T.purple,  desc:"Sends SMS follow-ups to unclosed leads after 24 hours." },
    appointment:    { icon:"◫", color:T.green,   desc:"Books consultations directly into the sales calendar." },
    reporting:      { icon:"◬", color:T.teal,    desc:"Generates weekly performance summaries and exports." },
    crm:            { icon:"◻", color:T.blue,    desc:"Bi-directional sync with GoHighLevel CRM." },
  };

  useEffect(() => {
    if (!apiFetch) { setAgents(MOCK.agents); setLoading(false); return; }
    apiFetch("/api/agents/config").then(r=>r.json())
      .then(d => {
        const list = d?.agents||d?.config||d||[];
        const parsed = Array.isArray(list) ? list : Object.entries(list).map(([k,v])=>({ id:k, name:k, enabled:v?.enabled??v??false, description:v?.description||"" }));
        setAgents(parsed.length ? parsed : MOCK.agents); setLoading(false);
      })
      .catch(() => { setAgents(MOCK.agents); setLoading(false); });
  }, [apiFetch]);

  const toggle = async (id, val) => {
    if (!apiFetch) { setAgents(prev=>prev.map(a=>a.id===id?{...a,enabled:val}:a)); return; }
    setSaving(true);
    setAgents(prev=>prev.map(a=>a.id===id?{...a,enabled:val}:a));
    try { await apiFetch("/api/agents/config",{ method:"PATCH", body:JSON.stringify({id,enabled:val}) }); }
    catch { setAgents(prev=>prev.map(a=>a.id===id?{...a,enabled:!val}:a)); }
    setSaving(false);
  };

  return (
    <div style={{ padding:24 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
        <div>
          <h2 style={{ margin:0, fontSize:20, fontWeight:700, color:T.white }}>AI Agents</h2>
          <div style={{ fontSize:12, color:T.muted, marginTop:4 }}>Enable or disable individual AI components</div>
        </div>
        {saving && <Mono style={{ fontSize:11, color:T.amber }}>Saving…</Mono>}
      </div>

      {loading ? (
        <div style={{ color:T.muted, fontSize:13 }}>Loading…</div>
      ) : (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))", gap:14 }}>
          {agents.map((ag, i) => {
            const meta = AGENT_META[ag.id] || { icon:"◈", color:T.accent, desc:ag.description||"" };
            return (
              <Card key={ag.id||i} glow={ag.enabled?meta.color:undefined} style={{ padding:0, borderTop:`2px solid ${a(meta.color,.5)}` }}>
                <div style={{ padding:"18px 20px" }}>
                  <div style={{ display:"flex", alignItems:"flex-start", gap:12, marginBottom:14 }}>
                    <div style={{ width:40, height:40, borderRadius:10, background:a(meta.color,.1), border:`1px solid ${a(meta.color,.2)}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:18, flexShrink:0 }}>{meta.icon}</div>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ color:T.white, fontWeight:600, fontSize:14 }}>{ag.name||ag.id}</div>
                      <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:3 }}>
                        <StatusDot active={ag.enabled} color={ag.enabled?meta.color:T.muted} />
                        <Mono style={{ color:ag.enabled?meta.color:T.muted, fontSize:10, textTransform:"uppercase" }}>{ag.enabled?"ACTIVE":"DISABLED"}</Mono>
                      </div>
                    </div>
                    <ToggleSwitch on={!!ag.enabled} onChange={v=>toggle(ag.id,v)} />
                  </div>
                  <div style={{ color:T.text, fontSize:12, lineHeight:1.6, marginBottom:14, minHeight:36 }}>
                    {meta.desc || ag.description || "No description available."}
                  </div>
                  <div style={{ display:"flex", justifyContent:"space-between", padding:"8px 0", borderTop:`1px solid ${T.border}` }}>
                    <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".08em" }}>STATUS</Mono>
                    <Mono style={{ color:ag.enabled?meta.color:T.muted, fontSize:10, fontWeight:600 }}>{ag.enabled?"RUNNING":"IDLE"}</Mono>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Reporting ──────────────────────────────────────────────────────────────
function ReportingPage({ apiFetch }) {
  const [monthly, setMonthly] = useState(null);
  const [weekly,  setWeekly]  = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!apiFetch) { setMonthly(MOCK.monthly); setWeekly(MOCK.weekly); setLoading(false); return; }
    Promise.all([
      apiFetch("/api/reports/monthly").then(r=>r.json()).catch(()=>null),
      apiFetch("/api/reports/weekly?days=30").then(r=>r.json()).catch(()=>null),
    ]).then(([m,w]) => { setMonthly(m??MOCK.monthly); setWeekly(w??MOCK.weekly); setLoading(false); });
  }, [apiFetch]);

  const curr   = monthly?.calls?.current  || {};
  const lstat  = monthly?.leads?.current  || {};
  const totals = weekly?.totals           || {};
  const days   = weekly?.days             || [];
  const funnel = weekly?.funnel           || MOCK.weekly.funnel;
  const period = monthly?.period?.label   || "";
  const maxCalls = Math.max(...days.map(d=>d.calls), 1);

  return (
    <div style={{ padding:24, display:"flex", flexDirection:"column", gap:20 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <h2 style={{ margin:0, fontSize:20, fontWeight:700, color:T.white }}>Reporting</h2>
        {period && <Mono style={{ fontSize:11, color:T.muted }}>{period}</Mono>}
      </div>

      {/* KPI row */}
      <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
        <Metric label="Monthly Calls"   value={loading?"…":(curr.calls??0)}                color={T.accent}  sub={monthly?.calls?.vs_prior?`${monthly.calls.vs_prior} vs last month`:undefined} />
        <Metric label="Conversion Rate" value={loading?"…":(lstat.conversion_rate??0)}     color={T.green}   unit="%" sub={monthly?.leads?.vs_prior?`${monthly.leads.vs_prior} vs last month`:undefined} />
        <Metric label="Avg Lead Score"  value={loading?"…":(lstat.avg_score??0)}           color={T.purple}  sub={lstat.hot?`${lstat.hot} hot leads`:undefined} />
        <Metric label="Calls (30d)"     value={loading?"…":(totals.calls??0)}              color={T.teal}    />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        {/* Bar chart */}
        <Card>
          <CardHeader title="Daily Calls (30 days)" info="Each bar = one day. Hover for exact count." />
          <div style={{ padding:"16px 20px" }}>
            {days.length === 0 ? (
              <div style={{ color:T.muted, fontSize:13 }}>No data yet.</div>
            ) : (
              <>
                <div style={{ display:"flex", alignItems:"flex-end", gap:2, height:80, marginBottom:8 }}>
                  {days.map(d => {
                    const pct = (d.calls / maxCalls) * 100;
                    return (
                      <div key={d.date} title={`${d.date}: ${d.calls} calls`} style={{ flex:1, minWidth:0, height:`${Math.max(pct,2)}%`, background:d.calls>0?a(T.accent,.5):a(T.muted,.15), borderRadius:"2px 2px 0 0", cursor:"default", transition:"background .15s" }}
                        onMouseEnter={e=>e.currentTarget.style.background=d.calls>0?T.accent:a(T.muted,.3)}
                        onMouseLeave={e=>e.currentTarget.style.background=d.calls>0?a(T.accent,.5):a(T.muted,.15)} />
                    );
                  })}
                </div>
                <div style={{ display:"flex", justifyContent:"space-between", fontSize:9, color:T.muted, fontFamily:"'JetBrains Mono',monospace" }}>
                  <span>{days[0]?.date?.slice(5)}</span><span>{days[days.length-1]?.date?.slice(5)}</span>
                </div>
              </>
            )}
          </div>
        </Card>

        {/* Funnel */}
        <Card>
          <CardHeader title="Lead Funnel" info="Conversion funnel from call received to booked assessment." />
          <div style={{ padding:"16px 20px", display:"flex", flexDirection:"column", gap:12 }}>
            {funnel.map((s, i) => (
              <div key={i}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                  <span style={{ color:T.textLight, fontSize:12 }}>{s.label}</span>
                  <Mono style={{ color:s.color, fontSize:12, fontWeight:700 }}>{s.value}</Mono>
                </div>
                <div style={{ height:8, background:T.dim, borderRadius:4, overflow:"hidden" }}>
                  <div style={{ height:"100%", width:`${(s.value/(funnel[0]?.value||1))*100}%`, background:s.color, borderRadius:4, opacity:.75, transition:"width .6s ease" }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Totals + Highlights */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
        <Card>
          <CardHeader title="30-Day Totals" />
          <div style={{ padding:"4px 0 8px" }}>
            {[["Calls",T.accent,totals.calls??0],["Leads",T.amber,totals.leads??0],["Hot Leads",T.red,totals.hot_leads??0],["Conversions",T.green,totals.conversions??0]].map(([label,color,value])=>(
              <div key={label} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"10px 18px", borderBottom:`1px solid ${T.border}` }}>
                <span style={{ fontSize:13, color:T.textLight }}>{label}</span>
                <Mono style={{ fontSize:18, fontWeight:700, color }}>{value}</Mono>
              </div>
            ))}
          </div>
        </Card>
        {monthly?.highlights?.length > 0 && (
          <Card>
            <CardHeader title="Highlights" sub="Key observations this month" />
            <div style={{ padding:"12px 20px 16px", display:"flex", flexDirection:"column", gap:8 }}>
              {monthly.highlights.map((h,i) => (
                <div key={i} style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
                  <span style={{ color:T.accent, fontSize:12, marginTop:2 }}>◆</span>
                  <span style={{ fontSize:13, color:T.text, lineHeight:1.5 }}>{h}</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

// ─── Settings ───────────────────────────────────────────────────────────────
function SettingsPage({ user }) {
  const [tab, setTab]     = useState("company");
  const [cfg, setCfg]     = useState(MOCK.retell);
  const [saved, setSaved] = useState(false);

  const set = (sec, key, val) => setCfg(p => ({ ...p, [sec]:{ ...p[sec], [key]:val } }));
  const save = () => { setSaved(true); setTimeout(() => setSaved(false), 2500); };

  const TABS = [
    { id:"company",        label:"Company",          icon:"◈", desc:"Business details" },
    { id:"voice",          label:"Voice AI",         icon:"◷", desc:"Greeting & TTS" },
    { id:"behavior",       label:"Conversation",     icon:"◎", desc:"Timing & dynamics" },
    { id:"calls",          label:"Call Handling",    icon:"◫", desc:"Duration & voicemail" },
    { id:"transcription",  label:"Transcription",    icon:"◬", desc:"STT & keywords" },
    { id:"analysis",       label:"Post-Call AI",     icon:"◻", desc:"Extraction prompts" },
    { id:"notifications",  label:"Notifications",    icon:"◳", desc:"Alerts & Slack" },
    { id:"sync",           label:"CRM Sync",         icon:"⊙", desc:"GoHighLevel" },
  ];

  return (
    <div style={{ padding:24, display:"flex", gap:16 }}>
      {/* Tab sidebar */}
      <div style={{ width:190, flexShrink:0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={()=>setTab(t.id)} className="nav-btn" style={{
            display:"flex", alignItems:"center", gap:10, width:"100%",
            padding:"10px 14px", borderRadius:8, marginBottom:4,
            background: tab===t.id ? a(T.accent,.06) : "transparent",
            border:`1px solid ${tab===t.id ? a(T.accent,.18) : "transparent"}`,
            color: tab===t.id ? T.accent : T.muted,
            fontSize:13, fontWeight: tab===t.id ? 600 : 400,
            cursor:"pointer", textAlign:"left",
          }}>
            <span style={{ fontSize:14, width:18, textAlign:"center" }}>{t.icon}</span>
            <div>
              <div>{t.label}</div>
              {tab===t.id && <div style={{ fontSize:9, opacity:.7, marginTop:1 }}>{t.desc}</div>}
            </div>
            {tab===t.id && <span style={{ marginLeft:"auto", width:5, height:5, borderRadius:"50%", background:T.accent, boxShadow:`0 0 8px ${T.accent}` }} />}
          </button>
        ))}
      </div>

      {/* Content panel */}
      <div style={{ flex:1, background:T.card, border:`1px solid ${T.border}`, borderRadius:12, padding:"24px 28px", minWidth:0 }}>

        {/* ── Company ── */}
        {tab === "company" && <>
          <SectionLabel info="Your business details used in proposals, email signatures, and customer-facing communications.">Company Profile</SectionLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <Field label="Company Name" value={user?.company||""} onChange={()=>{}} placeholder="Solar Sales Co" info="Shown on proposals and email headers." />
            <Field label="Contact Name" value={user?.name||""} onChange={()=>{}} info="Your name shown to leads." />
            <Field label="Phone"        value={user?.phone||""} onChange={()=>{}} placeholder="1300 765 274" />
            <Field label="Email"        value={user?.email||""} onChange={()=>{}} />
            <Field label="Website"      value="" onChange={()=>{}} placeholder="solarsales.com.au" />
            <SelectField label="State" value="WA" onChange={()=>{}} options={["WA","NSW","VIC","QLD","SA","TAS","NT","ACT"].map(s=>({value:s,label:s}))} />
          </div>
        </>}

        {/* ── Voice AI ── */}
        {tab === "voice" && <>
          <SectionLabel info="Configure how the AI voice receptionist greets callers and sounds on the phone.">Voice AI Configuration</SectionLabel>
          <Field label="AI Greeting" value={cfg.voice.greeting} onChange={v=>set("voice","greeting",v)} rows={3}
            info="The first thing callers hear. Keep it under 25 seconds spoken. Mention your company name and main offer." />
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <SelectField label="Voice Model" value={cfg.voice.model} onChange={v=>set("voice","model",v)}
              info="TTS engine model. Turbo v2 is fastest with lowest latency — recommended for live calls."
              options={[{value:"eleven_turbo_v2",label:"ElevenLabs Turbo v2 (Fast)"},{value:"eleven_flash_v2",label:"ElevenLabs Flash v2"},{value:"eleven_multilingual_v2",label:"ElevenLabs Multilingual v2"}]} />
            <SelectField label="Language" value={cfg.voice.language} onChange={v=>set("voice","language",v)}
              info="BCP-47 language code. Use en-AU for the Australian market — improves accent detection."
              options={[{value:"en-AU",label:"English (Australia)"},{value:"en-US",label:"English (US)"},{value:"en-GB",label:"English (UK)"}]} />
            <SelectField label="Voice Emotion" value={cfg.voice.emotion} onChange={v=>set("voice","emotion",v)}
              info="Tone of the AI's voice. Friendly works well for solar sales."
              options={[{value:"friendly",label:"Friendly"},{value:"professional",label:"Professional"},{value:"cheerful",label:"Cheerful"},{value:"calm",label:"Calm"}]} />
          </div>
          <Slider label="Voice Speed" value={cfg.voice.speed} onChange={v=>set("voice","speed",v)} min={0.5} max={2} step={0.05}
            info="Speech rate multiplier. 0.9–1.05 is most natural for Australian callers." />
          <Slider label="Voice Temperature" value={cfg.voice.temperature} onChange={v=>set("voice","temperature",v)} min={0} max={2} step={0.1}
            info="Controls voice variation. 0 = very stable, 2 = more expressive. 0.8–1.2 recommended." />
          <ToggleRow label="Dynamic Speed Matching" on={cfg.voice.dynSpeed} onChange={v=>set("voice","dynSpeed",v)}
            desc="AI automatically adjusts speaking speed to match the caller's pace"
            info="Highly recommended — makes the AI feel much more natural and human-like." />
          <ToggleRow label="Normalize for Speech" on={cfg.voice.normalize} onChange={v=>set("voice","normalize",v)}
            desc="Convert numbers and abbreviations to spoken words ($380 → 'three hundred and eighty dollars')"
            info="Prevents the AI from saying '$380' as 'dollar-sign-three-eight-zero'." />
        </>}

        {/* ── Behavior ── */}
        {tab === "behavior" && <>
          <SectionLabel info="Controls how the AI times its responses and handles natural conversation flow.">Conversation Dynamics</SectionLabel>
          <Slider label="Responsiveness" value={cfg.behavior.responsiveness} onChange={v=>set("behavior","responsiveness",v)} min={0} max={1} step={0.05}
            info="How quickly the AI replies after the caller stops speaking. 0 = waits longer (patient), 1 = replies instantly. 0.7–0.85 is natural." />
          <Slider label="Interruption Sensitivity" value={cfg.behavior.interruptSens} onChange={v=>set("behavior","interruptSens",v)} min={0} max={1} step={0.05}
            info="How easily a caller can cut in mid-sentence. 0 = AI never stops, 1 = stops immediately. 0.6–0.75 recommended." />
          <ToggleRow label="Dynamic Responsiveness" on={cfg.behavior.dynRespond} onChange={v=>set("behavior","dynRespond",v)}
            desc="Auto-adjust response timing based on caller's pace throughout the call"
            info="The AI adapts in real-time — speaks faster with fast talkers, slower with methodical ones." />
          <SubLabel info="Natural 'uh-huh' and 'yeah' sounds while the caller is speaking.">Backchannel</SubLabel>
          <ToggleRow label="Enable Backchannel" on={cfg.behavior.backchannel} onChange={v=>set("behavior","backchannel",v)}
            desc={'AI says "yeah", "uh-huh" naturally while caller speaks — makes it feel human'}
            info="Strongly recommended. Without this, the AI sounds robotic during caller monologues." />
          {cfg.behavior.backchannel && <>
            <Slider label="Backchannel Frequency" value={cfg.behavior.backchFreq} onChange={v=>set("behavior","backchFreq",v)} min={0} max={1} step={0.05}
              info="How often the AI backchannels. 0.6–0.85 sounds most natural." />
            <Field label="Backchannel Words" value={cfg.behavior.backchWords} onChange={v=>set("behavior","backchWords",v)}
              placeholder="yeah,uh-huh,right,sure" mono info="Comma-separated words. Test with your chosen voice — some sound better with certain words." />
          </>}
          <SubLabel info="Ambient background sound played during the call to make it feel like a real office.">Ambient Sound</SubLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <SelectField label="Background Sound" value={cfg.behavior.ambientSound} onChange={v=>set("behavior","ambientSound",v)}
              info="Subtle background noise. 'Office' recommended for solar sales."
              options={[{value:"none",label:"None (Silent)"},{value:"office",label:"Office"},{value:"coffee-shop",label:"Coffee Shop"},{value:"convention-hall",label:"Convention Hall"}]} />
            <Slider label="Ambient Volume" value={cfg.behavior.ambientVol} onChange={v=>set("behavior","ambientVol",v)} min={0} max={1} step={0.05}
              info="Keep low (0.3–0.5) so it doesn't interfere with the conversation." />
          </div>
          <SubLabel info="How the AI handles silence and reminds callers.">Silence Handling</SubLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <Field label="Reminder After Silence (ms)" value={cfg.behavior.reminderMs} onChange={v=>set("behavior","reminderMs",v)} type="number"
              info="If the caller is silent for this long after the AI speaks, it will gently prompt them. Default: 10000 (10s)." />
            <Field label="Max Reminders" value={cfg.behavior.reminderMax} onChange={v=>set("behavior","reminderMax",v)} type="number"
              info="How many times the AI will prompt before wrapping up the call. Default: 2." />
          </div>
        </>}

        {/* ── Call Handling ── */}
        {tab === "calls" && <>
          <SectionLabel info="Controls how the AI manages the call lifecycle — duration, voicemail, and escalation.">Call Handling</SectionLabel>
          <SubLabel>Duration & Timeouts</SubLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <Field label="Max Call Duration (ms)" value={cfg.calls.maxDuration} onChange={v=>set("calls","maxDuration",v)} type="number"
              info="Maximum call length before the AI wraps up. 300000 = 5 min. Default: 300000 for solar sales (most calls are 3–6 min)." />
            <Field label="Silence Timeout (ms)" value={cfg.calls.silenceTimeout} onChange={v=>set("calls","silenceTimeout",v)} type="number"
              info="End call after this much silence. 30000 = 30s. Default: 30000." />
          </div>
          <SubLabel info="Detect answering machines on outbound calls and leave a pre-recorded message.">Voicemail Detection</SubLabel>
          <ToggleRow label="Enable Voicemail Detection" on={cfg.calls.vmDetect} onChange={v=>set("calls","vmDetect",v)}
            desc="Detect voicemail/answering machines and leave a custom message"
            info="AI detects if it reached voicemail in the first 30s and leaves your custom message instead of waiting." />
          {cfg.calls.vmDetect && (
            <Field label="Voicemail Message" value={cfg.calls.vmMessage} onChange={v=>set("calls","vmMessage",v)} rows={2}
              info="Keep under 20 seconds spoken. Include your company name and a callback number." />
          )}
          <SubLabel info="Platform-level settings for your solar sales workflow.">Lead & Escalation Rules</SubLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <Field label="Hot Lead Score Threshold" value={cfg.calls.hotScore} onChange={v=>set("calls","hotScore",v)} type="number"
              info="Leads scoring above this trigger an instant notification. Default: 8 (out of 10)." />
            <Field label="Escalation Keywords" value={cfg.calls.escalateKeywords} onChange={v=>set("calls","escalateKeywords",v)} mono
              info="Comma-separated words. If a caller says any of these, the AI immediately transfers to a human. E.g: manager,complaint,angry" />
          </div>
          <ToggleRow label="Allow DTMF (Keypad Input)" on={cfg.calls.allowDtmf} onChange={v=>set("calls","allowDtmf",v)}
            desc="Let callers press keypad digits during the call"
            info="Only enable if you need callers to enter IDs or make menu selections. Not typically needed for solar sales." />
        </>}

        {/* ── Transcription ── */}
        {tab === "transcription" && <>
          <SectionLabel info="Controls how accurately calls are transcribed. Better transcription = better lead scoring.">Speech-to-Text (STT)</SectionLabel>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 20px" }}>
            <SelectField label="STT Mode" value={cfg.transcription.sttMode} onChange={v=>set("transcription","sttMode",v)}
              info="Fast = lower latency (recommended for live calls). Accurate = higher quality but slightly slower."
              options={[{value:"fast",label:"Fast (Low latency — recommended)"},{value:"accurate",label:"Accurate (Higher quality)"}]} />
          </div>
          <SubLabel info="Words the AI commonly mishears. Adding your key terms dramatically improves transcript accuracy.">Boosted Keywords</SubLabel>
          <Field label="Keywords to Boost" value={cfg.transcription.keywords} onChange={v=>set("transcription","keywords",v)} rows={3} mono
            placeholder="solar,Colorbond,inverter,kW,kilowatt,STC,feed-in tariff,Balcatta,Subiaco…"
            info="Comma-separated. Add: suburb names you service, your company name, solar jargon (kW, STC, inverter), competitor names. This is one of the highest-impact settings." />
          <div style={{ padding:"12px 16px", background:a(T.blue,.04), border:`1px solid ${a(T.blue,.15)}`, borderRadius:8 }}>
            <Mono style={{ color:T.blue, fontSize:10, fontWeight:600 }}>💡 TIP</Mono>
            <div style={{ color:T.text, fontSize:12, marginTop:6, lineHeight:1.6 }}>Add all suburb names in your service area, your company name, common Australian names, and solar terms. Without this, the AI often mishears "Colorbond" as "colour bond" or "kW" as "cable".</div>
          </div>
        </>}

        {/* ── Analysis ── */}
        {tab === "analysis" && <>
          <SectionLabel info="After each call, the AI runs these prompts to extract structured data and evaluate call quality.">Post-Call AI Analysis</SectionLabel>
          <SelectField label="Analysis Model" value={cfg.analysis.model} onChange={v=>set("analysis","model",v)}
            info="Which AI model evaluates the transcript. Mini is cheaper and fast enough for structured extraction."
            options={[{value:"gpt-4.1-mini",label:"GPT-4.1 Mini (Fast, cost-effective)"},{value:"gpt-4.1",label:"GPT-4.1 (More accurate)"},{value:"gpt-4o",label:"GPT-4o"}]} />
          <Field label="Success Evaluation Prompt" value={cfg.analysis.successPrompt} onChange={v=>set("analysis","successPrompt",v)} rows={3}
            info="Prompt used to determine if the call was successful. The AI evaluates the transcript against this and returns true/false." />
          <Field label="Summary Prompt" value={cfg.analysis.summaryPrompt} onChange={v=>set("analysis","summaryPrompt",v)} rows={3}
            info="Prompt for generating the call summary shown on the Calls page." />
          <Field label="Data Extraction Schema (JSON)" value={cfg.analysis.customFields} onChange={v=>set("analysis","customFields",v)} rows={6} mono
            info='JSON array defining structured fields extracted from every call. Each field needs: type, name, and description. These fields power your lead scoring.' />
          <div style={{ padding:"12px 16px", background:a(T.orange,.04), border:`1px solid ${a(T.orange,.15)}`, borderRadius:8 }}>
            <Mono style={{ color:T.orange, fontSize:10, fontWeight:600 }}>⚡ PRE-CONFIGURED FOR SOLAR</Mono>
            <div style={{ color:T.text, fontSize:12, marginTop:6, lineHeight:1.6 }}>
              Extracts: caller_name, suburb, monthly_bill, is_homeowner, and outcome. These map directly to your Leads table and power qualification scoring.
            </div>
          </div>
        </>}

        {/* ── Notifications ── */}
        {tab === "notifications" && <>
          <SectionLabel info="Configure how and when you receive alerts about new leads, calls, and system events.">Notification Settings</SectionLabel>
          <ToggleRow label="Slack Notifications" on={cfg.notifications.slackEnabled} onChange={v=>set("notifications","slackEnabled",v)}
            desc="Send alerts to your Slack workspace channel"
            info="Requires a Slack webhook URL. Notifications include hot lead alerts, daily briefings, and system warnings." />
          <ToggleRow label="Hot Lead Alerts" on={cfg.notifications.hotLeadAlert} onChange={v=>set("notifications","hotLeadAlert",v)}
            desc={`Instant notification when a lead scores ≥ ${cfg.calls.hotScore}`}
            info="Fires immediately via Slack and/or email when a high-intent lead is captured. Best conversion happens within 5 minutes of a hot lead." />
          <ToggleRow label="Daily Brief" on={cfg.notifications.dailyBrief} onChange={v=>set("notifications","dailyBrief",v)}
            desc="6AM summary of overnight calls, leads, and system activity"
            info="A digest of the previous 24 hours delivered each morning." />
          <ToggleRow label="Email Approval Alerts" on={cfg.notifications.emailApproval} onChange={v=>set("notifications","emailApproval",v)}
            desc="Notify when AI-drafted email replies need your review"
            info="Triggered when the Email Processor has drafted a reply requiring approval before sending." />
          <div style={{ marginTop:16 }}>
            <Field label="Slack Webhook URL" value={cfg.notifications.slackWebhook} onChange={v=>set("notifications","slackWebhook",v)} mono
              placeholder="https://hooks.slack.com/services/T.../B.../..."
              info="Create an Incoming Webhook in your Slack workspace (Manage Apps → Incoming Webhooks) and paste the URL here." />
          </div>
        </>}

        {/* ── CRM Sync ── */}
        {tab === "sync" && <>
          <SectionLabel info="Configure the bi-directional sync between Solar Sales AI and your GoHighLevel CRM.">CRM Sync (GoHighLevel)</SectionLabel>
          <Field label="Sync Interval (minutes)" value={cfg.sync.syncInterval} onChange={v=>set("sync","syncInterval",v)} type="number"
            info="How often qualified leads are pushed to GoHighLevel. Lower = more real-time. 15 minutes is recommended to avoid API rate limits." />
          <ToggleRow label="Auto-Qualify New Leads" on={cfg.sync.autoQualify} onChange={v=>set("sync","autoQualify",v)}
            desc="Score every new lead automatically as soon as a call or email is received"
            info="When disabled, leads sit unscored until you manually trigger qualification." />
          <ToggleRow label="Auto-Push to GoHighLevel" on={cfg.sync.autoPushGHL} onChange={v=>set("sync","autoPushGHL",v)}
            desc={`Automatically create GHL contacts when lead score ≥ ${cfg.calls.hotScore}`}
            info="When disabled, you review and approve each lead before it's pushed to your CRM. Useful when starting out to review AI quality." />
          <div style={{ marginTop:16, padding:"12px 16px", background:a(T.green,.04), border:`1px solid ${a(T.green,.15)}`, borderRadius:8 }}>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <StatusDot active={true} />
              <Mono style={{ color:T.green, fontSize:11, fontWeight:600 }}>GHL CONNECTED</Mono>
            </div>
            <div style={{ color:T.text, fontSize:12, marginTop:6 }}>GoHighLevel integration is active. Qualified leads sync automatically to your pipeline.</div>
          </div>
        </>}

        {/* Save bar */}
        <div style={{ marginTop:28, display:"flex", alignItems:"center", gap:12, paddingTop:16, borderTop:`1px solid ${T.border}` }}>
          <Btn color={saved?T.green:T.accent} variant={saved?"default":"solid"} onClick={save}>
            {saved ? "✓ SAVED" : "💾 SAVE CHANGES"}
          </Btn>
          {saved && <span style={{ color:T.green, fontSize:13 }}>Settings applied</span>}
        </div>
      </div>
    </div>
  );
}

// ─── Main shell ──────────────────────────────────────────────────────────────
export default function ClientDashboard() {
  const auth     = useAuth?.() || {};
  const user     = auth.user;
  const logout   = auth.logout;
  const apiFetch = auth.apiFetch;

  const [page, setPage] = useState("overview");
  const [clock, setClock] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const hotLeads = MOCK.leads.filter(l => (l.qualification_score ?? 0) >= 8).length;

  const navigate = p => setPage(p);

  const renderPage = () => {
    switch (page) {
      case "overview":     return <OverviewPage    apiFetch={apiFetch} onNavigate={navigate} />;
      case "leads":        return <LeadsPage       apiFetch={apiFetch} />;
      case "calls":        return <CallsPage       apiFetch={apiFetch} />;
      case "emails":       return <EmailsPage />;
      case "agents":       return <AgentsPage      apiFetch={apiFetch} />;
      case "reporting":    return <ReportingPage   apiFetch={apiFetch} />;
      case "settings":     return <SettingsPage    user={user} />;
      default:             return <OverviewPage    apiFetch={apiFetch} onNavigate={navigate} />;
    }
  };

  const pageTitle = NAV.flatMap(g=>g.items).find(i=>i.id===page)?.label || "Overview";

  return (
    <div style={{ display:"flex", height:"100vh", background:T.bg, fontFamily:"'Plus Jakarta Sans',sans-serif", color:T.text, overflow:"hidden" }}>
      <style>{STYLES}</style>

      {/* ── Sidebar ── */}
      <aside style={{ width:220, background:T.panel, borderRight:`1px solid ${T.border}`, display:"flex", flexDirection:"column", flexShrink:0 }}>
        {/* Logo */}
        <div style={{ padding:"18px 16px", borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:34, height:34, background:`linear-gradient(135deg,${T.amber},${T.orange})`, borderRadius:9, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16, flexShrink:0, boxShadow:`0 4px 12px ${a(T.amber,.25)}` }}>☀</div>
          <div>
            <Mono style={{ color:T.white, fontSize:11, fontWeight:700, letterSpacing:".06em" }}>SOLAR SALES</Mono>
            <Mono style={{ color:T.muted, fontSize:8, letterSpacing:".14em" }}>CLIENT PORTAL</Mono>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex:1, padding:"8px", overflowY:"auto" }}>
          {NAV.map(group => (
            <div key={group.section}>
              <Mono style={{ color:T.muted, fontSize:8, letterSpacing:".16em", padding:"14px 10px 4px", display:"block" }}>{group.section}</Mono>
              {group.items.map(item => {
                const active  = page === item.id;
                const badgeCt = item.badge === "hotLeads" ? hotLeads : 0;
                return (
                  <button key={item.id} onClick={()=>navigate(item.id)} className="nav-btn" style={{
                    display:"flex", alignItems:"center", gap:10, width:"100%",
                    padding:"9px 12px", borderRadius:8, marginBottom:2,
                    background: active ? a(T.accent,.06) : "transparent",
                    border:`1px solid ${active ? a(T.accent,.18) : "transparent"}`,
                    color: active ? T.accent : T.muted,
                    fontSize:13, fontWeight: active ? 600 : 400,
                    cursor:"pointer", textAlign:"left",
                  }}>
                    <span style={{ fontSize:13, width:18, textAlign:"center" }}>{item.icon}</span>
                    <span style={{ flex:1 }}>{item.label}</span>
                    {badgeCt > 0 && (
                      <span style={{ background:a(T.amber,.15), color:T.amber, borderRadius:10, padding:"1px 7px", fontSize:9, fontFamily:"'JetBrains Mono',monospace", fontWeight:600 }}>{badgeCt}</span>
                    )}
                    {active && <span style={{ width:5, height:5, borderRadius:"50%", background:T.accent, boxShadow:`0 0 10px ${T.accent}` }} />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div style={{ padding:"12px 14px", borderTop:`1px solid ${T.border}` }}>
          {/* CRM status */}
          <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:10 }}>
            <StatusDot active={true} />
            <Mono style={{ color:T.muted, fontSize:9, letterSpacing:".1em" }}>CRM CONNECTED</Mono>
          </div>
          {/* User pill */}
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:10, padding:"8px 10px", background:T.card, borderRadius:8, border:`1px solid ${T.border}` }}>
            <div style={{ width:26, height:26, borderRadius:"50%", background:a(T.accent,.15), border:`1px solid ${a(T.accent,.3)}`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, color:T.accent, flexShrink:0 }}>
              {(user?.name||user?.email||"C")[0].toUpperCase()}
            </div>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ color:T.white, fontSize:12, fontWeight:600, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{user?.name||user?.email||"Client"}</div>
              <Mono style={{ color:T.muted, fontSize:9 }}>CLIENT</Mono>
            </div>
          </div>
          {/* Sign out */}
          {logout && (
            <button onClick={logout} style={{
              width:"100%", padding:"7px 0", border:`1px solid ${T.border}`,
              background:"transparent", color:T.muted, fontSize:10,
              fontWeight:600, letterSpacing:1, borderRadius:7, cursor:"pointer",
              fontFamily:"'JetBrains Mono',monospace", textTransform:"uppercase", transition:"all .15s",
            }}
              onMouseEnter={e=>{ e.currentTarget.style.borderColor=T.red; e.currentTarget.style.color=T.red; }}
              onMouseLeave={e=>{ e.currentTarget.style.borderColor=T.border; e.currentTarget.style.color=T.muted; }}
            >Sign Out</button>
          )}
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
        {/* Topbar */}
        <div style={{ height:56, background:T.panel, borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", padding:"0 24px", gap:12, flexShrink:0 }}>
          <div style={{ flex:1 }}>
            <div style={{ color:T.white, fontWeight:600, fontSize:16 }}>{pageTitle}</div>
          </div>
          <Mono style={{ color:T.muted, fontSize:10 }}>
            {clock.toLocaleTimeString("en-AU",{ hour:"2-digit", minute:"2-digit", second:"2-digit" })} AWST
          </Mono>
          {hotLeads > 0 && (
            <button onClick={()=>navigate("leads")} style={{
              background:a(T.amber,.12), border:`1px solid ${a(T.amber,.4)}`,
              color:T.amber, borderRadius:20, padding:"4px 12px", fontSize:11,
              cursor:"pointer", fontFamily:"'JetBrains Mono',monospace",
              boxShadow:`0 0 10px ${a(T.amber,.25)}`, animation:"pulse 2s infinite",
            }}>⚡ {hotLeads} HOT LEAD{hotLeads>1?"S":""}</button>
          )}
          <button onClick={()=>navigate("settings")} style={{
            width:32, height:32, borderRadius:8, background:page==="settings"?a(T.accent,.08):"transparent",
            border:`1px solid ${page==="settings"?a(T.accent,.25):T.border}`,
            color:page==="settings"?T.accent:T.muted, cursor:"pointer", fontSize:14, display:"flex", alignItems:"center", justifyContent:"center",
          }}>⚙</button>
        </div>

        {/* Page content */}
        <div key={page} style={{ flex:1, overflowY:"auto" }}>
          {renderPage()}
        </div>
      </div>
    </div>
  );
}
