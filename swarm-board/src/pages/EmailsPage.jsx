/**
 * EmailsPage -- email queue with AI draft replies and human approval workflow.
 * Fetches from GET /api/emails and GET /api/emails/stats
 * Approves/discards via POST /gate/email-approve (action: "send" | "discard")
 * Bulk discard via POST /api/emails/bulk-discard
 */
import { useState, useEffect, useCallback, useRef } from "react";
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

function Skeleton({ width = "100%", height = 16 }) {
  return (
    <div style={{
      width, height, borderRadius: 6,
      background: `linear-gradient(90deg,${C.card} 25%,${C.border} 50%,${C.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

function UrgencyBar({ score }) {
  const val   = score != null ? Number(score) : 0;
  const color = val >= 8 ? C.red : val >= 5 ? C.amber : C.muted;
  const label = val >= 8 ? "HIGH" : val >= 5 ? "MED" : "LOW";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 3, height: 32, borderRadius: 2,
        background: color, boxShadow: val >= 8 ? `0 0 6px ${color}` : "none",
        flexShrink: 0,
      }} />
      <div>
        <div style={{ fontSize: 11, fontFamily: "'Syne Mono', monospace", color, lineHeight: 1 }}>
          {val}/10
        </div>
        <div style={{ fontSize: 9, color: C.muted, letterSpacing: 1 }}>{label}</div>
      </div>
    </div>
  );
}

function ClassificationPill({ classification }) {
  const colorMap = {
    NEW_ENQUIRY:     C.cyan,
    QUOTE_REQUEST:   C.amber,
    BOOKING_REQUEST: C.green,
    COMPLAINT:       C.red,
    SPAM:            C.muted,
    OTHER:           C.purple,
  };
  const color = colorMap[classification] || C.muted;
  return (
    <span style={{
      fontSize: 9, fontFamily: "'Syne Mono', monospace",
      color, background: h(color, 0.1), border: `1px solid ${h(color, 0.25)}`,
      borderRadius: 10, padding: "2px 8px", whiteSpace: "nowrap",
    }}>
      {(classification || "UNKNOWN").replace(/_/g, " ")}
    </span>
  );
}

function StatusPill({ status }) {
  const colorMap = { pending: C.amber, sent: C.green, discarded: C.muted };
  const col = colorMap[status] || C.muted;
  return (
    <span style={{
      fontSize: 9, fontFamily: "'Syne Mono', monospace",
      color: col, background: h(col, 0.1), border: `1px solid ${h(col, 0.25)}`,
      borderRadius: 10, padding: "2px 8px",
    }}>
      {(status || "pending").toUpperCase()}
    </span>
  );
}

function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div style={{
      position: "fixed", bottom: 28, right: 28, zIndex: 3000,
      background: C.panel, border: `1px solid ${h(toast.color, 0.45)}`,
      color: toast.color, borderRadius: 10, padding: "12px 20px",
      fontSize: 13, fontFamily: "'Syne Mono', monospace",
      boxShadow: `0 4px 24px ${h(toast.color, 0.22)}`,
      animation: "fadeIn .2s ease",
    }}>
      {toast.msg}
    </div>
  );
}

function EmailModal({ email, onClose, onSend, onDiscard, actionLoading }) {
  const [editedReply, setEdited]  = useState(email?.draft_reply || "");
  const [editing, setEditing]     = useState(false);
  const [fullEmail, setFull]      = useState(email);
  const [loadingFull, setLoading] = useState(false);
  const { apiFetch } = useAuth();

  useEffect(() => {
    setEdited(email?.draft_reply || "");
    setEditing(false);
    setFull(email);
    if (email && !email.body) {
      setLoading(true);
      apiFetch(`/api/emails/${email.id}`)
        .then(r => r.json())
        .then(d => { if (d.email) { setFull(d.email); setEdited(d.email.draft_reply || ""); } })
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [email]); // eslint-disable-line

  if (!email) return null;
  const isPending = fullEmail?.status === "pending";

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(5,8,16,0.9)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 2000, padding: 24,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: C.panel, border: `1px solid ${C.borderB}`,
        borderRadius: 18, padding: 28, width: "100%", maxWidth: 700,
        maxHeight: "90vh", overflow: "auto",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div style={{ flex: 1, minWidth: 0, paddingRight: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: C.white, marginBottom: 5 }}>
              {fullEmail?.subject || "(no subject)"}
            </div>
            <div style={{ fontSize: 12, color: C.muted }}>
              From: <span style={{ color: C.text }}>{fullEmail?.from_name || fullEmail?.from_email}</span>
              {fullEmail?.from_name && fullEmail?.from_email && (
                <span style={{ color: C.muted }}> &lt;{fullEmail.from_email}&gt;</span>
              )}
              {fullEmail?.received_at && (
                <> · {new Date(fullEmail.received_at).toLocaleString("en-AU")}</>
              )}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 8, padding: "5px 12px", cursor: "pointer", fontSize: 12, flexShrink: 0,
          }}>✕ Close</button>
        </div>

        <div style={{
          background: C.card, border: `1px solid ${C.border}`,
          borderRadius: 10, padding: "10px 16px", marginBottom: 20,
          display: "flex", gap: 20, flexWrap: "wrap",
        }}>
          <div>
            <div style={{ fontSize: 9, color: C.muted, marginBottom: 5, letterSpacing: 1 }}>CLASSIFICATION</div>
            <ClassificationPill classification={fullEmail?.classification} />
          </div>
          <div>
            <div style={{ fontSize: 9, color: C.muted, marginBottom: 4, letterSpacing: 1 }}>URGENCY</div>
            <UrgencyBar score={fullEmail?.urgency_score} />
          </div>
          <div>
            <div style={{ fontSize: 9, color: C.muted, marginBottom: 5, letterSpacing: 1 }}>STATUS</div>
            <StatusPill status={fullEmail?.status} />
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5, marginBottom: 10 }}>
            ORIGINAL EMAIL
          </div>
          {loadingFull ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[1,2,3].map(i => <Skeleton key={i} height={14} />)}
            </div>
          ) : (
            <div style={{
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 10, padding: "14px 16px",
              fontSize: 13, color: C.text, lineHeight: 1.65,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              maxHeight: 220, overflow: "auto",
            }}>
              {fullEmail?.body || "(no body available)"}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5 }}>
              AI DRAFT REPLY
            </div>
            {isPending && (
              <button
                onClick={() => setEditing(v => !v)}
                style={{
                  background: editing ? h(C.amber, 0.12) : "transparent",
                  border: `1px solid ${editing ? C.amber : C.border}`,
                  color: editing ? C.amber : C.muted,
                  borderRadius: 6, padding: "3px 11px",
                  cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
                }}
              >
                {editing ? "✓ DONE" : "✎ EDIT"}
              </button>
            )}
          </div>
          {editing ? (
            <textarea
              value={editedReply}
              onChange={e => setEdited(e.target.value)}
              rows={10}
              style={{
                width: "100%", background: C.card, border: `1px solid ${C.amber}`,
                color: C.text, borderRadius: 10, padding: "12px 14px",
                fontSize: 13, lineHeight: 1.65, resize: "vertical",
                fontFamily: "inherit", boxSizing: "border-box", outline: "none",
              }}
            />
          ) : (
            <div style={{
              background: h(C.amber, 0.04), border: `1px solid ${h(C.amber, 0.18)}`,
              borderRadius: 10, padding: "14px 16px",
              fontSize: 13, color: C.text, lineHeight: 1.65,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              maxHeight: 280, overflow: "auto",
            }}>
              {editedReply || <span style={{ color: C.muted, fontStyle: "italic" }}>No AI reply generated yet.</span>}
            </div>
          )}
        </div>

        {isPending ? (
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => onSend(fullEmail, editedReply)}
              disabled={actionLoading}
              style={{
                flex: 2, background: h(C.green, 0.12), border: `1px solid ${h(C.green, 0.38)}`,
                color: C.green, borderRadius: 8, padding: "12px 20px",
                cursor: actionLoading ? "not-allowed" : "pointer",
                fontSize: 12, fontFamily: "'Syne Mono', monospace",
                opacity: actionLoading ? 0.6 : 1, transition: "all .15s",
              }}
            >
              {actionLoading ? "SENDING…" : "✓ APPROVE & SEND"}
            </button>
            <button
              onClick={() => onDiscard(fullEmail)}
              disabled={actionLoading}
              style={{
                flex: 1, background: h(C.red, 0.08), border: `1px solid ${h(C.red, 0.25)}`,
                color: C.red, borderRadius: 8, padding: "12px 20px",
                cursor: actionLoading ? "not-allowed" : "pointer",
                fontSize: 12, fontFamily: "'Syne Mono', monospace",
                opacity: actionLoading ? 0.6 : 1,
              }}
            >
              ✕ DISCARD
            </button>
          </div>
        ) : (
          <div style={{
            textAlign: "center", fontSize: 12, color: C.muted,
            fontFamily: "'Syne Mono', monospace", padding: "8px 0",
          }}>
            EMAIL {(fullEmail?.status || "").toUpperCase()} — no further action needed.
          </div>
        )}
      </div>
    </div>
  );
}

const TABS = [
  { label: "PENDING",   value: "pending"   },
  { label: "ALL",       value: ""          },
  { label: "SENT",      value: "sent"      },
  { label: "DISCARDED", value: "discarded" },
];
const CLASS_OPTS = ["", "NEW_ENQUIRY", "QUOTE_REQUEST", "BOOKING_REQUEST", "COMPLAINT", "SPAM", "OTHER"];

export default function EmailsPage() {
  const { apiFetch } = useAuth();
  const [emails, setEmails]           = useState([]);
  const [stats, setStats]             = useState(null);
  const [loading, setLoading]         = useState(true);
  const [tab, setTab]                 = useState("pending");
  const [classFilter, setClass]       = useState("");
  const [search, setSearch]           = useState("");
  const [limit, setLimit]             = useState(50);
  const [total, setTotal]             = useState(0);
  const [offset, setOffset]           = useState(0);
  const [selected, setSelected]       = useState(new Set());
  const [modalEmail, setModal]        = useState(null);
  const [actionLoading, setActing]    = useState(false);
  const [toast, setToast]             = useState(null);
  const toastTimer                    = useRef(null);

  const showToast = (msg, color = C.green) => {
    clearTimeout(toastTimer.current);
    setToast({ msg, color });
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  };

  const loadStats = useCallback(async () => {
    try {
      const r = await apiFetch("/api/emails/stats");
      const d = await r.json();
      setStats(d);
    } catch {}
  }, [apiFetch]);

  const load = useCallback(async () => {
    setLoading(true);
    setSelected(new Set());
    try {
      const params = new URLSearchParams({ limit, offset });
      if (tab)         params.set("status", tab);
      if (classFilter) params.set("classification", classFilter);
      if (search)      params.set("search", search);
      const r = await apiFetch(`/api/emails?${params}`);
      const d = await r.json();
      setEmails(d.emails || []);
      setTotal(d.total || 0);
    } catch {
      setEmails([]);
    } finally {
      setLoading(false);
    }
  }, [apiFetch, tab, classFilter, search, limit, offset]); // eslint-disable-line

  useEffect(() => { load(); loadStats(); }, [load]); // eslint-disable-line

  const handleSend = async (email, editedBody) => {
    setActing(true);
    try {
      const body = editedBody?.trim() || email.draft_reply || "";
      const action = body !== email.draft_reply && editedBody?.trim() ? "edit" : "send";
      const r = await apiFetch("/gate/email-approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: email.id, action, edited_body: editedBody }),
      });
      if (!r.ok) throw new Error((await r.json()).error || "Send failed");
      showToast("Reply sent successfully");
      setModal(null);
      load();
      loadStats();
    } catch (e) {
      showToast(e.message || "Failed to send", C.red);
    } finally {
      setActing(false);
    }
  };

  const handleDiscard = async (email) => {
    setActing(true);
    try {
      await apiFetch("/gate/email-approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: email.id, action: "discard" }),
      });
      showToast("Email discarded", C.muted);
      setModal(null);
      load();
      loadStats();
    } catch {
      showToast("Failed to discard", C.red);
    } finally {
      setActing(false);
    }
  };

  const handleBulkDiscard = async () => {
    if (selected.size === 0) return;
    setActing(true);
    try {
      const r = await apiFetch("/api/emails/bulk-discard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [...selected] }),
      });
      const d = await r.json();
      showToast(`Discarded ${d.discarded} email${d.discarded !== 1 ? "s" : ""}`, C.muted);
      setSelected(new Set());
      load();
      loadStats();
    } catch {
      showToast("Bulk discard failed", C.red);
    } finally {
      setActing(false);
    }
  };

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === emails.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(emails.filter(e => e.status === "pending").map(e => e.id)));
    }
  };

  const pendingCount = stats?.pending ?? 0;
  const totalPages   = Math.ceil(total / limit);
  const currentPage  = Math.floor(offset / limit);

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <style>{SHIMMER + `@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}`}</style>
      <Toast toast={toast} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            EMAIL QUEUE
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: C.white }}>Emails</div>
            {pendingCount > 0 && (
              <div style={{
                background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
                color: C.amber, borderRadius: 20, padding: "2px 10px",
                fontSize: 12, fontFamily: "'Syne Mono', monospace",
                boxShadow: `0 0 10px ${h(C.amber, 0.3)}`,
              }}>
                {pendingCount} pending
              </div>
            )}
          </div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {stats ? `${stats.today_total} today · ${stats.sent} sent all-time · ${stats.discarded_today} auto-discarded today` : "Loading…"}
          </div>
        </div>
        <button onClick={() => { load(); loadStats(); }} style={{
          background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.3)}`,
          color: C.cyan, padding: "9px 18px", borderRadius: 8,
          cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
        }}>
          ↻ REFRESH
        </button>
      </div>

      <div style={{ display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" }}>
        {[
          { label: "Pending Review", value: stats?.pending ?? "—",         color: C.amber  },
          { label: "Sent Today",     value: stats?.today_total ?? "—",     color: C.green  },
          { label: "All-time Sent",  value: stats?.sent ?? "—",            color: C.cyan   },
          { label: "Auto-discarded", value: stats?.discarded_today ?? "—", color: C.muted  },
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

      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 5, background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: 4 }}>
          {TABS.map(t => {
            const active = tab === t.value;
            const col    = t.value === "pending" ? C.amber : t.value === "sent" ? C.green : t.value === "discarded" ? C.muted : C.cyan;
            return (
              <button key={t.value} onClick={() => { setTab(t.value); setOffset(0); }} style={{
                background: active ? h(col, 0.15) : "transparent",
                border: `1px solid ${active ? col : "transparent"}`,
                color: active ? col : C.muted,
                borderRadius: 6, padding: "6px 14px",
                cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
                transition: "all .13s",
              }}>
                {t.label}
                {t.value === "pending" && pendingCount > 0 && (
                  <span style={{
                    marginLeft: 6, background: h(C.amber, 0.2), border: `1px solid ${h(C.amber, 0.4)}`,
                    color: C.amber, borderRadius: 10, padding: "0 5px", fontSize: 10,
                  }}>{pendingCount}</span>
                )}
              </button>
            );
          })}
        </div>

        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setOffset(0); }}
          placeholder="Search sender, subject…"
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.text,
            borderRadius: 8, padding: "8px 14px", fontSize: 13, width: 200, outline: "none",
          }}
        />

        <select
          value={classFilter}
          onChange={e => { setClass(e.target.value); setOffset(0); }}
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 7, padding: "7px 10px", fontSize: 12,
          }}
        >
          {CLASS_OPTS.map(c => (
            <option key={c} value={c}>{c === "" ? "All Types" : c.replace(/_/g, " ")}</option>
          ))}
        </select>

        <select
          value={limit}
          onChange={e => { setLimit(Number(e.target.value)); setOffset(0); }}
          style={{
            background: C.card, border: `1px solid ${C.border}`, color: C.muted,
            borderRadius: 7, padding: "7px 10px", fontSize: 12, marginLeft: "auto",
          }}
        >
          {[25, 50, 100].map(n => <option key={n} value={n}>Show {n}</option>)}
        </select>
      </div>

      {selected.size > 0 && (
        <div style={{
          display: "flex", alignItems: "center", gap: 14,
          background: h(C.amber, 0.08), border: `1px solid ${h(C.amber, 0.3)}`,
          borderRadius: 10, padding: "10px 16px", marginBottom: 14,
          animation: "fadeIn .2s ease",
        }}>
          <span style={{ fontSize: 13, color: C.amber, fontFamily: "'Syne Mono', monospace" }}>
            {selected.size} selected
          </span>
          <button
            onClick={handleBulkDiscard}
            disabled={actionLoading}
            style={{
              background: h(C.red, 0.1), border: `1px solid ${h(C.red, 0.3)}`,
              color: C.red, borderRadius: 7, padding: "6px 14px",
              cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
            }}
          >
            ✕ DISCARD SELECTED
          </button>
          <button
            onClick={() => setSelected(new Set())}
            style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: C.muted, borderRadius: 7, padding: "6px 12px",
              cursor: "pointer", fontSize: 11,
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div style={{ background: C.panel, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "36px 52px 1.2fr 1.8fr 140px 80px 80px 90px",
          padding: "10px 16px", background: C.card, borderBottom: `1px solid ${C.border}`,
          alignItems: "center",
        }}>
          <input
            type="checkbox"
            checked={selected.size > 0 && selected.size === emails.filter(e => e.status === "pending").length}
            onChange={toggleAll}
            style={{ accentColor: C.amber, width: 14, height: 14 }}
          />
          <span style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1 }}>URG</span>
          {["From", "Subject", "Type", "Status", "Date", ""].map(col => (
            <span key={col} style={{ fontSize: 10, color: C.muted, fontFamily: "'Syne Mono', monospace", letterSpacing: 1 }}>{col}</span>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
            {[1,2,3,4,5,6].map(i => <Skeleton key={i} height={52} />)}
          </div>
        ) : emails.length === 0 ? (
          <div style={{ padding: "52px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>
              {tab === "pending" ? "📬" : "✉️"}
            </div>
            <div style={{ color: C.muted, fontSize: 13 }}>
              {tab === "pending"
                ? "No emails waiting for review — you're all caught up."
                : "No emails match this filter."}
            </div>
          </div>
        ) : (
          emails.map(email => {
            const isPending  = email.status === "pending";
            const urgency    = email.urgency_score || 0;
            const urgColor   = urgency >= 8 ? C.red : urgency >= 5 ? C.amber : C.muted;
            const isSelected = selected.has(email.id);

            return (
              <div
                key={email.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "36px 52px 1.2fr 1.8fr 140px 80px 80px 90px",
                  padding: "11px 16px",
                  borderBottom: `1px solid ${C.border}`,
                  alignItems: "center",
                  background: isSelected ? h(C.amber, 0.04) : "transparent",
                  borderLeft: `3px solid ${isPending ? urgColor : "transparent"}`,
                  transition: "background .1s",
                  cursor: "pointer",
                }}
                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = h(C.white, 0.015); }}
                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
              >
                <div onClick={e => { e.stopPropagation(); if (isPending) toggleSelect(email.id); }}>
                  {isPending && (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(email.id)}
                      style={{ accentColor: C.amber, width: 14, height: 14 }}
                    />
                  )}
                </div>
                <div onClick={() => setModal(email)}><UrgencyBar score={email.urgency_score} /></div>
                <div onClick={() => setModal(email)} style={{ minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: isPending ? C.white : C.text,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {email.from_name || email.from_email}
                  </div>
                  {email.from_name && (
                    <div style={{ fontSize: 11, color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {email.from_email}
                    </div>
                  )}
                </div>
                <div onClick={() => setModal(email)} style={{
                  fontSize: 13, color: isPending ? C.text : C.muted,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  paddingRight: 12,
                }}>
                  {email.subject || "(no subject)"}
                </div>
                <div onClick={() => setModal(email)}>
                  <ClassificationPill classification={email.classification} />
                </div>
                <div onClick={() => setModal(email)}>
                  <StatusPill status={email.status} />
                </div>
                <div onClick={() => setModal(email)} style={{ fontSize: 11, color: C.muted }}>
                  {email.received_at
                    ? new Date(email.received_at).toLocaleDateString("en-AU", { dateStyle: "short" })
                    : "—"}
                </div>
                <div style={{ display: "flex", gap: 5 }}>
                  <button
                    onClick={() => setModal(email)}
                    style={{
                      background: isPending ? h(C.amber, 0.12) : h(C.cyan, 0.1),
                      border: `1px solid ${isPending ? h(C.amber, 0.3) : h(C.cyan, 0.25)}`,
                      color: isPending ? C.amber : C.cyan,
                      borderRadius: 6, padding: "5px 10px",
                      fontSize: 10, cursor: "pointer", fontFamily: "'Syne Mono', monospace",
                    }}
                  >
                    {isPending ? "REVIEW" : "VIEW"}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 10, paddingTop: 20 }}>
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: offset === 0 ? C.muted : C.text,
              borderRadius: 8, padding: "6px 14px", cursor: offset === 0 ? "not-allowed" : "pointer", fontSize: 12,
            }}
          >← Prev</button>
          <span style={{ fontSize: 12, color: C.muted }}>
            Page {currentPage + 1} of {totalPages} · {total} total
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= total}
            style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: offset + limit >= total ? C.muted : C.text,
              borderRadius: 8, padding: "6px 14px",
              cursor: offset + limit >= total ? "not-allowed" : "pointer", fontSize: 12,
            }}
          >Next →</button>
        </div>
      )}

      <div style={{ textAlign: "center", fontSize: 12, color: C.muted, paddingTop: 16 }}>
        Classified by AI email agent · sorted by urgency
      </div>

      <EmailModal
        email={modalEmail}
        onClose={() => setModal(null)}
        onSend={handleSend}
        onDiscard={handleDiscard}
        actionLoading={actionLoading}
      />
    </div>
  );
}
