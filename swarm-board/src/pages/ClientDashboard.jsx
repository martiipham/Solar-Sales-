/**
 * ClientDashboard — client-facing portal wired to real API.
 *
 * Pages: Dashboard · Leads · Calls · Emails · Reports · Billing · Support · Settings
 *
 * Live APIs used:
 *   GET /api/voice/status       — AI receptionist status
 *   GET /api/calls/stats        — call performance metrics
 *   GET /api/calls              — call log (limit 50)
 *   GET /api/calls/:id          — single call detail + transcript
 *   GET /api/swarm/leads        — lead list (qualification_score, name, status, created_at)
 *
 * Static sections: Reports, Billing, Support, Settings (no backend APIs yet)
 * Emails: empty state (no /api/emails endpoint yet)
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

/* ─── Theme ────────────────────────────────────────────────────────────────── */
const G = {
  bg:    "#0B0F1A", surf:  "#111827", card:  "#161E2E", cardH: "#1C2538",
  bdr:   "#1E2D45", bdrL:  "#253550",
  gold:  "#E8B84B", goldD: "#B8891A",
  sky:   "#38BDF8", mint:  "#34D399", rose:  "#FB7185", violet:"#A78BFA",
  txt:   "#CBD5E1", sub:   "#64748B", wht:   "#F8FAFC",
};
function h(col, op) {
  return col + Math.round(op * 255).toString(16).padStart(2, "0");
}

const STYLE = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Outfit:wght@300;400;500;600&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0B0F1A;font-family:'Outfit',sans-serif;color:#CBD5E1}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:#111827}
::-webkit-scrollbar-thumb{background:#1E2D45;border-radius:4px}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.r1{animation:rise .38s cubic-bezier(.16,1,.3,1) both}
.r2{animation:rise .38s cubic-bezier(.16,1,.3,1) .07s both}
.r3{animation:rise .38s cubic-bezier(.16,1,.3,1) .14s both}
.r4{animation:rise .38s cubic-bezier(.16,1,.3,1) .21s both}
.r5{animation:rise .38s cubic-bezier(.16,1,.3,1) .28s both}
.ch{transition:all .18s ease;cursor:pointer}
.ch:hover{background:#1C2538 !important;border-color:#253550 !important;transform:translateY(-1px)}
.btn{transition:all .16s ease;cursor:pointer}
.btn:hover{opacity:.82;transform:translateY(-1px)}
.navbtn{transition:all .14s ease;cursor:pointer}
.navbtn:hover{background:rgba(232,184,75,.07) !important;color:#E8B84B !important}
.row{transition:background .12s;cursor:pointer}
.row:hover{background:rgba(248,250,252,.025) !important}
input,textarea{outline:none;transition:border-color .15s;font-family:'Outfit',sans-serif}
input:focus,textarea:focus{border-color:#E8B84B !important}
.pulse{animation:blink 2.5s ease infinite}
`;

/* ─── Static chart data (no chart API exists yet) ──────────────────────────── */
const CHART = [
  {day:"Mon",calls:18,leads:11},{day:"Tue",calls:24,leads:15},{day:"Wed",calls:31,leads:19},
  {day:"Thu",calls:22,leads:13},{day:"Fri",calls:28,leads:17},{day:"Sat",calls:14,leads:8},{day:"Sun",calls:10,leads:6},
];

/* ─── Nav config ────────────────────────────────────────────────────────────── */
const NAV_CFG = [
  { section: "OVERVIEW", items: [{ id: "dashboard", icon: "◈", label: "Dashboard" }] },
  { section: "MY LEADS", items: [
    { id: "leads",  icon: "⭐", label: "Leads" },
    { id: "calls",  icon: "📞", label: "Calls" },
    { id: "emails", icon: "✉️", label: "Emails" },
  ]},
  { section: "INSIGHTS", items: [{ id: "reporting", icon: "▦", label: "Reports" }] },
  { section: "ACCOUNT",  items: [
    { id: "billing",  icon: "💳", label: "Billing" },
    { id: "support",  icon: "💬", label: "Support" },
    { id: "settings", icon: "⚙",  label: "Settings" },
  ]},
];

const TITLES = {
  dashboard: "Dashboard", leads: "My Leads", calls: "Call History",
  emails: "Email Inbox", reporting: "Reports", billing: "Billing",
  support: "Support", settings: "Settings",
};

/* ─── Shared helpers ────────────────────────────────────────────────────────── */
function Score({ v }) {
  if (v == null) return <span style={{ color: G.sub, fontSize: 13 }}>—</span>;
  const c = v >= 7 ? G.mint : v >= 5 ? G.gold : G.rose;
  return (
    <span style={{ background: h(c, .12), border: `1px solid ${h(c, .3)}`, color: c, borderRadius: 20, padding: "2px 10px", fontSize: 12, fontWeight: 600 }}>
      {Number(v).toFixed(1)}
    </span>
  );
}

function Chip({ label, color }) {
  return (
    <span style={{ background: h(color, .1), border: `1px solid ${h(color, .25)}`, color, borderRadius: 20, padding: "3px 10px", fontSize: 11, fontWeight: 500, whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function Avt({ name, size }) {
  const sz = size || 38;
  const ini = (name || "?").split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div style={{ width: sz, height: sz, borderRadius: 10, background: `linear-gradient(135deg,${h(G.gold, .18)},${h(G.mint, .12)})`, border: `1px solid ${h(G.gold, .22)}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontWeight: 700, color: G.gold, fontSize: Math.round(sz * 0.35) }}>
      {ini}
    </div>
  );
}

