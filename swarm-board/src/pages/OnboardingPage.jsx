/**
 * OnboardingPage — guided 5-step wizard for new solar company clients.
 * Steps: Company Info → CRM (GHL) → Voice AI → Knowledge Base → Go Live
 */
import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";

const C = {
  bg: "#050810", panel: "#080D1A", card: "#0C1222",
  border: "#132035", borderB: "#1E3050",
  amber: "#F59E0B", cyan: "#22D3EE", green: "#4ADE80",
  red: "#F87171", muted: "#475569", text: "#CBD5E1", white: "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

function Input({ label, value, onChange, placeholder, type = "text", hint }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {label && <label style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{label}</label>}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: "100%", background: C.card, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: "10px 14px", color: C.white, fontSize: 13,
          outline: "none", boxSizing: "border-box",
        }}
      />
      {hint && <div style={{ fontSize: 11, color: C.muted }}>{hint}</div>}
    </div>
  );
}

const STEPS = [
  { key: "company",   label: "Company Info",   icon: "🏢" },
  { key: "crm",       label: "CRM Setup",      icon: "🔗" },
  { key: "voice",     label: "Voice AI",       icon: "🤖" },
  { key: "knowledge", label: "Knowledge Base", icon: "📚" },
  { key: "complete",  label: "Go Live",        icon: "🚀" },
];

