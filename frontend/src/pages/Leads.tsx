/**
 * Leads — /leads
 *
 * Displays all inbound leads with qualification scores, statuses, and
 * inline status updates. Filters by status and free-text search.
 *
 * API:
 *   GET  /api/leads?limit=100
 *   PATCH /api/leads/:lead_id/status  { status }
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Lead {
  id: number;
  name: string;
  phone: string;
  email: string;
  suburb: string;
  state: string;
  qualification_score: number;
  score_reason: string;
  recommended_action: string;
  status: 'new' | 'contacted' | 'called' | 'converted' | 'nurture' | 'closed';
  created_at: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const LEAD_STATUSES = ['new', 'contacted', 'called', 'converted', 'nurture', 'closed'] as const;

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  new:       { bg: '#312e81', text: '#a5b4fc' },
  contacted: { bg: '#1e3a5f', text: '#60a5fa' },
  called:    { bg: '#2e1065', text: '#c4b5fd' },
  converted: { bg: '#052e16', text: '#34d399' },
  nurture:   { bg: '#451a03', text: '#f59e0b' },
  closed:    { bg: '#1f2937', text: '#9ca3af' },
};

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
  },
  filterBar: {
    display: 'flex',
    gap: 10,
    marginBottom: 20,
    alignItems: 'center',
  },
  input: {
    padding: '9px 12px',
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    color: '#f0f0f5',
    fontSize: 13,
    outline: 'none',
    fontFamily: 'inherit',
  },
  select: {
    padding: '9px 12px',
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    color: '#f0f0f5',
    fontSize: 13,
    outline: 'none',
    fontFamily: 'inherit',
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
  loadingText: {
    textAlign: 'center' as const,
    color: '#6b7280',
    fontSize: 14,
    padding: '40px 0',
  },
  emptyText: {
    textAlign: 'center' as const,
    color: '#4b5563',
    fontSize: 13,
    padding: '28px 0',
  },
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    apiJSON<{ leads: Lead[]; count: number }>('/api/leads?limit=100')
      .then(({ leads: list }) => setLeads(list))
      .catch((err: unknown) => setError(String((err as Error).message ?? err)))
      .finally(() => setLoading(false));
  }, []);

  async function handleStatusChange(id: number, status: string) {
    try {
      await apiJSON<{ ok: boolean }>(`/api/leads/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      setLeads((prev) =>
        prev.map((l) => (l.id === id ? { ...l, status: status as Lead['status'] } : l)),
      );
    } catch (err: unknown) {
      console.error('Failed to update lead status:', (err as Error).message ?? err);
    }
  }

  const filtered = leads.filter((l) => {
    const matchStatus = !statusFilter || l.status === statusFilter;
    const q = searchQuery.toLowerCase();
    const matchSearch =
      !q ||
      l.name.toLowerCase().includes(q) ||
      l.email.toLowerCase().includes(q) ||
      l.suburb.toLowerCase().includes(q);
    return matchStatus && matchSearch;
  });

  function scoreColor(score: number): string {
    if (score >= 8) return '#34d399';
    if (score >= 5) return '#f59e0b';
    return '#f87171';
  }

  function formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleDateString('en-AU', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return iso;
    }
  }

  if (loading) {
    return (
      <div style={s.page}>
        <p style={s.loadingText}>Loading leads...</p>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <h1 style={s.title}>Leads</h1>
      <p style={s.subtitle}>
        {filtered.length} of {leads.length} leads
      </p>

      {error && <div style={s.errorBanner}>{error}</div>}

      {/* Filter bar */}
      <div style={s.filterBar}>
        <input
          style={{ ...s.input, flex: 1, minWidth: 200 }}
          type="text"
          placeholder="Search name, email, suburb..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          style={s.select}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Statuses</option>
          {LEAD_STATUSES.map((st) => (
            <option key={st} value={st}>
              {st.charAt(0).toUpperCase() + st.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={s.card}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Name</th>
              <th style={s.th}>Location</th>
              <th style={s.th}>Score</th>
              <th style={s.th}>Status</th>
              <th style={s.th}>Recommended Action</th>
              <th style={s.th}>Created</th>
              <th style={s.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ ...s.td, ...s.emptyText, borderBottom: 'none' }}>
                  No leads match your filters
                </td>
              </tr>
            ) : (
              filtered.map((lead) => {
                const statusColor = STATUS_COLORS[lead.status] ?? STATUS_COLORS.closed;
                return (
                  <tr key={lead.id}>
                    {/* Name */}
                    <td style={s.td}>
                      <div style={{ fontWeight: 500, color: '#f0f0f5' }}>{lead.name}</div>
                      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
                        {lead.phone}
                      </div>
                    </td>

                    {/* Location */}
                    <td style={s.td}>
                      {lead.suburb}, {lead.state}
                    </td>

                    {/* Score */}
                    <td style={{ ...s.td, fontWeight: 600, color: scoreColor(lead.qualification_score) }}>
                      {lead.qualification_score}
                    </td>

                    {/* Status badge */}
                    <td style={s.td}>
                      <span
                        style={{
                          backgroundColor: statusColor.bg,
                          color: statusColor.text,
                          borderRadius: 4,
                          padding: '3px 8px',
                          fontSize: 11,
                          fontWeight: 600,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {lead.status.toUpperCase()}
                      </span>
                    </td>

                    {/* Recommended action */}
                    <td style={{ ...s.td, maxWidth: 200, color: '#9ca3af' }}>
                      {lead.recommended_action}
                    </td>

                    {/* Created */}
                    <td style={{ ...s.td, whiteSpace: 'nowrap', color: '#6b7280' }}>
                      {formatDate(lead.created_at)}
                    </td>

                    {/* Actions — inline status change */}
                    <td style={s.td}>
                      <select
                        style={{ ...s.select, width: 'auto' }}
                        value={lead.status}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                      >
                        {LEAD_STATUSES.map((st) => (
                          <option key={st} value={st}>
                            {st.charAt(0).toUpperCase() + st.slice(1)}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
