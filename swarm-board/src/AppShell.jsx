/**
 * AppShell — top-level router and auth guard.
 *
 * Routing is hash-based (#/board, #/settings, etc.) — no react-router needed.
 * Handles:
 *   - Auth gate: shows LoginScreen until user is authenticated
 *   - Role-based redirect: clients land on /overview, others on /overview
 *   - Two fully self-contained shells based on role:
 *     - AdminDashboard for admin/owner roles
 *     - ClientDashboard for client role
 *   - Fallback to default page for unknown routes
 */
import { useState, useEffect } from "react";
import { useAuth } from "./AuthContext";
import LoginScreen from "./LoginScreen";
import AdminDashboard from "./pages/AdminDashboard";
import ClientDashboard from "./pages/ClientDashboard";

// Pages that require a minimum role
const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const PAGE_MIN_ROLE = {
  overview:         "client",
  calls:            "client",
  "knowledge-base": "client",
  "client-view":    "admin",
  onboarding:       "admin",
  board:            "admin",
  leads:            "admin",
  emails:           "admin",
  agents:           "admin",
  reporting:        "admin",
  docs:             "admin",
  settings:         "admin",
  companies:        "admin",
  users:            "owner",
  apikeys:          "owner",
};

function canAccess(userRole, page) {
  const minRole = PAGE_MIN_ROLE[page] || "admin";
  return (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 0);
}

function getHashPage() {
  const hash = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return hash || "";
}

function LoadingScreen() {
  return (
    <div style={{
      background: "#050810", height: "100vh",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        fontFamily: "'Syne Mono', monospace",
        fontSize: 12, color: "#F59E0B", letterSpacing: 2,
        animation: "blink 1s step-end infinite",
      }}>
        INITIALISING…
      </div>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne+Mono&display=swap');
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
      `}</style>
    </div>
  );
}

export default function AppShell() {
  const { user, loading } = useAuth();

  const [page, setPage] = useState(getHashPage);

  useEffect(() => {
    const onHash = () => setPage(getHashPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!user) return;
    const userRole = user.role;
    if (!page || !canAccess(userRole, page)) {
      const dest = "overview";
      window.location.hash = dest;
      setPage(dest);
    }
  }, [user]); // eslint-disable-line

  const navigate = p => {
    window.location.hash = p;
    setPage(p);
  };

  if (loading) return <LoadingScreen />;
  if (!user)   return <LoginScreen />;

  const role       = user.role;
  const activePage = (page && canAccess(role, page)) ? page : "overview";

  // Clients get their own self-contained portal
  if (role === "client") {
    return <ClientDashboard onNavigate={navigate} />;
  }

  // Admin/Owner — fully self-contained AdminDashboard shell
  return <AdminDashboard currentPage={activePage} onNavigate={navigate} />;
}
