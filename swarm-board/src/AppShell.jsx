/**
 * AppShell — top-level router and auth guard.
 *
 * Routing is hash-based (#/board, #/settings, etc.) — no react-router needed.
 * Handles:
 *   - Auth gate: shows LoginScreen until user is authenticated
 *   - Role-based redirect: clients land on /overview, others on /overview
 *   - Layout + page rendering
 *   - Fallback to default page for unknown routes
 */
import { useState, useEffect } from "react";
import { useAuth } from "./AuthContext";
import LoginScreen from "./LoginScreen";
import Layout from "./Layout";
import App from "./App";
import SettingsPage from "./pages/SettingsPage";
import CompanyPage from "./pages/CompanyPage";
import UsersPage from "./pages/UsersPage";
import ApiKeysPage from "./pages/ApiKeysPage";
import ClientDashboard from "./pages/ClientDashboard";
import CallsPage from "./pages/CallsPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import OnboardingPage from "./pages/OnboardingPage";
import DocsPage from "./pages/DocsPage";
import LeadsPage from "./pages/LeadsPage";
import AgentsPage from "./pages/AgentsPage";

// Pages that require a minimum role
const ROLE_RANK = { client: 0, admin: 1, owner: 2 };
const PAGE_MIN_ROLE = {
  overview:        "client",
  calls:           "client",
  "knowledge-base": "client",
  onboarding:      "client",
  board:           "admin",
  leads:           "admin",
  agents:          "admin",
  docs:            "admin",
  settings:        "admin",
  companies:       "admin",
  users:           "owner",
  apikeys:         "owner",
};

function canAccess(userRole, page) {
  const minRole = PAGE_MIN_ROLE[page] || "admin";
  return (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[minRole] ?? 0);
}

function defaultPage(role) {
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

  const [page, setPage] = useState(getHashPage);

  useEffect(() => {
    const onHash = () => setPage(getHashPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!user) return;
    const role = user.role;
    if (!page || !canAccess(role, page)) {
      const dest = defaultPage(role);
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
  const activePage = (page && canAccess(role, page)) ? page : defaultPage(role);

  const renderPage = () => {
    switch (activePage) {
      case "overview":
        // Clients see the AI-focused dashboard; admins/owners see the swarm overview
        return role === "client"
          ? <ClientDashboard onNavigate={navigate} />
          : <App initialView="overview" />;
      case "board":
        return <App initialView="board" />;
      case "calls":
        return <CallsPage />;
      case "knowledge-base":
        return <KnowledgeBasePage />;
      case "onboarding":
        return <OnboardingPage onNavigate={navigate} />;
      case "settings":
        return <SettingsPage />;
      case "companies":
        return <CompanyPage />;
      case "users":
        return <UsersPage />;
      case "apikeys":
        return <ApiKeysPage />;
      case "leads":
        return <LeadsPage />;
      case "agents":
        return <AgentsPage />;
      case "docs":
        return <DocsPage />;
      default:
        return role === "client"
          ? <ClientDashboard onNavigate={navigate} />
          : <App initialView="overview" />;
    }
  };

  return (
    <Layout currentPage={activePage} onNavigate={navigate}>
      {renderPage()}
    </Layout>
  );
}
