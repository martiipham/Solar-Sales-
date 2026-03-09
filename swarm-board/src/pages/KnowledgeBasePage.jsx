/**
 * KnowledgeBasePage — lets clients (and admins) manage what their AI knows.
 * Tabs: Company Profile | Products | FAQs | Objection Handlers
 */
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../AuthContext";

const C = {
  bg: "#050810", panel: "#080D1A", card: "#0C1222",
  border: "#132035", borderB: "#1E3050",
  amber: "#F59E0B", cyan: "#22D3EE", green: "#4ADE80",
  red: "#F87171", muted: "#475569", text: "#CBD5E1", white: "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");
const SHIMMER = `@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}`;

function Skeleton({ width = "100%", height = 16, radius = 6 }) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background: `linear-gradient(90deg,${C.card} 25%,${C.border} 50%,${C.card} 75%)`,
      backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
    }} />
  );
}

function Input({ label, value, onChange, placeholder, type = "text", multiline = false }) {
  const baseStyle = {
    width: "100%", background: C.card, border: `1px solid ${C.border}`,
    borderRadius: 8, padding: "9px 12px", color: C.white, fontSize: 13,
    outline: "none", boxSizing: "border-box", fontFamily: "inherit",
    resize: multiline ? "vertical" : "none",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {label && <label style={{ fontSize: 11, color: C.muted, letterSpacing: 0.5 }}>{label}</label>}
      {multiline
        ? <textarea rows={3} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={baseStyle} />
        : <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} style={baseStyle} />
      }
    </div>
  );
}

function SaveBtn({ onClick, saving, saved }) {
  return (
    <button onClick={onClick} disabled={saving} style={{
      background: saved ? h(C.green, 0.15) : h(C.amber, 0.15),
      border: `1px solid ${saved ? h(C.green, 0.4) : h(C.amber, 0.4)}`,
      color: saved ? C.green : C.amber,
      borderRadius: 8, padding: "8px 20px", cursor: saving ? "not-allowed" : "pointer",
      fontSize: 12, fontFamily: "'Syne Mono', monospace", transition: "all .2s",
    }}>
      {saving ? "SAVING…" : saved ? "✓ SAVED" : "SAVE"}
    </button>
  );
}