function Sec({ title, action, onAction, children }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ fontFamily: "'Playfair Display',serif", fontSize: 17, color: G.wht, fontWeight: 600 }}>{title}</h2>
        {action && (
          <button onClick={onAction} className="btn" style={{ background: "none", border: "none", color: G.gold, fontSize: 13, fontWeight: 500, cursor: "pointer", padding: 0 }}>
            {action} →
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function Empty({ icon = "📭", msg }) {
  return (
    <div style={{ textAlign: "center", padding: "40px 20px", color: G.sub }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>{icon}</div>
      <div style={{ fontSize: 14 }}>{msg}</div>
    </div>
  );
}

/* ─── Dashboard page ────────────────────────────────────────────────────────── */
function DashboardPage({ go }) {
  const { apiFetch, user } = useAuth();
  const [voice,  setVoice]  = useState(null);
  const [stats,  setStats]  = useState(null);
  const [leads,  setLeads]  = useState([]);

  const load = useCallback(async () => {
    try {
      const [vr, sr, lr] = await Promise.all([
        apiFetch("/api/voice/status").then(r => r.json()),
        apiFetch("/api/calls/stats").then(r => r.json()),
        apiFetch("/api/swarm/leads?limit=6").then(r => r.json()),
      ]);
      setVoice(vr);
      setStats(sr);
      setLeads((lr.leads || []).filter(l => (l.qualification_score || 0) >= 7));
    } catch { /* ignore */ }
  }, [apiFetch]);

  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const firstName = (user?.name || "there").split(" ")[0];
  const aiOnline  = voice?.status === "live";
  const aiColor   = aiOnline ? G.mint : G.rose;
  const aiLabel   = aiOnline ? "AI ONLINE" : (voice?.status === "needs_setup" ? "NEEDS SETUP" : "OFFLINE");

  const mx = Math.max(...CHART.map(d => d.calls));

  const tiles = [
    { icon: "📞", val: stats?.this_month?.calls    ?? "—", delta: "", label: "Calls Answered",  sub: "This month" },
    { icon: "⭐", val: stats?.this_week?.completed  ?? "—", delta: "", label: "Leads Qualified", sub: "This week" },
    { icon: "📅", val: stats?.this_week?.booking_rate != null ? `${stats.this_week.booking_rate}%` : "—", delta: "", label: "Booking Rate", sub: "This week" },
    { icon: "⏱",  val: stats?.this_week?.avg_duration ?? "—", delta: "", label: "Avg Call Length", sub: "This week" },
    { icon: "🎯", val: stats?.this_week?.avg_score ?? "—", delta: "", label: "Avg Lead Score",  sub: "This week" },
    { icon: "⏰", val: stats?.today?.calls ?? "—", delta: "", label: "Calls Today",       sub: "Live count" },
  ];

  return (
    <div>
      {/* Hero card */}
      <div className="r1" style={{ background: `linear-gradient(120deg,${h(G.gold, .08)},${h(G.sky, .05)})`, border: `1px solid ${h(G.gold, .18)}`, borderRadius: 12, padding: "18px 22px", marginBottom: 22, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 20, color: G.wht, marginBottom: 3 }}>Good morning, {firstName} ☀</div>
          <div style={{ color: G.sub, fontSize: 14 }}>Your AI receptionist <strong style={{ color: G.gold }}>Aria</strong> has answered <strong style={{ color: G.wht }}>{stats?.today?.calls ?? "…"} calls</strong> already today.</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, background: h(aiColor, .1), border: `1px solid ${h(aiColor, .25)}`, borderRadius: 20, padding: "6px 14px" }}>
            <span className="pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: aiColor, display: "inline-block" }} />
            <span style={{ color: aiColor, fontSize: 12, fontWeight: 600 }}>{aiLabel}</span>
          </div>
          <div style={{ color: G.sub, fontSize: 12, marginTop: 6 }}>Retell: {voice?.retell ? "✓" : "—"} · Agent: {voice?.agent_ready ? "✓" : "—"}</div>
        </div>
      </div>

      {/* KPI tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 22 }}>
        {tiles.map((s, i) => (
          <div key={s.label} className={`r${i + 1} ch`} style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "18px 20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <span style={{ fontSize: 22 }}>{s.icon}</span>
              {s.delta && <span style={{ color: G.mint, fontSize: 12, fontWeight: 600, background: h(G.mint, .1), borderRadius: 20, padding: "2px 8px" }}>{s.delta}</span>}
            </div>
            <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 28, color: G.wht, fontWeight: 600, lineHeight: 1, marginBottom: 4 }}>{s.val}</div>
            <div style={{ color: G.wht, fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{s.label}</div>
            <div style={{ color: G.sub, fontSize: 12 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Chart + hot leads */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="r3" style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="This Week" action="Full Report" onAction={() => go("reporting")}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 100 }}>
              {CHART.map(d => (
                <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 88 }}>
                    <div style={{ width: 10, height: `${(d.calls / mx) * 100}%`, background: `linear-gradient(to top,${G.gold},${h(G.gold, .45)})`, borderRadius: "3px 3px 0 0", minHeight: 3 }} />
                    <div style={{ width: 10, height: `${(d.leads / mx) * 100}%`, background: `linear-gradient(to top,${G.mint},${h(G.mint, .4)})`, borderRadius: "3px 3px 0 0", minHeight: 3 }} />
                  </div>
                  <div style={{ color: G.sub, fontSize: 10, fontWeight: 500 }}>{d.day}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 14, marginTop: 12 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: G.sub, fontSize: 12 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: G.gold, display: "inline-block" }} />Calls</span>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: G.sub, fontSize: 12 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: G.mint, display: "inline-block" }} />Leads</span>
            </div>
          </Sec>
        </div>

        <div className="r4" style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="Hot Leads — Call Now" action="All Leads" onAction={() => go("leads")}>
            {leads.length === 0 && <Empty msg="No hot leads right now" />}
            {leads.map(l => (
              <div key={l.id} className="row" style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: `1px solid ${G.bdr}` }}>
                <Avt name={l.name || "?"} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: G.wht, fontWeight: 500, fontSize: 14, marginBottom: 2 }}>{l.name}</div>
                  <div style={{ color: G.sub, fontSize: 12 }}>{l.recommended_action || "Follow up"}</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <Score v={l.qualification_score} />
                  <span style={{ color: G.sub, fontSize: 11 }}>{l.created_at ? new Date(l.created_at).toLocaleDateString("en-AU", { day: "numeric", month: "short" }) : ""}</span>
                </div>
              </div>
            ))}
          </Sec>
        </div>
      </div>
    </div>
  );
}

