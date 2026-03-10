/**
 * SettingsPage — view and edit all runtime app settings grouped by category.
 * Also includes Change Password section for the current user.
 */
import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { useToast } from "../components/Toast";
import InfoTip from "../components/InfoTip";

const C = {
  bg:      "#050810",
  panel:   "#080D1A",
  card:    "#0C1222",
  cardHov: "#101828",
  border:  "#132035",
  borderB: "#1E3050",
  amber:   "#F59E0B",
  cyan:    "#22D3EE",
  green:   "#4ADE80",
  red:     "#F87171",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

const TIPS = {
  "crm.sync_interval_min":       "How often (minutes) the CRM cache is refreshed from GoHighLevel.",
  "crm.active":                  "Which CRM is active. Currently: ghl.",
  "notify.slack_enabled":        "Send Slack alerts for hot leads (score ≥ 8), call completions, and errors.",
  "notify.hot_lead_threshold":   "Minimum lead score (1–10) that triggers a Slack HOT LEAD alert.",
  "voice.enabled":               "Enable the Retell AI voice receptionist for inbound and outbound calls.",
  "voice.outbound_enabled":      "Automatically fire an outbound call to hot leads after qualification.",
  "voice.transfer_threshold":    "Lead score at which the AI transfers the call to a human sales rep.",
  "agents.qualification_enabled": "Run lead qualification automatically when a new lead arrives via webhook.",
  "agents.proposal_enabled":     "Automatically generate a solar proposal after a lead is qualified.",
  "email.agent_enabled":         "Master on/off switch. When OFF, no inbound emails are processed.",
  "email.auto_send_enabled":     "When ON, emails scoring above the threshold are sent automatically without review.",
  "email.auto_send_threshold":   "Urgency score (1-10) required to trigger auto-send. Default 9 (rarely fires).",
  "email.auto_discard_spam":     "Auto-discard emails classified as SPAM without showing them in the queue.",
  "email.imap_poll_interval":    "Seconds between inbox checks for direct IMAP (Gmail/Outlook). Set to 0 to disable.",
  "email.reply_prompt":          "Custom AI instructions appended to every draft reply prompt. Describe tone, sign-off, and anything to always mention.",
  "agents.email_enabled":        "Enable the email processor to triage and draft replies to inbound emails.",
  "schedule.crm_sync_min":       "Interval (minutes) between CRM sync runs. Default: 30.",
};

const CATEGORY_LABELS = {
  voice:    "🎙️ Voice AI",
  agents:   "🤖 Agent Toggles",
  crm:      "🔗 CRM Sync",
  notify:   "🔔 Notifications",
  schedule: "🕐 Scheduler",
  email:    "✉️ Email Processing",
};

function SettingRow({ keyName, value, description, onChange }) {
  const tip = TIPS[keyName];
  const isBool     = value === "true" || value === "false";
  const isNum      = !isNaN(Number(value)) && !isBool && value !== "";
  const isTextarea = keyName === "email.reply_prompt";

  return (
    <div style={{
      display: "flex", alignItems: isTextarea ? "flex-start" : "center",
      flexDirection: isTextarea ? "column" : "row",
      padding: "12px 16px",
      borderBottom: `1px solid ${C.border}`,
      gap: isTextarea ? 10 : 16,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
          <span className="mono" style={{ fontSize: 12, color: C.cyan }}>{keyName}</span>
          {tip && <InfoTip text={tip} />}
        </div>
        {description && (
          <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>{description}</div>
        )}
      </div>
      <div style={{ flexShrink: 0 }}>
        {isBool ? (
          <button
            onClick={() => onChange(keyName, value === "true" ? "false" : "true")}
            style={{
              background: value === "true" ? h(C.green, 0.15) : h(C.muted, 0.1),
              border: `1px solid ${value === "true" ? C.green : C.muted}`,
              color: value === "true" ? C.green : C.muted,
              padding: "5px 14px", borderRadius: 6, cursor: "pointer",
              fontSize: 12, fontFamily: "'Syne Mono', monospace", letterSpacing: 1,
            }}
          >
            {value === "true" ? "ON" : "OFF"}
          </button>
        ) : isTextarea ? (
          <textarea
            defaultValue={value}
            rows={4}
            onBlur={e => { if (e.target.value !== value) onChange(keyName, e.target.value); }}
            placeholder="e.g. Always mention our 10-year warranty. Sign off as 'The SunPower Team'."
            style={{
              background: C.card, border: `1px solid ${C.border}`,
              color: C.text, borderRadius: 8, padding: "8px 12px",
              fontSize: 13, width: "100%", resize: "vertical",
              fontFamily: "inherit", lineHeight: 1.55, outline: "none",
              boxSizing: "border-box",
            }}
          />
        ) : (
          <input
            type={isNum ? "number" : "text"}
            defaultValue={value}
            onBlur={e => { if (e.target.value !== value) onChange(keyName, e.target.value); }}
            style={{
              background: C.card, border: `1px solid ${C.border}`,
              color: C.text, borderRadius: 6, padding: "6px 10px",
              fontSize: 13, width: isNum ? 90 : 140,
              fontFamily: isNum ? "'Syne Mono', monospace" : "inherit",
              textAlign: isNum ? "right" : "left",
            }}
          />
        )}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { apiFetch, user } = useAuth();
  const { toast } = useToast();
  const [settings, setSettings] = useState({});
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);

  // Change password state
  const [pwForm, setPwForm] = useState({ current: "", new: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);

  useEffect(() => {
    apiFetch("/api/settings")
      .then(r => r.json())
      .then(d => setSettings(d.settings || {}))
      .catch(() => toast.error("Failed to load settings"))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const handleChange = async (key, value) => {
    setSaving(true);
    try {
      const r = await apiFetch("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({ [key]: value }),
      });
      if (!r.ok) throw new Error((await r.json()).error);
      // Update local state
      setSettings(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(cat => {
          next[cat] = next[cat].map(s => s.key === key ? { ...s, value } : s);
        });
        return next;
      });
      toast.success("Setting saved");
    } catch (e) {
      toast.error(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordChange = async e => {
    e.preventDefault();
    if (pwForm.new !== pwForm.confirm) { toast.error("New passwords don't match"); return; }
    if (pwForm.new.length < 8) { toast.error("Password must be at least 8 characters"); return; }
    setPwSaving(true);
    try {
      const r = await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current: pwForm.current, new: pwForm.new }),
      });
      if (!r.ok) throw new Error((await r.json()).error);
      toast.success("Password updated successfully");
      setPwForm({ current: "", new: "", confirm: "" });
    } catch (e) {
      toast.error(e.message || "Failed to update password");
    } finally {
      setPwSaving(false);
    }
  };

  const iS = {
    background: C.card, border: `1px solid ${C.border}`,
    color: C.text, borderRadius: 8, padding: "10px 14px",
    fontSize: 13, width: "100%",
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
          CONFIGURATION
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 6 }}>
          Settings
        </div>
        <div style={{ fontSize: 13, color: C.muted }}>
          Runtime configuration — changes take effect immediately without restarting.
        </div>
      </div>

      {loading ? (
        <div style={{ color: C.muted, fontSize: 13 }}>Loading settings…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 760 }}>
          {Object.entries(settings).map(([category, rows]) => (
            <div key={category} style={{
              background: C.panel, border: `1px solid ${C.border}`,
              borderRadius: 14, overflow: "hidden",
            }}>
              <div style={{
                padding: "14px 16px",
                borderBottom: `1px solid ${C.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: C.text }}>
                  {CATEGORY_LABELS[category] || category}
                </span>
                {saving && (
                  <span className="mono" style={{ fontSize: 10, color: C.amber }}>saving…</span>
                )}
              </div>
              {rows.map(s => (
                <SettingRow
                  key={s.key}
                  keyName={s.key}
                  value={s.value}
                  description={s.description}
                  onChange={handleChange}
                />
              ))}
            </div>
          ))}

          {/* Change Password */}
          <div style={{
            background: C.panel, border: `1px solid ${C.border}`,
            borderRadius: 14, overflow: "hidden",
          }}>
            <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}` }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: C.text }}>🔒 Change Password</span>
            </div>
            <form onSubmit={handlePasswordChange} style={{ padding: 20 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 380 }}>
                {[
                  ["current", "Current password"],
                  ["new",     "New password (8+ chars)"],
                  ["confirm", "Confirm new password"],
                ].map(([field, label]) => (
                  <div key={field}>
                    <label style={{
                      display: "block", fontSize: 11, color: C.muted,
                      fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5,
                      textTransform: "uppercase", marginBottom: 6,
                    }}>
                      {label}
                    </label>
                    <input
                      type="password"
                      value={pwForm[field]}
                      onChange={e => setPwForm(f => ({ ...f, [field]: e.target.value }))}
                      style={iS}
                    />
                  </div>
                ))}
                <button
                  type="submit"
                  disabled={pwSaving}
                  style={{
                    alignSelf: "flex-start",
                    background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
                    color: C.amber, padding: "9px 20px",
                    borderRadius: 8, cursor: "pointer", fontSize: 12,
                    fontFamily: "'Syne Mono', monospace",
                  }}
                >
                  {pwSaving ? "SAVING…" : "UPDATE PASSWORD"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
