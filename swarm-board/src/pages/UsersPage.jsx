/**
 * UsersPage — manage platform users: create, edit role, disable, reset password.
 * Owner-only for role changes and account creation.
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
  orange:  "#FB923C",
  purple:  "#C084FC",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

const ROLE_COLOR = { owner: C.amber, admin: C.cyan, client: C.green };
const ROLE_TIP = {
  owner: "Full access — manage users, settings, companies, and all swarm operations.",
  admin: "Manage leads, experiments, CRM, and settings. Cannot manage users.",
  client: "Read-only access to their own company dashboard only.",
};

function UserModal({ user, onSave, onClose, isOwner }) {
  const { apiFetch } = useAuth();
  const { toast } = useToast();
  const isNew = !user?.id;
  const [form, setForm] = useState({
    name:      user?.name      || "",
    email:     user?.email     || "",
    role:      user?.role      || "admin",
    client_id: user?.client_id || "",
    password:  "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async e => {
    e.preventDefault();
    if (!form.name || !form.email) { toast.error("Name and email required"); return; }
    if (isNew && !form.password) { toast.error("Password required for new users"); return; }
    setSaving(true);
    try {
      let r;
      if (isNew) {
        r = await apiFetch("/api/users", { method: "POST", body: JSON.stringify(form) });
      } else {
        const updates = { name: form.name, role: form.role, client_id: form.client_id };
        if (form.password) updates.password = form.password;
        r = await apiFetch(`/api/users/${user.id}`, { method: "PATCH", body: JSON.stringify(updates) });
      }
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
      toast.success(isNew ? "User created" : "User updated");
      onSave(data.user);
    } catch (e) {
      toast.error(e.message || "Failed to save user");
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
        background: C.panel, border: `1px solid ${C.borderB}`, borderRadius: 16,
        padding: 28, width: "90vw", maxWidth: 480, maxHeight: "92vh", overflowY: "auto",
        boxShadow: "0 24px 80px rgba(0,0,0,.7)", animation: "fadeUp .2s ease",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 22 }}>
          <span className="mono" style={{ fontSize: 12, color: C.amber, letterSpacing: 2 }}>
            {isNew ? "INVITE USER" : "EDIT USER"}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", fontSize: 18 }}>✕</button>
        </div>

        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label style={lS}>Full Name *</label>
              <input value={form.name} onChange={e => set("name", e.target.value)} placeholder="Jane Smith" style={iS} />
            </div>
            <div>
              <label style={lS}>Email *</label>
              <input type="email" value={form.email} onChange={e => set("email", e.target.value)}
                placeholder="jane@company.com" disabled={!isNew} style={{ ...iS, opacity: isNew ? 1 : 0.6 }} />
            </div>
          </div>

          <div>
            <label style={{ ...lS }}>
              Role{" "}
              <InfoTip text={ROLE_TIP[form.role]} />
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              {["owner", "admin", "client"].map(role => {
                const active = form.role === role;
                const col = ROLE_COLOR[role];
                const disabled = !isOwner && role === "owner";
                return (
                  <button
                    key={role}
                    type="button"
                    disabled={disabled}
                    onClick={() => set("role", role)}
                    style={{
                      flex: 1, padding: "8px 0",
                      background: active ? h(col, 0.15) : "transparent",
                      border: `1px solid ${active ? col : C.border}`,
                      color: active ? col : C.muted,
                      borderRadius: 8, cursor: disabled ? "not-allowed" : "pointer",
                      fontSize: 11, fontFamily: "'Syne Mono', monospace",
                      opacity: disabled ? 0.4 : 1,
                    }}
                  >
                    {role.toUpperCase()}
                  </button>
                );
              })}
            </div>
          </div>

          {form.role === "client" && (
            <div>
              <label style={lS}>
                Client ID <InfoTip text="Links this user to a company profile. They will only see that company's dashboard." />
              </label>
              <input value={form.client_id} onChange={e => set("client_id", e.target.value)}
                placeholder="perth-solar-co" style={iS} />
            </div>
          )}

          <div>
            <label style={lS}>
              {isNew ? "Password *" : "New Password"}{" "}
              {!isNew && <InfoTip text="Leave blank to keep current password." />}
            </label>
            <input type="password" value={form.password} onChange={e => set("password", e.target.value)}
              placeholder={isNew ? "Min 8 characters" : "Leave blank to keep current"} style={iS} />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, paddingTop: 8, borderTop: `1px solid ${C.border}` }}>
            <button type="button" onClick={onClose} style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: C.muted, padding: "9px 18px", borderRadius: 8, cursor: "pointer", fontSize: 12,
            }}>CANCEL</button>
            <button type="submit" disabled={saving} style={{
              background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
              color: C.amber, padding: "9px 22px", borderRadius: 8, cursor: "pointer",
              fontSize: 12, fontFamily: "'Syne Mono', monospace",
            }}>
              {saving ? "SAVING…" : isNew ? "CREATE USER" : "SAVE"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const { apiFetch, user: me } = useAuth();
  const { toast } = useToast();
  const [users, setUsers]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [editTarget, setEditTarget] = useState(null);
  const [showModal, setShowModal]   = useState(false);
  const [disableTarget, setDisableTarget] = useState(null);
  const isOwner = me?.role === "owner";

  useEffect(() => {
    apiFetch("/api/users")
      .then(r => r.json())
      .then(d => setUsers(d.users || []))
      .catch(() => toast.error("Failed to load users"))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const handleSave = u => {
    setUsers(prev => {
      const exists = prev.find(x => x.id === u.id);
      return exists ? prev.map(x => x.id === u.id ? u : x) : [u, ...prev];
    });
    setShowModal(false);
    setEditTarget(null);
  };

  const handleToggleActive = async () => {
    const target = disableTarget;
    setDisableTarget(null);
    try {
      const r = await apiFetch(`/api/users/${target.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !target.active }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error);
      setUsers(prev => prev.map(u => u.id === target.id ? data.user : u));
      toast.success(target.active ? "User disabled" : "User re-enabled");
    } catch (e) {
      toast.error(e.message || "Failed to update user");
    }
  };

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 32px", background: C.bg }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 28 }}>
        <div>
          <div className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 2, marginBottom: 6 }}>
            ACCESS CONTROL
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 6 }}>Users</div>
          <div style={{ fontSize: 13, color: C.muted }}>
            {users.filter(u => u.active).length} active user{users.filter(u => u.active).length !== 1 ? "s" : ""}
          </div>
        </div>
        {isOwner && (
          <button
            onClick={() => { setEditTarget(null); setShowModal(true); }}
            style={{
              background: h(C.amber, 0.15), border: `1px solid ${C.amber}`,
              color: C.amber, padding: "10px 20px", borderRadius: 8,
              cursor: "pointer", fontSize: 12, fontFamily: "'Syne Mono', monospace",
            }}
          >
            + INVITE USER
          </button>
        )}
      </div>

      {/* Role legend */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        {Object.entries(ROLE_TIP).map(([role, tip]) => (
          <div key={role} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{
              fontSize: 10, fontFamily: "'Syne Mono', monospace",
              background: h(ROLE_COLOR[role], 0.12),
              border: `1px solid ${h(ROLE_COLOR[role], 0.3)}`,
              color: ROLE_COLOR[role], borderRadius: 20, padding: "2px 10px",
            }}>{role.toUpperCase()}</span>
            <InfoTip text={tip} />
          </div>
        ))}
      </div>

      {loading ? (
        <div style={{ color: C.muted, fontSize: 13 }}>Loading…</div>
      ) : (
        <div style={{
          background: C.panel, border: `1px solid ${C.border}`,
          borderRadius: 14, overflow: "hidden", maxWidth: 800,
        }}>
          {/* Table header */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 200px 100px 80px 100px",
            padding: "10px 16px", borderBottom: `1px solid ${C.border}`,
            background: C.card,
          }}>
            {["User", "Email", "Role", "Status", "Actions"].map(h2 => (
              <span key={h2} className="mono" style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>{h2}</span>
            ))}
          </div>

          {users.map(u => {
            const roleCol = ROLE_COLOR[u.role] || C.muted;
            const isSelf = u.id === me?.id;
            return (
              <div key={u.id} style={{
                display: "grid", gridTemplateColumns: "1fr 200px 100px 80px 100px",
                padding: "13px 16px", borderBottom: `1px solid ${C.border}`,
                alignItems: "center", opacity: u.active ? 1 : 0.5,
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.white }}>
                    {u.name} {isSelf && <span style={{ fontSize: 10, color: C.muted }}>(you)</span>}
                  </div>
                  {u.last_login && (
                    <div style={{ fontSize: 11, color: C.muted }}>
                      Last login {new Date(u.last_login).toLocaleDateString("en-AU")}
                    </div>
                  )}
                </div>
                <div style={{ fontSize: 12, color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {u.email}
                </div>
                <div>
                  <span style={{
                    fontSize: 10, fontFamily: "'Syne Mono', monospace",
                    background: h(roleCol, 0.12), border: `1px solid ${h(roleCol, 0.3)}`,
                    color: roleCol, borderRadius: 20, padding: "2px 9px",
                  }}>{u.role.toUpperCase()}</span>
                </div>
                <div>
                  <span style={{
                    fontSize: 10, fontFamily: "'Syne Mono', monospace",
                    color: u.active ? C.green : C.muted,
                  }}>
                    {u.active ? "● Active" : "○ Off"}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    onClick={() => { setEditTarget(u); setShowModal(true); }}
                    style={{
                      background: h(C.cyan, 0.1), border: `1px solid ${h(C.cyan, 0.25)}`,
                      color: C.cyan, padding: "4px 10px", borderRadius: 5,
                      cursor: "pointer", fontSize: 10,
                    }}
                  >Edit</button>
                  {isOwner && !isSelf && (
                    <button
                      onClick={() => setDisableTarget(u)}
                      style={{
                        background: u.active ? h(C.red, 0.08) : h(C.green, 0.08),
                        border: `1px solid ${u.active ? h(C.red, 0.25) : h(C.green, 0.25)}`,
                        color: u.active ? C.red : C.green,
                        padding: "4px 8px", borderRadius: 5, cursor: "pointer", fontSize: 10,
                      }}
                    >
                      {u.active ? "Disable" : "Enable"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <UserModal
          user={editTarget}
          isOwner={isOwner}
          onSave={handleSave}
          onClose={() => { setShowModal(false); setEditTarget(null); }}
        />
      )}

      <Confirm
        open={!!disableTarget}
        title={disableTarget?.active ? `Disable ${disableTarget?.name}?` : `Re-enable ${disableTarget?.name}?`}
        message={disableTarget?.active
          ? "They will be signed out immediately and cannot log back in."
          : "They will regain access to the platform."
        }
        confirmLabel={disableTarget?.active ? "DISABLE" : "ENABLE"}
        danger={disableTarget?.active}
        onConfirm={handleToggleActive}
        onCancel={() => setDisableTarget(null)}
      />
    </div>
  );
}