/* ─── Leads page ────────────────────────────────────────────────────────────── */
function LeadsPage() {
  const { apiFetch } = useAuth();
  const [leads,  setLeads]  = useState([]);
  const [filter, setFilter] = useState("all");
  const [exp,    setExp]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/swarm/leads?limit=50")
      .then(r => r.json())
      .then(d => setLeads(d.leads || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [apiFetch]);

  const scMap = { new: G.sky, hot: G.rose, contacted: G.gold, called: G.mint, converted: G.mint, nurture: G.violet, closed: G.sub };

  const list = leads.filter(l => {
    if (filter === "hot")    return (l.qualification_score || 0) >= 7;
    if (filter === "nurture") return (l.qualification_score || 0) < 7 && l.status !== "closed" && l.status !== "converted";
    return true;
  });

  return (
    <div className="r1">
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {[["all", "All Leads"], ["hot", "🔥 Hot"], ["nurture", "Nurture"]].map(([v, lbl]) => (
          <button key={v} onClick={() => setFilter(v)} className="btn"
            style={{ background: filter === v ? h(G.gold, .1) : "transparent", border: `1px solid ${filter === v ? h(G.gold, .35) : G.bdr}`, color: filter === v ? G.gold : G.sub, borderRadius: 20, padding: "7px 16px", fontSize: 13, fontWeight: filter === v ? 600 : 400 }}>
            {lbl}
          </button>
        ))}
        <span style={{ marginLeft: "auto", color: G.sub, fontSize: 13, alignSelf: "center" }}>{list.length} leads</span>
      </div>

      {loading && <Empty icon="⏳" msg="Loading leads…" />}
      {!loading && list.length === 0 && <Empty msg="No leads yet" />}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {list.map(l => {
          const sc = l.qualification_score || 0;
          const statusKey = sc >= 7 ? "hot" : l.status || "new";
          const statusColor = scMap[statusKey] || G.sub;
          const statusLabel = statusKey.charAt(0).toUpperCase() + statusKey.slice(1);
          const open = exp === l.id;
          return (
            <div key={l.id}>
              <div className="ch row" onClick={() => setExp(open ? null : l.id)}
                style={{ background: G.card, border: `1px solid ${open ? h(G.gold, .28) : G.bdr}`, borderRadius: open ? "10px 10px 0 0" : "10px", padding: "16px 18px", display: "flex", alignItems: "center", gap: 14 }}>
                <Avt name={l.name || "?"} />
                <div style={{ flex: 1 }}>
                  <div style={{ color: G.wht, fontWeight: 600, fontSize: 15, marginBottom: 3 }}>{l.name || "Unknown"}</div>
                  <div style={{ color: G.sub, fontSize: 13 }}>{l.recommended_action || "—"}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Score v={l.qualification_score} />
                  <Chip label={statusLabel} color={statusColor} />
                  <span style={{ color: G.sub, fontSize: 12, minWidth: 80, textAlign: "right" }}>
                    {l.created_at ? new Date(l.created_at).toLocaleDateString("en-AU", { day: "numeric", month: "short" }) : ""}
                  </span>
                  <span style={{ color: G.sub, fontSize: 13 }}>{open ? "▲" : "▼"}</span>
                </div>
              </div>
              {open && (
                <div style={{ background: h(G.gold, .03), border: `1px solid ${h(G.gold, .18)}`, borderTop: "none", borderRadius: "0 0 10px 10px", padding: "16px 18px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  <div>
                    <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 8 }}>Lead Details</div>
                    <div style={{ fontSize: 13, lineHeight: 1.9, color: G.txt }}>
                      <div>📋 Status: <span style={{ color: G.gold, fontWeight: 600 }}>{l.status || "new"}</span></div>
                      <div>🗓 Created: <span style={{ color: G.txt }}>{l.created_at ? new Date(l.created_at).toLocaleString("en-AU") : "—"}</span></div>
                    </div>
                  </div>
                  <div>
                    <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 8 }}>AI Score</div>
                    <div style={{ marginBottom: 8 }}><Score v={l.qualification_score} /></div>
                    <div style={{ color: G.sub, fontSize: 12 }}>Scored on call qualification criteria.</div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ color: G.sub, fontSize: 12, lineHeight: 1.6 }}>{l.recommended_action || "No specific action noted."}</div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Calls page ────────────────────────────────────────────────────────────── */
function CallsPage() {
  const { apiFetch } = useAuth();
  const [calls,   setCalls]   = useState([]);
  const [stats,   setStats]   = useState(null);
  const [exp,     setExp]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch("/api/calls?limit=50").then(r => r.json()),
      apiFetch("/api/calls/stats").then(r => r.json()),
    ])
      .then(([cd, sd]) => { setCalls(cd.calls || []); setStats(sd); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [apiFetch]);

  function outcomeFromCall(c) {
    const score = c.lead_score;
    if (c.status !== "completed") return [G.sub, "Missed"];
    if (score >= 7) return [G.mint, "Booked"];
    if (score >= 5) return [G.sky,  "Qualified"];
    if (score >= 1) return [G.gold, "Nurture"];
    return [G.sky, "Completed"];
  }

  const statTiles = [
    ["📞 " + (stats?.this_month?.calls ?? "—"), "Total this month",   G.gold],
    ["📅 " + (stats?.this_week?.completed ?? "—"), "Completed this week", G.mint],
    ["⏱ "  + (stats?.this_week?.avg_duration ?? "—"), "Avg call length",   G.sky],
    ["🎯 " + (stats?.this_week?.booking_rate != null ? stats.this_week.booking_rate + "%" : "—"), "Booking rate", G.violet],
  ];

  return (
    <div className="r1">
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        {statTiles.map(([v, l, c]) => (
          <div key={l} style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "14px 18px", flex: 1, minWidth: 120 }}>
            <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 22, color: c, fontWeight: 600, marginBottom: 3 }}>{v}</div>
            <div style={{ color: G.sub, fontSize: 12 }}>{l}</div>
          </div>
        ))}
      </div>

      <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${G.bdr}` }}>
          <h3 style={{ fontFamily: "'Playfair Display',serif", fontSize: 16, color: G.wht }}>Recent Calls</h3>
        </div>
        {loading && <Empty icon="⏳" msg="Loading calls…" />}
        {!loading && calls.length === 0 && <Empty msg="No calls yet" />}
        {calls.map(c => {
          const [cc, cl] = outcomeFromCall(c);
          const open = exp === c.call_id;
          const caller = c.from_phone || "Unknown";
          const time = c.started_at ? new Date(c.started_at).toLocaleString("en-AU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
          return (
            <div key={c.call_id}>
              <div className="row" onClick={() => setExp(open ? null : c.call_id)}
                style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", borderBottom: `1px solid ${G.bdr}`, background: open ? h(G.gold, .03) : "transparent" }}>
                <div style={{ width: 38, height: 38, borderRadius: 10, background: h(cc, .1), border: `1px solid ${h(cc, .25)}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17, flexShrink: 0 }}>🎙</div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: G.wht, fontWeight: 500, fontSize: 14, marginBottom: 2 }}>{caller}</div>
                  <div style={{ color: G.sub, fontSize: 12 }}>{time} · {c.duration_fmt || "0:00"}</div>
                </div>
                <Chip label={cl} color={cc} />
                <Score v={c.lead_score} />
                <span style={{ color: G.sub, fontSize: 13 }}>{open ? "▲" : "▼"}</span>
              </div>
              {open && (
                <div style={{ padding: "14px 20px", background: h(G.gold, .03), borderBottom: `1px solid ${G.bdr}` }}>
                  {c.transcript && c.transcript.length > 0 ? (
                    <div>
                      <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 8 }}>Transcript</div>
                      <div style={{ maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
                        {c.transcript.map((msg, i) => (
                          <div key={i} style={{ background: G.surf, borderRadius: 8, padding: "8px 12px", border: `1px solid ${G.bdr}` }}>
                            <span style={{ color: G.gold, fontSize: 11, fontWeight: 600, marginRight: 8 }}>{msg.role || msg.speaker || "—"}</span>
                            <span style={{ color: G.txt, fontSize: 13 }}>{msg.content || msg.text || ""}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: G.sub, fontSize: 13, fontStyle: "italic" }}>No transcript available.</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Emails page — empty state (no API yet) ────────────────────────────────── */
function EmailsPage() {
  return (
    <div className="r1">
      <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 12, padding: "48px 32px", textAlign: "center" }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>✉️</div>
        <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 20, color: G.wht, marginBottom: 8 }}>Email Inbox</div>
        <div style={{ color: G.sub, fontSize: 14, maxWidth: 360, margin: "0 auto" }}>
          Email handling is active. The inbox view is coming soon — your AI is still triaging and replying to emails automatically.
        </div>
      </div>
    </div>
  );
}

/* ─── Reports page — static ─────────────────────────────────────────────────── */
function ReportingPage() {
  const [range, setRange] = useState("month");
  const mx = Math.max(...CHART.map(d => d.calls));
  return (
    <div className="r1">
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {[["month", "This Month"], ["quarter", "Quarter"], ["year", "Year"]].map(([v, l]) => (
          <button key={v} onClick={() => setRange(v)} className="btn"
            style={{ background: range === v ? h(G.gold, .1) : "transparent", border: `1px solid ${range === v ? h(G.gold, .35) : G.bdr}`, color: range === v ? G.gold : G.sub, borderRadius: 20, padding: "7px 16px", fontSize: 13, fontWeight: range === v ? 600 : 400 }}>
            {l}
          </button>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 18 }}>
        {[["147", "Calls Answered", "+18%", G.gold], ["89", "Leads Generated", "+24%", G.mint], ["31", "Bookings", "+11%", G.sky], ["$127K", "Pipeline Value", "+32%", G.violet], ["22%", "Close Rate", "+4pp", G.mint], ["94hrs", "Time Saved", "", G.gold]].map(([val, lbl, delta, c]) => (
          <div key={lbl} style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "16px 18px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ color: G.sub, fontSize: 12 }}>{lbl}</span>
              {delta && <span style={{ color: G.mint, fontSize: 11, fontWeight: 600 }}>{delta}</span>}
            </div>
            <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 26, color: c, fontWeight: 600 }}>{val}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 14 }}>
        <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="Daily Activity">
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 120 }}>
              {CHART.map(d => (
                <div key={d.day} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 100 }}>
                    <div style={{ width: 12, height: `${(d.calls / mx) * 100}%`, background: `linear-gradient(to top,${G.gold},${h(G.gold, .4)})`, borderRadius: "3px 3px 0 0", minHeight: 4 }} />
                    <div style={{ width: 12, height: `${(d.leads / mx) * 100}%`, background: `linear-gradient(to top,${G.mint},${h(G.mint, .4)})`, borderRadius: "3px 3px 0 0", minHeight: 4 }} />
                  </div>
                  <div style={{ color: G.sub, fontSize: 11 }}>{d.day}</div>
                </div>
              ))}
            </div>
          </Sec>
        </div>
        <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="Conversion Funnel">
            {[["Calls Received", 147, G.gold], ["Leads Created", 89, G.sky], ["Qualified", 54, G.violet], ["Booked", 31, G.mint], ["Proposals", 18, G.mint]].map(([lbl, val, c]) => (
              <div key={lbl} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ color: G.txt, fontSize: 12 }}>{lbl}</span>
                  <span style={{ color: c, fontWeight: 600, fontSize: 12 }}>{val}</span>
                </div>
                <div style={{ height: 7, background: G.bdr, borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(val / 147) * 100}%`, background: c, borderRadius: 4, opacity: .8 }} />
                </div>
              </div>
            ))}
          </Sec>
        </div>
      </div>
    </div>
  );
}

/* ─── Billing page — static ─────────────────────────────────────────────────── */
function BillingPage() {
  const features = ["24/7 AI Voice Receptionist", "Unlimited calls", "Email triage & auto-reply", "Lead qualification & scoring", "Proposal generation", "GHL CRM sync", "Priority support"];
  const invoices = [{ date: "10 Mar 2026", amt: 497 }, { date: "10 Feb 2026", amt: 497 }, { date: "10 Jan 2026", amt: 397 }];
  return (
    <div className="r1">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{ background: `linear-gradient(135deg,${h(G.gold, .08)},${h(G.sky, .04)})`, border: `1px solid ${h(G.gold, .25)}`, borderRadius: 12, padding: "22px 24px" }}>
          <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 6 }}>Current Plan</div>
          <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 28, color: G.wht, marginBottom: 4 }}>Professional</div>
          <div style={{ fontFamily: "'Playfair Display',serif", fontSize: 36, color: G.gold, marginBottom: 4 }}>
            $497<span style={{ fontSize: 16, color: G.sub, fontFamily: "'Outfit',sans-serif", fontWeight: 400 }}>/month</span>
          </div>
          <div style={{ color: G.sub, fontSize: 13, marginBottom: 18 }}>Next billing: 10 Apr 2026</div>
          {features.map(f => (
            <div key={f} style={{ display: "flex", alignItems: "center", gap: 8, color: G.txt, fontSize: 13, marginBottom: 7 }}>
              <span style={{ color: G.mint, fontSize: 14 }}>✓</span> {f}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "18px 20px" }}>
            <div style={{ color: G.wht, fontWeight: 600, fontSize: 15, marginBottom: 14, fontFamily: "'Playfair Display',serif" }}>Invoice History</div>
            {invoices.map((inv, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 0", borderBottom: `1px solid ${G.bdr}` }}>
                <span style={{ color: G.txt, fontSize: 13 }}>{inv.date}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ color: G.wht, fontWeight: 600 }}>${inv.amt}</span>
                  <Chip label="PAID" color={G.mint} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Support page — static ─────────────────────────────────────────────────── */
function SupportPage() {
  const [msg, setMsg] = useState("");
  const [sent, setSent] = useState(false);
  return (
    <div className="r1">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
        {[["AI Receptionist", "Operational", G.mint, "🤖"], ["CRM Sync", "Active", G.mint, "🔄"], ["Uptime", "99.8%", G.sky, "📊"], ["Response Time", "< 1 sec", G.gold, "⚡"]].map(([lbl, val, c, ic]) => (
          <div key={lbl} style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "16px 18px", display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 24 }}>{ic}</span>
            <div>
              <div style={{ color: G.sub, fontSize: 12, marginBottom: 3 }}>{lbl}</div>
              <div style={{ color: c, fontWeight: 600, fontSize: 15 }}>{val}</div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="Send a Message">
            <div style={{ marginBottom: 12 }}>
              <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 5 }}>Message</div>
              <textarea value={msg} onChange={e => setMsg(e.target.value)} rows={4} placeholder="Describe your question…"
                style={{ width: "100%", background: G.surf, border: `1px solid ${G.bdr}`, borderRadius: 7, padding: "9px 12px", color: G.txt, fontSize: 13, resize: "vertical", lineHeight: 1.6 }} />
            </div>
            <button className="btn" onClick={() => { if (msg) { setSent(true); setMsg(""); setTimeout(() => setSent(false), 3000); } }}
              style={{ background: sent ? h(G.mint, .1) : h(G.gold, .1), border: `1px solid ${sent ? h(G.mint, .3) : h(G.gold, .3)}`, color: sent ? G.mint : G.gold, borderRadius: 7, padding: "9px 20px", fontSize: 13, fontWeight: 500, width: "100%", transition: "all .2s" }}>
              {sent ? "✓ Message Sent!" : "Send Message →"}
            </button>
          </Sec>
        </div>
        <div style={{ background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "20px 22px" }}>
          <Sec title="Quick Help">
            {[
              ["How do I update my AI greeting?", "Settings → Voice AI → Greeting"],
              ["Can I add team members?", "Settings → Team to invite staff"],
              ["How do I pause the AI?", "Settings → Voice AI and toggle it off"],
              ["What is the cancellation policy?", "Cancel anytime — no lock-in contracts"],
            ].map(([q, a]) => (
              <div key={q} style={{ padding: "10px 0", borderBottom: `1px solid ${G.bdr}` }}>
                <div style={{ color: G.txt, fontSize: 13, fontWeight: 500, marginBottom: 3 }}>{q}</div>
                <div style={{ color: G.sub, fontSize: 12 }}>{a}</div>
              </div>
            ))}
          </Sec>
        </div>
      </div>
    </div>
  );
}

/* ─── Settings page — static ────────────────────────────────────────────────── */
function SettingsPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("business");
  const [saved, setSaved] = useState(false);
  const [greeting, setGreeting] = useState("Hi, you've reached Solar Sales AI — I'm Aria your AI assistant.");
  const [hotScore, setHotScore] = useState("7");
  const TABS = [{ id: "business", label: "My Business" }, { id: "voice", label: "Voice AI" }, { id: "notifications", label: "Notifications" }];
  const [notifs, setNotifs] = useState({ hot: true, daily: true, booking: true, approval: false });
  const save = () => { setSaved(true); setTimeout(() => setSaved(false), 2500); };
  return (
    <div className="r1" style={{ display: "flex", gap: 14 }}>
      <div style={{ width: 170, flexShrink: 0 }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className="navbtn"
            style={{ display: "flex", alignItems: "center", width: "100%", padding: "10px 12px", background: tab === t.id ? h(G.gold, .08) : "transparent", border: `1px solid ${tab === t.id ? h(G.gold, .2) : "transparent"}`, borderRadius: 7, color: tab === t.id ? G.gold : G.sub, fontSize: 14, fontWeight: tab === t.id ? 600 : 400, cursor: "pointer", marginBottom: 3, textAlign: "left" }}>
            {t.label}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, background: G.card, border: `1px solid ${G.bdr}`, borderRadius: 10, padding: "22px 24px" }}>
        {tab === "business" && (
          <div>
            <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${G.bdr}` }}>Account Info</div>
            <div style={{ color: G.txt, fontSize: 14, marginBottom: 8 }}>Name: <strong style={{ color: G.wht }}>{user?.name || "—"}</strong></div>
            <div style={{ color: G.txt, fontSize: 14 }}>Email: <strong style={{ color: G.wht }}>{user?.email || "—"}</strong></div>
          </div>
        )}
        {tab === "voice" && (
          <div>
            <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${G.bdr}` }}>AI Receptionist</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 5 }}>AI Greeting</div>
              <textarea value={greeting} onChange={e => setGreeting(e.target.value)} rows={3}
                style={{ width: "100%", background: G.surf, border: `1px solid ${G.bdr}`, borderRadius: 7, padding: "9px 12px", color: G.txt, fontSize: 13, resize: "vertical", lineHeight: 1.6 }} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 5 }}>Hot Lead Threshold</div>
              <input type="number" value={hotScore} onChange={e => setHotScore(e.target.value)}
                style={{ width: 120, background: G.surf, border: `1px solid ${G.bdr}`, borderRadius: 7, padding: "9px 12px", color: G.txt, fontSize: 13 }} />
              <div style={{ color: G.sub, fontSize: 12, marginTop: 5 }}>Leads above this score are flagged as hot.</div>
            </div>
          </div>
        )}
        {tab === "notifications" && (
          <div>
            <div style={{ color: G.sub, fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 14, paddingBottom: 10, borderBottom: `1px solid ${G.bdr}` }}>Notification Preferences</div>
            {[["hot", "Hot Lead Alert", "Notify when a lead scores 7 or above"], ["daily", "Daily Summary", "Morning email recap of yesterday"], ["booking", "New Booking", "Alert when AI books an assessment"], ["approval", "Email Approval", "When AI needs you to review a draft"]].map(([key, lbl, desc]) => (
              <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "13px 0", borderBottom: `1px solid ${G.bdr}` }}>
                <div>
                  <div style={{ color: G.txt, fontWeight: 500, marginBottom: 2 }}>{lbl}</div>
                  <div style={{ color: G.sub, fontSize: 12 }}>{desc}</div>
                </div>
                <div onClick={() => setNotifs(n => ({ ...n, [key]: !n[key] }))}
                  style={{ position: "relative", width: 40, height: 22, background: notifs[key] ? h(G.gold, .3) : G.bdr, borderRadius: 11, cursor: "pointer", border: `1px solid ${notifs[key] ? G.gold : G.bdr}`, transition: "all .2s", flexShrink: 0 }}>
                  <div style={{ position: "absolute", top: 2, left: notifs[key] ? 20 : 2, width: 16, height: 16, borderRadius: "50%", background: notifs[key] ? G.gold : G.sub, transition: "all .2s" }} />
                </div>
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 22 }}>
          <button className="btn" onClick={save}
            style={{ background: saved ? h(G.mint, .1) : h(G.gold, .1), border: `1px solid ${saved ? h(G.mint, .3) : h(G.gold, .3)}`, color: saved ? G.mint : G.gold, borderRadius: 7, padding: "10px 26px", fontSize: 14, fontWeight: 500, transition: "all .2s" }}>
            {saved ? "✓ Saved!" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Main shell ────────────────────────────────────────────────────────────── */
export default function ClientDashboard() {
  const { user, logout } = useAuth();
  const [page,  setPage]  = useState("dashboard");
  const [clock, setClock] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <style>{STYLE}</style>
      <div style={{ display: "flex", height: "100vh", background: G.bg, overflow: "hidden" }}>

        {/* Sidebar */}
        <div style={{ width: 215, background: G.surf, borderRight: `1px solid ${G.bdr}`, display: "flex", flexDirection: "column", flexShrink: 0 }}>
          {/* Logo */}
          <button onClick={() => setPage("dashboard")} className="btn"
            style={{ display: "flex", alignItems: "center", gap: 11, padding: "18px 16px", background: "transparent", border: "none", borderBottom: `1px solid ${G.bdr}`, cursor: "pointer", width: "100%" }}>
            <div style={{ width: 34, height: 34, background: `linear-gradient(135deg,${G.gold},${G.goldD})`, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0, boxShadow: `0 4px 12px ${h(G.gold, .3)}` }}>☀</div>
            <div style={{ textAlign: "left" }}>
              <div style={{ fontFamily: "'Playfair Display',serif", color: G.wht, fontSize: 14, fontWeight: 600, lineHeight: 1.2 }}>Solar Admin</div>
              <div style={{ color: G.sub, fontSize: 10, fontWeight: 500, letterSpacing: ".06em" }}>AI PLATFORM</div>
            </div>
          </button>

          {/* Nav items */}
          <div style={{ flex: 1, padding: "14px 10px", overflowY: "auto" }}>
            {NAV_CFG.map(({ section, items }) => (
              <div key={section} style={{ marginBottom: 18 }}>
                <div style={{ color: G.sub, fontSize: 9, fontWeight: 600, letterSpacing: ".15em", padding: "0 8px", marginBottom: 6 }}>{section}</div>
                {items.map(item => {
                  const active = page === item.id;
                  return (
                    <button key={item.id} onClick={() => setPage(item.id)} className="navbtn"
                      style={{ display: "flex", alignItems: "center", gap: 9, width: "100%", padding: "9px 11px", background: active ? h(G.gold, .08) : "transparent", border: `1px solid ${active ? h(G.gold, .2) : "transparent"}`, borderRadius: 7, color: active ? G.gold : G.sub, fontSize: 14, fontWeight: active ? 600 : 400, cursor: "pointer", marginBottom: 2, textAlign: "left" }}>
                      <span style={{ fontSize: 15 }}>{item.icon}</span>
                      <span style={{ flex: 1 }}>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          {/* User info + sign out */}
          <div style={{ padding: "12px 14px", borderTop: `1px solid ${G.bdr}`, flexShrink: 0 }}>
            <div style={{ background: h(G.gold, .06), border: `1px solid ${h(G.gold, .15)}`, borderRadius: 8, padding: "10px 12px", marginBottom: 10 }}>
              <div style={{ color: G.wht, fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{user?.name || "Client"}</div>
              <div style={{ color: G.sub, fontSize: 11, marginBottom: 4 }}>{user?.email}</div>
              <div style={{ color: G.gold, fontSize: 10, fontWeight: 600, letterSpacing: ".06em" }}>CLIENT</div>
            </div>
            <button onClick={logout} className="btn"
              style={{ width: "100%", background: "transparent", border: `1px solid ${G.bdr}`, color: G.sub, padding: "8px 12px", borderRadius: 7, cursor: "pointer", fontSize: 12, fontFamily: "'Outfit',sans-serif", fontWeight: 500 }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = G.rose; e.currentTarget.style.color = G.rose; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = G.bdr; e.currentTarget.style.color = G.sub; }}>
              Sign Out
            </button>
          </div>
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Header */}
          <div style={{ padding: "12px 24px", borderBottom: `1px solid ${G.bdr}`, display: "flex", alignItems: "center", justifyContent: "space-between", background: G.surf, flexShrink: 0 }}>
            <div>
              <div style={{ fontFamily: "'Playfair Display',serif", color: G.wht, fontSize: 20, fontWeight: 600 }}>{TITLES[page]}</div>
              <div style={{ color: G.sub, fontSize: 12 }}>
                {clock.toLocaleDateString("en-AU", { weekday: "long", day: "numeric", month: "long", year: "numeric" })} · {clock.toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })} AWST
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button onClick={() => setPage("settings")} className="btn"
                style={{ width: 34, height: 34, background: page === "settings" ? h(G.gold, .1) : "transparent", border: `1px solid ${page === "settings" ? h(G.gold, .3) : G.bdr}`, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: page === "settings" ? G.gold : G.sub, fontSize: 17 }}>
                ⚙
              </button>
              <Avt name={user?.name || "?"} size={34} />
            </div>
          </div>

          {/* Page content */}
          <div style={{ flex: 1, overflowY: "auto", padding: "22px 26px" }}>
            {page === "dashboard" && <DashboardPage go={setPage} />}
            {page === "leads"     && <LeadsPage />}
            {page === "calls"     && <CallsPage />}
            {page === "emails"    && <EmailsPage />}
            {page === "reporting" && <ReportingPage />}
            {page === "billing"   && <BillingPage />}
            {page === "support"   && <SupportPage />}
            {page === "settings"  && <SettingsPage />}
          </div>
        </div>
      </div>
    </>
  );
}
