/**
 * Knowledge Base — /knowledge-base
 *
 * Three-tab CRUD interface for the voice agent's knowledge:
 *   - FAQs        : common questions + answers the AI can recite
 *   - Objections  : sales objection handling scripts
 *   - Products    : solar products with pricing, features, brands
 *
 * Talks to /api/kb/* endpoints via the shared api-client.
 */

import React, { useEffect, useState } from 'react';
import { apiJSON } from '../lib/api-client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface FAQ {
  id: number;
  question: string;
  answer: string;
  category: string;
  priority: number;
}

interface Objection {
  id: number;
  objection: string;
  response: string;
  priority: number;
}

interface Product {
  id: number;
  product_type: string;
  name: string;
  description: string;
  price_from_aud: number;
  price_to_aud: number;
  features: string;
  brands: string;
  active: number;
}

type TabId = 'faqs' | 'objections' | 'products';

// ── Styles ────────────────────────────────────────────────────────────────────

const base: Record<string, React.CSSProperties> = {
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
  tabBar: {
    display: 'flex',
    gap: 0,
    marginBottom: 24,
    borderBottom: '1px solid #1e1e2e',
  },
  tab: {
    padding: '10px 24px',
    fontSize: 13,
    fontWeight: 500,
    color: '#6b7280',
    cursor: 'pointer',
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    fontFamily: 'inherit',
  },
  card: {
    backgroundColor: '#0d0d14',
    border: '1px solid #1e1e2e',
    borderRadius: 10,
    padding: 28,
    marginBottom: 12,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: '#f0f0f5',
    marginBottom: 4,
  },
  itemBody: {
    fontSize: 13,
    color: '#9ca3af',
    lineHeight: 1.6,
  },
  itemMeta: {
    fontSize: 11,
    color: '#6b7280',
    marginTop: 6,
  },
  itemActions: {
    display: 'flex',
    gap: 8,
    marginTop: 12,
  },
  btnPrimary: {
    padding: '8px 16px',
    backgroundColor: '#4f46e5',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  btnSecondary: {
    padding: '8px 16px',
    backgroundColor: 'transparent',
    color: '#9ca3af',
    border: '1px solid #1e1e2e',
    borderRadius: 6,
    fontSize: 13,
    cursor: 'pointer',
  },
  btnDanger: {
    padding: '8px 16px',
    backgroundColor: 'transparent',
    color: '#f87171',
    border: '1px solid #7f1d1d',
    borderRadius: 6,
    fontSize: 13,
    cursor: 'pointer',
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
  addHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
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
  sectionHeading: {
    fontSize: 15,
    fontWeight: 600,
    color: '#f0f0f5',
    margin: 0,
  },
};

// Derived styles that reference base entries — built after base is defined
const s: Record<string, React.CSSProperties> = {
  ...base,
  tabActive: {
    ...base.tab,
    color: '#f0f0f5',
    borderBottom: '2px solid #4f46e5',
  },
  addCard: {
    ...base.card,
    borderStyle: 'dashed',
  },
  textarea: {
    ...base.input,
    minHeight: 80,
    resize: 'vertical' as const,
  },
};

// ── Small helpers ─────────────────────────────────────────────────────────────

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div style={s.fieldRow}>
      <label style={s.label}>{label}</label>
      {children}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function KnowledgeBase() {
  const [activeTab, setActiveTab] = useState<TabId>('faqs');

  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [objections, setObjections] = useState<Objection[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<Record<string, string>>({});

  // ── Loaders ──────────────────────────────────────────────────────────────

  async function loadFaqs() {
    setLoading(true);
    setError(null);
    try {
      const { faqs: list } = await apiJSON<{ faqs: FAQ[] }>('/api/kb/faqs');
      setFaqs(list);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function loadObjections() {
    setLoading(true);
    setError(null);
    try {
      const { objections: list } = await apiJSON<{ objections: Objection[] }>(
        '/api/kb/objections',
      );
      setObjections(list);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function loadProducts() {
    setLoading(true);
    setError(null);
    try {
      const { products: list } = await apiJSON<{ products: Product[] }>('/api/kb/products');
      setProducts(list);
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  // Load FAQs on mount
  useEffect(() => {
    loadFaqs();
  }, []);

  // Lazy-load when switching tabs (only if data is empty)
  useEffect(() => {
    if (activeTab === 'objections' && objections.length === 0) loadObjections();
    if (activeTab === 'products' && products.length === 0) loadProducts();
    // Reset form state on tab change
    setShowAddForm(false);
    setEditingId(null);
    setFormData({});
  }, [activeTab]);

  // ── Tab switch helper ────────────────────────────────────────────────────

  function switchTab(tab: TabId) {
    setActiveTab(tab);
    setError(null);
  }

  // ── Form helpers ─────────────────────────────────────────────────────────

  function field(key: string): string {
    return formData[key] ?? '';
  }

  function setField(key: string, value: string) {
    setFormData((prev) => ({ ...prev, [key]: value }));
  }

  function openAddForm() {
    setEditingId(null);
    setFormData({});
    setShowAddForm(true);
  }

  function closeAddForm() {
    setShowAddForm(false);
    setFormData({});
  }

  function openEditForm(item: FAQ | Objection | Product) {
    setShowAddForm(false);
    setEditingId(item.id);
    const data: Record<string, string> = {};
    for (const [k, v] of Object.entries(item)) {
      data[k] = String(v);
    }
    setFormData(data);
  }

  function closeEditForm() {
    setEditingId(null);
    setFormData({});
  }

  // ── FAQ CRUD ─────────────────────────────────────────────────────────────

  async function addFaq() {
    setLoading(true);
    setError(null);
    try {
      await apiJSON('/api/kb/faqs', {
        method: 'POST',
        body: JSON.stringify({
          question: field('question'),
          answer: field('answer'),
          category: field('category') || 'General',
          priority: parseInt(field('priority') || '1', 10),
        }),
      });
      closeAddForm();
      await loadFaqs();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function saveFaq(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/faqs/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          question: field('question'),
          answer: field('answer'),
          category: field('category') || 'General',
          priority: parseInt(field('priority') || '1', 10),
        }),
      });
      closeEditForm();
      await loadFaqs();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function deleteFaq(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/faqs/${id}`, { method: 'DELETE' });
      await loadFaqs();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  // ── Objection CRUD ───────────────────────────────────────────────────────

  async function addObjection() {
    setLoading(true);
    setError(null);
    try {
      await apiJSON('/api/kb/objections', {
        method: 'POST',
        body: JSON.stringify({
          objection: field('objection'),
          response: field('response'),
          priority: parseInt(field('priority') || '1', 10),
        }),
      });
      closeAddForm();
      await loadObjections();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function saveObjection(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/objections/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          objection: field('objection'),
          response: field('response'),
          priority: parseInt(field('priority') || '1', 10),
        }),
      });
      closeEditForm();
      await loadObjections();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function deleteObjection(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/objections/${id}`, { method: 'DELETE' });
      await loadObjections();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  // ── Product CRUD ─────────────────────────────────────────────────────────

  async function addProduct() {
    setLoading(true);
    setError(null);
    try {
      await apiJSON('/api/kb/products', {
        method: 'POST',
        body: JSON.stringify({
          product_type: field('product_type') || 'solar_panels',
          name: field('name'),
          description: field('description'),
          price_from_aud: parseFloat(field('price_from_aud') || '0'),
          price_to_aud: parseFloat(field('price_to_aud') || '0'),
          features: field('features'),
          brands: field('brands'),
        }),
      });
      closeAddForm();
      await loadProducts();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function saveProduct(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/products/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          product_type: field('product_type'),
          name: field('name'),
          description: field('description'),
          price_from_aud: parseFloat(field('price_from_aud') || '0'),
          price_to_aud: parseFloat(field('price_to_aud') || '0'),
          features: field('features'),
          brands: field('brands'),
        }),
      });
      closeEditForm();
      await loadProducts();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function deleteProduct(id: number) {
    setLoading(true);
    setError(null);
    try {
      await apiJSON(`/api/kb/products/${id}`, { method: 'DELETE' });
      await loadProducts();
    } catch (err: unknown) {
      setError(String((err as Error).message ?? err));
    } finally {
      setLoading(false);
    }
  }

  // ── Render helpers ───────────────────────────────────────────────────────

  const addLabel: Record<TabId, string> = {
    faqs: 'Add FAQ',
    objections: 'Add Objection',
    products: 'Add Product',
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={s.page}>
      {/* Header */}
      <h1 style={s.title}>Knowledge Base</h1>
      <p style={s.subtitle}>
        Manage the FAQs, objection responses, and products your voice agent uses on every call.
      </p>

      {/* Tabs */}
      <div style={s.tabBar}>
        {(['faqs', 'objections', 'products'] as TabId[]).map((tab) => (
          <button
            key={tab}
            style={activeTab === tab ? s.tabActive : s.tab}
            onClick={() => switchTab(tab)}
          >
            {tab === 'faqs' ? 'FAQs' : tab === 'objections' ? 'Objections' : 'Products'}
          </button>
        ))}
      </div>

      {/* Error banner */}
      {error && <div style={s.errorBanner}>{error}</div>}

      {/* Add row */}
      <div style={s.addHeader}>
        <p style={s.sectionHeading}>
          {activeTab === 'faqs'
            ? `${faqs.length} FAQ${faqs.length !== 1 ? 's' : ''}`
            : activeTab === 'objections'
              ? `${objections.length} objection${objections.length !== 1 ? 's' : ''}`
              : `${products.filter((p) => p.active === 1).length} active product${products.filter((p) => p.active === 1).length !== 1 ? 's' : ''}`}
        </p>
        {!showAddForm && (
          <button style={s.btnPrimary} onClick={openAddForm} disabled={loading}>
            {addLabel[activeTab]}
          </button>
        )}
      </div>

      {/* ── FAQs ─────────────────────────────────────────────────────────── */}
      {activeTab === 'faqs' && (
        <>
          {/* Add form */}
          {showAddForm && (
            <div style={s.addCard}>
              <Field label="Question">
                <input
                  style={s.input}
                  value={field('question')}
                  onChange={(e) => setField('question', e.target.value)}
                  placeholder="e.g. How long does installation take?"
                />
              </Field>
              <Field label="Answer">
                <textarea
                  style={s.textarea}
                  value={field('answer')}
                  onChange={(e) => setField('answer', e.target.value)}
                  placeholder="Provide a complete answer the agent can read verbatim."
                />
              </Field>
              <Field label="Category">
                <input
                  style={s.input}
                  value={field('category')}
                  onChange={(e) => setField('category', e.target.value)}
                  placeholder="General"
                />
              </Field>
              <Field label="Priority">
                <input
                  style={s.input}
                  type="number"
                  value={field('priority') || '1'}
                  onChange={(e) => setField('priority', e.target.value)}
                  min={1}
                />
              </Field>
              <div style={s.itemActions}>
                <button style={s.btnPrimary} onClick={addFaq} disabled={loading}>
                  {loading ? 'Saving…' : 'Save FAQ'}
                </button>
                <button style={s.btnSecondary} onClick={closeAddForm} disabled={loading}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* FAQ list */}
          {loading && faqs.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: 13 }}>Loading…</p>
          ) : (
            faqs.map((faq) => (
              <div key={faq.id} style={s.card}>
                {editingId === faq.id ? (
                  <>
                    <Field label="Question">
                      <input
                        style={s.input}
                        value={field('question')}
                        onChange={(e) => setField('question', e.target.value)}
                      />
                    </Field>
                    <Field label="Answer">
                      <textarea
                        style={s.textarea}
                        value={field('answer')}
                        onChange={(e) => setField('answer', e.target.value)}
                      />
                    </Field>
                    <Field label="Category">
                      <input
                        style={s.input}
                        value={field('category')}
                        onChange={(e) => setField('category', e.target.value)}
                      />
                    </Field>
                    <Field label="Priority">
                      <input
                        style={s.input}
                        type="number"
                        value={field('priority')}
                        onChange={(e) => setField('priority', e.target.value)}
                        min={1}
                      />
                    </Field>
                    <div style={s.itemActions}>
                      <button
                        style={s.btnPrimary}
                        onClick={() => saveFaq(faq.id)}
                        disabled={loading}
                      >
                        {loading ? 'Saving…' : 'Save'}
                      </button>
                      <button
                        style={s.btnSecondary}
                        onClick={closeEditForm}
                        disabled={loading}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p style={s.itemTitle}>{faq.question}</p>
                    <p style={s.itemBody}>{faq.answer}</p>
                    <p style={s.itemMeta}>
                      Category: {faq.category} &middot; Priority: {faq.priority}
                    </p>
                    <div style={s.itemActions}>
                      <button
                        style={s.btnSecondary}
                        onClick={() => openEditForm(faq)}
                        disabled={loading}
                      >
                        Edit
                      </button>
                      <button
                        style={s.btnDanger}
                        onClick={() => deleteFaq(faq.id)}
                        disabled={loading}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </>
      )}

      {/* ── Objections ───────────────────────────────────────────────────── */}
      {activeTab === 'objections' && (
        <>
          {/* Add form */}
          {showAddForm && (
            <div style={s.addCard}>
              <Field label="Objection">
                <textarea
                  style={s.textarea}
                  value={field('objection')}
                  onChange={(e) => setField('objection', e.target.value)}
                  placeholder='e.g. "Solar is too expensive for us right now."'
                />
              </Field>
              <Field label="Response">
                <textarea
                  style={s.textarea}
                  value={field('response')}
                  onChange={(e) => setField('response', e.target.value)}
                  placeholder="How the agent should respond to this objection."
                />
              </Field>
              <Field label="Priority">
                <input
                  style={s.input}
                  type="number"
                  value={field('priority') || '1'}
                  onChange={(e) => setField('priority', e.target.value)}
                  min={1}
                />
              </Field>
              <div style={s.itemActions}>
                <button style={s.btnPrimary} onClick={addObjection} disabled={loading}>
                  {loading ? 'Saving…' : 'Save Objection'}
                </button>
                <button style={s.btnSecondary} onClick={closeAddForm} disabled={loading}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Objection list */}
          {loading && objections.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: 13 }}>Loading…</p>
          ) : (
            objections.map((obj) => (
              <div key={obj.id} style={s.card}>
                {editingId === obj.id ? (
                  <>
                    <Field label="Objection">
                      <textarea
                        style={s.textarea}
                        value={field('objection')}
                        onChange={(e) => setField('objection', e.target.value)}
                      />
                    </Field>
                    <Field label="Response">
                      <textarea
                        style={s.textarea}
                        value={field('response')}
                        onChange={(e) => setField('response', e.target.value)}
                      />
                    </Field>
                    <Field label="Priority">
                      <input
                        style={s.input}
                        type="number"
                        value={field('priority')}
                        onChange={(e) => setField('priority', e.target.value)}
                        min={1}
                      />
                    </Field>
                    <div style={s.itemActions}>
                      <button
                        style={s.btnPrimary}
                        onClick={() => saveObjection(obj.id)}
                        disabled={loading}
                      >
                        {loading ? 'Saving…' : 'Save'}
                      </button>
                      <button
                        style={s.btnSecondary}
                        onClick={closeEditForm}
                        disabled={loading}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p style={s.itemTitle}>{obj.objection}</p>
                    <p style={s.itemBody}>{obj.response}</p>
                    <p style={s.itemMeta}>Priority: {obj.priority}</p>
                    <div style={s.itemActions}>
                      <button
                        style={s.btnSecondary}
                        onClick={() => openEditForm(obj)}
                        disabled={loading}
                      >
                        Edit
                      </button>
                      <button
                        style={s.btnDanger}
                        onClick={() => deleteObjection(obj.id)}
                        disabled={loading}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </>
      )}

      {/* ── Products ─────────────────────────────────────────────────────── */}
      {activeTab === 'products' && (
        <>
          {/* Add form */}
          {showAddForm && (
            <div style={s.addCard}>
              <Field label="Product Type">
                <select
                  style={s.input}
                  value={field('product_type') || 'solar_panels'}
                  onChange={(e) => setField('product_type', e.target.value)}
                >
                  <option value="solar_panels">Solar Panels</option>
                  <option value="batteries">Batteries</option>
                  <option value="inverters">Inverters</option>
                  <option value="installation">Installation</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              <Field label="Name">
                <input
                  style={s.input}
                  value={field('name')}
                  onChange={(e) => setField('name', e.target.value)}
                  placeholder="e.g. Premium Residential Solar Package"
                />
              </Field>
              <Field label="Description">
                <textarea
                  style={s.textarea}
                  value={field('description')}
                  onChange={(e) => setField('description', e.target.value)}
                  placeholder="Describe what's included and who it suits."
                />
              </Field>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Field label="Price From (AUD)">
                  <input
                    style={s.input}
                    type="number"
                    value={field('price_from_aud') || '0'}
                    onChange={(e) => setField('price_from_aud', e.target.value)}
                    min={0}
                  />
                </Field>
                <Field label="Price To (AUD)">
                  <input
                    style={s.input}
                    type="number"
                    value={field('price_to_aud') || '0'}
                    onChange={(e) => setField('price_to_aud', e.target.value)}
                    min={0}
                  />
                </Field>
              </div>
              <Field label="Features">
                <input
                  style={s.input}
                  value={field('features')}
                  onChange={(e) => setField('features', e.target.value)}
                  placeholder="e.g. Tier 1, 400W, monocrystalline"
                />
              </Field>
              <Field label="Brands">
                <input
                  style={s.input}
                  value={field('brands')}
                  onChange={(e) => setField('brands', e.target.value)}
                  placeholder="e.g. LG, SunPower"
                />
              </Field>
              <div style={s.itemActions}>
                <button style={s.btnPrimary} onClick={addProduct} disabled={loading}>
                  {loading ? 'Saving…' : 'Save Product'}
                </button>
                <button style={s.btnSecondary} onClick={closeAddForm} disabled={loading}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Product list — active only */}
          {loading && products.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: 13 }}>Loading…</p>
          ) : (
            products
              .filter((p) => p.active === 1)
              .map((product) => (
                <div key={product.id} style={s.card}>
                  {editingId === product.id ? (
                    <>
                      <Field label="Product Type">
                        <select
                          style={s.input}
                          value={field('product_type')}
                          onChange={(e) => setField('product_type', e.target.value)}
                        >
                          <option value="solar_panels">Solar Panels</option>
                          <option value="batteries">Batteries</option>
                          <option value="inverters">Inverters</option>
                          <option value="installation">Installation</option>
                          <option value="other">Other</option>
                        </select>
                      </Field>
                      <Field label="Name">
                        <input
                          style={s.input}
                          value={field('name')}
                          onChange={(e) => setField('name', e.target.value)}
                        />
                      </Field>
                      <Field label="Description">
                        <textarea
                          style={s.textarea}
                          value={field('description')}
                          onChange={(e) => setField('description', e.target.value)}
                        />
                      </Field>
                      <div
                        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}
                      >
                        <Field label="Price From (AUD)">
                          <input
                            style={s.input}
                            type="number"
                            value={field('price_from_aud')}
                            onChange={(e) => setField('price_from_aud', e.target.value)}
                            min={0}
                          />
                        </Field>
                        <Field label="Price To (AUD)">
                          <input
                            style={s.input}
                            type="number"
                            value={field('price_to_aud')}
                            onChange={(e) => setField('price_to_aud', e.target.value)}
                            min={0}
                          />
                        </Field>
                      </div>
                      <Field label="Features">
                        <input
                          style={s.input}
                          value={field('features')}
                          onChange={(e) => setField('features', e.target.value)}
                        />
                      </Field>
                      <Field label="Brands">
                        <input
                          style={s.input}
                          value={field('brands')}
                          onChange={(e) => setField('brands', e.target.value)}
                        />
                      </Field>
                      <div style={s.itemActions}>
                        <button
                          style={s.btnPrimary}
                          onClick={() => saveProduct(product.id)}
                          disabled={loading}
                        >
                          {loading ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          style={s.btnSecondary}
                          onClick={closeEditForm}
                          disabled={loading}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p style={s.itemTitle}>{product.name}</p>
                      <p style={s.itemBody}>{product.description}</p>
                      <p style={s.itemMeta}>
                        AUD ${product.price_from_aud.toLocaleString()}
                        {product.price_to_aud > 0 &&
                          ` – $${product.price_to_aud.toLocaleString()}`}{' '}
                        &middot; {product.product_type.replace(/_/g, ' ')}
                        {product.brands && ` · ${product.brands}`}
                        {product.features && ` · ${product.features}`}
                      </p>
                      <div style={s.itemActions}>
                        <button
                          style={s.btnSecondary}
                          onClick={() => openEditForm(product)}
                          disabled={loading}
                        >
                          Edit
                        </button>
                        <button
                          style={s.btnDanger}
                          onClick={() => deleteProduct(product.id)}
                          disabled={loading}
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))
          )}
        </>
      )}
    </div>
  );
}
