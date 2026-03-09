/**
 * Layout — persistent sidebar navigation + main content area.
 *
 * Role-based nav:
 *   owner  → sees everything
 *   admin  → sees everything except Users & API Keys
 *   client → sees only their Client Dashboard
 *
 * Props:
 *   currentPage  — active page key (string)
 *   onNavigate   — (pageKey) => void
 *   children     — page content
 */
import { useState } from "react";
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

// Nav items — icon, label, page key, min role
const NAV_ITEMS = [
  { icon: "◈",  label: "Overview",       page: "overview",      minRole: "client" },
  { icon: "📞", label: "Calls",          page: "calls",         minRole: "client" },
  { icon: "📚", label: "Knowledge Base", page: "knowledge-base", minRole: "client" },
  { icon: "—",  label: null,             page: null,            minRole: "client" }, // separator
  { icon: "◫",  label: "Board",          page: "board",         minRole: "admin"  },
  { icon: "◎",  label: "Leads",          page: "leads",         minRole: "admin"  },
  { icon: "⚗",  label: "Experiments",   page: "experiments",   minRole: "admin"  },
  { icon: "🤖", label: "Agents",         page: "agents",        minRole: "admin"  },
  { icon: "—",  label: null,             page: null,            minRole: "admin"  }, // separator
  { icon: "🚀", label: "Onboarding",    page: "onboarding",    minRole: "client" },
  { icon: "📄", label: "Docs",           page: "docs",          minRole: "admin"  },
  { icon: "⚙",  label: "Settings",      page: "settings",      minRole: "admin"  },
  { icon: "🏢", label: "Companies",      page: "companies",     minRole: "admin"  },
  { icon: "👥", label: "Users",          page: "users",         minRole: "owner"  },
  { icon: "🔑", label: "API Keys",       page: "apikeys",       minRole: "owner"  },
];

const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const canSee = (userRole, minRole) =>
  (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 0);

function NavItem({ item, active, onClick }) {
  const [hovered, setHovered] = useState(false);
  if (!item.label) {
    return <div style={{ height: 1, background: C.border, margin: "8px 12px" }} />;
  }
  const highlight = active || hovered;
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
      {active && (
        <span style={{
          marginLeft: "auto", width: 5, height: 5, borderRadius: "50%",
          background: C.amber, boxShadow: `0 0 6px ${C.amber}`,
        }} />
      )}
    </button>
  );
}

export default function Layout({ currentPage, onNavigate, children }) {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const role = user?.role || "client";
  const visibleNav = NAV_ITEMS.filter(item =>
    item.label === null || canSee(role, item.minRole)
  );

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
                  SOLAR SWARM
                </div>
                <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, whiteSpace: "nowrap" }}>
                  Agent Platform
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
        <nav style={{ flex: 1, padding: "12px 8px", overflowY: "auto", overflowX: "hidden" }}>
          {collapsed
            ? visibleNav.filter(i => i.label).map(item => (
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
            : visibleNav.map((item, i) => (
              item.label === null
                ? <div key={i} style={{ height: 1, background: C.border, margin: "8px 0" }} />
                : <NavItem
                    key={item.page}
                    item={item}
                    active={currentPage === item.page}
                    onClick={onNavigate}
                  />
            ))
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
              <span style={{
                fontSize: 10, fontFamily: "'Syne Mono', monospace",
                background: h(roleColor, 0.12),
                border: `1px solid ${h(roleColor, 0.3)}`,
                color: roleColor,
                borderRadius: 20, padding: "1px 8px",
              }}>
                {role.toUpperCase()}
              </span>
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
