/**
 * AppShell — top-level router and auth guard.
 *
 * Routing is hash-based (#/board, #/settings, etc.) — no react-router needed.
 * Handles:
 *   - Auth gate: shows LoginScreen until user is authenticated
 *   - Role-based redirect: clients land on /client, others on /overview
 *   - Layout + page rendering
 *   - Fallback to default page for unknown routes
 */
import { useState, useEffect } from "react";
import { useAuth } from "./AuthContext";
import LoginScreen from "./LoginScreen";
import Layout from "./Layout";
import App from "./App";                                  // Board + Overview (existing)
import SettingsPage from "./pages/SettingsPage";
import CompanyPage from "./pages/CompanyPage";
import UsersPage from "./pages/UsersPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import ClientDashboard from "./pages/ClientDashboard";
import LeadsPage from "./pages/LeadsPage";
import ExperimentsPage from "./pages/ExperimentsPage";

// Pages that require a minimum role
const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const PAGE_MIN_ROLE = {
  board:       "admin",
  overview:    "client",
  leads:       "admin",
  experiments: "admin",
  settings:    "admin",
  companies:   "admin",
  users:       "owner",
  apikeys:     "owner",
  client:      "client",
};

function canAccess(userRole, page) {
  const minRole = PAGE_MIN_ROLE[page] || "admin";
  return (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 0);
}

function defaultPage(role) {
  if (role === "client") return "client";
  return "overview";
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

  // Derive active page from URL hash
  const [page, setPage] = useState(getHashPage);

  // Sync page ↔ hash
  useEffect(() => {
    const onHash = () => setPage(getHashPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Redirect to default page after login or if hash is empty/inaccessible
  useEffect(() => {
    if (!user) return;
    const role = user.role;
    const target = page || defaultPage(role);
    if (!page || !canAccess(role, page)) {
      const dest = canAccess(role, page) ? page : defaultPage(role);
      window.location.hash = dest;
      setPage(dest);
    }
  }, [user]); // eslint-disable-line

  const navigate = p => {
    window.location.hash = p;
    setPage(p);
  };

  // 1. Still validating stored token
  if (loading) return <LoadingScreen />;

  // 2. Not logged in
  if (!user) return <LoginScreen />;

  // 3. Authenticated — render page inside Layout
  const role = user.role;
  const activePage = (page && canAccess(role, page)) ? page : defaultPage(role);

  const renderPage = () => {
    switch (activePage) {
      case "board":
      case "overview":
        return <App initialView={activePage === "board" ? "board" : "overview"} />;
      case "leads":
        return <LeadsPage />;
      case "experiments":
        return <ExperimentsPage />;
      case "settings":
        return <SettingsPage />;
      case "companies":
        return <CompanyPage />;
      case "users":
        return <UsersPage />;
      case "apikeys":
        return <ApiKeysPage />;
      case "client":
        return <ClientDashboard />;
      default:
        return <App initialView="overview" />;
    }
  };

  return (
    <Layout currentPage={activePage} onNavigate={navigate}>
      {renderPage()}
    </Layout>
  );
}
