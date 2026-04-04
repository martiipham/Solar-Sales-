/**
 * Reports — /reports
 *
 * Three sections:
 *   1. All-Time Summary   — lifetime call and lead stats
 *   2. Monthly Report     — current vs prior month with deltas
 *   3. 30-Day Trend       — bar chart + totals row
 *
 * Talks exclusively to /api/reports/* via the shared api-client.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface SummaryReport {
  total_calls: number;
  total_leads: number;
  total_converted: number;
  avg_lead_score: number;
  conversion_rate: number;
  active_since: string | null;
}

interface CallPeriod {
  calls: number;
  completed: number;
  avg_duration: string;
  avg_score: number;
}

interface LeadPeriod {
  total: number;
  hot: number;
  converted: number;
  conversion_rate: number;
  avg_score: number;
}

interface MonthlyReport {
  period: {
    label: string;
    start: string;
    end: string;
  };
  calls: {
    current: CallPeriod;
    prior: CallPeriod;
    vs_prior: string;
  };
  leads: {
    current: LeadPeriod;
    prior: LeadPeriod;
    vs_prior: string;
  };
  highlights?: string[];
}

interface DayRecord {
  date: string;
  calls: number;
  leads: number;
  hot_leads: number;
  conversions: number;
}

interface WeeklyReport {
  window_days: number;
  days: DayRecord[];
  totals: {
    calls: number;
    leads: number;
    hot_leads: number;
    conversions: number;
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
  card: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 10,
    padding: 28,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: '#f0f0f5',
    margin: '0 0 20px',
  },
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 12,
    marginBottom: 8,
  },
  metricBox: {
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '16px',
    textAlign: 'center' as const,
  },
  metricValue: {
    fontSize: 26,
    fontWeight: 700,
    color: '#f0f0f5',
    margin: '0 0 4px',
  },
  metricLabel: {
    fontSize: 11,
    color: '#6b7280',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  },
  deltaPositive: {
    fontSize: 13,
    fontWeight: 600,
    color: '#34d399',
  },
  deltaNeutral: {
    fontSize: 13,
    fontWeight: 600,
    color: '#6b7280',
  },
  deltaNegative: {
    fontSize: 13,
    fontWeight: 600,
    color: '#f87171',
  },
  splitGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    marginBottom: 16,
  },
  subCard: {
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: 16,
  },
  subTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#9ca3af',
    marginBottom: 12,
  },
  highlightItem: {
    fontSize: 13,
    color: '#d1d5db',
    padding: '6px 0',
    borderBottom: '1px solid #12121c',
  },
  trendSection: {
    marginTop: 8,
  },
  trendBars: {
    display: 'flex',
    gap: 2,
    alignItems: 'flex-end',
    height: 64,
    marginTop: 16,
  },
  trendLabel: {
    fontSize: 10,
    color: '#6b7280',
    marginTop: 4,
    textAlign: 'center' as const,
  },
  totalsRow: {
    display: 'flex',
    gap: 24,
    marginTop: 12,
    paddingTop: 12,
    borderTop: '1px solid #1e1e2e',
  },
  totalItem: {
    fontSize: 13,
    color: '#9ca3af',
  },
  errorBanner: {
    backgroundColor: '#1f1010',
    border: '1px solid #7f1d1d',
    borderRadius: 6,
    padding: '10px 14px',
    fontSize: 13,
    color: '#f87171',
    marginBottom: 16,
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function deltaStyle(delta: string): React.CSSProperties {
  if (delta.startsWith('+')) return s.deltaPositive;
  if (delta.startsWith('-')) return s.deltaNegative;
  return s.deltaNeutral;
}

function formatActiveSince(iso: string | null): string {
  if (!iso) return 'N/A';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'N/A';
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Reports() {
  const [summary, setSummary] = useState<SummaryReport | null>(null);
  const [monthly, setMonthly] = useState<MonthlyReport | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      apiJSON<SummaryReport>('/api/reports/summary'),
      apiJSON<MonthlyReport>('/api/reports/monthly'),
      apiJSON<WeeklyReport>('/api/reports/weekly?days=30'),
    ])
      .then(([s, m, w]) => {
        setSummary(s);
        setMonthly(m);
        setWeekly(w);
      })
      .catch((err: unknown) => setError(String((err as Error).message ?? err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={s.page}>
        <p style={{ color: '#6b7280', fontSize: 13 }}>Loading reports…</p>
      </div>
    );
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <h1 style={s.title}>Reports</h1>
      <p style={s.subtitle}>Performance analytics for your AI receptionist</p>

      {error && <div style={s.errorBanner}>{error}</div>}

      {/* ── All-Time Summary ─────────────────────────────────────────────── */}
      {summary && (
        <div style={s.card}>
          <p style={s.sectionTitle}>All-Time Summary</p>
          <div style={s.metricGrid}>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{summary.total_calls}</p>
              <p style={s.metricLabel}>Total Calls</p>
            </div>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{summary.total_leads}</p>
              <p style={s.metricLabel}>Total Leads</p>
            </div>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{summary.total_converted}</p>
              <p style={s.metricLabel}>Conversions</p>
            </div>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{summary.conversion_rate.toFixed(1)}%</p>
              <p style={s.metricLabel}>Conversion Rate</p>
            </div>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{summary.avg_lead_score.toFixed(1)}</p>
              <p style={s.metricLabel}>Avg Lead Score</p>
            </div>
            <div style={s.metricBox}>
              <p style={s.metricValue}>{formatActiveSince(summary.active_since)}</p>
              <p style={s.metricLabel}>Active Since</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Monthly Report ───────────────────────────────────────────────── */}
      {monthly && (
        <div style={s.card}>
          <p style={s.sectionTitle}>Monthly Report: {monthly.period.label}</p>

          <div style={s.splitGrid}>
            {/* Calls sub-card */}
            <div style={s.subCard}>
              <p style={s.subTitle}>
                Calls{' '}
                <span style={deltaStyle(monthly.calls.vs_prior)}>{monthly.calls.vs_prior}</span>
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>
                      Calls this month
                    </td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.calls.current.calls}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>
                      Completed
                    </td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.calls.current.completed}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>
                      Avg duration
                    </td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.calls.current.avg_duration}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280' }}>Avg score</td>
                    <td style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right' }}>
                      {monthly.calls.current.avg_score.toFixed(1)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Leads sub-card */}
            <div style={s.subCard}>
              <p style={s.subTitle}>
                Leads{' '}
                <span style={deltaStyle(monthly.leads.vs_prior)}>{monthly.leads.vs_prior}</span>
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>Total</td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.leads.current.total}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>Hot</td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.leads.current.hot}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280', paddingBottom: 6 }}>
                      Converted
                    </td>
                    <td
                      style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right', paddingBottom: 6 }}
                    >
                      {monthly.leads.current.converted}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ fontSize: 12, color: '#6b7280' }}>Conversion rate</td>
                    <td style={{ fontSize: 13, color: '#f0f0f5', textAlign: 'right' }}>
                      {monthly.leads.current.conversion_rate.toFixed(1)}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Highlights */}
          {monthly.highlights && monthly.highlights.length > 0 && (
            <div>
              <p style={s.subTitle}>Highlights</p>
              {monthly.highlights.map((item, i) => (
                <div key={i} style={s.highlightItem}>
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── 30-Day Trend ─────────────────────────────────────────────────── */}
      {weekly && (
        <div style={s.card}>
          <p style={s.sectionTitle}>30-Day Trend</p>

          <div style={s.trendSection}>
            <div style={s.trendBars}>
              {(() => {
                const maxCalls = Math.max(...weekly.days.map((d) => d.calls), 1);
                return weekly.days.map((day) => (
                  <div
                    key={day.date}
                    style={{
                      backgroundColor: '#4f46e5',
                      borderRadius: '2px 2px 0 0',
                      flex: 1,
                      minWidth: 3,
                      height: `${(day.calls / maxCalls) * 56 + 8}px`,
                    }}
                    title={`${day.date}: ${day.calls} calls`}
                  />
                ));
              })()}
            </div>
          </div>

          <div style={s.totalsRow}>
            <span style={s.totalItem}>Calls: {weekly.totals.calls}</span>
            <span style={s.totalItem}>Leads: {weekly.totals.leads}</span>
            <span style={s.totalItem}>Hot: {weekly.totals.hot_leads}</span>
            <span style={s.totalItem}>Converted: {weekly.totals.conversions}</span>
          </div>
        </div>
      )}
    </div>
  );
}
