import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import CRMWizard from './pages/CRMWizard';

// Lazy-load pages that don't exist yet (will be built next)
// Using inline placeholders for now — real pages replace these
const Dashboard = React.lazy(() =>
  import('./pages/Dashboard').catch(() => ({ default: () => <Placeholder name="Dashboard" /> }))
);
const Calls = React.lazy(() =>
  import('./pages/Calls').catch(() => ({ default: () => <Placeholder name="Calls" /> }))
);
const Leads = React.lazy(() =>
  import('./pages/Leads').catch(() => ({ default: () => <Placeholder name="Leads" /> }))
);
const Emails = React.lazy(() =>
  import('./pages/Emails').catch(() => ({ default: () => <Placeholder name="Emails" /> }))
);
const KnowledgeBase = React.lazy(() =>
  import('./pages/KnowledgeBase').catch(() => ({ default: () => <Placeholder name="Knowledge Base" /> }))
);
const Reports = React.lazy(() =>
  import('./pages/Reports').catch(() => ({ default: () => <Placeholder name="Reports" /> }))
);
const Settings = React.lazy(() =>
  import('./pages/Settings').catch(() => ({ default: () => <Placeholder name="Settings" /> }))
);

function Placeholder({ name }: { name: string }) {
  return (
    <div style={{ padding: '40px 32px', color: '#6b7280', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#f0f0f5', marginBottom: 8 }}>{name}</div>
      <div style={{ fontSize: 14 }}>Loading...</div>
    </div>
  );
}

const style: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    minHeight: '100vh',
    backgroundColor: '#0a0a0f',
    color: '#f0f0f5',
  },
  main: {
    flex: 1,
    overflow: 'auto',
  },
};

export default function App() {
  return (
    <div style={style.shell}>
      <Sidebar />
      <main style={style.main}>
        <Suspense fallback={<Placeholder name="Loading..." />}>
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/calls" element={<Calls />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/emails" element={<Emails />} />
            <Route path="/crm-wizard" element={<CRMWizard />} />
            <Route path="/knowledge-base" element={<KnowledgeBase />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}
