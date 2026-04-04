/**
 * Calls — /calls
 *
 * Lists all inbound voice calls with stats summary, expandable transcripts,
 * and paginated load-more. Talks to /api/calls and /api/calls/stats.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TranscriptEntry {
  role: string;
  content: string;
}

interface Call {
  call_id: string;
  from_phone: string;
  status: 'completed' | 'failed' | 'in_progress' | string;
  duration_seconds: number;
  duration_fmt: string;
  lead_score: number;
  started_at: string;
  transcript: TranscriptEntry[];
}

interface CallStats {
  today: {
    calls: number;
  };
  this_week: {
    calls: number;
    completed: number;
    avg_duration: string;
    avg_score: number;
    booking_rate: number;
  };
  this_month: {
    calls: number;
    completed: number;
  };
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 900,
    margin: '40px auto',
    padding: '0 24px 60px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
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
    margin: '0 0 24px',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 12,
    marginBottom: 20,
  },
  statCard: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '16px 20px',
    textAlign: 'center' as const,
  },
  statValue: {
    fontSize: 24,
    fontWeight: 700,
    color: '#f0f0f5',
    margin: '0 0 4px',
  },
  statLabel: {
    fontSize: 11,
    color: '#6b7280',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  },
  card: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 10,
    padding: 28,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
  },
  th: {
    textAlign: 'left' as const,
    padding: '8px 12px',
    fontSize: 12,
    fontWeight: 600,
    color: '#6b7280',
    borderBottom: '1px solid #1e1e2e',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  },
  td: {
    padding: '10px 12px',
    fontSize: 13,
    color: '#d1d5db',
    borderBottom: '1px solid #12121c',
    cursor: 'pointer',
  },
  transcriptBox: {
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '16px 20px',
    margin: '4px 0 12px',
  },
  transcriptEntry: {
    marginBottom: 12,
  },
  transcriptRole: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    marginBottom: 3,
  },
  transcriptContent: {
    fontSize: 13,
    color: '#d1d5db',
    lineHeight: 1.6,
  },
};

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  completed: '#34d399',
  failed: '#f87171',
  in_progress: '#f59e0b',
};

function statusColor(status: string): string {
  return STATUS_COLORS[status] ?? '#6b7280';
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-AU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Calls() {
  const [calls, setCalls] = useState<Call[]>([]);
  const [stats, setStats] = useState<CallStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      apiJSON<{ calls: Call[]; total: number }>('/api/calls?limit=20&offset=0'),
      apiJSON<CallStats>('/api/calls/stats'),
    ])
      .then(([callsData, statsData]) => {
        setCalls(callsData.calls);
        setTotal(callsData.total);
        setStats(statsData);
      })
      .catch((err: unknown) => setError(String((err as Error).message ?? err)))
      .finally(() => setLoading(false));
  }, []);

  async function loadMore() {
    const nextOffset = offset + 20;
    try {
      const data = await apiJSON<{ calls: Call[]; total: number }>(
        `/api/calls?limit=20&offset=${nextOffset}`,
      );
      setCalls((prev) => [...prev, ...data.calls]);
      setTotal(data.total);
      setOffset(nextOffset);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    }
  }

  function toggleExpand(id: string) {
    setExpandedCallId((prev) => (prev === id ? null : id));
  }

  if (loading) {
    return (
      <div style={s.page}>
        <p style={{ color: '#6b7280', fontSize: 13 }}>Loading calls…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={s.page}>
        <div
          style={{
            backgroundColor: '#1f1010',
            border: '1px solid #7f1d1d',
            borderRadius: 6,
            padding: '10px 14px',
            fontSize: 13,
            color: '#f87171',
          }}
        >
          {error}
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <h1 style={s.title}>Calls</h1>
      <p style={s.subtitle}>{total} call{total !== 1 ? 's' : ''} total</p>

      {/* Stats grid */}
      <div style={s.statsGrid}>
        <div style={s.statCard}>
          <p style={s.statValue}>{stats?.today.calls ?? 0}</p>
          <p style={s.statLabel}>Today's Calls</p>
        </div>
        <div style={s.statCard}>
          <p style={s.statValue}>{stats?.this_week.calls ?? 0}</p>
          <p style={s.statLabel}>This Week</p>
        </div>
        <div style={s.statCard}>
          <p style={s.statValue}>{stats?.this_week.avg_duration ?? '0:00'}</p>
          <p style={s.statLabel}>Avg Duration</p>
        </div>
        <div style={s.statCard}>
          <p style={s.statValue}>{stats?.this_week.booking_rate ?? 0}%</p>
          <p style={s.statLabel}>Booking Rate</p>
        </div>
      </div>

      {/* Calls table */}
      <div style={s.card}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>From</th>
              <th style={s.th}>Duration</th>
              <th style={s.th}>Score</th>
              <th style={s.th}>Status</th>
              <th style={s.th}>Date</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 && (
              <tr>
                <td colSpan={5} style={{ ...s.td, color: '#4b5563', textAlign: 'center', padding: '24px 12px' }}>
                  No calls yet
                </td>
              </tr>
            )}
            {calls.map((call) => (
              <React.Fragment key={call.call_id}>
                {/* Main row */}
                <tr onClick={() => toggleExpand(call.call_id)}>
                  <td style={s.td}>{call.from_phone}</td>
                  <td style={s.td}>{call.duration_fmt}</td>
                  <td style={s.td}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 24,
                        height: 24,
                        lineHeight: '24px',
                        textAlign: 'center',
                        borderRadius: 4,
                        fontSize: 12,
                        fontWeight: 700,
                        backgroundColor:
                          call.lead_score >= 7
                            ? '#052e1a'
                            : call.lead_score >= 4
                            ? '#1c1a05'
                            : '#1f1010',
                        color:
                          call.lead_score >= 7
                            ? '#34d399'
                            : call.lead_score >= 4
                            ? '#f59e0b'
                            : '#f87171',
                      }}
                    >
                      {call.lead_score}
                    </span>
                  </td>
                  <td style={s.td}>
                    <span style={{ color: statusColor(call.status), fontWeight: 500 }}>
                      {call.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ ...s.td, color: '#6b7280' }}>{formatDate(call.started_at)}</td>
                </tr>

                {/* Expanded transcript row */}
                {expandedCallId === call.call_id && (
                  <tr>
                    <td
                      colSpan={5}
                      style={{ padding: '0 12px 4px', borderBottom: '1px solid #12121c' }}
                    >
                      <div style={s.transcriptBox}>
                        {call.transcript.length === 0 ? (
                          <p style={{ fontSize: 13, color: '#4b5563', margin: 0 }}>
                            No transcript available
                          </p>
                        ) : (
                          call.transcript.map((entry, idx) => (
                            <div key={idx} style={s.transcriptEntry}>
                              <div
                                style={{
                                  ...s.transcriptRole,
                                  color: entry.role === 'agent' ? '#a5b4fc' : '#34d399',
                                }}
                              >
                                {entry.role}
                              </div>
                              <div style={s.transcriptContent}>{entry.content}</div>
                            </div>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>

        {/* Load more */}
        {calls.length < total && (
          <div style={{ textAlign: 'center', marginTop: 20 }}>
            <button
              onClick={loadMore}
              style={{
                padding: '9px 20px',
                backgroundColor: 'transparent',
                color: '#9ca3af',
                border: '1px solid #1e1e2e',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Load more
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
