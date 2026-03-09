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
  "budget.weekly_aud":         "Total AUD budget available per week across all experiments.",
  "budget.max_single_bet_pct": "Maximum fraction of the weekly budget for any single experiment (Kelly cap).",
  "confidence.auto_proceed":   "Experiments scoring above this (0–10) are auto-approved without human review.",
  "confidence.human_gate":     "Experiments between this and auto_proceed are queued for human approval.",
  "confidence.auto_kill":      "Experiments scoring below this are automatically rejected.",
  "kelly.fractional":          "Fractional Kelly multiplier. 0.25 = bet 25% of the full Kelly fraction, reducing risk.",
  "breaker.yellow_failures":   "Number of consecutive experiment failures before a Yellow (warning) alert fires.",
  "breaker.orange_burn_rate":  "Budget burn rate multiplier (e.g. 1.5 = 150% of planned spend) that triggers Orange.",
  "breaker.red_failures":      "Consecutive failures that trigger Red — all agent activity halts immediately.",
  "breaker.red_single_loss_pct": "A single experiment loss exceeding this fraction of weekly budget triggers Red.",
  "portfolio.exploit_pct":     "Share of budget allocated to proven, low-risk strategies (exploit bucket).",
  "portfolio.explore_pct":     "Share of budget allocated to new, unproven strategies (explore bucket).",
  "portfolio.moonshot_pct":    "Share of budget allocated to high-risk, high-reward experiments.",
  "crm.sync_interval_min":     "How often the CRM cache is refreshed from GoHighLevel/HubSpot/Salesforce.",
  "crm.active":                "Which CRM is currently active. Options: ghl, hubspot, salesforce.",
  "notify.slack_enabled":      "Send Slack alerts for experiment approvals, failures, and circuit breaker events.",
};

const CATEGORY_LABELS = {
  budget:    "💰 Budget",
  confidence: "🎯 Confidence Routing",
  capital:   "📐 Kelly Capital",
  circuit:   "🔴 Circuit Breaker",
  portfolio: "📊 Portfolio Allocation",
  schedule:  "🕐 Scheduler",
  crm:       "🔗 CRM",
  notify:    "🔔 Notifications",
};

function SettingRow({ keyName, value, description, onChange }) {
  const tip = TIPS[keyName];
  const isBool = value === "true" || value === "false";
  const isNum  = !isNaN(Number(value)) && !isBool;

  return (
    <div style={{
      display: "flex", alignItems: "center",
      padding: "12px 16px",
      borderBottom: `1px solid ${C.border}`,
      gap: 16,
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
