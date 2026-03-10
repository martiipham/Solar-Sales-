/**
 * Layout — persistent sidebar navigation + main content area.
 *
 * Role-based nav:
 *   owner  → sees everything
 *   admin  → sees everything except Users & API Keys
 *   client → sees only their Client Dashboard
 *
 * Nav sections:
 *   OPERATIONS: Leads, Calls, Emails
 *   SETUP:      Company, Knowledge Base, Settings
 *   ADMIN:      API Keys, Users, Onboarding, Docs
 *
 * Props:
 *   currentPage  — active page key (string)
 *   onNavigate   — (pageKey) => void
 *   children     — page content
 */
import { useState, useEffect } from "react";
import { useAuth } from "./AuthContext";

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
  purple:  "#C084FC",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
  dim:     "#1A2540",
};
const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

// Item types: "link" | "separator" | "section"
const NAV_ITEMS = [
  { type: "link",      icon: "◈",  label: "Dashboard",      page: "overview",       minRole: "client" },
  { type: "section",   label: "OPERATIONS",                                          minRole: "admin"  },
  { type: "link",      icon: "◎",  label: "Leads",           page: "leads",          minRole: "admin"  },
  { type: "link",      icon: "📞", label: "Calls",           page: "calls",          minRole: "client" },
  { type: "link",      icon: "✉️", label: "Emails",          page: "emails",         minRole: "admin"  },
  { type: "section",   label: "SETUP",                                               minRole: "admin"  },
  { type: "link",      icon: "🏢", label: "Company",         page: "companies",      minRole: "admin"  },
  { type: "link",      icon: "📚", label: "Knowledge Base",  page: "knowledge-base", minRole: "client" },
  { type: "link",      icon: "⚙",  label: "Settings",        page: "settings",       minRole: "admin"  },
  { type: "section",   label: "ADMIN",                                               minRole: "owner"  },
  { type: "link",      icon: "🔑", label: "API Keys",        page: "apikeys",        minRole: "owner"  },
  { type: "link",      icon: "👥", label: "Users",           page: "users",          minRole: "owner"  },
  { type: "link",      icon: "👁", label: "Client Preview",  page: "client-view",    minRole: "admin"  },
  { type: "link",      icon: "🚀", label: "Onboarding",      page: "onboarding",     minRole: "admin"  },
  { type: "link",      icon: "📄", label: "Docs",            page: "docs",           minRole: "admin"  },
];

const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const canSee = (userRole, minRole) =>
  (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 0);

function NavItem({ item, active, onClick, badge }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={() => onClick(item.page)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        width: "100%", padding: "9px 14px",
        background: active ? h(C.amber, 0.1) : hovered ? h(C.amber, 0.05) : "transparent",
        border: `1px solid ${active ? h(C.amber, 0.3) : "transparent"}`,
        borderRadius: 8,
        color: active ? C.amber : hovered ? C.text : C.muted,
        cursor: "pointer", fontSize: 13, fontWeight: active ? 600 : 400,
        textAlign: "left", transition: "all .13s",
      }}
    >
      <span style={{ fontSize: 15, width: 20, textAlign: "center", flexShrink: 0 }}>
        {item.icon}
      </span>
      <span>{item.label}</span>
      {badge ? (
        <span style={{
          marginLeft: "auto", minWidth: 18, height: 18,
          background: C.amber, borderRadius: 9,
          fontSize: 10, fontFamily: "'Syne Mono', monospace",
          color: "#050810", display: "flex", alignItems: "center",
          justifyContent: "center", padding: "0 5px",
          boxShadow: `0 0 8px ${h(C.amber, 0.5)}`,
        }}>
          {badge > 99 ? "99+" : badge}
        </span>
      ) : active ? (
        <span style={{
          marginLeft: "auto", width: 5, height: 5, borderRadius: "50%",
          background: C.amber, boxShadow: `0 0 6px ${C.amber}`,
        }} />
      ) : null}
    </button>
  );
}

function SectionLabel({ label }) {
  return (
    <div style={{
      padding: "14px 14px 4px",
      fontSize: 9,
      fontFamily: "'Syne Mono', monospace",
      letterSpacing: 2,
      color: C.muted,
    }}>
      {label}
    </div>
  );
}