function DeleteBtn({ onClick }) {
  const [confirm, setConfirm] = useState(false);
  if (confirm) return (
    <div style={{ display: "flex", gap: 6 }}>
      <button onClick={onClick} style={{
        background: h(C.red, 0.15), border: `1px solid ${h(C.red, 0.4)}`,
        color: C.red, borderRadius: 6, padding: "5px 10px", cursor: "pointer", fontSize: 11,
      }}>Confirm</button>
      <button onClick={() => setConfirm(false)} style={{
        background: "transparent", border: `1px solid ${C.border}`,
        color: C.muted, borderRadius: 6, padding: "5px 10px", cursor: "pointer", fontSize: 11,
      }}>Cancel</button>
    </div>
  );
  return (
    <button onClick={() => setConfirm(true)} style={{
      background: "transparent", border: `1px solid ${C.border}`,
      color: C.muted, borderRadius: 6, padding: "5px 10px", cursor: "pointer", fontSize: 11,
    }}>Delete</button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: Company Profile
// ─────────────────────────────────────────────────────────────────────────────
function ProfileTab({ apiFetch }) {
  const FIELDS = [
    { key: "company_name",      label: "Company Name *" },
    { key: "abn",               label: "ABN" },
    { key: "phone",             label: "Phone Number" },
    { key: "email",             label: "Email" },
    { key: "website",           label: "Website" },
    { key: "service_areas",     label: "Service Areas (comma-separated states/suburbs)" },
    { key: "years_in_business", label: "Years in Business", type: "number" },
    { key: "num_installers",    label: "Number of Installers", type: "number" },
    { key: "certifications",    label: "Certifications (e.g. CEC Approved Retailer)" },
  ];

  const [form, setForm]   = useState({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/kb/profile").then(r => r.json()).then(d => {
      setForm(d.profile || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []); // eslint-disable-line

  const save = async () => {
    setSaving(true);
    try {
      await apiFetch("/api/kb/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.white }}>Company Profile</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>Your AI receptionist introduces itself using this information</div>
        </div>
        <SaveBtn onClick={save} saving={saving} saved={saved} />
      </div>
      <div style={{ padding: 20 }}>
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[1,2,3,4].map(i => <Skeleton key={i} height={50} />)}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {FIELDS.map(f => (
              <div key={f.key} style={{ gridColumn: f.key === "service_areas" || f.key === "certifications" ? "1 / -1" : undefined }}>
                <Input
                  label={f.label}
                  type={f.type || "text"}
                  value={form[f.key] || ""}
                  onChange={v => setForm(p => ({ ...p, [f.key]: v }))}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: Products
// ─────────────────────────────────────────────────────────────────────────────
function ProductsTab({ apiFetch }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [adding, setAdding]     = useState(false);
  const [newProd, setNewProd]   = useState({ product_type: "solar_system", name: "", description: "", price_from_aud: "", price_to_aud: "", brands: "" });
  const [saving, setSaving]     = useState(false);

  const load = () => apiFetch("/api/kb/products").then(r => r.json()).then(d => {
    setProducts(d.products || []);
    setLoading(false);
  });

  useEffect(() => { load(); }, []); // eslint-disable-line

  const addProduct = async () => {
    setSaving(true);
    try {
      await apiFetch("/api/kb/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newProd),
      });
      setAdding(false);
      setNewProd({ product_type: "solar_system", name: "", description: "", price_from_aud: "", price_to_aud: "", brands: "" });
      load();
    } finally { setSaving(false); }
  };

  const deleteProduct = async (id) => {
    await apiFetch(`/api/kb/products/${id}`, { method: "DELETE" });
    load();
  };

  const TYPES = ["solar_system", "battery", "ev_charger", "inverter", "other"];

  return (
    <div>
      <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.white }}>Products & Services</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>Your AI quotes pricing from these during calls</div>
        </div>
        <button onClick={() => setAdding(v => !v)} style={{
          background: h(C.amber, 0.12), border: `1px solid ${h(C.amber, 0.35)}`,
          color: C.amber, borderRadius: 8, padding: "7px 16px",
          cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
        }}>
          {adding ? "CANCEL" : "+ ADD PRODUCT"}
        </button>
      </div>

      {adding && (
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${C.border}`, background: h(C.amber, 0.04) }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: C.muted, display: "block", marginBottom: 5 }}>Type</label>
              <select value={newProd.product_type} onChange={e => setNewProd(p => ({ ...p, product_type: e.target.value }))}
                style={{ width: "100%", background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "9px 12px", color: C.white, fontSize: 13 }}>
                {TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <Input label="Product Name *" value={newProd.name} onChange={v => setNewProd(p => ({ ...p, name: v }))} placeholder="e.g. 6.6kW Solar System" />
            <Input label="Price From (AUD)" type="number" value={newProd.price_from_aud} onChange={v => setNewProd(p => ({ ...p, price_from_aud: v }))} placeholder="4500" />
            <Input label="Price To (AUD)" type="number" value={newProd.price_to_aud} onChange={v => setNewProd(p => ({ ...p, price_to_aud: v }))} placeholder="6500" />
            <div style={{ gridColumn: "1 / -1" }}>
              <Input label="Description" value={newProd.description} onChange={v => setNewProd(p => ({ ...p, description: v }))} multiline placeholder="Brief description for the AI to use when explaining this product" />
            </div>
            <Input label="Brands" value={newProd.brands} onChange={v => setNewProd(p => ({ ...p, brands: v }))} placeholder="REC, Jinko, Fronius" />
          </div>
          <button onClick={addProduct} disabled={saving || !newProd.name} style={{
            background: h(C.green, 0.15), border: `1px solid ${h(C.green, 0.4)}`,
            color: C.green, borderRadius: 8, padding: "8px 20px",
            cursor: saving || !newProd.name ? "not-allowed" : "pointer", fontSize: 12,
          }}>
            {saving ? "Adding…" : "Add Product"}
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
          {[1,2,3].map(i => <Skeleton key={i} height={60} />)}
        </div>
      ) : products.length === 0 ? (
        <div style={{ padding: "36px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>
          No products yet. Add your solar systems, batteries, and other services above.
        </div>
      ) : products.map(p => (
        <div key={p.id} style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", gap: 16, alignItems: "flex-start" }}>
          <div style={{
            background: h(C.amber, 0.1), border: `1px solid ${h(C.amber, 0.25)}`,
            borderRadius: 8, padding: "4px 10px", fontSize: 10, color: C.amber,
            fontFamily: "'Syne Mono', monospace", flexShrink: 0, marginTop: 2,
          }}>
            {(p.product_type || "product").toUpperCase().replace(/_/g, " ")}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: C.white }}>{p.name}</div>
            {p.description && <div style={{ fontSize: 12, color: C.muted, marginTop: 3 }}>{p.description}</div>}
            <div style={{ fontSize: 12, color: C.text, marginTop: 4 }}>
              {p.price_from_aud && `$${Number(p.price_from_aud).toLocaleString()}`}
              {p.price_to_aud && ` – $${Number(p.price_to_aud).toLocaleString()}`}
              {p.brands && ` · ${p.brands}`}
            </div>
          </div>
          <DeleteBtn onClick={() => deleteProduct(p.id)} />
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Generic list tab (FAQs + Objections share the same pattern)
// ─────────────────────────────────────────────────────────────────────────────
function ListTab({ apiFetch, endpoint, itemKey, fields, title, subtitle, emptyMsg, addLabel }) {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding]   = useState(false);
  const [form, setForm]       = useState({});
  const [saving, setSaving]   = useState(false);
  const [editId, setEditId]   = useState(null);
  const [editForm, setEditForm] = useState({});
  const [editSaving, setEditSaving] = useState(false);
  const [editSaved, setEditSaved] = useState(false);

  const load = () => apiFetch(`/api/kb/${endpoint}`).then(r => r.json()).then(d => {
    setItems(d[itemKey] || []);
    setLoading(false);
  });

  useEffect(() => { load(); }, []); // eslint-disable-line

  const add = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/kb/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setAdding(false);
      setForm({});
      load();
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    await apiFetch(`/api/kb/${endpoint}/${id}`, { method: "DELETE" });
    load();
  };

  const saveEdit = async (id) => {
    setEditSaving(true);
    try {
      await apiFetch(`/api/kb/${endpoint}/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editForm),
      });
      setEditSaved(true);
      setTimeout(() => { setEditSaved(false); setEditId(null); }, 1500);
      load();
    } finally { setEditSaving(false); }
  };

  const primaryField = fields[0];

  return (
    <div>
      <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.white }}>{title}</div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>{subtitle}</div>
        </div>
        <button onClick={() => setAdding(v => !v)} style={{
          background: h(C.amber, 0.12), border: `1px solid ${h(C.amber, 0.35)}`,
          color: C.amber, borderRadius: 8, padding: "7px 16px",
          cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
        }}>
          {adding ? "CANCEL" : `+ ${addLabel}`}
        </button>
      </div>

      {adding && (
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${C.border}`, background: h(C.amber, 0.04) }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 12 }}>
            {fields.map(f => (
              <Input key={f.key} label={f.label} multiline={f.multiline}
                value={form[f.key] || ""}
                onChange={v => setForm(p => ({ ...p, [f.key]: v }))}
                placeholder={f.placeholder}
              />
            ))}
          </div>
          <button onClick={add} disabled={saving || !form[primaryField.key]} style={{
            background: h(C.green, 0.15), border: `1px solid ${h(C.green, 0.4)}`,
            color: C.green, borderRadius: 8, padding: "8px 20px",
            cursor: saving || !form[primaryField.key] ? "not-allowed" : "pointer", fontSize: 12,
          }}>
            {saving ? "Adding…" : "Add"}
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
          {[1,2,3].map(i => <Skeleton key={i} height={70} />)}
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: "36px 20px", textAlign: "center", color: C.muted, fontSize: 13 }}>{emptyMsg}</div>
      ) : items.map(item => (
        <div key={item.id} style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}` }}>
          {editId === item.id ? (
            <div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
                {fields.map(f => (
                  <Input key={f.key} label={f.label} multiline={f.multiline}
                    value={editForm[f.key] ?? item[f.key] ?? ""}
                    onChange={v => setEditForm(p => ({ ...p, [f.key]: v }))}
                  />
                ))}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <SaveBtn onClick={() => saveEdit(item.id)} saving={editSaving} saved={editSaved} />
                <button onClick={() => setEditId(null)} style={{
                  background: "transparent", border: `1px solid ${C.border}`,
                  color: C.muted, borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontSize: 12,
                }}>Cancel</button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1 }}>
                {fields.map((f, i) => (
                  <div key={f.key} style={{ marginBottom: i < fields.length - 1 ? 4 : 0 }}>
                    {i === 0
                      ? <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{item[f.key]}</div>
                      : <div style={{ fontSize: 12, color: C.text }}><span style={{ color: C.muted }}>{f.label}: </span>{item[f.key]}</div>
                    }
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button onClick={() => { setEditId(item.id); setEditForm({}); }} style={{
                  background: "transparent", border: `1px solid ${C.border}`,
                  color: C.muted, borderRadius: 6, padding: "5px 10px", cursor: "pointer", fontSize: 11,
                }}>Edit</button>
                <DeleteBtn onClick={() => remove(item.id)} />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────────────────────
const TABS = [
  { key: "profile",    label: "Company Profile" },
  { key: "products",  label: "Products" },
  { key: "faqs",      label: "FAQs" },
  { key: "objections", label: "Objections" },
];

export default function KnowledgeBasePage() {
  const { apiFetch } = useAuth();
  const [tab, setTab] = useState("profile");

  return (
    <div style={{ flex: 1, overflow: "auto", background: C.bg }}>
      <style>{SHIMMER}</style>

      {/* Header */}
      <div style={{
        background: C.panel, borderBottom: `1px solid ${C.border}`,
        padding: "20px 32px",
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: C.white }}>AI Knowledge Base</div>
        <div style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
          Train your AI receptionist — everything here is used live during calls
        </div>
      </div>

      {/* Info banner */}
      <div style={{ margin: "20px 32px 0", padding: "12px 18px", background: h(C.cyan, 0.05), border: `1px solid ${h(C.cyan, 0.2)}`, borderRadius: 10 }}>
        <div style={{ fontSize: 12, color: C.cyan }}>
          💡 Changes take effect on the next call. Your AI uses this to answer questions, quote pricing, overcome objections, and book appointments.
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: "20px 32px 0", display: "flex", gap: 4, borderBottom: `1px solid ${C.border}`, marginTop: 4 }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            background: tab === t.key ? h(C.amber, 0.1) : "transparent",
            border: tab === t.key ? `1px solid ${h(C.amber, 0.35)}` : "1px solid transparent",
            borderBottomColor: "transparent",
            color: tab === t.key ? C.amber : C.muted,
            borderRadius: "8px 8px 0 0", padding: "9px 20px",
            cursor: "pointer", fontSize: 13, fontWeight: tab === t.key ? 600 : 400,
            transition: "all .13s",
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ margin: "0 32px 32px", background: C.panel, border: `1px solid ${C.border}`, borderTop: "none", borderRadius: "0 0 14px 14px", overflow: "hidden" }}>
        {tab === "profile" && <ProfileTab apiFetch={apiFetch} />}
        {tab === "products" && <ProductsTab apiFetch={apiFetch} />}
        {tab === "faqs" && (
          <ListTab
            apiFetch={apiFetch}
            endpoint="faqs" itemKey="faqs"
            title="Frequently Asked Questions"
            subtitle="Your AI answers these during every call"
            emptyMsg="No FAQs yet. Add common questions about pricing, process, warranties, and rebates."
            addLabel="ADD FAQ"
            fields={[
              { key: "question", label: "Question *", placeholder: "e.g. How much does solar cost?" },
              { key: "answer",   label: "Answer *",   multiline: true, placeholder: "After the federal rebate, a 6.6kW system typically costs…" },
              { key: "category", label: "Category",   placeholder: "pricing / process / technical / rebates" },
            ]}
          />
        )}
        {tab === "objections" && (
          <ListTab
            apiFetch={apiFetch}
            endpoint="objections" itemKey="objections"
            title="Objection Handlers"
            subtitle="How your AI responds when customers push back"
            emptyMsg="No objection handlers yet. Add responses to common objections like price, timing, and competition."
            addLabel="ADD OBJECTION"
            fields={[
              { key: "objection", label: "Customer says... *",  placeholder: "e.g. I need to think about it" },
              { key: "response",  label: "AI responds with... *", multiline: true, placeholder: "Completely understand — it's a significant decision. Would it help if I…" },
            ]}
          />
        )}
      </div>
    </div>
  );
}
