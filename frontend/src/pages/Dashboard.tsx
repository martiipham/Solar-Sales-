/**
 * SolarAdmin Dashboard — /dashboard
 *
 * Real-time overview of the AI receptionist system:
 *   - KPI grid: calls, leads, emails, approvals, proposals, CRM stats
 *   - Voice status card: Retell AI + ElevenLabs + agent readiness
 *   - Agent status card: per-agent enabled state and last run time
 *
 * Data sources:
 *   GET /api/dashboard/summary
 *   GET /api/voice/status
 *   GET /api/agents/config
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface DashboardSummary {
  calls_today: number;
  emails_today: number;
  leads_today: number;
  hot_leads: number;
  proposals_sent: number;
  crm_last_sync: string | null;
  contacts_total: number;
  calls_this_week: number;
  pending_approvals: number;
}

interface VoiceStatus {
  status: 'live' | 'needs_setup' | 'offline';
  retell: boolean;
  elevenlabs: boolean;
  agent_ready: boolean;
}

interface AgentSchedule {
  last_run: string;
  running: boolean;
}

interface AgentsConfig {
  agents: Record<string, boolean>;
  schedule: Record<string, AgentSchedule>;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 900,
    margin: '40px auto',
    padding: '0 24px 60px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },
  header: {
    marginBottom: 32,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: '#f0f0f5',
    margin: '0 0 6px',
  },
  subtitle: {
    fontSize: 14,
    color: '#6b7280',
    margin: 0,
  },
  card: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 10,
    padding: 28,
    marginBottom: 20,
  },
  kpiGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 12,
    marginBottom: 20,
  },
  kpiCard: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '16px 20px',
  },
  kpiValue: {
    fontSize: 28,
    fontWeight: 700,
    color: '#f0f0f5',
    margin: '0 0 4px',
  },
  kpiLabel: {
    fontSize: 12,
    color: '#6b7280',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: '#f0f0f5',
    margin: '0 0 16px',
  },
  agentRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 0',
    borderBottom: '1px solid #12121c',
  },
  loadingWrap: {
    textAlign: 'center' as const,
    padding: '80px 0',
    color: '#6b7280',
    fontSize: 14,
  },
  errorBanner: {
    backgroundColor: '#1f1010',
    border: '1px solid #7f1d1d',
    borderRadius: 6,
    padding: '10px 14px',
    fontSize: 13,
    color: '#f87171',
    marginBottom: 20,
  },
};

// ── Inline components ─────────────────────────────────────────────────────────

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={s.kpiCard}>
      <div style={s.kpiValue}>{value}</div>
      <div style={s.kpiLabel}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: '#4b5563', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function StatusDot({ color }: { color: string }) {
  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        display: 'inline-block',
        marginRight: 6,
        backgroundColor: color,
        flexShrink: 0,
      }}
    />
  );
}

function CheckRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #12121c' }}>
      <StatusDot color={ok ? '#34d399' : '#f87171'} />
      <span style={{ fontSize: 13, color: '#d1d5db', flex: 1 }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 600, color: ok ? '#34d399' : '#f87171' }}>
        {ok ? '✓' : '✗'}
      </span>
    </div>
  );
}

function Badge({ enabled }: { enabled: boolean }) {
  return (
    <span
      style={{
        padding: '3px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        backgroundColor: enabled ? '#4f46e5' : '#1e1e2e',
        color: enabled ? '#fff' : '#6b7280',
      }}
    >
      {enabled ? 'ENABLED' : 'DISABLED'}
    </span>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatLastSync(iso: string | null): string {
  if (!iso) return 'Never';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'Never';
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatLastRun(iso: string | undefined): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return undefined;
  return `Last run: ${d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

function voiceStatusColor(status: VoiceStatus['status']): string {
  if (status === 'live') return '#34d399';
  if (status === 'needs_setup') return '#f59e0b';
  return '#f87171';
}

function voiceStatusLabel(status: VoiceStatus['status']): string {
  if (status === 'live') return 'Live';
  if (status === 'needs_setup') return 'Needs Setup';
  return 'Offline';
}

function formatAgentName(id: string): string {
  return id
    .replace(/_/g, ' ')
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [voice, setVoice] = useState<VoiceStatus | null>(null);
  const [agents, setAgents] = useState<AgentsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      apiJSON<DashboardSummary>('/api/dashboard/summary'),
      apiJSON<VoiceStatus>('/api/voice/status'),
      apiJSON<AgentsConfig>('/api/agents/config'),
    ])
      .then(([summaryData, voiceData, agentsData]) => {
        setSummary(summaryData);
        setVoice(voiceData);
        setAgents(agentsData);
      })
      .catch((err: unknown) => {
        setError(String((err as Error).message ?? err));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={s.page}>
        <div style={s.loadingWrap}>Loading dashboard...</div>
      </div>
    );
  }

  const agentEntries = agents ? Object.entries(agents.agents) : [];

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <h1 style={s.title}>Dashboard</h1>
        <p style={s.subtitle}>Real-time overview of your AI receptionist</p>
      </div>

      {/* Error banner */}
      {error && <div style={s.errorBanner}>{error}</div>}

      {/* KPI Grid — 9 cards */}
      <div style={s.kpiGrid}>
        <KpiCard label="Calls Today" value={summary?.calls_today ?? 0} />
        <KpiCard label="Leads Today" value={summary?.leads_today ?? 0} />
        <KpiCard label="Hot Leads" value={summary?.hot_leads ?? 0} />
        <KpiCard label="Emails Today" value={summary?.emails_today ?? 0} />
        <KpiCard
          label="Pending Approvals"
          value={summary?.pending_approvals ?? 0}
        />
        <KpiCard label="Calls This Week" value={summary?.calls_this_week ?? 0} />
        <KpiCard label="Proposals Sent" value={summary?.proposals_sent ?? 0} />
        <KpiCard label="CRM Contacts" value={summary?.contacts_total ?? 0} />
        <KpiCard
          label="CRM Last Sync"
          value={formatLastSync(summary?.crm_last_sync ?? null)}
        />
      </div>

      {/* Voice Status */}
      <div style={s.card}>
        <p style={s.sectionTitle}>Voice Status</p>

        {/* Status badge */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <StatusDot color={voice ? voiceStatusColor(voice.status) : '#4b5563'} />
          <span
            style={{
              padding: '3px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              backgroundColor: voice ? `${voiceStatusColor(voice.status)}22` : '#1e1e2e',
              color: voice ? voiceStatusColor(voice.status) : '#6b7280',
            }}
          >
            {voice ? voiceStatusLabel(voice.status).toUpperCase() : 'UNKNOWN'}
          </span>
        </div>

        {/* Service checks */}
        <CheckRow label="Retell AI" ok={voice?.retell ?? false} />
        <CheckRow label="ElevenLabs" ok={voice?.elevenlabs ?? false} />
        <div style={{ display: 'flex', alignItems: 'center', padding: '8px 0' }}>
          <StatusDot color={(voice?.agent_ready ?? false) ? '#34d399' : '#f87171'} />
          <span style={{ fontSize: 13, color: '#d1d5db', flex: 1 }}>Agent Ready</span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: (voice?.agent_ready ?? false) ? '#34d399' : '#f87171',
            }}
          >
            {(voice?.agent_ready ?? false) ? '✓' : '✗'}
          </span>
        </div>
      </div>

      {/* Agent Status */}
      <div style={s.card}>
        <p style={s.sectionTitle}>Active Agents</p>

        {agentEntries.length === 0 ? (
          <p style={{ fontSize: 13, color: '#4b5563', margin: 0 }}>No agents configured.</p>
        ) : (
          agentEntries.map(([agentId, enabled], idx) => {
            const schedule = agents?.schedule?.[agentId];
            const lastRunLabel = formatLastRun(schedule?.last_run);
            const isLast = idx === agentEntries.length - 1;

            return (
              <div
                key={agentId}
                style={{
                  ...s.agentRow,
                  ...(isLast ? { borderBottom: 'none' } : {}),
                }}
              >
                <div>
                  <div style={{ fontSize: 13, color: '#d1d5db', fontWeight: 500 }}>
                    {formatAgentName(agentId)}
                  </div>
                  {lastRunLabel && (
                    <div style={{ fontSize: 11, color: '#4b5563', marginTop: 2 }}>
                      {lastRunLabel}
                      {schedule?.running && (
                        <span style={{ marginLeft: 6, color: '#34d399' }}>running</span>
                      )}
                    </div>
                  )}
                </div>
                <Badge enabled={enabled} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