export default function Layout({ currentPage, onNavigate, children }) {
  const { user, logout, apiFetch } = useAuth();
  const [collapsed, setCollapsed]   = useState(false);
  const [emailBadge, setEmailBadge] = useState(0);
  const isPreviewingClient = currentPage === "client-view";

  useEffect(() => {
    if (!user || (user.role === "client")) return;
    const fetchBadge = () => {
      apiFetch("/api/emails/stats")
        .then(r => r.json())
        .then(d => setEmailBadge(d.pending || 0))
        .catch(() => {});
    };
    fetchBadge();
    const timer = setInterval(fetchBadge, 60000); // refresh every 60s
    return () => clearInterval(timer);
  }, [user]); // eslint-disable-line

  const role = user?.role || "client";
  const visibleNav = NAV_ITEMS.filter(item => canSee(role, item.minRole || "client"));

  const roleColors = { owner: C.amber, admin: C.cyan, client: C.green };
  const roleColor = roleColors[role] || C.muted;

  return (
    <div style={{ display: "flex", height: "100vh", background: C.bg, overflow: "hidden" }}>

      {/* Sidebar */}
      <aside style={{
        width: collapsed ? 56 : 220,
        flexShrink: 0,
        background: C.panel,
        borderRight: `1px solid ${C.border}`,
        display: "flex", flexDirection: "column",
        transition: "width .2s ease",
        overflow: "hidden",
      }}>
        {/* Logo */}
        <div style={{
          padding: collapsed ? "18px 0" : "20px 18px",
          borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center",
          justifyContent: collapsed ? "center" : "space-between",
          gap: 10, flexShrink: 0,
        }}>
          {!collapsed && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>☀️</span>
              <div style={{ minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 12, color: C.amber, letterSpacing: 2, whiteSpace: "nowrap" }}>
                  SOLAR ADMIN
                </div>
                <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, whiteSpace: "nowrap" }}>
                  AI Platform
                </div>
              </div>
            </div>
          )}
          {collapsed && <span style={{ fontSize: 20 }}>☀️</span>}
          <button
            onClick={() => setCollapsed(v => !v)}
            style={{
              background: "transparent", border: `1px solid ${C.border}`,
              color: C.muted, borderRadius: 6, padding: "3px 6px",
              cursor: "pointer", fontSize: 11, flexShrink: 0,
            }}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, padding: "8px 8px", overflowY: "auto", overflowX: "hidden" }}>
          {collapsed
            ? visibleNav.filter(i => i.type === "link").map(item => (
              <button
                key={item.page}
                onClick={() => onNavigate(item.page)}
                title={item.label}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  width: "100%", padding: "10px 0",
                  background: currentPage === item.page ? h(C.amber, 0.1) : "transparent",
                  border: "none", borderRadius: 8,
                  color: currentPage === item.page ? C.amber : C.muted,
                  cursor: "pointer", fontSize: 16,
                  transition: "all .13s",
                }}
              >
                {item.icon}
              </button>
            ))
            : visibleNav.map((item, i) => {
              if (item.type === "section") {
                return <SectionLabel key={`s-${i}`} label={item.label} />;
              }
              return (
                <NavItem
                  key={item.page}
                  item={item}
                  active={currentPage === item.page}
                  onClick={onNavigate}
                  badge={item.page === "emails" && emailBadge > 0 ? emailBadge : null}
                />
              );
            })
          }
        </nav>

        {/* User profile + logout */}
        {!collapsed && (
          <div style={{
            padding: "14px 14px",
            borderTop: `1px solid ${C.border}`,
            flexShrink: 0,
          }}>
            <div style={{
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 10, padding: "10px 12px",
              marginBottom: 8,
            }}>
              <div style={{ fontSize: 13, color: C.white, fontWeight: 600, marginBottom: 2 }}>
                {user?.name || "Unknown"}
              </div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 5 }}>
                {user?.email}
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 2 }}>
                <span style={{
                  fontSize: 10, fontFamily: "'Syne Mono', monospace",
                  background: h(roleColor, 0.12),
                  border: `1px solid ${h(roleColor, 0.3)}`,
                  color: roleColor,
                  borderRadius: 20, padding: "1px 8px",
                }}>
                  {role.toUpperCase()}
                </span>
                {canSee(role, "admin") && (
                  <button
                    onClick={() => onNavigate(isPreviewingClient ? "overview" : "client-view")}
                    title={isPreviewingClient ? "Exit client preview" : "Preview as client"}
                    style={{
                      fontSize: 10, fontFamily: "'Syne Mono', monospace",
                      background: isPreviewingClient ? h(C.cyan, 0.15) : "transparent",
                      border: `1px solid ${isPreviewingClient ? h(C.cyan, 0.4) : h(C.muted, 0.3)}`,
                      color: isPreviewingClient ? C.cyan : C.muted,
                      borderRadius: 20, padding: "1px 8px",
                      cursor: "pointer", transition: "all .15s",
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = C.cyan; e.currentTarget.style.color = C.cyan; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = isPreviewingClient ? h(C.cyan, 0.4) : h(C.muted, 0.3); e.currentTarget.style.color = isPreviewingClient ? C.cyan : C.muted; }}
                  >
                    {isPreviewingClient ? "EXIT PREVIEW" : "CLIENT VIEW"}
                  </button>
                )}
              </div>
            </div>
            <button
              onClick={logout}
              style={{
                width: "100%", background: "transparent",
                border: `1px solid ${C.border}`,
                color: C.muted, padding: "8px 12px",
                borderRadius: 8, cursor: "pointer", fontSize: 12,
                fontFamily: "'Syne Mono', monospace",
                transition: "all .15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = C.red; e.currentTarget.style.color = C.red; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.muted; }}
            >
              SIGN OUT
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {children}
      </main>
    </div>
  );
}
