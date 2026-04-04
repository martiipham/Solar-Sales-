/**
 * CRM Integration Wizard — /crm-wizard
 *
 * 5-step flow:
 *   0. Select provider
 *   1. Enter credentials
 *   2. Configure field mapping
 *   3. Test connection
 *   4. Review & save
 *
 * Talks exclusively to /api/crm/* endpoints via the shared api-client.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface CredentialField {
  key: string;
  label: string;
  type: 'text' | 'password';
  required: boolean;
}

interface Provider {
  id: string;
  name: string;
  description: string;
  credentials: CredentialField[];
  active: boolean;
  configured: boolean;
}

interface FieldMapping {
  canonical: string;
  crm_field: string;
  editable: boolean;
  custom?: boolean;
}

interface TestResult {
  success: boolean;
  message?: string;
  error?: string;
  contacts_found?: number;
  sample_fields?: string[];
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 780,
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
  stepper: {
    display: 'flex',
    alignItems: 'center',
    gap: 0,
    marginBottom: 36,
  },
  step: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  stepDot: {
    width: 28,
    height: 28,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    fontWeight: 600,
    flexShrink: 0,
  },
  stepLabel: {
    fontSize: 12,
    fontWeight: 500,
    whiteSpace: 'nowrap' as const,
  },
  stepLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#1e1e2e',
    margin: '0 8px',
  },
  card: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 10,
    padding: 28,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: '#f0f0f5',
    margin: '0 0 20px',
  },
  providerGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 12,
  },
  providerCard: {
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '16px 18px',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background-color 0.15s',
  },
  providerCardActive: {
    borderColor: '#4f46e5',
    backgroundColor: '#1e1e3a',
  },
  providerName: {
    fontSize: 14,
    fontWeight: 600,
    color: '#f0f0f5',
    margin: '0 0 4px',
  },
  providerDesc: {
    fontSize: 12,
    color: '#6b7280',
    margin: 0,
    lineHeight: 1.5,
  },
  label: {
    display: 'block',
    fontSize: 13,
    fontWeight: 500,
    color: '#d1d5db',
    marginBottom: 6,
  },
  input: {
    width: '100%',
    padding: '9px 12px',
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    color: '#f0f0f5',
    fontSize: 13,
    outline: 'none',
    boxSizing: 'border-box' as const,
    fontFamily: 'inherit',
  },
  fieldRow: {
    marginBottom: 16,
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
  tdCode: {
    fontFamily: 'monospace',
    color: '#a5b4fc',
  },
  testBox: {
    backgroundColor: '#0a0a0f',
    border: '1px solid #1e1e2e',
    borderRadius: 8,
    padding: '20px 24px',
    marginBottom: 20,
  },
  testSuccess: {
    color: '#34d399',
    fontSize: 13,
    fontWeight: 600,
  },
  testError: {
    color: '#f87171',
    fontSize: 13,
    fontWeight: 600,
  },
  testMeta: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 8,
  },
  actions: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 28,
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
    transition: 'background-color 0.15s',
  },
  btnSecondary: {
    padding: '9px 20px',
    backgroundColor: 'transparent',
    color: '#9ca3af',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
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
  successBanner: {
    textAlign: 'center' as const,
    padding: 32,
  },
  successIcon: {
    fontSize: 40,
    marginBottom: 12,
  },
  successTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: '#34d399',
    margin: '0 0 8px',
  },
  successBody: {
    fontSize: 14,
    color: '#6b7280',
    margin: 0,
  },
};

// ── Step labels ───────────────────────────────────────────────────────────────

const STEPS = ['Provider', 'Credentials', 'Field Map', 'Test', 'Review'];

// ── Component ─────────────────────────────────────────────────────────────────

export default function CRMWizard() {
  const [step, setStep] = useState(0);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [fieldMapping, setFieldMapping] = useState<FieldMapping[]>([]);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Load providers on mount
  useEffect(() => {
    apiJSON<{ providers: Provider[] }>('/api/crm/providers')
      .then(({ providers: list }) => setProviders(list))
      .catch((err) => setError(String(err.message ?? err)));
  }, []);

  // Load field mapping when entering step 2
  useEffect(() => {
    if (step !== 2 || !selectedProvider) return;
    setLoading(true);
    setError(null);
    apiJSON<{ mapping: FieldMapping[] }>(`/api/crm/field-mapping/${selectedProvider.id}`)
      .then(({ mapping }) => setFieldMapping(mapping))
      .catch((err) => setError(String(err.message ?? err)))
      .finally(() => setLoading(false));
  }, [step, selectedProvider]);

  function handleCredentialChange(key: string, value: string) {
    setCredentials((prev) => ({ ...prev, [key]: value }));
  }

  function handleFieldMappingChange(canonical: string, crm_field: string) {
    setFieldMapping((prev) =>
      prev.map((f) => (f.canonical === canonical ? { ...f, crm_field } : f)),
    );
  }

  async function runConnectionTest() {
    if (!selectedProvider) return;
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const result = await apiJSON<TestResult>('/api/crm/test-connection', {
        method: 'POST',
        body: JSON.stringify({ provider: selectedProvider.id, credentials }),
      });
      setTestResult(result);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!selectedProvider) return;
    setLoading(true);
    setError(null);
    try {
      const overrides: Record<string, string> = {};
      for (const f of fieldMapping) {
        overrides[f.canonical] = f.crm_field;
      }
      await apiJSON('/api/crm/save-config', {
        method: 'POST',
        body: JSON.stringify({
          provider: selectedProvider.id,
          credentials,
          field_mapping: overrides,
        }),
      });
      setSaved(true);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  function validateStep(): boolean {
    if (step === 0) return selectedProvider !== null;
    if (step === 1 && selectedProvider) {
      const required = selectedProvider.credentials.filter((c) => c.required);
      return required.every((c) => (credentials[c.key] ?? '').trim() !== '');
    }
    if (step === 3) return testResult?.success === true;
    return true;
  }

  function next() {
    if (step === 3 && !testResult) {
      runConnectionTest();
      return;
    }
    setError(null);
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  function back() {
    setError(null);
    setStep((s) => Math.max(s - 1, 0));
  }

  if (saved) {
    return (
      <div style={s.page}>
        <div style={s.card}>
          <div style={s.successBanner}>
            <div style={s.successIcon}>✅</div>
            <p style={s.successTitle}>CRM connected successfully</p>
            <p style={s.successBody}>
              {selectedProvider?.name} is now active. The voice agent will sync leads automatically.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <div style={s.header}>
        <h1 style={s.title}>CRM Integration Wizard</h1>
        <p style={s.subtitle}>
          Connect your CRM in 5 steps. Leads from every call will sync automatically.
        </p>
      </div>

      {/* Stepper */}
      <div style={s.stepper}>
        {STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          const dotBg = done ? '#34d399' : active ? '#4f46e5' : '#1e1e2e';
          const dotColor = done || active ? '#fff' : '#4b5563';
          const labelColor = active ? '#f0f0f5' : done ? '#34d399' : '#4b5563';
          return (
            <React.Fragment key={label}>
              <div style={s.step}>
                <div style={{ ...s.stepDot, backgroundColor: dotBg, color: dotColor }}>
                  {done ? '✓' : i + 1}
                </div>
                <span style={{ ...s.stepLabel, color: labelColor }}>{label}</span>
              </div>
              {i < STEPS.length - 1 && <div style={s.stepLine} />}
            </React.Fragment>
          );
        })}
      </div>

      {error && <div style={s.errorBanner}>{error}</div>}

      <div style={s.card}>
        {/* Step 0: Select Provider */}
        {step === 0 && (
          <>
            <p style={s.sectionTitle}>Select your CRM</p>
            <div style={s.providerGrid}>
              {providers.map((p) => (
                <div
                  key={p.id}
                  style={{
                    ...s.providerCard,
                    ...(selectedProvider?.id === p.id ? s.providerCardActive : {}),
                  }}
                  onClick={() => setSelectedProvider(p)}
                >
                  <p style={s.providerName}>
                    {p.name}
                    {p.active && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 10,
                          color: '#34d399',
                          fontWeight: 500,
                        }}
                      >
                        ACTIVE
                      </span>
                    )}
                    {p.configured && !p.active && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 10,
                          color: '#f59e0b',
                          fontWeight: 500,
                        }}
                      >
                        CONFIGURED
                      </span>
                    )}
                  </p>
                  <p style={s.providerDesc}>{p.description}</p>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Step 1: Credentials */}
        {step === 1 && selectedProvider && (
          <>
            <p style={s.sectionTitle}>{selectedProvider.name} — API credentials</p>
            {selectedProvider.credentials.map((field) => (
              <div key={field.key} style={s.fieldRow}>
                <label style={s.label}>
                  {field.label}
                  {field.required && <span style={{ color: '#f87171', marginLeft: 3 }}>*</span>}
                </label>
                <input
                  style={s.input}
                  type={field.type}
                  value={credentials[field.key] ?? ''}
                  onChange={(e) => handleCredentialChange(field.key, e.target.value)}
                  autoComplete="off"
                />
              </div>
            ))}
          </>
        )}

        {/* Step 2: Field Mapping */}
        {step === 2 && (
          <>
            <p style={s.sectionTitle}>Field mapping</p>
            {loading ? (
              <p style={{ color: '#6b7280', fontSize: 13 }}>Loading field map…</p>
            ) : (
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>SolarAdmin field</th>
                    <th style={s.th}>CRM field</th>
                  </tr>
                </thead>
                <tbody>
                  {fieldMapping.map((f) => (
                    <tr key={f.canonical}>
                      <td style={{ ...s.td, ...s.tdCode }}>{f.canonical}</td>
                      <td style={s.td}>
                        {f.editable ? (
                          <input
                            style={{ ...s.input, padding: '6px 10px' }}
                            value={f.crm_field}
                            onChange={(e) =>
                              handleFieldMappingChange(f.canonical, e.target.value)
                            }
                          />
                        ) : (
                          <span style={s.tdCode}>{f.crm_field}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}

        {/* Step 3: Test Connection */}
        {step === 3 && (
          <>
            <p style={s.sectionTitle}>Test connection</p>
            <div style={s.testBox}>
              {!testResult && !loading && (
                <p style={{ color: '#6b7280', fontSize: 13, margin: 0 }}>
                  Click "Run Test" to verify your credentials by fetching recent contacts.
                </p>
              )}
              {loading && (
                <p style={{ color: '#6b7280', fontSize: 13, margin: 0 }}>Connecting…</p>
              )}
              {testResult && (
                <>
                  <p style={testResult.success ? s.testSuccess : s.testError}>
                    {testResult.success ? '✓ Connected' : '✗ Failed'}
                  </p>
                  <p style={s.testMeta}>
                    {testResult.success ? testResult.message : testResult.error}
                  </p>
                  {testResult.success && testResult.contacts_found !== undefined && (
                    <p style={s.testMeta}>
                      {testResult.contacts_found} contact(s) found in CRM.
                    </p>
                  )}
                </>
              )}
            </div>
            {!loading && !testResult?.success && (
              <button style={s.btnPrimary} onClick={runConnectionTest}>
                Run Test
              </button>
            )}
          </>
        )}

        {/* Step 4: Review & Save */}
        {step === 4 && selectedProvider && (
          <>
            <p style={s.sectionTitle}>Review & activate</p>
            <table style={s.table}>
              <tbody>
                <tr>
                  <td style={{ ...s.td, color: '#6b7280', width: 160 }}>Provider</td>
                  <td style={s.td}>{selectedProvider.name}</td>
                </tr>
                <tr>
                  <td style={{ ...s.td, color: '#6b7280' }}>Credentials</td>
                  <td style={s.td}>
                    {selectedProvider.credentials.map((c) => (
                      <span key={c.key} style={{ marginRight: 12, fontSize: 12, color: '#a5b4fc' }}>
                        {c.label}
                      </span>
                    ))}
                  </td>
                </tr>
                <tr>
                  <td style={{ ...s.td, color: '#6b7280' }}>Field mappings</td>
                  <td style={s.td}>{fieldMapping.length} fields configured</td>
                </tr>
                <tr>
                  <td style={{ ...s.td, color: '#6b7280' }}>Connection test</td>
                  <td style={{ ...s.td, color: '#34d399' }}>✓ Passed</td>
                </tr>
              </tbody>
            </table>
          </>
        )}

        {/* Actions */}
        <div style={s.actions}>
          <button style={s.btnSecondary} onClick={back} disabled={step === 0 || loading}>
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              style={{ ...s.btnPrimary, opacity: validateStep() ? 1 : 0.5 }}
              onClick={next}
              disabled={!validateStep() || loading}
            >
              {step === 3 && !testResult ? 'Run Test' : 'Continue'}
            </button>
          ) : (
            <button
              style={{ ...s.btnPrimary, backgroundColor: '#059669' }}
              onClick={handleSave}
              disabled={loading}
            >
              {loading ? 'Saving…' : 'Activate CRM'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
