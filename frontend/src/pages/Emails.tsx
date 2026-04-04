/**
 * Emails — /emails
 *
 * AI-classified email inbox with approve/edit/discard workflow.
 * Talks to /api/emails, /api/emails/stats, /gate/email-approve,
 * and /api/emails/bulk-discard via the shared api-client.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EmailListItem {
  id: number;
  received_at: string;
  from_email: string;
  from_name: string;
  subject: string;
  classification: string;
  urgency_score: number;
  draft_reply: string;
  status: 'pending' | 'sent' | 'discarded';
}

interface EmailStats {
  pending: number;
  sent: number;
  today_total: number;
  today_pending: number;
  discarded_today: number;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const tab: React.CSSProperties = {
  padding: '10px 20px',
  fontSize: 13,
  fontWeight: 500,
  color: '#6b7280',
  cursor: 'pointer',
  background: 'none',
  border: 'none',
  borderBottomWidth: 2,
  borderBottomStyle: 'solid' as const,
  borderBottomColor: 'transparent',
  fontFamily: 'inherit',
};

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
  statsBar: {
    display: 'flex',
    gap: 12,
    marginBottom: 20,
    flexWrap: 'wrap' as const,
  },
  statPill: {
    padding: '5px 14px',
    borderRadius: 20,
    fontSize: 12,
    fontWeight: 600,
    backgroundColor: '#1e1e2e',
    color: '#d1d5db',
  },
  tabBar: {
    display: 'flex',
    gap: 0,
    marginBottom: 20,
    borderBottom: '1px solid #1e1e2e',
  },
  tab,
  tabActive: {
    ...tab,
    color: '#f0f0f5',
    borderBottomColor: '#4f46e5',
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
  expandedCell: {
    padding: '16px 12px 20px',
    backgroundColor: '#0a0a0f',
  },
  textarea: {
    width: '100%',
    minHeight: 120,
    padding: '9px 12px',
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    color: '#f0f0f5',
    fontSize: 13,
    fontFamily: 'inherit',
    resize: 'vertical' as const,
    boxSizing: 'border-box' as const,
  },
  actionRow: {
    display: 'flex',
    gap: 10,
    marginTop: 12,
  },
  btnGreen: {
    padding: '8px 16px',
    backgroundColor: '#065f46',
    color: '#34d399',
    border: '1px solid #34d399',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  btnPurple: {
    padding: '8px 16px',
    backgroundColor: '#4f46e5',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  btnRed: {
    padding: '8px 16px',
    backgroundColor: 'transparent',
    color: '#f87171',
    border: '1px solid #7f1d1d',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
  bulkBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
    padding: '10px 14px',
    backgroundColor: '#1e1e2e',
    borderRadius: 6,
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

const STATUS_TABS = ['pending', 'sent', 'discarded', 'all'] as const;
type StatusTab = (typeof STATUS_TABS)[number];

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function urgencyColor(score: number): string {
  if (score >= 8) return '#f87171';
  if (score >= 5) return '#f59e0b';
  return '#34d399';
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Emails() {
  const [emails, setEmails] = useState<EmailListItem[]>([]);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusTab>('pending');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [editDrafts, setEditDrafts] = useState<Record<number, string>>({});
  const [actionLoading, setActionLoading] = useState(false);

  async function loadEmails(status: string) {
    setLoading(true);
    setError(null);
    try {
      const query = status === 'all' ? '' : `?status=${status}&limit=50`;
      const data = await apiJSON<{ emails: EmailListItem[]; total: number }>(
        `/api/emails${query}`,
      );
      setEmails(data.emails);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  // Load emails on mount and when statusFilter changes
  useEffect(() => {
    loadEmails(statusFilter);
  }, [statusFilter]);

  // Load stats on mount
  useEffect(() => {
    apiJSON<EmailStats>('/api/emails/stats')
      .then((data) => setStats(data))
      .catch(() => {
        // Stats failure is non-blocking
      });
  }, []);

  function toggleSelected(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function updateDraft(emailId: number, value: string) {
    setEditDrafts((prev) => ({ ...prev, [emailId]: value }));
  }

  async function handleAction(
    emailId: number,
    action: 'send' | 'edit' | 'discard',
  ) {
    setActionLoading(true);
    setError(null);
    try {
      const body: { email_id: number; action: string; edited_body?: string } = {
        email_id: emailId,
        action,
      };
      if (action === 'edit' && editDrafts[emailId] !== undefined) {
        body.edited_body = editDrafts[emailId];
      }
      await apiJSON('/gate/email-approve', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      // Remove from local list
      setEmails((prev) => prev.filter((e) => e.id !== emailId));
      setExpandedId(null);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(emailId);
        return next;
      });
      // Refresh stats
      apiJSON<EmailStats>('/api/emails/stats')
        .then((data) => setStats(data))
        .catch(() => {});
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleBulkDiscard() {
    if (selectedIds.size === 0) return;
    setActionLoading(true);
    setError(null);
    try {
      const ids = [...selectedIds];
      await apiJSON('/api/emails/bulk-discard', {
        method: 'POST',
        body: JSON.stringify({ ids }),
      });
      setEmails((prev) => prev.filter((e) => !ids.includes(e.id)));
      setSelectedIds(new Set());
      // Refresh stats
      apiJSON<EmailStats>('/api/emails/stats')
        .then((data) => setStats(data))
        .catch(() => {});
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <h1 style={s.title}>Emails</h1>
      <p style={s.subtitle}>AI-classified email inbox</p>

      {/* Stats bar */}
      {stats && (
        <div style={s.statsBar}>
          <span style={s.statPill}>Pending: {stats.pending}</span>
          <span style={s.statPill}>Sent: {stats.sent}</span>
          <span style={s.statPill}>Today: {stats.today_total}</span>
        </div>
      )}

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div style={s.bulkBar}>
          <span style={{ fontSize: 13, color: '#d1d5db' }}>
            {selectedIds.size} selected
          </span>
          <button
            style={{ ...s.btnRed, opacity: actionLoading ? 0.6 : 1 }}
            onClick={handleBulkDiscard}
            disabled={actionLoading}
          >
            Discard All Selected
          </button>
        </div>
      )}

      {/* Status tabs */}
      <div style={s.tabBar}>
        {STATUS_TABS.map((t) => (
          <button
            key={t}
            style={statusFilter === t ? s.tabActive : s.tab}
            onClick={() => {
              setStatusFilter(t);
              setExpandedId(null);
              setSelectedIds(new Set());
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Error banner */}
      {error && <div style={s.errorBanner}>{error}</div>}

      {/* Main card */}
      <div style={s.card}>
        {loading ? (
          <p style={{ color: '#6b7280', fontSize: 13, margin: 0 }}>Loading…</p>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={{ ...s.th, width: 32 }}>&#9633;</th>
                <th style={s.th}>From</th>
                <th style={s.th}>Subject</th>
                <th style={s.th}>Urgency</th>
                <th style={s.th}>Class</th>
                <th style={s.th}>Status</th>
                <th style={s.th}>Received</th>
              </tr>
            </thead>
            <tbody>
              {emails.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    style={{ ...s.td, color: '#6b7280', cursor: 'default', textAlign: 'center' }}
                  >
                    No emails
                  </td>
                </tr>
              ) : (
                emails.map((email) => (
                  <React.Fragment key={email.id}>
                    <tr>
                      {/* Checkbox */}
                      <td
                        style={{ ...s.td, cursor: 'default' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.has(email.id)}
                          onChange={() => toggleSelected(email.id)}
                        />
                      </td>

                      {/* From */}
                      <td
                        style={s.td}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        <span style={{ fontWeight: 500 }}>
                          {email.from_name || email.from_email}
                        </span>
                        {email.from_name && (
                          <span
                            style={{
                              display: 'block',
                              fontSize: 11,
                              color: '#6b7280',
                              marginTop: 1,
                            }}
                          >
                            {email.from_email}
                          </span>
                        )}
                      </td>

                      {/* Subject */}
                      <td
                        style={{ ...s.td, maxWidth: 260 }}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        <span
                          style={{
                            display: 'block',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {email.subject}
                        </span>
                      </td>

                      {/* Urgency */}
                      <td
                        style={{
                          ...s.td,
                          color: urgencyColor(email.urgency_score),
                          fontWeight: 600,
                        }}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        {email.urgency_score}
                      </td>

                      {/* Classification */}
                      <td
                        style={{ ...s.td, color: '#a5b4fc', fontSize: 12 }}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        {email.classification}
                      </td>

                      {/* Status */}
                      <td
                        style={s.td}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            color:
                              email.status === 'sent'
                                ? '#34d399'
                                : email.status === 'discarded'
                                ? '#6b7280'
                                : '#f59e0b',
                          }}
                        >
                          {email.status.toUpperCase()}
                        </span>
                      </td>

                      {/* Received */}
                      <td
                        style={{ ...s.td, fontSize: 12, color: '#6b7280' }}
                        onClick={() =>
                          setExpandedId(expandedId === email.id ? null : email.id)
                        }
                      >
                        {formatDate(email.received_at)}
                      </td>
                    </tr>

                    {/* Expanded row */}
                    {expandedId === email.id && (
                      <tr>
                        <td colSpan={7} style={s.expandedCell}>
                          <p
                            style={{
                              margin: '0 0 8px',
                              fontSize: 12,
                              fontWeight: 600,
                              color: '#6b7280',
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            Draft Reply:
                          </p>
                          <textarea
                            style={s.textarea}
                            value={editDrafts[email.id] ?? email.draft_reply}
                            onChange={(e) => updateDraft(email.id, e.target.value)}
                          />
                          <div style={s.actionRow}>
                            <button
                              style={{
                                ...s.btnGreen,
                                opacity: actionLoading ? 0.6 : 1,
                              }}
                              disabled={actionLoading}
                              onClick={() => handleAction(email.id, 'send')}
                            >
                              Approve &amp; Send
                            </button>
                            <button
                              style={{
                                ...s.btnPurple,
                                opacity: actionLoading ? 0.6 : 1,
                              }}
                              disabled={actionLoading}
                              onClick={() => handleAction(email.id, 'edit')}
                            >
                              Edit &amp; Send
                            </button>
                            <button
                              style={{
                                ...s.btnRed,
                                opacity: actionLoading ? 0.6 : 1,
                              }}
                              disabled={actionLoading}
                              onClick={() => handleAction(email.id, 'discard')}
                            >
                              Discard
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
