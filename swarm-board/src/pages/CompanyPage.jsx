/**
 * CompanyPage — manage solar SME client company profiles.
 * Create, view, edit, and delete company profiles with branding settings.
 */
import { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import { useToast } from "../components/Toast";
import Confirm from "../components/Confirm";
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

const EMPTY_FORM = {
  client_id: "", name: "", abn: "", address: "",
  logo_url: "", primary_color: "#F59E0B",
  contact_email: "", contact_phone: "", website: "", notes: "",
};

function CompanyCard({ company, onEdit, onDelete }) {
  const [hov, setHov] = useState(false);
  const accent = company.primary_color || C.amber;
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.cardHov : C.card,
        border: `1px solid ${hov ? accent + "55" : C.border}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: 12, padding: "18px 20px",
        transition: "all .15s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: C.white, marginBottom: 4 }}>
            {company.name}
          </div>
          <div className="mono" style={{ fontSize: 11, color: C.muted, marginBottom: 10 }}>
            {company.client_id}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {company.contact_email && (
              <span style={{ fontSize: 12, color: C.muted }}>✉ {company.contact_email}</span>
            )}
            {company.contact_phone && (
              <span style={{ fontSize: 12, color: C.muted }}>📞 {company.contact_phone}</span>
            )}
            {company.abn && (
              <span style={{ fontSize: 12, color: C.muted }}>ABN {company.abn}</span>
            )}
            {company.website && (
              <a href={company.website} target="_blank" rel="noreferrer"
                style={{ fontSize: 12, color: accent }}>
                🌐 Website
              </a>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button onClick={() => onEdit(company)} style={{
            background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.3)}`,
            color: C.cyan, padding: "6px 14px", borderRadius: 6,
            cursor: "pointer", fontSize: 11, fontFamily: "'Syne Mono', monospace",
          }}>EDIT</button>
          <button onClick={() => onDelete(company)} style={{
            background: h(C.red, 0.08), border: `1px solid ${h(C.red, 0.25)}`,
            color: C.red, padding: "6px 12px", borderRadius: 6,
            cursor: "pointer", fontSize: 11,
          }}>✕</button>
        </div>
      </div>
    </div>
  );
}

