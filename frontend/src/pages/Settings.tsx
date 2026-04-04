/**
 * Settings — /settings
 *
 * Three sections:
 *   1. Agent Toggles   — enable/disable individual agents
 *   2. App Settings    — grouped key-value config with save bar
 *   3. API Keys        — list, generate, and revoke API keys
 *
 * Talks exclusively to /api/settings, /api/agents/config, /api/keys
 * via the shared api-client.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface SettingItem {
  key: string;
  value: string;
  description: string;
  updated_at: string;
}

interface AgentsConfig {
  agents: Record<string, boolean>;
  schedule: Record<string, { last_run: string; running: boolean }>;
}

interface ApiKey {
  id: number;
  key_id: string;
  name: string;
  prefix: string;
  permissions: string;
  active: boolean;
  created_at: string;
  last_used: string | null;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const inputBase: React.CSSProperties = {
  padding: '7px 10px',
  backgroundColor: '#0a0a0f',
  border: '1px solid #1e1e2e',
  borderRadius: 5,
  color: '#f0f0f5',
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
  width: 160,
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
    margin: '0 0 32px',
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
  categoryLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: '#4f46e5',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    margin: '20px 0 10px',
  },
  settingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 0',
    borderBottom: '1px solid #12121c',
    gap: 16,
  },
  settingLeft: {
    flex: 1,
    minWidth: 0,
  },
  settingKey: {
    fontSize: 13,
    color: '#a5b4fc',
    fontFamily: 'monospace',
    marginBottom: 2,
  },
  settingDesc: {
    fontSize: 12,
    color: '#6b7280',
  },
  input: inputBase,
  agentRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 0',
    borderBottom: '1px solid #12121c',
  },
  agentName: {
    fontSize: 13,
    color: '#d1d5db',
    fontFamily: 'monospace',
  },
  agentMeta: {
    fontSize: 11,
    color: '#6b7280',
    marginTop: 2,
  },
  keyCard: {
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '14px 16px',
    marginBottom: 8,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  keyMeta: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 4,
  },
  rawKeyBox: {
    backgroundColor: '#0a0a0f',
    border: '1px solid #34d399',
    borderRadius: 6,
    padding: '10px 14px',
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#34d399',
    marginBottom: 16,
    wordBreak: 'break-all' as const,
  },
  btnPrimary: {
    padding: '9px 20px',
    backgroundColor: '#4f46e5',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  btnDanger: {
    padding: '7px 12px',
    backgroundColor: 'transparent',
    color: '#f87171',
    border: '1px solid #7f1d1d',
    borderRadius: 5,
    fontSize: 12,
    cursor: 'pointer',
  },
  saveBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginTop: 20,
  },
  addKeyRow: {
    display: 'flex',
    gap: 10,
    marginTop: 16,
  },
  addKeyInput: {
    ...inputBase,
    width: 220,
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

function toggleStyle(enabled: boolean): React.CSSProperties {
  return {
    width: 38,
    height: 20,
    borderRadius: 10,
    backgroundColor: enabled ? '#4f46e5' : '#374151',
    border: 'none',
    cursor: 'pointer',
    position: 'relative' as const,
    transition: 'background-color 0.2s',
  };
}

function toggleThumbStyle(enabled: boolean): React.CSSProperties {
  return {
    position: 'absolute' as const,
    top: 2,
    left: enabled ? 18 : 2,
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: '#fff',
    transition: 'left 0.2s',
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, SettingItem[]>>({});
  const [agentsConfig, setAgentsConfig] = useState<AgentsConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [dirtySettings, setDirtySettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyRevealed, setNewKeyRevealed] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function fetchAll() {
    try {
      const [settingsData, agentsData, keysData] = await Promise.all([
        apiJSON<{ settings: Record<string, SettingItem[]> }>('/api/settings'),
        apiJSON<AgentsConfig>('/api/agents/config'),
        apiJSON<{ keys: ApiKey[] }>('/api/keys'),
      ]);
      setSettings(settingsData.settings);
      setAgentsConfig(agentsData);
      setApiKeys(keysData.keys);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchAll();
  }, []);

  function handleSettingChange(key: string, value: string) {
    setDirtySettings((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSaveSettings() {
    setSaving(true);
    setError(null);
    try {
      await apiJSON('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify(dirtySettings),
      });
      setDirtySettings({});
      const { settings: refreshed } = await apiJSON<{ settings: Record<string, SettingItem[]> }>('/api/settings');
      setSettings(refreshed);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setSaving(false);
    }
  }

  async function handleAgentToggle(agentId: string, currentEnabled: boolean) {
    try {
      await apiJSON('/api/agents/config', {
        method: 'PATCH',
        body: JSON.stringify({ agent_id: agentId, enabled: !currentEnabled }),
      });
      setAgentsConfig((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          agents: { ...prev.agents, [agentId]: !currentEnabled },
        };
      });
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleCreateKey() {
    setError(null);
    try {
      const data = await apiJSON<{ raw_key: string; key_id: string; name: string }>('/api/keys', {
        method: 'POST',
        body: JSON.stringify({ name: newKeyName }),
      });
      setNewKeyRevealed(data.raw_key);
      setNewKeyName('');
      const { keys } = await apiJSON<{ keys: ApiKey[] }>('/api/keys');
      setApiKeys(keys);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    }
  }

  async function handleDeleteKey(keyId: string) {
    setError(null);
    try {
      await apiJSON(`/api/keys/${keyId}`, { method: 'DELETE' });
      setApiKeys((prev) => prev.filter((k) => k.key_id !== keyId));
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    }
  }

  if (loading) {
    return (
      <div style={s.page}>
        <p style={{ color: '#6b7280', fontSize: 14 }}>Loading settings…</p>
      </div>
    );
  }

  const dirtyCount = Object.keys(dirtySettings).length;

  return (
    <div style={s.page}>
      <h1 style={s.title}>Settings</h1>
      <p style={s.subtitle}>Configure your AI receptionist</p>

      {error && <div style={s.errorBanner}>{error}</div>}

      {/* ── Agent Configuration ────────────────────────────────────────────── */}
      <div style={s.card}>
        <p style={s.sectionTitle}>Agent Configuration</p>
        {agentsConfig && Object.entries(agentsConfig.agents).map(([agentId, enabled]) => {
          const schedInfo = agentsConfig.schedule[agentId];
          const lastRun = schedInfo?.last_run
            ? new Date(schedInfo.last_run).toLocaleString()
            : 'Never run';
          return (
            <div key={agentId} style={s.agentRow}>
              <div>
                <div style={s.agentName}>{agentId}</div>
                <div style={s.agentMeta}>{lastRun}</div>
              </div>
              <button
                style={toggleStyle(enabled)}
                onClick={() => handleAgentToggle(agentId, enabled)}
                aria-label={`Toggle ${agentId}`}
              >
                <div style={toggleThumbStyle(enabled)} />
              </button>
            </div>
          );
        })}
        {agentsConfig && Object.keys(agentsConfig.agents).length === 0 && (
          <p style={{ color: '#6b7280', fontSize: 13 }}>No agents configured.</p>
        )}
      </div>

      {/* ── Application Settings ───────────────────────────────────────────── */}
      <div style={s.card}>
        <p style={s.sectionTitle}>Application Settings</p>
        {Object.entries(settings).map(([category, items]) => (
          <React.Fragment key={category}>
            <p style={s.categoryLabel}>{category}</p>
            {items.map((item) => {
              const isBoolean = item.value === 'true' || item.value === 'false';
              const currentValue = dirtySettings[item.key] ?? item.value;
              const boolEnabled = currentValue === 'true';
              return (
                <div key={item.key} style={s.settingRow}>
                  <div style={s.settingLeft}>
                    <div style={s.settingKey}>{item.key}</div>
                    <div style={s.settingDesc}>{item.description}</div>
                  </div>
                  {isBoolean ? (
                    <button
                      style={toggleStyle(boolEnabled)}
                      onClick={() =>
                        handleSettingChange(item.key, boolEnabled ? 'false' : 'true')
                      }
                      aria-label={`Toggle ${item.key}`}
                    >
                      <div style={toggleThumbStyle(boolEnabled)} />
                    </button>
                  ) : (
                    <input
                      style={s.input}
                      value={currentValue}
                      onChange={(e) => handleSettingChange(item.key, e.target.value)}
                    />
                  )}
                </div>
              );
            })}
          </React.Fragment>
        ))}

        {dirtyCount > 0 && (
          <div style={s.saveBar}>
            <button
              style={{ ...s.btnPrimary, opacity: saving ? 0.7 : 1 }}
              onClick={handleSaveSettings}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              {dirtyCount} unsaved {dirtyCount === 1 ? 'change' : 'changes'}
            </span>
          </div>
        )}
      </div>

      {/* ── API Keys ───────────────────────────────────────────────────────── */}
      <div style={s.card}>
        <p style={s.sectionTitle}>API Keys</p>

        {newKeyRevealed && (
          <>
            <p style={{ fontSize: 12, color: '#f59e0b', margin: '0 0 6px' }}>
              Copy this key now — it will not be shown again.
            </p>
            <div style={s.rawKeyBox}>{newKeyRevealed}</div>
          </>
        )}

        {apiKeys.map((key) => (
          <div key={key.key_id} style={s.keyCard}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#f0f0f5' }}>{key.name}</div>
              <div style={s.keyMeta}>
                <span style={{ fontFamily: 'monospace', color: '#a5b4fc' }}>{key.prefix}…</span>
                {' · '}
                {key.permissions}
                {' · '}
                {key.last_used
                  ? `Last used ${new Date(key.last_used).toLocaleDateString()}`
                  : 'Never used'}
              </div>
            </div>
            <button style={s.btnDanger} onClick={() => handleDeleteKey(key.key_id)}>
              Revoke
            </button>
          </div>
        ))}

        {apiKeys.length === 0 && !newKeyRevealed && (
          <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 8 }}>No API keys yet.</p>
        )}

        <div style={s.addKeyRow}>
          <input
            style={s.addKeyInput}
            placeholder="Key name…"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newKeyName.trim()) handleCreateKey();
            }}
          />
          <button
            style={{ ...s.btnPrimary, opacity: newKeyName.trim() ? 1 : 0.4 }}
            onClick={handleCreateKey}
            disabled={!newKeyName.trim()}
          >
            Generate Key
          </button>
        </div>
      </div>
    </div>
  );
}
