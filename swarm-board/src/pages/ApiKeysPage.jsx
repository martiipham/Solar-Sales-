/**
 * ApiKeysPage — generate and manage API keys for client embeds and webhook auth.
 * Keys are shown once on creation. Stored as SHA-256 hash only.
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

const PERM_INFO = {
  read:    "Read-only access to dashboard metrics and lead data.",
  write:   "Can create and update leads, experiments, and pipeline stages.",
  webhook: "Authorises inbound webhook calls (GHL, voice, email).",
};

export default function ApiKeysPage() {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const [keys, setKeys]             = useState([]);
  const [loading, setLoading]       = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey]         = useState(null); // revealed once after creation
  const [revokeTarget, setRevokeTarget] = useState(null);

  // Create form state
  const [form, setForm] = useState({ name: "", client_id: "", permissions: ["read"] });

  useEffect(() => {
    apiFetch("/api/keys")
      .then(r => r.json())
      .then(d => setKeys(d.keys || []))
      .catch(() => toast.error("Failed to load API keys"))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const togglePerm = perm => {
    setForm(f => ({
      ...f,
      permissions: f.permissions.includes(perm)
        ? f.permissions.filter(p => p !== perm)
        : [...f.permissions, perm],
    }));
  };

  const handleCreate = async e => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error("Key name is required"); return; }
    try {
      const r = await apiFetch("/api/keys", { method: "POST", body: JSON.stringify(form) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
      setNewKey(data.key);
      setKeys(prev => [{ key_id: data.key_id, name: data.name, permissions: JSON.stringify(data.permissions), active: 1, created_at: new Date().toISOString() }, ...prev]);
      setShowCreate(false);
      setForm({ name: "", client_id: "", permissions: ["read"] });
    } catch (e) {
      toast.error(e.message || "Failed to create key");
    }
  };

  const handleRevoke = async () => {
    const target = revokeTarget;
    setRevokeTarget(null);
    try {
      const r = await apiFetch(`/api/keys/${target.key_id}`, { method: "DELETE" });
      if (!r.ok) throw new Error((await r.json()).error);
      setKeys(prev => prev.filter(k => k.key_id !== target.key_id));
      toast.success("API key revoked");
    } catch (e) {
      toast.error(e.message || "Failed to revoke key");
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
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 28 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            MACHINE ACCESS
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 6 }}>
            API Keys{" "}
            <InfoTip
              text="API keys authorise machine-to-machine calls (webhooks, client embeds). Send them in the X-API-Key header."
              position="right"
            />
          </div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {keys.filter(k => k.active).length} active key{keys.filter(k => k.active).length !== 1 ? "s" : ""}
          </div>
        </div>
        <button
          onClick={() => setShowCreate(v => !v)}
          style={{
            background: showCreate ? h(C.amber, 0.2) : h(C.amber, 0.12),
            border: `1px solid ${C.amber}`,
            color: C.amber, padding: "10px 20px", borderRadius: 8,
            cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
          }}
        >
          {showCreate ? "✕ CANCEL" : "+ NEW KEY"}
        </button>
      </div>

      {/* New key reveal banner */}
      {newKey && (
        <div style={{
          background: h(C.green, 0.08),
          border: `1px solid ${C.green}`,
          borderRadius: 12, padding: "18px 20px",
          marginBottom: 24,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: C.green, marginBottom: 8 }}>
                ✓ Key created — copy it now. It will not be shown again.
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <code style={{
                  background: C.card, border: `1px solid ${C.border}`,
                  borderRadius: 6, padding: "8px 14px",
                  fontSize: 13, color: C.cyan, fontFamily: "monospace",
                  wordBreak: "break-all", flex: 1,
                }}>
                  {newKey}
                </code>
                <button
                  onClick={() => { navigator.clipboard.writeText(newKey); toast.success("Copied!"); }}
                  style={{
                    background: h(C.cyan, 0.12), border: `1px solid ${h(C.cyan, 0.3)}`,
                    color: C.cyan, padding: "8px 14px", borderRadius: 6,
                    cursor: "pointer", fontSize: 12, flexShrink: 0,
                  }}
                >
                  COPY
                </button>
              </div>
              <div style={{ fontSize: 12, color: C.muted, marginTop: 8 }}>
                Add to your HTTP headers: <code style={{ color: C.text }}>X-API-Key: {newKey.substring(0, 20)}…</code>
              </div>
            </div>
            <button onClick={() => setNewKey(null)} style={{
              background: "none", border: "none", color: C.muted, cursor: "pointer", fontSize: 16,
            }}>✕</button>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} style={{
          background: C.panel, border: `1px solid ${C.borderB}`,
          borderRadius: 14, padding: 24, marginBottom: 24, maxWidth: 520,
        }}>
          <div className="mono" style={{ fontSize: 11, color: C.amber, letterSpacing: 1.5, marginBottom: 18 }}>
            NEW API KEY
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={lS}>Key Name *</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. GHL Webhook, Perth Solar Dashboard" style={iS} autoFocus />
            </div>
            <div>
              <label style={lS}>
                Client ID <InfoTip text="Optional. Scopes this key to a specific company. Leave blank for platform-wide access." />
              </label>
              <input value={form.client_id} onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
                placeholder="perth-solar-co (optional)" style={iS} />
            </div>
            <div>
              <label style={lS}>Permissions</label>
              <div style={{ display: "flex", gap: 10 }}>
                {Object.entries(PERM_INFO).map(([perm, tip]) => {
                  const active = form.permissions.includes(perm);
                  const col = perm === "read" ? C.cyan : perm === "write" ? C.amber : C.purple;
                  return (
                    <button
                      key={perm}
                      type="button"
                      onClick={() => togglePerm(perm)}
                      title={tip}
                      style={{
                        flex: 1, padding: "7px 0",
                        background: active ? h(col, 0.15) : "transparent",
                        border: `1px solid ${active ? col : C.border}`,
                        color: active ? col : C.muted,
                        borderRadius: 7, cursor: "pointer",
                        fontSize: 11, fontFamily: "'Syne Mono', monospace",
                      }}
                    >
                      {perm.toUpperCase()}
                    </button>
                  );
                })}
              </div>
              <div style={{ fontSize: 11, color: C.muted, marginTop: 6 }}>
                {form.permissions.length > 0 && PERM_INFO[form.permissions[0]]}
              </div>
            </div>
            <div style={{ display: "flex", gap: 10, paddingTop: 4 }}>
              <button type="submit" style={{
                background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
                color: C.amber, padding: "9px 22px", borderRadius: 8,
                cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
              }}>
                GENERATE KEY
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Keys table */}
      {loading ? (
        <div style={{ color: C.muted, fontSize: 13 }}>Loading…</div>
      ) : keys.length === 0 ? (
        <div style={{
          textAlign: "center", padding: "60px 20px",
          background: C.panel, border: `1px dashed ${C.border}`,
          borderRadius: 14, color: C.muted,
        }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>🔑</div>
          <div style={{ fontSize: 14, color: C.text, marginBottom: 6 }}>No API keys yet</div>
          <div style={{ fontSize: 13 }}>Generate a key to authenticate webhook calls and client embeds.</div>
        </div>
      ) : (
        <div style={{
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 14, overflow: "hidden", maxWidth: 800,
        }}>
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 160px 180px 120px 80px",
            padding: "10px 16px", borderBottom: `1px solid ${C.border}`,
            background: C.card,
          }}>
            {["Name", "Key ID", "Permissions", "Created", ""].map((h2, i) => (
              <span key={i} className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{h2}</span>
            ))}
          </div>
          {keys.map(k => {
            const perms = (() => { try { return JSON.parse(k.permissions); } catch { return []; } })();
            const active = !!k.active;
            return (
              <div key={k.key_id} style={{
                display: "grid", gridTemplateColumns: "1fr 160px 180px 120px 80px",
                padding: "13px 16px", borderBottom: `1px solid ${C.border}`,
                alignItems: "center", opacity: active ? 1 : 0.45,
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>{k.name}</div>
                  {k.client_id && <div style={{ fontSize: 11, color: C.muted }}>{k.client_id}</div>}
                  {k.last_used && <div style={{ fontSize: 11, color: C.muted }}>Last used {new Date(k.last_used).toLocaleDateString("en-AU")}</div>}
                </div>
                <div>
                  <code className="mono" style={{ fontSize: 11, color: C.cyan }}>{k.key_id}</code>
                </div>
                <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                  {perms.map(p => {
                    const col = p === "read" ? C.cyan : p === "write" ? C.amber : C.purple;
                    return (
                      <span key={p} style={{
                        fontSize: 9, fontFamily: "'Syne Mono', monospace",
                        background: h(col, 0.12), border: `1px solid ${h(col, 0.3)}`,
                        color: col, borderRadius: 10, padding: "1px 7px",
                      }}>{p}</span>
                    );
                  })}
                </div>
                <div style={{ fontSize: 12, color: C.muted }}>
                  {new Date(k.created_at).toLocaleDateString("en-AU")}
                </div>
                <div>
                  {active && (
                    <button
                      onClick={() => setRevokeTarget(k)}
                      style={{
                        background: h(C.red, 0.08), border: `1px solid ${h(C.red, 0.25)}`,
                        color: C.red, padding: "5px 10px", borderRadius: 5,
                        cursor: "pointer", fontSize: 10,
                      }}
                    >Revoke</button>
                  )}
                  {!active && <span style={{ fontSize: 11, color: C.muted }}>Revoked</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Confirm
        open={!!revokeTarget}
        title={`Revoke "${revokeTarget?.name}"?`}
        message="Any system using this key will immediately lose access. This cannot be undone."
        confirmLabel="REVOKE"
        danger
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </div>
  );
}