function CompanyModal({ company, onSave, onClose }) {
  const [form, setForm] = useState(company ? { ...company } : { ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const isNew = !company?.id;

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async e => {
    e.preventDefault();
    if (!form.name || !form.client_id) { toast.error("Name and Client ID are required"); return; }
    setSaving(true);
    try {
      let r;
      if (isNew) {
        r = await apiFetch("/api/companies", { method: "POST", body: JSON.stringify(form) });
      } else {
        r = await apiFetch(`/api/companies/${company.client_id}`, { method: "PATCH", body: JSON.stringify(form) });
      }
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
      toast.success(isNew ? "Company created" : "Company updated");
      onSave(data.company);
    } catch (e) {
      toast.error(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const iS = {
    background: C.card, border: `1px solid ${C.border}`, color: C.text,
    borderRadius: 8, padding: "9px 12px", fontSize: 13, width: "100%",
  };
  const lS = {
    display: "block", fontSize: 10, color: C.muted,
    fontFamily: "'Syne Mono', monospace", letterSpacing: 1.5,
    textTransform: "uppercase", marginBottom: 5,
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(5,8,16,.88)",
      zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center",
      backdropFilter: "blur(4px)",
    }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: C.panel, border: `1px solid ${C.borderB}`,
        borderRadius: 16, padding: 28,
        width: "90vw", maxWidth: 560, maxHeight: "92vh", overflowY: "auto",
        boxShadow: "0 24px 80px rgba(0,0,0,.7)",
        animation: "fadeUp .2s ease",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
          <span className="mono" style={{ fontSize: 12, color: C.amber, letterSpacing: 2 }}>
            {isNew ? "NEW COMPANY" : "EDIT COMPANY"}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", fontSize: 18 }}>✕</button>
        </div>

        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label style={lS}>Company Name *</label>
              <input value={form.name} onChange={e => set("name", e.target.value)} placeholder="Perth Solar Co." style={iS} />
            </div>
            <div>
              <label style={{ ...lS }}>
                Client ID * <InfoTip text="Short slug used in URLs and API calls. e.g. 'perth-solar-co'. Lowercase, no spaces." />
              </label>
              <input
                value={form.client_id}
                onChange={e => set("client_id", e.target.value.toLowerCase().replace(/\s+/g, "-"))}
                placeholder="perth-solar-co"
                disabled={!isNew}
                style={{ ...iS, opacity: isNew ? 1 : 0.6 }}
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label style={lS}>ABN</label>
              <input value={form.abn} onChange={e => set("abn", e.target.value)} placeholder="12 345 678 901" style={iS} />
            </div>
            <div>
              <label style={lS}>Phone</label>
              <input value={form.contact_phone} onChange={e => set("contact_phone", e.target.value)} placeholder="+61 8 0000 0000" style={iS} />
            </div>
          </div>

          <div>
            <label style={lS}>Contact Email</label>
            <input type="email" value={form.contact_email} onChange={e => set("contact_email", e.target.value)} placeholder="owner@company.com.au" style={iS} />
          </div>

          <div>
            <label style={lS}>Website</label>
            <input type="url" value={form.website} onChange={e => set("website", e.target.value)} placeholder="https://company.com.au" style={iS} />
          </div>

          <div>
            <label style={lS}>Address</label>
            <input value={form.address} onChange={e => set("address", e.target.value)} placeholder="123 St Georges Tce, Perth WA 6000" style={iS} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 14, alignItems: "end" }}>
            <div>
              <label style={lS}>Logo URL <InfoTip text="Publicly accessible URL to the company logo image. Used in client dashboards and PDF reports." /></label>
              <input value={form.logo_url} onChange={e => set("logo_url", e.target.value)} placeholder="https://company.com.au/logo.png" style={iS} />
            </div>
            <div>
              <label style={lS}>Brand Colour</label>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="color"
                  value={form.primary_color || "#F59E0B"}
                  onChange={e => set("primary_color", e.target.value)}
                  style={{ width: 44, height: 40, borderRadius: 8, border: `1px solid ${C.border}`, cursor: "pointer", background: "none", padding: 2 }}
                />
                <span className="mono" style={{ fontSize: 11, color: C.muted }}>{form.primary_color}</span>
              </div>
            </div>
          </div>

          <div>
            <label style={lS}>Internal Notes</label>
            <textarea value={form.notes} onChange={e => set("notes", e.target.value)} rows={3}
              placeholder="Retainer start date, special requirements, key contacts…"
              style={{ ...iS, resize: "vertical" }} />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, paddingTop: 8, borderTop: `1px solid ${C.border}` }}>
            <button type="button" onClick={onClose} style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: C.muted, padding: "9px 18px", borderRadius: 8, cursor: "pointer", fontSize: 12,
            }}>CANCEL</button>
            <button type="submit" disabled={saving} style={{
              background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
              color: C.amber, padding: "9px 22px", borderRadius: 8,
              cursor: "pointer", fontSize: 12,
              fontFamily: "'Syne Mono', monospace",
            }}>
              {saving ? "SAVING…" : isNew ? "CREATE" : "SAVE"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CompanyPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [editTarget, setEditTarget] = useState(null);
  const [showModal, setShowModal]   = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
    apiFetch("/api/companies")
      .then(r => r.json())
      .then(d => setCompanies(d.companies || []))
      .catch(() => toast.error("Failed to load companies"))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const handleSave = company => {
    setCompanies(prev => {
      const exists = prev.find(c => c.id === company.id);
      return exists ? prev.map(c => c.id === company.id ? company : c) : [company, ...prev];
    });
    setShowModal(false);
    setEditTarget(null);
  };

  const handleDelete = async () => {
    try {
      const r = await apiFetch(`/api/companies/${deleteTarget.client_id}`, { method: "DELETE" });
      if (!r.ok) throw new Error((await r.json()).error);
      setCompanies(prev => prev.filter(c => c.id !== deleteTarget.id));
      toast.success(`${deleteTarget.name} deleted`);
    } catch (e) {
      toast.error(e.message || "Failed to delete");
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 28 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            CLIENT MANAGEMENT
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 6 }}>
            Companies
          </div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {companies.length} client{companies.length !== 1 ? "s" : ""} on retainer
          </div>
        </div>
        <button
          onClick={() => { setEditTarget(null); setShowModal(true); }}
          style={{
            background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
            color: C.amber, padding: "10px 20px", borderRadius: 8,
            cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
          }}
        >
          + NEW COMPANY
        </button>
      </div>

      {loading ? (
        <div style={{ color: C.muted, fontSize: 13 }}>Loading…</div>
      ) : companies.length === 0 ? (
        <div style={{
          textAlign: "center", padding: "60px 20px",
          background: C.panel, border: `1px dashed ${C.border}`,
          borderRadius: 14, color: C.muted,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🏢</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 6 }}>No companies yet</div>
          <div style={{ fontSize: 13, marginBottom: 20 }}>Add your first solar SME client to get started.</div>
          <button
            onClick={() => { setEditTarget(null); setShowModal(true); }}
            style={{
              background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
              color: C.amber, padding: "10px 24px", borderRadius: 8,
              cursor: "pointer", fontSize: 13,
            }}
          >
            Add Company
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 800 }}>
          {companies.map(c => (
            <CompanyCard
              key={c.id}
              company={c}
              onEdit={co => { setEditTarget(co); setShowModal(true); }}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      )}

      {showModal && (
        <CompanyModal
          company={editTarget}
          onSave={handleSave}
          onClose={() => { setShowModal(false); setEditTarget(null); }}
        />
      )}

      <Confirm
        open={!!deleteTarget}
        title={`Delete ${deleteTarget?.name}?`}
        message="This will remove the company profile and cannot be undone."
        confirmLabel="DELETE"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