function StepIndicator({ steps, currentStep, completedSteps }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 36 }}>
      {STEPS.map((s, i) => {
        const done    = completedSteps[s.key];
        const active  = s.key === currentStep;
        const color   = done ? C.green : active ? C.amber : C.muted;
        return (
          <div key={s.key} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : 0 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 40, height: 40, borderRadius: "50%",
                background: done ? h(C.green, 0.15) : active ? h(C.amber, 0.15) : h(C.muted, 0.08),
                border: `2px solid ${color}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 18, transition: "all .2s",
                boxShadow: active ? `0 0 12px ${h(C.amber, 0.3)}` : "none",
              }}>
                {done ? "✓" : s.icon}
              </div>
              <div style={{ fontSize: 10, color, whiteSpace: "nowrap", fontWeight: active ? 600 : 400 }}>
                {s.label}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                flex: 1, height: 2, margin: "0 6px", marginBottom: 16,
                background: done ? C.green : C.border, transition: "background .3s",
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step panels
// ─────────────────────────────────────────────────────────────────────────────

function CompanyStep({ apiFetch, onDone }) {
  const [form, setForm] = useState({ company_name: "", abn: "", phone: "", email: "", website: "", service_areas: "", years_in_business: "", num_installers: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const submit = async () => {
    if (!form.company_name.trim()) { setError("Company name is required."); return; }
    setSaving(true); setError("");
    try {
      const res = await apiFetch("/api/onboarding/company", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.ok) onDone(data.status);
      else setError(data.error || "Something went wrong.");
    } finally { setSaving(false); }
  };

  const F = (key, label, placeholder, hint) => (
    <Input key={key} label={label} value={form[key]} onChange={v => setForm(p => ({ ...p, [key]: v }))} placeholder={placeholder} hint={hint} />
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>Tell us about your company</div>
      <div style={{ fontSize: 13, color: C.muted, marginBottom: 8 }}>
        Your AI receptionist will introduce itself as a representative of your company. Get this right and it sounds exactly like your team.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={{ gridColumn: "1 / -1" }}>
          {F("company_name", "Company Name *", "SunTech Solar Perth")}
        </div>
        {F("abn", "ABN", "12 345 678 901")}
        {F("phone", "Business Phone", "08 9XXX XXXX")}
        {F("email", "Business Email", "info@yourcompany.com.au")}
        {F("website", "Website", "https://yourcompany.com.au")}
        <div style={{ gridColumn: "1 / -1" }}>
          {F("service_areas", "Service Areas", "Perth Metro, Mandurah, Joondalup", "Comma-separated — your AI will only quote customers in these areas")}
        </div>
        {F("years_in_business", "Years in Business", "8")}
        {F("num_installers", "Number of Installers", "12")}
      </div>
      {error && <div style={{ color: C.red, fontSize: 12 }}>{error}</div>}
      <button onClick={submit} disabled={saving} style={{
        background: h(C.amber, 0.15), border: `1px solid ${h(C.amber, 0.4)}`,
        color: C.amber, borderRadius: 10, padding: "12px 28px", fontSize: 14,
        fontWeight: 600, cursor: saving ? "not-allowed" : "pointer", transition: "all .15s",
        alignSelf: "flex-start",
      }}>
        {saving ? "Saving…" : "Continue →"}
      </button>
    </div>
  );
}

function CRMStep({ apiFetch, onDone }) {
  const [form, setForm] = useState({ ghl_api_key: "", ghl_location_id: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const submit = async () => {
    if (!form.ghl_api_key || !form.ghl_location_id) { setError("Both fields are required."); return; }
    setSaving(true); setError("");
    try {
      const res = await apiFetch("/api/onboarding/crm", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.ok) onDone(data.status);
      else setError(data.error || "Something went wrong.");
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>Connect GoHighLevel</div>
      <div style={{ fontSize: 13, color: C.muted, marginBottom: 8 }}>
        Your AI receptionist writes every lead directly into your GHL pipeline. Contacts are created, scored, and moved through stages automatically during the call.
      </div>

      {/* How-to card */}
      <div style={{ background: h(C.cyan, 0.05), border: `1px solid ${h(C.cyan, 0.2)}`, borderRadius: 10, padding: "14px 16px" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.cyan, marginBottom: 8 }}>How to find your GHL credentials</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {[
            "1. Log into GoHighLevel → Settings → Integrations → API",
            "2. Copy your Private API Key",
            "3. In Settings → Business Info, copy your Location ID",
          ].map((step, i) => (
            <div key={i} style={{ fontSize: 12, color: C.text }}>{step}</div>
          ))}
        </div>
      </div>

      <Input label="GHL Private API Key *" value={form.ghl_api_key}
        onChange={v => setForm(p => ({ ...p, ghl_api_key: v }))}
        placeholder="eyJhbGciOiJSUzI1NiIsInR5cCI6Ikp…"
        hint="Never share this key — it's stored securely" />

      <Input label="GHL Location ID *" value={form.ghl_location_id}
        onChange={v => setForm(p => ({ ...p, ghl_location_id: v }))}
        placeholder="abc123def456…" />

      {error && <div style={{ color: C.red, fontSize: 12 }}>{error}</div>}
      <button onClick={submit} disabled={saving} style={{
        background: h(C.amber, 0.15), border: `1px solid ${h(C.amber, 0.4)}`,
        color: C.amber, borderRadius: 10, padding: "12px 28px", fontSize: 14,
        fontWeight: 600, cursor: saving ? "not-allowed" : "pointer",
        alignSelf: "flex-start",
      }}>
        {saving ? "Connecting…" : "Connect GHL →"}
      </button>
    </div>
  );
}

function VoiceStep({ apiFetch, onDone }) {
  const [form, setForm] = useState({ retell_agent_id: "", phone: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const submit = async () => {
    if (!form.retell_agent_id || !form.phone) { setError("Both fields are required."); return; }
    setSaving(true); setError("");
    try {
      const res = await apiFetch("/api/onboarding/voice", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.ok) onDone(data.status);
      else setError(data.error || "Something went wrong.");
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>Configure your AI Receptionist</div>
      <div style={{ fontSize: 13, color: C.muted, marginBottom: 8 }}>
        We use Retell AI to power the voice. Your AI receptionist gets a dedicated phone number that forwards to it 24/7.
      </div>

      <div style={{ background: h(C.amber, 0.05), border: `1px solid ${h(C.amber, 0.2)}`, borderRadius: 10, padding: "14px 16px" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.amber, marginBottom: 8 }}>Setup steps in Retell AI</div>
        {[
          "1. Log into retellai.com → Create Agent → Custom LLM",
          "2. Set LLM endpoint to: https://your-server.com/voice/response",
          "3. Set post-call webhook to: https://your-server.com/voice/post-call",
          "4. Purchase a phone number in Retell and link it to your agent",
          "5. Copy the Agent ID from your agent settings",
        ].map((s, i) => <div key={i} style={{ fontSize: 12, color: C.text, marginBottom: 4 }}>{s}</div>)}
      </div>

      <Input label="Retell Agent ID *" value={form.retell_agent_id}
        onChange={v => setForm(p => ({ ...p, retell_agent_id: v }))}
        placeholder="agent_xxxxxxxxxxxxx"
        hint="Found in your Retell dashboard under Agent Settings" />

      <Input label="Your Retell Phone Number *" value={form.phone}
        onChange={v => setForm(p => ({ ...p, phone: v }))}
        placeholder="+61 8 XXXX XXXX"
        hint="The number customers call — must be linked to your Retell agent" />

      {error && <div style={{ color: C.red, fontSize: 12 }}>{error}</div>}
      <button onClick={submit} disabled={saving} style={{
        background: h(C.amber, 0.15), border: `1px solid ${h(C.amber, 0.4)}`,
        color: C.amber, borderRadius: 10, padding: "12px 28px", fontSize: 14,
        fontWeight: 600, cursor: saving ? "not-allowed" : "pointer",
        alignSelf: "flex-start",
      }}>
        {saving ? "Saving…" : "Save Voice Config →"}
      </button>
    </div>
  );
}

function KnowledgeStep({ apiFetch, onDone, onNavigate }) {
  const [saving, setSaving] = useState(false);

  const markDone = async () => {
    setSaving(true);
    try {
      const res = await apiFetch("/api/onboarding/knowledge", { method: "POST" });
      const data = await res.json();
      if (data.ok) onDone(data.status);
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 4 }}>Train your AI</div>
      <div style={{ fontSize: 13, color: C.muted, marginBottom: 8 }}>
        Your AI receptionist uses the knowledge base to answer questions accurately. Fill it in now to get the most out of your first calls.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {[
          { icon: "💲", title: "Products & Pricing", desc: "System sizes, prices after rebates, battery add-ons" },
          { icon: "❓", title: "FAQs", desc: "Process, warranties, finance options, council approval" },
          { icon: "🛡️", title: "Objection Handlers", desc: "Responses to price, timing, competition, and trust objections" },
          { icon: "☀️", title: "Rebate Info", desc: "STC federal rebate + state schemes for your service area" },
        ].map(item => (
          <div key={item.title} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 16px" }}>
            <div style={{ fontSize: 22, marginBottom: 6 }}>{item.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.white, marginBottom: 4 }}>{item.title}</div>
            <div style={{ fontSize: 12, color: C.muted }}>{item.desc}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {onNavigate && (
          <button onClick={() => onNavigate("knowledge-base")} style={{
            background: h(C.cyan, 0.12), border: `1px solid ${h(C.cyan, 0.35)}`,
            color: C.cyan, borderRadius: 10, padding: "12px 24px", fontSize: 14,
            fontWeight: 600, cursor: "pointer",
          }}>
            Open Knowledge Base →
          </button>
        )}
        <button onClick={markDone} disabled={saving} style={{
          background: h(C.amber, 0.12), border: `1px solid ${h(C.amber, 0.35)}`,
          color: C.amber, borderRadius: 10, padding: "12px 24px", fontSize: 14,
          fontWeight: 600, cursor: saving ? "not-allowed" : "pointer",
        }}>
          {saving ? "Marking done…" : "I've filled it in →"}
        </button>
      </div>
    </div>
  );
}

function CompleteStep({ apiFetch, onDone }) {
  const [saving, setSaving] = useState(false);
  const [done, setDone]     = useState(false);

  const goLive = async () => {
    setSaving(true);
    try {
      const res = await apiFetch("/api/onboarding/complete", { method: "POST" });
      const data = await res.json();
      if (data.ok) { setDone(true); onDone(data.status); }
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, alignItems: "center", textAlign: "center", padding: "20px 0" }}>
      {done ? (
        <>
          <div style={{ fontSize: 60 }}>🚀</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: C.green }}>You're live!</div>
          <div style={{ fontSize: 14, color: C.text, maxWidth: 420 }}>
            Your AI receptionist is now answering calls 24/7, qualifying leads, and populating your GHL pipeline automatically.
          </div>
          <div style={{ background: h(C.green, 0.08), border: `1px solid ${h(C.green, 0.25)}`, borderRadius: 12, padding: "16px 24px", maxWidth: 420 }}>
            <div style={{ fontSize: 13, color: C.green, fontWeight: 600, marginBottom: 8 }}>What happens now</div>
            {[
              "Inbound calls ring your Retell number",
              "AI qualifies and scores every lead",
              "Hot leads (score 7+) get priority follow-up",
              "All data flows into your GHL pipeline",
              "You see everything in your dashboard",
            ].map((item, i) => (
              <div key={i} style={{ fontSize: 12, color: C.text, marginBottom: 4, textAlign: "left" }}>
                ✓ {item}
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div style={{ fontSize: 56 }}>🎉</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: C.white }}>Almost there!</div>
          <div style={{ fontSize: 14, color: C.muted, maxWidth: 440 }}>
            You've completed all the setup steps. Click below to activate your AI receptionist and go live.
          </div>
          <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
            {[
              ["✓ Company profile", C.green],
              ["✓ GHL connected", C.green],
              ["✓ Voice AI configured", C.green],
              ["✓ Knowledge base ready", C.green],
            ].map(([label, color]) => (
              <span key={label} style={{
                fontSize: 12, color, background: h(color, 0.08),
                border: `1px solid ${h(color, 0.25)}`, borderRadius: 20,
                padding: "4px 14px",
              }}>{label}</span>
            ))}
          </div>
          <button onClick={goLive} disabled={saving} style={{
            background: h(C.green, 0.15), border: `2px solid ${h(C.green, 0.5)}`,
            color: C.green, borderRadius: 12, padding: "14px 36px", fontSize: 16,
            fontWeight: 700, cursor: saving ? "not-allowed" : "pointer",
            boxShadow: `0 0 20px ${h(C.green, 0.2)}`,
            transition: "all .2s",
          }}>
            {saving ? "Activating…" : "🚀 Go Live Now"}
          </button>
        </>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
export default function OnboardingPage({ onNavigate }) {
  const { apiFetch } = useAuth();
  const [status, setStatus]     = useState(null);
  const [currentStep, setCurrentStep] = useState("company");
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    apiFetch("/api/onboarding/status").then(r => r.json()).then(data => {
      setStatus(data);
      // Jump to first incomplete step
      const next = STEPS.find(s => !data.steps?.[s.key]);
      if (next) setCurrentStep(next.key);
      else setCurrentStep("complete");
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []); // eslint-disable-line

  const handleStepDone = (newStatus) => {
    setStatus(newStatus);
    const next = STEPS.find(s => !newStatus.steps?.[s.key]);
    if (next) setCurrentStep(next.key);
    else setCurrentStep("complete");
  };

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: C.bg }}>
        <div style={{ color: C.muted, fontFamily: "'Syne Mono', monospace", fontSize: 12, letterSpacing: 2 }}>LOADING…</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: "auto", background: C.bg }}>
      {/* Header */}
      <div style={{
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        padding: "20px 32px",
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: C.white }}>Setup Wizard</div>
        <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
          Get your AI receptionist live in 5 steps
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: C.border }}>
        <div style={{
          height: "100%", background: C.amber,
          width: `${status?.percent_done ?? 0}%`,
          transition: "width .4s ease",
        }} />
      </div>

      <div style={{ padding: "32px", maxWidth: 700, margin: "0 auto" }}>

        {/* Step indicator */}
        <StepIndicator
          steps={STEPS}
          currentStep={currentStep}
          completedSteps={status?.steps || {}}
        />

        {/* Step content card */}
        <div style={{
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 18, padding: "32px 36px",
        }}>
          {currentStep === "company" && (
            <CompanyStep apiFetch={apiFetch} onDone={handleStepDone} />
          )}
          {currentStep === "crm" && (
            <CRMStep apiFetch={apiFetch} onDone={handleStepDone} />
          )}
          {currentStep === "voice" && (
            <VoiceStep apiFetch={apiFetch} onDone={handleStepDone} />
          )}
          {currentStep === "knowledge" && (
            <KnowledgeStep apiFetch={apiFetch} onDone={handleStepDone} onNavigate={onNavigate} />
          )}
          {currentStep === "complete" && (
            <CompleteStep apiFetch={apiFetch} onDone={handleStepDone} />
          )}
        </div>

        {/* Step nav — allow jumping to completed steps */}
        {status && Object.values(status.steps).some(Boolean) && currentStep !== "complete" && (
          <div style={{ marginTop: 20, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: C.muted, display: "flex", alignItems: "center" }}>Jump to:</span>
            {STEPS.filter(s => status.steps[s.key] && s.key !== currentStep).map(s => (
              <button key={s.key} onClick={() => setCurrentStep(s.key)} style={{
                background: "transparent", border: `1px solid ${C.border}`,
                color: C.muted, borderRadius: 6, padding: "4px 12px",
                cursor: "pointer", fontSize: 11,
              }}>
                {s.icon} {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
